import json
import openai
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
from nearai.shared.client_config import ClientConfig
from nearai.config import Config, load_config_file

# Add vector store ID file path to base paths
def get_base_paths():
    """Get standardized paths used throughout the agent."""
    base_dir = Path("/Users/georgemarlow/.nearai/registry/dailies.near/news-agent/0.1.5")
    return {
        'base': base_dir,
        'pdf': base_dir / "pdfs",
        'dataset': base_dir / "dataset",
        'newspapers': base_dir / "dataset" / "newspapers",
        'metadata': base_dir / "dataset" / "metadata.json",
        'vector_store_id': base_dir / "vector/vector_store_id.txt"
    }

def retry_with_backoff(func: Callable, max_retries: int = 3, initial_delay: float = 1.0):
    """Retry a function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except openai.InternalServerError:
            if attempt == max_retries - 1:
                raise
            delay = initial_delay * (2 ** attempt)
            time.sleep(delay)
            continue
        except Exception:
            raise

def initialize_clients() -> Tuple[ClientConfig, openai.OpenAI]:
    """Initialize OpenAI and NEAR AI Hub clients."""
    CONFIG = Config()
    config_data = load_config_file(local=False)
    CONFIG = CONFIG.update_with(config_data)
    
    if CONFIG.api_url is None:
        raise ValueError("CONFIG.api_url is None")
    
    base_url = CONFIG.api_url + "/v1"
    client_config = ClientConfig(base_url=base_url, auth=CONFIG.auth)
    client = openai.OpenAI(base_url=base_url, api_key=json.dumps(config_data["auth"]))
    
    return client_config, client

def get_vector_store_id() -> Optional[str]:
    """Get the stored vector store ID if it exists."""
    paths = get_base_paths()
    try:
        if paths['vector_store_id'].exists():
            return paths['vector_store_id'].read_text().strip()
    except Exception:
        pass
    return None