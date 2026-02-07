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

def search(query: str, top_k: int = 5):
    """Search for similar content."""
    db = get_db()
    
    stats = get_stats(db)
    if stats['total_chunks'] == 0:
        print("No content indexed yet. Run ./index.py first.")
        return []
    
    print(f"Searching {stats['total_chunks']} chunks...\n")
    
    # Embed query
    query_embedding = embed(query)
    
    # Get all embeddings and compute similarities
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
    
    results = search(args.query, args.top)
    
    if args.json:
        import json
        print(json.dumps(results, indent=2))
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
