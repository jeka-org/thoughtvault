# ThoughtVault

Local semantic memory system for AI agents. Zero API cost.

## Features

1. **Semantic Search** - Find related content by meaning, not just keywords
2. **Auto-Capture** - Automatically extract and store important info from conversations
3. **Local Embeddings** - Uses Ollama (nomic-embed-text) - runs entirely on your machine

## Requirements

- Ollama with `nomic-embed-text` model
- Python 3.10+
- SQLite (included in Python)

## Quick Start

```bash
# Index your files
./index.py ~/path/to/your/files

# Search semantically
./search.py "what projects do I have"

# Auto-capture from conversation
./capture.py "conversation transcript here"
```

## How It Works

### Indexing
1. Scans markdown files in specified directories
2. Chunks content into ~500 token pieces
3. Generates embeddings via Ollama (local, free)
4. Stores chunks + embeddings in SQLite

### Search
1. Embeds your query
2. Finds similar chunks via cosine similarity
3. Returns relevant file snippets with source locations

### Auto-Capture
1. Analyzes conversation text
2. Extracts: decisions, projects, lessons, todos
3. Appends to appropriate memory files

## Architecture

```
thoughtvault/
├── index.py      # Index files into vector DB
├── search.py     # Semantic search CLI
├── capture.py    # Auto-capture from conversations
├── lib/
│   ├── embeddings.py  # Ollama embedding client
│   ├── chunker.py     # Text chunking
│   └── db.py          # SQLite vector storage
└── memory.db     # SQLite database with embeddings
```

## Credits

Built by Spark (an AI agent) for better memory continuity.
MIT License.
