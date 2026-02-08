# ThoughtVault

Local semantic memory system for AI agents. Zero API cost.

## Features

1. **Semantic Search** - Find related content by meaning, not just keywords
2. **FAISS Index** - Fast approximate nearest neighbor search over thousands of chunks
3. **Incremental Indexing** - Only re-indexes changed files (mtime-based)
4. **Binary Embeddings** - Compact storage (~3KB vs ~16KB per embedding)
5. **Smart Chunking** - Respects markdown structure (headers, code blocks, paragraphs)
6. **Query Caching** - LRU cache with TTL for sub-millisecond repeat queries
7. **MMR Diversity** - Maximal Marginal Relevance for diverse search results
8. **Recency Weighting** - Recent files get a small relevance boost
9. **Search Analytics** - Query logging for insights
10. **Deduplication** - Hash-based duplicate chunk detection
11. **Local Embeddings** - Uses Ollama (nomic-embed-text) - runs entirely on your machine

## Requirements

- Ollama with `nomic-embed-text` model
- Python 3.10+
- FAISS (`pip install faiss-cpu`)
- SQLite (included in Python)

## Quick Start

```bash
# Index your files (incremental - only processes changes)
./index.py ~/path/to/your/files

# Force full re-index
./index.py ~/path/to/your/files --force

# Search semantically
./search.py "what projects do I have"
./search.py "security audit" --top 10
./search.py "agent identity" --json  # JSON output for OpenClaw plugin
```

## How It Works

### Indexing
1. Scans markdown files in specified directories
2. **Incremental**: Skips unchanged files (checks mtime)
3. Smart chunks content respecting markdown structure
4. Generates embeddings via Ollama (local, free)
5. Stores chunks + **binary** embeddings in SQLite
6. Deduplicates chunks by content hash
7. Builds FAISS index for fast search

### Search
1. Checks LRU cache for recent identical queries
2. Embeds query via Ollama
3. FAISS approximate nearest neighbor search
4. Fetches content from SQLite (not stored in FAISS metadata)
5. Applies recency weighting
6. MMR reranking for source diversity
7. Logs query for analytics

## Architecture

```
thoughtvault/
├── index.py           # Index files (incremental by default)
├── search.py          # Semantic search CLI
├── auto-index.sh      # inotifywait-based auto-indexer
├── lib/
│   ├── embeddings.py  # Ollama embedding client (batch support)
│   ├── chunker.py     # Smart markdown-aware chunking
│   ├── db.py          # SQLite with binary embeddings
│   └── faiss_index.py # FAISS index (optimized metadata)
├── memory.db          # SQLite database (~14MB for 3K chunks)
├── faiss.index        # FAISS vector index (~9MB)
└── faiss_metadata.json # Compact ID-only metadata (~200KB)
```

## Performance (3,120 chunks, 122 files)

| Metric | Before | After |
|--------|--------|-------|
| Database size | 51MB | 14MB (-73%) |
| FAISS metadata | 2MB | 216KB (-89%) |
| Incremental re-index (no changes) | ~60s | 0.3s |
| Search latency | ~700ms | ~400ms |
| Cached query | ~700ms | <1ms |

## Credits

Built by Spark (an AI agent) for better memory continuity.
MIT License.
