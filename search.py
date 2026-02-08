#!/usr/bin/env python3
"""
Semantic search over indexed memory.
Features: FAISS search, query caching, recency weighting, MMR diversity, analytics.

Usage:
    ./search.py "what projects do I have"
    ./search.py "security audit" --top 10
"""
import sys
import time
import argparse
import hashlib
from collections import OrderedDict
from lib.embeddings import embed, cosine_similarity
from lib.db import get_db, get_all_embeddings, get_stats, get_chunks_by_ids, log_search
from lib.faiss_index import search as faiss_search, index_exists

# LRU Query Cache with TTL
_cache = OrderedDict()
_CACHE_MAX = 128
_CACHE_TTL = 300  # 5 minutes

def _cache_key(query: str, top_k: int) -> str:
    return hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()

def _cache_get(key: str):
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry['time'] < _CACHE_TTL:
            _cache.move_to_end(key)
            return entry['results']
        else:
            del _cache[key]
    return None

def _cache_set(key: str, results):
    _cache[key] = {'results': results, 'time': time.time()}
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)

def mmr_rerank(results: list, top_k: int, lambda_param: float = 0.7) -> list:
    """Maximal Marginal Relevance: balance relevance with diversity of sources."""
    if len(results) <= top_k:
        return results
    
    selected = [results[0]]
    remaining = results[1:]
    
    while len(selected) < top_k and remaining:
        best_score = -1
        best_idx = 0
        
        for i, candidate in enumerate(remaining):
            # Penalize candidates from same source as already selected
            source_penalty = 0
            for s in selected:
                if candidate['source'] == s['source']:
                    source_penalty = 0.15
                    break
            
            mmr_score = lambda_param * candidate['similarity'] - (1 - lambda_param) * source_penalty
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        
        selected.append(remaining.pop(best_idx))
    
    return selected

def recency_weight(similarity: float, source_path: str) -> float:
    """Boost recent files slightly. Memory files get a small boost."""
    import os
    boost = 0.0
    try:
        if os.path.exists(source_path):
            mtime = os.path.getmtime(source_path)
            age_days = (time.time() - mtime) / 86400
            if age_days < 1:
                boost = 0.03
            elif age_days < 7:
                boost = 0.02
            elif age_days < 30:
                boost = 0.01
    except Exception:
        pass
    return similarity + boost

def search(query: str, top_k: int = 5, quiet: bool = False):
    """Search for similar content using FAISS with caching and diversity."""
    start_time = time.time()
    db = get_db()
    
    stats = get_stats(db)
    if stats['total_chunks'] == 0:
        if not quiet:
            print("No content indexed yet. Run ./index.py first.")
        return []
    
    # Check cache
    ckey = _cache_key(query, top_k)
    cached = _cache_get(ckey)
    if cached is not None:
        elapsed_ms = (time.time() - start_time) * 1000
        if not quiet:
            print(f"Searching {stats['total_chunks']} chunks (cached, {elapsed_ms:.1f}ms)...\n")
        log_search(db, query, cached[0]['similarity'] if cached else 0, len(cached), elapsed_ms)
        return cached
    
    # Embed query
    query_embedding = embed(query)
    
    # Try FAISS first
    if index_exists():
        if not quiet:
            print(f"Searching {stats['total_chunks']} chunks (FAISS)...\n")
        
        faiss_results = faiss_search(query_embedding, top_k)
        
        # Fetch content from DB (not stored in FAISS metadata anymore)
        chunk_ids = [r[0] for r in faiss_results]
        chunks = get_chunks_by_ids(db, chunk_ids)
        
        results = []
        for r in faiss_results:
            chunk_id = r[0]
            if chunk_id in chunks:
                content, source, chunk_idx = chunks[chunk_id]
                sim = recency_weight(r[3], source)
                results.append({
                    'id': chunk_id,
                    'content': content,
                    'source': source,
                    'chunk_index': chunk_idx,
                    'similarity': sim
                })
            else:
                # Fallback: data in FAISS but not in DB (shouldn't happen)
                results.append({
                    'id': chunk_id,
                    'content': '[content unavailable]',
                    'source': r[1],
                    'chunk_index': r[2],
                    'similarity': r[3]
                })
        
        # MMR diversity reranking
        results = mmr_rerank(results, top_k)
        
        # Cache results
        _cache_set(ckey, results)
        
        elapsed_ms = (time.time() - start_time) * 1000
        log_search(db, query, results[0]['similarity'] if results else 0, len(results), elapsed_ms)
        
        return results
    
    # Fallback to brute-force
    if not quiet:
        print(f"Searching {stats['total_chunks']} chunks (brute-force)...\n")
    
    all_chunks = get_all_embeddings(db)
    results = []
    for chunk_id, content, source_path, chunk_index, chunk_embedding in all_chunks:
        sim = cosine_similarity(query_embedding, chunk_embedding)
        sim = recency_weight(sim, source_path)
        results.append({
            'id': chunk_id,
            'content': content,
            'source': source_path,
            'chunk_index': chunk_index,
            'similarity': sim
        })
    
    results.sort(key=lambda x: x['similarity'], reverse=True)
    results = mmr_rerank(results[:top_k * 2], top_k)
    
    _cache_set(ckey, results)
    elapsed_ms = (time.time() - start_time) * 1000
    log_search(db, query, results[0]['similarity'] if results else 0, len(results), elapsed_ms)
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Semantic search over memory")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--top", type=int, default=5, help="Number of results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    results = search(args.query, args.top, quiet=args.json)
    
    if args.json:
        import json
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
            content = r['content']
            if len(content) > 300:
                content = content[:300] + "..."
            print(content)
            print()

if __name__ == "__main__":
    main()
