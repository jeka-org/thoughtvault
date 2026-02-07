#!/usr/bin/env python3
"""
Index files into the semantic memory database.

Usage:
    ./index.py <directory> [--ext .md] [--force]
"""
import sys
import argparse
from pathlib import Path
from lib.embeddings import embed
from lib.chunker import chunk_file
from lib.db import get_db, store_chunk, delete_source, get_stats

def index_directory(directory: Path, extensions: list, force: bool = False):
    """Index all matching files in a directory."""
    db = get_db()
    
    files = []
    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))
    
    print(f"Found {len(files)} files to index")
    
    total_chunks = 0
    for file_path in files:
        # Skip hidden files (relative to index directory)
        try:
            rel_path = file_path.relative_to(directory)
            if any(part.startswith('.') for part in rel_path.parts):
                continue
        except ValueError:
            pass  # Not relative, just process it
        
        print(f"  Indexing: {file_path}")
        
        if force:
            deleted = delete_source(db, str(file_path))
            if deleted:
                print(f"    Deleted {deleted} existing chunks")
        
        chunks = chunk_file(file_path)
        for content, idx, source in chunks:
            try:
                embedding = embed(content)
                store_chunk(db, content, source, idx, embedding)
                total_chunks += 1
            except Exception as e:
                print(f"    Error embedding chunk {idx}: {e}")
    
    print(f"\n✓ Indexed {total_chunks} chunks from {len(files)} files")
    
    stats = get_stats(db)
    print(f"  Total in database: {stats['total_chunks']} chunks from {stats['total_files']} files")

def main():
    parser = argparse.ArgumentParser(description="Index files into semantic memory")
    parser.add_argument("directory", type=Path, help="Directory to index")
    parser.add_argument("--ext", action="append", default=[".md"], 
                        help="File extensions to index (default: .md)")
    parser.add_argument("--force", action="store_true",
                        help="Re-index existing files")
    
    args = parser.parse_args()
    
    if not args.directory.exists():
        print(f"Error: {args.directory} does not exist")
        sys.exit(1)
    
    index_directory(args.directory, args.ext, args.force)

if __name__ == "__main__":
    main()
