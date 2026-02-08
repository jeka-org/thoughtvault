"""
FAISS index for fast similarity search.
Optimized: metadata stores only IDs, content fetched from DB on demand.
"""
import faiss
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Optional

INDEX_PATH = Path(__file__).parent.parent / "faiss.index"
METADATA_PATH = Path(__file__).parent.parent / "faiss_metadata.json"

def build_index(embeddings_data) -> None:
    """
    Build FAISS index. Accepts either:
    - List of (id, source_path, chunk_index, embedding) tuples (optimized)
    - List of (id, content, source_path, chunk_index, embedding) tuples (legacy)
    """
    if not embeddings_data:
        return
    
    # Detect format
    if len(embeddings_data[0]) == 4:
        vectors = np.array([e[3] for e in embeddings_data], dtype=np.float32)
        metadata = [(e[0], e[1], e[2]) for e in embeddings_data]  # id, source, chunk_idx
    else:
        vectors = np.array([e[4] for e in embeddings_data], dtype=np.float32)
        metadata = [(e[0], e[2], e[3]) for e in embeddings_data]  # id, source, chunk_idx (skip content)
    
    faiss.normalize_L2(vectors)
    
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    
    faiss.write_index(index, str(INDEX_PATH))
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f)
    
    print(f"Built FAISS index: {len(embeddings_data)} vectors, {dim} dims")

def load_index() -> Tuple[Optional[faiss.Index], Optional[List]]:
    """Load FAISS index and metadata from disk."""
    if not INDEX_PATH.exists() or not METADATA_PATH.exists():
        return None, None
    index = faiss.read_index(str(INDEX_PATH))
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    return index, metadata

def search(query_embedding: List[float], top_k: int = 5) -> List[Tuple[int, str, int, float]]:
    """
    Search FAISS index.
    Returns: List of (id, source_path, chunk_index, similarity_score)
    """
    index, metadata = load_index()
    if index is None:
        return []
    
    query_vec = np.array([query_embedding], dtype=np.float32)
    faiss.normalize_L2(query_vec)
    
    scores, indices = index.search(query_vec, min(top_k * 2, index.ntotal))  # over-fetch for MMR
    
    results = []
    for i, idx in enumerate(indices[0]):
        if idx >= 0 and idx < len(metadata):
            m = metadata[idx]
            # Handle both old (4-element with content) and new (3-element) metadata
            if len(m) == 4:
                results.append((m[0], m[2], m[3], float(scores[0][i])))
            else:
                results.append((m[0], m[1], m[2], float(scores[0][i])))
    
    return results

def index_exists() -> bool:
    """Check if FAISS index exists."""
    return INDEX_PATH.exists() and METADATA_PATH.exists()
