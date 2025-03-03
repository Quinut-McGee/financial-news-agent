import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from nearai.agents.environment import Environment
from config import get_base_paths

async def find_article_by_id(env: Environment, article_id: int) -> Tuple[Optional[Dict], Optional[Path]]:
    """Find an article by its ID in the metadata and return both metadata and file path."""
    paths = get_base_paths()
    metadata_path = paths['metadata']
    
    if not metadata_path.exists():
        env.add_reply("Error: Metadata file not found.")
        return None, None
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        # Look for the article in sources
        for source_name, articles in metadata.get('sources', {}).items():
            for article in articles:
                if article.get('id') == article_id:
                    # Found the article metadata
                    # Now look for the actual file in the appropriate category folder(s)
                    categories = article.get('categories', [])
                    
                    if not categories:
                        env.add_reply(f"Error: Article {article_id} has no categories.")
                        return article, None
                    
                    # Try to find the file in any of the categories
                    for category in categories:
                        category_dir = paths['newspapers'] / category
                        
                        if category_dir.exists():
                            # Look for files with this article ID in the name
                            pattern = f"*_{article_id}_*"
                            matches = list(category_dir.glob(pattern))
                            
                            if matches:
                                # Return the first match
                                return article, matches[0]
        
        # If we get here, we didn't find the article
        env.add_reply(f"Article with ID {article_id} not found.")
        return None, None
        
    except Exception as e:
        env.add_reply(f"Error finding article: {str(e)}")
        return None, None

def extract_article_content(file_path: Path) -> str:
    """Extract the actual article content from a file, removing metadata."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Check if the file has the expected format with METADATA and CONTENT sections
        if "CONTENT:" in content:
            # Extract just the content part
            content_part = content.split("CONTENT:", 1)[1].strip()
            return content_part
        else:
            # Return the whole thing if it doesn't have the expected format
            return content
            
    except Exception as e:
        return f"Error extracting content: {str(e)}"

async def summarize_specific_article(env: Environment, article_id: int) -> None:
    """Summarize a specific article by its ID in a narrative, story-like format."""
    article_meta, file_path = await find_article_by_id(env, article_id)
    
    if not article_meta or not file_path:
        # Error message already added by find_article_by_id
        return
    
    try:
        # Extract article content
        content = extract_article_content(file_path)
        
        # Get essential metadata
        source = article_meta.get('source', 'Unknown Source')
        date = article_meta.get('date', 'Unknown Date')
        title = article_meta.get('title', 'Untitled Article')
        categories = article_meta.get('categories', [])
        category = categories[0] if categories else "General"
        
        # Add article header
        env.add_reply(f"Article {article_id} from {source} ({date})")
        
        # For short articles (under 1500 characters), just display them directly
        if len(content) < 1500:
            env.add_reply(content)
            return
        
        # For longer articles, generate a narrative, story-like summary
        prompt = [
            {
                "role": "system",
                "content": """You are a skilled financial journalist who transforms complex financial articles into engaging narratives. 

Your summaries should:
1. Begin with a compelling title that captures the essence of the article
2. Flow like a story with clear paragraphs, smooth transitions, and a coherent narrative arc
3. Preserve all key financial data, market trends, and economic indicators within the narrative
4. Integrate statistics, expert quotes, and insights naturally into the storytelling
5. Avoid bullet points, numbered lists, or section headers that break the narrative flow
6. Maintain a journalistic tone while making complex financial concepts accessible
7. End with a forward-looking conclusion that puts the information in context

Focus on crafting a summary that reads like a well-written financial news article rather than a structured report."""
            },
            {
                "role": "user",
                "content": f"Transform this financial article into an engaging narrative summary that retains all key financial information and insights, but reads like a story:\n\n{content}"
            }
        ]
        
        # Generate the narrative summary
        summary = env.completion(messages=prompt, max_tokens=800)
        env.add_reply(summary)
        
    except Exception as e:
        env.add_reply(f"Error summarizing article: {str(e)}")