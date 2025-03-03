import json
import re
from typing import Dict, List
from nearai.agents.environment import Environment
from nearai.shared.inference_client import InferenceClient
from config import get_base_paths, initialize_clients, retry_with_backoff
from vector.vector_store import vector_store

def get_article_headlines(category: str, metadata: Dict) -> List[Dict]:
    """Get headlines for a specific category."""
    try:
        if not isinstance(metadata, dict) or "sources" not in metadata:
            print("Invalid metadata format")
            return []
            
        headlines = []
        for source, articles in metadata["sources"].items():
            if not isinstance(articles, list):
                continue
                
            for article in articles:
                if not isinstance(article, dict):
                    continue
                    
                categories = article.get("categories", [])
                if not isinstance(categories, list):
                    continue
                    
                if category.lower() in [cat.lower() for cat in categories]:
                    headlines.append({
                        "id": article.get("id", 0),
                        "title": article.get("title", "Untitled"),
                        "source": source,
                        "date": article.get("date", "Unknown date")
                    })
                    
        return headlines
    except Exception as e:
        print(f"Error getting headlines: {str(e)}")
        return []

def show_category_headlines(env: Environment, category: str):
    """Show headlines for a category with improved formatting."""
    try:
        paths = get_base_paths()
        
        # Load metadata
        if not paths['metadata'].exists():
            env.add_reply("No articles found.")
            return
            
        with open(paths['metadata'], 'r') as f:
            metadata = json.load(f)
        
        # Get articles with titles and dates
        articles = []
        for source_name, source_articles in metadata.get('sources', {}).items():
            for article in source_articles:
                if category.lower() in [cat.lower() for cat in article.get('categories', [])]:
                    articles.append({
                        'id': article.get('id', 0),
                        'title': article.get('title', 'Untitled'),
                        'source': source_name,
                        'date': article.get('date', 'Unknown date')
                    })
        
        if not articles:
            env.add_reply(f"No articles found in the {category.capitalize()} category.")
            return
        
        # Sort by date (newest first) and then by ID
        articles.sort(key=lambda x: (x.get('date', ''), x.get('id', 0)), reverse=True)
        
        # Create a nicer formatted response
        try:
            response = f"## Latest {category.capitalize()} Headlines\n\n"
            for article in articles[:15]:  # Limit to 15 articles
                title = article['title'][:80] + "..." if len(article['title']) > 80 else article['title']
                response += f"**{article['id']}:** {title} ({article['source']}, {article['date']})\n\n"
            
            response += "To read a full article, type 'Read article X' where X is the article ID."
            env.add_reply(response)
        except Exception as e:
            # Ultra minimal fallback
            ids = [str(article['id']) for article in articles]
            env.add_reply(f"Found {len(ids)} articles in {category}. IDs: {', '.join(ids)}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        env.add_reply("Error listing articles.")

async def generate_category_summary(env: Environment, category: str):
    """Generate a comprehensive narrative analysis of all articles in a category with a macroeconomic perspective."""
    paths = get_base_paths()
    try:
        # Try vector store first for relevant articles
        results = await vector_store.query_articles(
            query=f"Latest market trends developments in {category} market analysis financial impact",
            category=category.lower(),
            limit=6  # Get more content for comprehensive analysis
        )
        
        articles = []
        article_sources = []
        
        if results:
            for result in results:
                try:
                    # Handle different result formats
                    source_path = None
                    if hasattr(result, 'source_path'):
                        source_path = result.source_path
                    elif isinstance(result, dict) and 'source_path' in result:
                        source_path = result['source_path']
                        
                    if source_path:
                        with open(source_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            metadata_section = content.split("CONTENT:")[0] if "CONTENT:" in content else ""
                            source_match = re.search(r'Source: (.+)', metadata_section)
                            date_match = re.search(r'Date: (.+)', metadata_section)
                            
                            source = source_match.group(1) if source_match else "Unknown Source"
                            date = date_match.group(1) if date_match else "Unknown Date"
                            
                            articles.append(content.split("CONTENT:")[-1].strip() if "CONTENT:" in content else content)
                            article_sources.append(f"{source} ({date})")
                except Exception as e:
                    print(f"Error reading vector store result: {str(e)}")
                    continue
        
        # Fall back to directory-based approach if needed
        if not articles:
            category_dir = paths['newspapers'] / category.lower()
            if not category_dir.exists() or not category_dir.is_dir():
                env.add_reply(f"Category directory not found: {category}")
                return
                
            for file in category_dir.glob("*.txt"):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        metadata_section = content.split("CONTENT:")[0] if "CONTENT:" in content else ""
                        source_match = re.search(r'Source: (.+)', metadata_section)
                        date_match = re.search(r'Date: (.+)', metadata_section)
                        
                        source = source_match.group(1) if source_match else "Unknown Source"
                        date = date_match.group(1) if date_match else "Unknown Date"
                        
                        articles.append(content.split("CONTENT:")[-1].strip() if "CONTENT:" in content else content)
                        article_sources.append(f"{source} ({date})")
                except Exception as e:
                    print(f"Error reading file {file}: {str(e)}")
                    continue

        if not articles:
            env.add_reply(f"No readable articles found in the {category} category.")
            return

        # Combine content from a few articles to provide context
        article_text = "\n=========\n".join(
            f"Source: {source}\n{article}" 
            for source, article in zip(article_sources, articles[:3])
        )
        
        # New narrative-style prompt instructing the LLM to produce a flowing, story-like report
        prompt = [
            {
                "role": "system",
                "content": f"""You are a seasoned financial journalist and macroeconomist. Using the financial data provided, write a narrative report on the {category} market. 
Your report should:
- Weave together key trends, news events, and statistics into a coherent story.
- Explain why the key market changes matter, and how they might influence future market behavior.
- Include context, analysis, and smooth transitions rather than simply listing bullet points.
- Use specific numbers, dates, and facts to support your insights.
Organize your report into coherent paragraphs that tell a clear story of the current market environment."""
            },
            {
                "role": "user",
                "content": f"Based on this financial information, provide a comprehensive narrative analysis of the {category} market:\n\n{article_text}"
            }
        ]
            
        # Use env.completion if available
        if hasattr(env, 'completion'):
            summary = env.completion(messages=prompt, max_tokens=1000)
        else:
            client_config, _ = initialize_clients()
            inference = InferenceClient(client_config)
            
            def make_completion():
                return inference.completions(
                    model="llama-v3p1-70b-instruct",
                    messages=prompt,
                    max_tokens=1000
                )
            results = retry_with_backoff(make_completion)
            summary = results["choices"][0]["message"]["content"]
        
        # Format and display the narrative analysis
        title = f"# {category} Market Analysis"
        show_headlines = f"\n\nTo view all articles in this category, reply with 'show articles about {category}'"
        
        env.add_reply(f"{title}\n\n{summary}{show_headlines}")

    except Exception as e:
        env.add_reply(f"Error generating category summary: {str(e)}")
        env.add_reply("Here are the latest headlines in this category:")
        show_category_headlines(env, category.lower())
