import json
import re
from pathlib import Path
from typing import Dict, List

def load_metadata() -> Dict:
    """Load metadata about processed articles."""
    from config import get_base_paths
    paths = get_base_paths()
    
    try:
        if paths['metadata'].exists():
            with open(paths['metadata'], 'r') as f:
                metadata = json.load(f)
                # Ensure required fields exist
                metadata.setdefault("sources", {})
                metadata.setdefault("processed_pdfs", {})
                metadata.setdefault("article_count", 0)
                return metadata
        return {"sources": {}, "processed_pdfs": {}, "article_count": 0}
    except json.JSONDecodeError as e:
        print(f"Error decoding metadata JSON: {str(e)}")
        return {"sources": {}, "processed_pdfs": {}, "article_count": 0}

def find_article_by_id(article_id: int, metadata: Dict) -> Dict:
    """Find article details by ID."""
    try:
        if not isinstance(metadata, dict) or "sources" not in metadata:
            return None
            
        for source, articles in metadata["sources"].items():
            if not isinstance(articles, list):
                continue
                
            for article in articles:
                if not isinstance(article, dict):
                    continue
                    
                if article.get("id") == article_id:
                    return article
        return None
    except Exception as e:
        print(f"Error finding article: {str(e)}")
        return None

def build_article_list(category_dir: Path) -> List[Dict]:
    """Helper function to build list of articles from a category directory."""
    articles = []
    for file_path in category_dir.glob("*.txt"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                metadata_section = content.split("CONTENT:")[0]
                
                # Extract metadata using regex
                source_match = re.search(r'Source:\s*(.+?)(?:\n|$)', metadata_section)
                date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', metadata_section)
                title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', metadata_section)
                id_match = re.search(r'ID:\s*(\d+)', metadata_section)
                
                if all([source_match, date_match, title_match, id_match]):
                    articles.append({
                        'id': int(id_match.group(1)),
                        'title': title_match.group(1).strip(),
                        'source': source_match.group(1).strip(),
                        'date': date_match.group(1).strip(),
                        'file_path': str(file_path)
                    })
        except Exception as e:
            print(f"Error reading {file_path}: {str(e)}")
            continue
    return articles