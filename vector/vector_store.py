import asyncio
from typing import Optional, List, Dict
from pathlib import Path
from config import get_base_paths, initialize_clients
from .vector import VectorStoreManager

class VectorStoreWrapper:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreWrapper, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.manager = VectorStoreManager()
            self.vs_id = None
            self._initialized = True
    
    async def initialize(self) -> bool:
        """Initialize vector store if needed. Create if none exists."""
        from config import get_vector_store_id
        try:
            paths = get_base_paths()
            existing_vs_id = get_vector_store_id()
            if existing_vs_id:
                self.vs_id = existing_vs_id
                return True
            
            # No existing vector store ID => create one
            articles = self.manager.get_articles_by_category(str(paths['dataset']))
            if not articles:
                print("No articles found in dataset to initialize vector store.")
                return False
                
            new_vs_id = await self.manager.create_vector_store(articles)
            self.manager.save_vector_store_id(new_vs_id, str(paths['vector_store_id']))
            self.vs_id = new_vs_id
            return True
            
        except Exception as e:
            print(f"Error initializing vector store: {str(e)}")
            return False
    
    async def update_store(self):
        """
        Update the existing vector store with brand-new articles only.
        """
        paths = get_base_paths()
        if not self.vs_id:
            # If there's no existing store, try to initialize first
            if not await self.initialize():
                print("No existing vector store and failed to initialize.")
                return False
        
        articles = self.manager.get_articles_by_category(str(paths['dataset']))
        if not articles:
            print("No articles found to update.")
            return False
        
        try:
            await self.manager.update_vector_store(self.vs_id, articles)
            return True
        except Exception as e:
            print(f"Error updating vector store: {str(e)}")
            return False
    
    async def query_articles(self, query: str, category: Optional[str] = None, 
                             limit: int = 5) -> List[Dict]:
        """Query vector store for relevant articles."""
        if not self.vs_id:
            if not await self.initialize():
                return []
        
        try:
            results = await self.manager.query_vector_store(
                self.vs_id, 
                query, 
                category=category,
                limit=limit
            )
            return results
        except Exception as e:
            print(f"Error querying vector store: {str(e)}")
            return []

vector_store = VectorStoreWrapper()  # Singleton instance
