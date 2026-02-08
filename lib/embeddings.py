"""
Ollama embedding client with batch support.
"""
import requests
from typing import List

OLLAMA_URL = "http://localhost:11434"
MODEL = "nomic-embed-text"

def embed(text: str) -> List[float]:
    """Generate embedding for a single text."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": MODEL, "prompt": text},
        timeout=30
    )
    response.raise_for_status()
    return response.json()["embedding"]

def embed_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Generate embeddings for multiple texts in batches."""
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        # Ollama doesn't have native batch endpoint, but we can pipeline
        batch_results = []
        for text in batch:
            try:
                batch_results.append(embed(text))
            except Exception as e:
                print(f"  Error embedding text: {e}")
                batch_results.append(None)
        results.extend(batch_results)
    return results

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

if __name__ == "__main__":
    vec = embed("Hello world")
    print(f"Embedding dimension: {len(vec)}")
    print(f"First 5 values: {vec[:5]}")
