import json
import openai
import os
import tempfile
import time
from glob import glob
from pathlib import Path
from typing import List, Dict
from nearai.shared.client_config import ClientConfig
from nearai.shared.inference_client import InferenceClient
from nearai.config import Config, load_config_file

INGESTED_FILES_PATH = "ingested_files.json"

def chunk_text(content: str, chunk_size: int = 500) -> List[str]:
    """Split article text into smaller chunks of approximately 'chunk_size' words."""
    words = content.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
    return chunks

class VectorStoreManager:
    def __init__(self):
        # Load NEAR AI Hub configuration
        self.CONFIG = Config()
        config_data = load_config_file(local=False)
        self.CONFIG = self.CONFIG.update_with(config_data)
        
        if self.CONFIG.api_url is None:
            raise ValueError("CONFIG.api_url is None")
        
        base_url = self.CONFIG.api_url + "/v1"
        self.client_config = ClientConfig(base_url=base_url, auth=self.CONFIG.auth)
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=json.dumps(config_data["auth"])
        )

    def get_articles_by_category(self, base_dir: str) -> Dict[str, List[Path]]:
        """
        Return a dict of {category_name: [list_of_txt_file_paths]}.
        Each category is a subfolder in base_dir, each containing .txt articles.
        """
        base_path = Path(base_dir)
        newspapers_path = base_path / "newspapers"
        if newspapers_path.exists() and newspapers_path.is_dir():
            base_path = newspapers_path

        articles_by_category = {}
        
        # Look for all category directories
        for category_dir in base_path.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                article_files = list(category_dir.glob("*.txt"))
                if article_files:
                    articles_by_category[category_dir.name] = article_files
        
        return articles_by_category

    def load_ingested_files(self) -> Dict[str, bool]:
        """Load a dictionary of ingested file paths from local JSON. Key=filepath, value=True."""
        if not os.path.exists(INGESTED_FILES_PATH):
            return {}
        try:
            with open(INGESTED_FILES_PATH, "r") as f:
                data = json.load(f)
            return data
        except Exception:
            return {}

    def save_ingested_files(self, ingested_dict: Dict[str, bool]):
        """Save updated ingested file dictionary to JSON."""
        try:
            with open(INGESTED_FILES_PATH, "w") as f:
                json.dump(ingested_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving ingested_files.json: {str(e)}")

    async def create_vector_store(self, articles_by_category: Dict[str, List[Path]], 
                                  store_name: str = "newspaper_articles") -> str:
        """
        Create a fresh vector store, ingest all articles from scratch (with chunking).
        """
        try:
            # Create vector store
            vs = self.client.beta.vector_stores.create(name=store_name)
            print(f"Created vector store: {vs.id}")
            
            total_files = sum(len(files) for files in articles_by_category.values())
            processed_files = 0
            total_chunks = 0
            
            ingested_dict = self.load_ingested_files()
            
            # Process articles by category
            for category, article_files in articles_by_category.items():
                print(f"\nProcessing {category} articles...")
                
                for file_path in article_files:
                    # Chunk each file, then upload each chunk as a separate record.            
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        # chunk the content
                        chunks = chunk_text(content, chunk_size=500)
                        
                        for idx, chunk in enumerate(chunks):
                            # Create a temporary file with metadata
                            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_file:
                                metadata = {
                                    "category": category,
                                    "filename": file_path.name,
                                    "source_path": str(file_path),
                                    "chunk_index": idx
                                }
                                temp_file.write(f"METADATA: {json.dumps(metadata)}\n\n")
                                temp_file.write(chunk)
                                temp_file.flush()
                                
                                # Upload and attach to vector store
                                uploaded_file = self.client.files.create(
                                    file=open(temp_file.name, "rb"),
                                    purpose="assistants"
                                )
                                self.client.beta.vector_stores.files.create(
                                    vector_store_id=vs.id,
                                    file_id=uploaded_file.id
                                )
                                total_chunks += 1
                            # Clean up temp file
                            if 'temp_file' in locals():
                                os.unlink(temp_file.name)
                    
                        processed_files += 1
                        print(f"Progress: {processed_files}/{total_files} files processed")

                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")
                        continue

            # Wait for processing completion with a timeout
            max_attempts = 30  # Maximum number of attempts (60 seconds with 2-second delay)
            attempts = 0
            last_completed = 0
            
            while attempts < max_attempts:
                status = self.client.beta.vector_stores.retrieve(vs.id)
                completed = status.file_counts.completed if status.file_counts else 0
                
                # Print status message
                print(f"Files indexed: {completed}/{total_chunks}")
                
                # If all files are processed or no progress for a while, break
                if completed >= total_chunks:
                    print("All files have been indexed successfully!")
                    break
                    
                # If no change in completed count for several iterations, exit loop
                if completed == last_completed:
                    attempts += 1
                else:
                    attempts = 0  # Reset counter if progress is being made
                    
                last_completed = completed
                time.sleep(2)
            
            # Even if we timed out, continue with what we have
            if attempts >= max_attempts:
                print("Indexing is taking longer than expected. Continuing with available indexed files.")
    
            # Mark all files as ingested
            for category, article_files in articles_by_category.items():
                for file_path in article_files:
                    ingested_dict[str(file_path)] = True
            self.save_ingested_files(ingested_dict)

            return vs.id
            
        except Exception as e:
            raise Exception(f"Error creating vector store: {str(e)}")

    async def update_vector_store(self, vs_id: str, articles_by_category: Dict[str, List[Path]]):
        """
        Update an existing vector store by uploading only new articles
        that have not been ingested yet. Use chunking for each new article.
        """
        try:
            ingested_dict = self.load_ingested_files()
            new_files_to_process = []

            # Gather new files
            for category, article_files in articles_by_category.items():
                for file_path in article_files:
                    if str(file_path) not in ingested_dict:
                        new_files_to_process.append((category, file_path))

            if not new_files_to_process:
                print("No new files to ingest.")
                return True  # Treat as success if there's nothing new to update

            print(f"Found {len(new_files_to_process)} new files to ingest.")
            processed_files = 0
            total_new = len(new_files_to_process)
            total_chunks = 0

            for category, file_path in new_files_to_process:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    chunks = chunk_text(content, chunk_size=500)

                    for idx, chunk in enumerate(chunks):
                        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_file:
                            metadata = {
                                "category": category,
                                "filename": file_path.name,
                                "source_path": str(file_path),
                                "chunk_index": idx
                            }
                            temp_file.write(f"METADATA: {json.dumps(metadata)}\n\n")
                            temp_file.write(chunk)
                            temp_file.flush()

                            uploaded_file = self.client.files.create(
                                file=open(temp_file.name, "rb"),
                                purpose="assistants",
                            )
                            self.client.beta.vector_stores.files.create(
                                vector_store_id=vs_id,
                                file_id=uploaded_file.id,
                            )
                            total_chunks += 1
                        # Clean up temp file
                        if 'temp_file' in locals():
                            os.unlink(temp_file.name)

                    # Mark file as ingested
                    ingested_dict[str(file_path)] = True
                    processed_files += 1
                    print(f"Ingested new file [{processed_files}/{total_new}]: {file_path.name}")

                except Exception as e:
                    print(f"Error processing new file {file_path}: {str(e)}")

            # Save updated ingested dict
            self.save_ingested_files(ingested_dict)

            # Wait for the indexing to complete with a timeout
            max_attempts = 30  # Maximum number of attempts (60 seconds with 2-second delay)
            attempts = 0
            last_completed = 0
            
            while attempts < max_attempts:
                status = self.client.beta.vector_stores.retrieve(vs_id)
                completed = status.file_counts.completed if status.file_counts else 0
                
                print(f"Vector store indexing: {completed} files completed.")
                
                if completed >= total_chunks:
                    print("All files have been indexed successfully!")
                    break
                    
                # If no change in completed count for several iterations, exit loop
                if completed == last_completed:
                    attempts += 1
                else:
                    attempts = 0  # Reset counter if progress is being made
                    
                last_completed = completed
                time.sleep(2)
            
            # Even if we timed out, continue with what we have
            if attempts >= max_attempts:
                print("Indexing is taking longer than expected. Continuing with available indexed files.")

            return True

        except Exception as e:
            raise Exception(f"Error updating vector store: {str(e)}")


    def save_vector_store_id(self, vs_id: str, output_file: str = "vector_store_id.txt"):
        """Save vector store ID to file."""
        try:
            with open(output_file, "w") as f:
                f.write(vs_id)
            print(f"\nVector store ID saved to {output_file}")
        except Exception as e:
            print(f"Error saving vector store ID: {str(e)}")

    async def query_vector_store(self, vs_id: str, query: str, 
                                category: str = None, limit: int = 5) -> List[Dict]:
        """Query the vector store for relevant articles using the NEAR AI search endpoint."""
        try:
            query_params = {
                "query": query,
                "limit": limit
            }
            
            if category:
                query_params["filter"] = {"category": category}
            
            # Use the client.post method as per NEAR AI's vector store documentation.
            base_url = self.client_config.base_url
            results = await self.client.post(
                path=f"{base_url}/vector_stores/{vs_id}/search",
                body=query_params,
                cast_to=dict
            )
            
            # Expecting a 'matching_files' field in the response
            return results.get("matching_files", [])
            
        except Exception as e:
            raise Exception(f"Error querying vector store: {str(e)}")


# meant for standalone testing
async def main():
    try:
        manager = VectorStoreManager()
        
        # Get articles from processed directory
        articles = manager.get_articles_by_category("../dataset/newspapers")
        
        if not articles:
            print("No articles found. Please process the newspaper PDF first.")
            return
        
        print(f"Found articles in {len(articles)} categories")
        
        # Create and populate vector store
        vs_id = await manager.create_vector_store(articles)
        print(f"\nVector store created successfully. ID: {vs_id}")
        
        # Save vector store ID
        manager.save_vector_store_id(vs_id)
        
        # Test query
        test_query = "What are the latest developments in financial markets?"
        results = await manager.query_vector_store(vs_id, test_query)
        print(f"\nTest query results: {len(results)} matches found")
        
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())