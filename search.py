#!/usr/bin/env python3
"""
Semantic search over indexed memory.

Usage:
    ./search.py "what projects do I have"
    ./search.py "security audit" --top 10
"""
import sys
import argparse
from lib.embeddings import embed, cosine_similarity
from lib.db import get_db, get_all_embeddings, get_stats
from lib.faiss_index import search as faiss_search, index_exists

def search(query: str, top_k: int = 5, quiet: bool = False):
    """Search for similar content using FAISS (fast) or brute-force (fallback)."""
    db = get_db()
    
    stats = get_stats(db)
    if stats['total_chunks'] == 0:
        if not quiet:
            print("No content indexed yet. Run ./index.py first.")
        return []
    
    # Embed query
    query_embedding = embed(query)
    
    # Try FAISS first (fast path)
    if index_exists():
        if not quiet:
            print(f"Searching {stats['total_chunks']} chunks (FAISS)...\n")
        
        faiss_results = faiss_search(query_embedding, top_k)
        results = [{
            'id': r[0],
            'content': r[1],
            'source': r[2],
            'chunk_index': r[3],
            'similarity': r[4]
        } for r in faiss_results]
        return results
    
    # Fallback to brute-force
    if not quiet:
        print(f"Searching {stats['total_chunks']} chunks (brute-force)...\n")
    
    all_chunks = get_all_embeddings(db)
    
    results = []
    for chunk_id, content, source_path, chunk_index, chunk_embedding in all_chunks:
        sim = cosine_similarity(query_embedding, chunk_embedding)
        results.append({
            'id': chunk_id,
            'content': content,
            'source': source_path,
            'chunk_index': chunk_index,
            'similarity': sim
        })
    
    # Sort by similarity
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    return results[:top_k]

def main():
    parser = argparse.ArgumentParser(description="Semantic search over memory")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--top", type=int, default=5, help="Number of results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    results = search(args.query, args.top, quiet=args.json)
    
    if args.json:
        import json
        # Format for OpenClaw plugin compatibility
        formatted = [{
            'file': r['source'],
            'line': r['chunk_index'],
            'score': r['similarity'],
            'text': r['content']
        } for r in results]
        print(json.dumps(formatted))
    else:
        for i, r in enumerate(results, 1):
            print(f"━━━ Result {i} (similarity: {r['similarity']:.3f}) ━━━")
            print(f"Source: {r['source']}#{r['chunk_index']}")
            print()
            # Show first 300 chars of content
            content = r['content']
            if len(content) > 300:
                content = content[:300] + "..."
            print(content)
            print()

if __name__ == "__main__":
    main()
