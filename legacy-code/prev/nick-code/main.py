import boto3
import json
import numpy as np
from typing import List, Dict, Tuple
from pathlib import Path
import os
import pickle
from datetime import datetime
from config import Config
import shutil
import tiktoken
from rich import print
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track

# Initialize rich console for better output
console = Console()

MAX_TOKENS = 7900  # Increased safety margin for API overhead

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        console.print(f"[yellow]Warning: Error counting tokens: {e}. Using character-based approximation.[/yellow]")
        return len(text) // 4

def truncate_text(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """Truncate text to stay within token limit."""
    current_tokens = count_tokens(text)
    if current_tokens <= max_tokens:
        return text
    
    # Leave more room for API overhead and JSON wrapper
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    truncated_tokens = tokens[:max_tokens-50]  # Larger safety margin
    truncated_text = encoding.decode(truncated_tokens) + "..."
    
    console.print(f"[yellow]Warning: Text truncated from {current_tokens} to {count_tokens(truncated_text)} tokens[/yellow]")
    return truncated_text

def init_bedrock_client(config: Config):
    return boto3.client('bedrock-runtime',
                       region_name=config.BEDROCK_REGION,
                       aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                       aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY)

def generate_embedding(text: str, client) -> List[float]:
    # Debug token count
    token_count = count_tokens(text)
    console.print(f"[blue]Generating embedding for text with {token_count} tokens[/blue]")
    
    # Truncate text if necessary
    text = truncate_text(text)
    body = json.dumps({"inputText": text})
    response = client.invoke_model(modelId=Config.EMBEDDING_MODEL, body=body)
    embedding = json.loads(response['body'].read())['embedding']
    return embedding

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2)

class KnownTexts:
    def __init__(self, texts_dir: str, cache_file: str = 'embeddings_cache.pkl'):
        self.texts_dir = Path(texts_dir)
        self.cache_file = Path(cache_file)
        self.texts_and_embeddings: Dict[str, Dict] = {}
        self.load_cache()

    def load_cache(self):
        """Load cached embeddings if they exist."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    self.texts_and_embeddings = pickle.load(f)
                console.print(f"[green]Loaded {len(self.texts_and_embeddings)} cached embeddings[/green]")
            except Exception as e:
                console.print(f"[red]Error loading cache: {e}[/red]")
                self.texts_and_embeddings = {}

    def save_cache(self):
        """Save embeddings cache to disk."""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.texts_and_embeddings, f)
        console.print(f"[green]Saved {len(self.texts_and_embeddings)} embeddings to cache[/green]")

    def update_known_texts(self, client) -> int:
        new_files = 0
        self.texts_dir.mkdir(exist_ok=True)

        for file_path in track(list(self.texts_dir.glob('*.txt')), description="Processing files"):
            file_info = {
                'path': str(file_path),
                'modified_time': datetime.fromtimestamp(file_path.stat().st_mtime)
            }

            if (str(file_path) not in self.texts_and_embeddings or 
                self.texts_and_embeddings[str(file_path)]['modified_time'] < file_info['modified_time']):
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read().strip()
                    
                    if not text:
                        console.print(f"[yellow]Warning: File {file_path} is empty[/yellow]")
                        continue
                    
                    # Check token count and truncate if needed
                    text = truncate_text(text)
                    embedding = generate_embedding(text, client)
                    
                    self.texts_and_embeddings[str(file_path)] = {
                        'text': text,
                        'embedding': embedding,
                        'modified_time': file_info['modified_time'],
                        'token_count': count_tokens(text)
                    }
                    
                    new_files += 1
                    console.print(f"[green]Processed: {file_path.name}[/green]")
                
                except Exception as e:
                    console.print(f"[red]Error processing {file_path}: {e}[/red]")
                    continue

        if new_files > 0:
            self.save_cache()

        return new_files

    def get_all_embeddings(self) -> Dict[str, List[float]]:
        """Return dictionary of text:embedding pairs for comparison."""
        return {info['text']: info['embedding'] 
                for info in self.texts_and_embeddings.values()}

def compare_embeddings(query_text: str, known_texts: Dict[str, List[float]], client) -> List[Tuple[str, float]]:
    """Compare query embedding against known embeddings."""
    try:
        # Truncate query text if needed before generating embedding
        query_text = truncate_text(query_text)
        query_embedding = generate_embedding(query_text, client)
        similarities = []
        
        for text, embedding in known_texts.items():
            similarity = cosine_similarity(query_embedding, embedding)
            similarities.append((text, similarity))
        
        return sorted(similarities, key=lambda x: x[1], reverse=True)
    
    except Exception as e:
        console.print(f"[red]Error comparing embeddings: {str(e)}[/red]")
        return []

def read_query_file(query_file: Path) -> str:
    """Read the query text from file."""
    try:
        with open(query_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        raise Exception(f"Error reading query file: {e}")

def save_query_to_known_texts(query_file: Path, known_texts_dir: Path, timestamp: datetime) -> Path:
    """Save the query text to known_texts directory with timestamp."""
    # Check token count before saving
    with open(query_file, 'r', encoding='utf-8') as f:
        query_text = f.read().strip()
    
    if count_tokens(query_text) > MAX_TOKENS:
        console.print("[yellow]Warning: Query text exceeds token limit and will be truncated[/yellow]")
        query_text = truncate_text(query_text)
    
    # Create a filename with timestamp
    new_filename = f"query_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
    new_path = known_texts_dir / new_filename
    
    # Save the potentially truncated text
    with open(new_path, 'w', encoding='utf-8') as f:
        f.write(query_text)
    
    console.print(f"[green]Saved query to known texts as: {new_filename}[/green]")
    return new_path

def print_results(results: List[Tuple[str, float]], query_text: str):
    """Print comparison results in a formatted table."""
    table = Table(title="Text Similarity Results", show_header=True, header_style="bold magenta")
    table.add_column("Similarity", justify="right", style="cyan", no_wrap=True)
    table.add_column("Text Preview", style="green")
    table.add_column("File", style="blue")
    
    # First, show the query text
    console.print(Panel(query_text[:200] + "..." if len(query_text) > 200 else query_text, 
                       title="Query Text", 
                       style="yellow"))
    
    console.print("\n")  # Add some spacing
    
    # Add rows to the table
    for text, similarity in results:
        # Get a preview of the text (first 100 characters)
        preview = text[:100] + "..." if len(text) > 100 else text
        # Format similarity score as percentage
        similarity_str = f"{similarity:.2%}"
        table.add_row(similarity_str, preview, "")

    console.print(table)

def main():
    try:
        # Load configuration
        config = Config.from_yaml('config.yaml')
        
        # Initialize client
        client = init_bedrock_client(config)
        
        # Setup paths
        query_file = Path('query.txt')
        if not query_file.exists():
            console.print("[red]Please create query.txt with the text you want to compare[/red]")
            return
        
        # Initialize known texts manager
        known_texts = KnownTexts('known_texts')
        
        # Read query text
        query = read_query_file(query_file)
        
        # Save query to known_texts
        timestamp = datetime.now()
        save_query_to_known_texts(query_file, known_texts.texts_dir, timestamp)
        
        # Update embeddings from text files
        new_files = known_texts.update_known_texts(client)
        console.print(f"[blue]Processed {new_files} new or modified files[/blue]")
        
        # Get all embeddings for comparison
        embeddings_dict = known_texts.get_all_embeddings()
        
        if not embeddings_dict:
            console.print("[red]No known texts available for comparison.[/red]")
            return
        
        # Compare embeddings and print results
        results = compare_embeddings(query, embeddings_dict, client)
        print_results(results, query)

    except Exception as e:
        console.print(f"[red]Error in main execution: {str(e)}[/red]")

if __name__ == "__main__":
    main()