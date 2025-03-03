from pdf2image import convert_from_path
import pytesseract
import os
import re
from pathlib import Path
import json
from datetime import datetime
import hashlib
from typing import Dict, Set, List
from config import get_base_paths


class ArticleProcessor:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.category_keywords = {
            "Inflation": {
                "inflation", "cpi", "consumer price", "price increases", 
                "monetary policy", "deflation", "inflationary pressure"
            },
            "Stocks": {
                "stocks", "equity market", "dow jones", "s&p 500", 
                "stock market", "wall street", "earnings report", "dividend"
            },
            "Bonds": {
                "bonds", "treasury", "fixed income", "yield curve",
                "bond market", "debt securities", "municipal bonds"
            },
            "Commodities": {
                "commodities", "commodity prices", "crude oil", "gold prices",
                "precious metals", "agricultural commodities", "raw materials"
            },
            "Infrastructure": {
                "infrastructure", "public works", "construction project",
                "transportation system", "public transit", "urban development"
            },
            "Real Estate": {
                "real estate", "housing market", "property value", "mortgage rate",
                "commercial property", "residential market", "home prices"
            },
            "Energy": {
                "energy sector", "oil prices", "natural gas", "renewable energy",
                "power generation", "energy policy", "energy market"
            }
        }
        
        # Create directory structure
        (self.base_dir / "newspapers").mkdir(parents=True, exist_ok=True)
        for category in list(self.category_keywords.keys()) + ["general"]:
            (self.base_dir / "newspapers" / category).mkdir(parents=True, exist_ok=True)
        
        # Load or create metadata
        self.metadata_file = self.base_dir / "metadata.json"
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
                # Ensure all required fields exist
                if "processed_pdfs" not in self.metadata:
                    self.metadata["processed_pdfs"] = {}
                if "sources" not in self.metadata:
                    self.metadata["sources"] = {}
                if "article_count" not in self.metadata:
                    self.metadata["article_count"] = 0
        else:
            self.metadata = {
                "processed_pdfs": {},
                "sources": {},
                "article_count": 0,
                "last_processed": None
            }

    def extract_title(self, text: str) -> str:
        """Extract a meaningful title from article text."""
        # Get first non-empty line
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return "Untitled Article"
            
        # Clean up the title
        title = lines[0]
        # Remove common prefixes
        title = re.sub(r'^(BY|OPINION|EDITORIAL|FEATURE):', '', title, flags=re.IGNORECASE).strip()
        # Limit length
        if len(title) > 100:
            title = title[:97] + "..."
        return title

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate a hash of the file content."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def get_pdf_metadata(self, pdf_path: str, force_update: bool = False) -> Dict:
        pdf_file = Path(pdf_path)
        file_hash = self.calculate_file_hash(pdf_path)
        
        if not force_update and pdf_file.name in self.metadata["processed_pdfs"]:
            stored_info = self.metadata["processed_pdfs"][pdf_file.name]
            if stored_info["file_hash"] == file_hash:
                print(f"\nSkipping {pdf_file.name} - already processed on {stored_info['processed_date']}")
                return None
        
        print(f"\nProcessing new file: {pdf_file.name}")
        source = input(f"Enter the source name for {pdf_file.name} (e.g., Barrons, WSJ): ").strip()
        if not source:
            source = pdf_file.stem
            
        while True:
            date = input(f"Enter the publication date for {pdf_file.name} (YYYY-MM-DD): ").strip()
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
                break
            try:
                datetime.strptime(date, "%Y-%m-%d")
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD")
        
        return {
            "source": source,
            "date": date,
            "file_hash": file_hash,
            "filename": pdf_file.name
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using OCR."""
        print(f"Converting PDF to images...")
        images = convert_from_path(pdf_path, dpi=300)
        
        extracted_text = ""
        for page_number, image in enumerate(images, start=1):
            print(f"Processing page {page_number}/{len(images)}...")
            text = pytesseract.image_to_string(image, lang="eng")
            extracted_text += f"\n--- Page {page_number} ---\n{text}"
        
        return extracted_text

    def split_into_articles(self, text: str) -> List[str]:
        """Split text into articles."""
        # Remove headers/footers
        text = re.sub(r'To reprint or license content.*?not permitted\.', '', text, flags=re.DOTALL)
        text = re.sub(r'Copyright ©.*?\d{4}.*?\n', '', text, flags=re.DOTALL)
        
        # Split on various markers
        sections = re.split(r'(?=(?:\n\s*\n[A-Z][A-Z\s]{10,}\n)|(?:P\.\d+\n)|(?:\n\s*By [A-Z][a-zA-Z\s]+\n))', text)
        
        articles = []
        for section in sections:
            if not section.strip():
                continue
            
            content = re.sub(r'---\s*Page\s*\d+\s*---', '', section)
            content = re.sub(r'\s+', ' ', content)
            content = content.strip()
            
            if len(content) > 200:
                articles.append(content)
        
        return articles

    def classify_article(self, article_text: str) -> Set[str]:
        """Determine categories for an article."""
        article_text = article_text.lower()
        categories = set()
        
        first_para = article_text.split('\n')[0] if '\n' in article_text else article_text
        
        for category, keywords in self.category_keywords.items():
            keyword_matches = 0
            important_matches = 0
            
            for keyword in keywords:
                matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', article_text))
                keyword_matches += matches
                
                if keyword in first_para:
                    important_matches += 1
            
            if (keyword_matches >= 3) or (important_matches >= 1 and keyword_matches >= 2):
                categories.add(category)
        
        if len(article_text.split()) > 200 and not categories:
            categories.add("general")
        
        return categories

    def save_article(self, article_text: str, categories: Set[str], source_info: Dict) -> None:
        """Save article with metadata."""
        if not categories:
            return
            
        self.metadata["article_count"] += 1
        article_id = self.metadata["article_count"]
        
        # Extract and clean title
        title = self.extract_title(article_text)
        
        # Create article metadata
        article_metadata = {
            "id": article_id,
            "source": source_info["source"],
            "date": source_info["date"],
            "title": title,
            "categories": list(categories),
            "processed_at": datetime.now().isoformat()
        }
        
        # Add metadata header to article content
        content_with_metadata = f"""METADATA:
Source: {source_info['source']}
Date: {source_info['date']}
Categories: {', '.join(categories)}
Title: {title}
ID: {article_id}

CONTENT:
{article_text}
"""
        
        # Save to each category folder
        clean_title = re.sub(r'[^\w\s-]', '', title).replace(' ', '_')
        for category in categories:
            filename = f"{source_info['source']}_{article_id}_{clean_title}.txt"
            filepath = self.base_dir / "newspapers" / category / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_with_metadata)
        
        # Update source metadata
        if source_info["source"] not in self.metadata["sources"]:
            self.metadata["sources"][source_info["source"]] = []
        
        self.metadata["sources"][source_info["source"]].append(article_metadata)
        
        # Save metadata file after each article
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def process_pdf(self, pdf_path: str) -> None:
        """Process a single PDF."""
        source_info = self.get_pdf_metadata(pdf_path)
        if source_info is None:  # Skip if already processed
            return
            
        try:
            full_text = self.extract_text_from_pdf(pdf_path)
            articles = self.split_into_articles(full_text)
            
            print(f"\nFound {len(articles)} articles in {source_info['source']} ({source_info['date']})")
            
            for idx, article in enumerate(articles, 1):
                print(f"\nProcessing article {idx}/{len(articles)}...")
                categories = self.classify_article(article)
                
                if categories:
                    self.save_article(article, categories, source_info)
                    print(f"Article {idx} categorized as: {', '.join(categories)}")
                else:
                    print(f"Article {idx} skipped - no relevant categories found")
            
            # Record successful processing
            self.metadata["processed_pdfs"][source_info["filename"]] = {
                "processed_date": datetime.now().strftime("%Y-%m-%d"),
                "file_hash": source_info["file_hash"],
                "source": source_info["source"],
                "pub_date": source_info["date"]
            }
            self.metadata["last_processed"] = datetime.now().isoformat()
            
            # Save final metadata
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
                
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")

    def process_directory(self, pdf_dir: str) -> None:
        """Process all PDFs in a directory."""
        pdf_dir = Path(pdf_dir)
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        
        if not pdf_files:
            print("No PDF files found in directory")
            return
        
        print(f"Found {len(pdf_files)} PDF files to process")
        for pdf_file in pdf_files:
            try:
                self.process_pdf(str(pdf_file))
                print(f"Completed processing {pdf_file.name}")
            except Exception as e:
                print(f"Error processing {pdf_file.name}: {str(e)}")

def main():
    # Configuration
    paths = get_base_paths()
    base_dir = str(paths['dataset'])
    pdf_dir = str(paths['pdf'])
    # Initialize processor
    processor = ArticleProcessor(base_dir)
    
    # Process all PDFs in directory
    processor.process_directory(pdf_dir)

if __name__ == "__main__":
    main()