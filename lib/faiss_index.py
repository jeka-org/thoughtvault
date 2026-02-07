"""
FAISS index for fast similarity search
"""
import faiss
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Optional

INDEX_PATH = Path(__file__).parent.parent / "faiss.index"
METADATA_PATH = Path(__file__).parent.parent / "faiss_metadata.json"

def build_index(embeddings: List[Tuple[int, str, str, int, List[float]]]) -> None:
    """Build FAISS index from embeddings and save to disk."""
    if not embeddings:
        return
    
    # Extract vectors and metadata
    vectors = np.array([e[4] for e in embeddings], dtype=np.float32)
    metadata = [(e[0], e[1], e[2], e[3]) for e in embeddings]  # id, content, source, chunk_idx
    
    # Normalize vectors for cosine similarity (use inner product after normalization)
    faiss.normalize_L2(vectors)
    
    # Create index - use IndexFlatIP for exact search with inner product (= cosine after normalization)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    
    # Save index and metadata
    faiss.write_index(index, str(INDEX_PATH))
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f)
    
    print(f"Built FAISS index: {len(embeddings)} vectors, {dim} dims")

def load_index() -> Tuple[Optional[faiss.Index], Optional[List]]:
    """Load FAISS index and metadata from disk."""
    if not INDEX_PATH.exists() or not METADATA_PATH.exists():
        return None, None
    
    index = faiss.read_index(str(INDEX_PATH))
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    
    return index, metadata

def search(query_embedding: List[float], top_k: int = 5) -> List[Tuple[int, str, str, int, float]]:
    """
    Search for similar chunks using FAISS.
    Returns: List of (id, content, source_path, chunk_index, similarity_score)
    """
    index, metadata = load_index()
    if index is None:
        return []
    
    # Prepare query vector
    query_vec = np.array([query_embedding], dtype=np.float32)
    faiss.normalize_L2(query_vec)
    
    # Search
    scores, indices = index.search(query_vec, min(top_k, index.ntotal))
    
    results = []
    for i, idx in enumerate(indices[0]):
        if idx >= 0 and idx < len(metadata):
            m = metadata[idx]
            results.append((m[0], m[1], m[2], m[3], float(scores[0][i])))
    
    return results

def index_exists() -> bool:
    """Check if FAISS index exists."""
    return INDEX_PATH.exists() and METADATA_PATH.exists()
