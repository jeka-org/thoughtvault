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

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/jeka-org/thoughtvault.git
cd thoughtvault

# 2. Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# 3. Install Python dependencies
pip install -r requirements.txt

# 5. Start Ollama and verify the model is available
ollama serve &  # start Ollama daemon (skip if already running)
ollama pull nomic-embed-text
ollama list  # should show nomic-embed-text

# 6. Index your files
./index.py ~/path/to/your/markdown/files

# 7. Search
./search.py "your query here"
```

## Quick Start

```bash
# Index your files (incremental - only processes changes)
./index.py ~/path/to/your/files

# Force full re-index
./index.py ~/path/to/your/files --force

# Search semantically
./search.py "what projects do I have"
./search.py "security audit" --top 10
./search.py "project architecture" --json  # JSON output for integrations
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
├── memory.db          # SQLite database (~11MB for 2.7K chunks)
├── faiss.index        # FAISS vector index (~8MB)
└── faiss_metadata.json # Compact ID-only metadata (~180KB)
```

## Performance (2,670 chunks, validated 2026-02-08)

| Metric | Value |
|--------|-------|
| Database size | 11MB |
| FAISS index | 7.8MB |
| FAISS metadata | 179KB |
| Search latency | ~96ms |
| Cached query | ~3ms (32x speedup) |
| Incremental re-index (no changes) | <1s |
| Embedding size | 3KB per chunk (binary float32) |

## OpenClaw Plugin

ThoughtVault includes an [OpenClaw](https://github.com/openclaw/openclaw) memory plugin that provides `memory_search` and `memory_get` tools to all agents on the same instance.

### Plugin Installation

```bash
# 1. Install ThoughtVault (follow steps above first)

# 2. Install the plugin into OpenClaw
openclaw plugins install ./openclaw-plugin

# 3. Enable it and set as the memory provider
openclaw plugins enable thoughtvault-memory

# 4. Configure the plugin (in openclaw.json or via CLI)
# Set plugins.slots.memory = "thoughtvault-memory"
# Set plugins.entries.thoughtvault-memory.config.thoughtvaultPath to your ThoughtVault path
```

Or manually: copy `openclaw-plugin/` to `~/.openclaw/extensions/thoughtvault-memory/` and add to your config:

```json
{
  "plugins": {
    "slots": { "memory": "thoughtvault-memory" },
    "entries": {
      "thoughtvault-memory": {
        "enabled": true,
        "config": {
          "thoughtvaultPath": "~/thoughtvault",
          "topK": 5
        }
      }
    }
  }
}
```

### What Agents Get

- **memory_search** - Semantic search across all indexed markdown files
- **memory_get** - Read specific sections from any indexed file
- **CLI commands** - `openclaw thoughtvault search/reindex/stats`

Every agent on the same OpenClaw instance shares the same semantic memory index. Index your workspace once, all agents can search it.

## License

AGPL-3.0 — See [LICENSE](LICENSE) for details.
