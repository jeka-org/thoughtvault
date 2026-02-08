#!/usr/bin/env python3
"""
Index files into the semantic memory database.
Supports incremental indexing (only re-indexes changed files).

Usage:
    ./index.py <directory> [--ext .md] [--force]
"""
import sys
import os
import hashlib
import argparse
import time
from pathlib import Path
from lib.embeddings import embed, embed_batch
from lib.chunker import chunk_file
from lib.db import (get_db, store_chunk, delete_source, get_stats, 
                    get_embeddings_only, get_file_mtime, get_content_hashes,
                    get_indexed_files)
from lib.faiss_index import build_index

SKIP_DIRS = ['digests', 'drafts', 'homepage-backup', 'content/toolkit-threads', 'content/toolkit-articles']

def should_skip(rel_path: str) -> bool:
    """Check if file should be skipped."""
    parts = Path(rel_path).parts
    if any(part.startswith('.') for part in parts):
        return True
    if any(skip in rel_path for skip in SKIP_DIRS):
        return True
    return False

def file_needs_reindex(db, file_path: Path, source_key: str) -> bool:
    """Check if file has changed since last index using mtime."""
    current_mtime = file_path.stat().st_mtime
    stored_mtime = get_file_mtime(db, source_key)
    if stored_mtime is None:
        return True  # New file
    return abs(current_mtime - stored_mtime) > 0.01  # Changed

def index_directory(directory: Path, extensions: list, force: bool = False):
    """Index all matching files in a directory."""
    start_time = time.time()
    db = get_db()
    
    files = []
    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))
    
    # Filter out skipped files
    valid_files = []
    for file_path in files:
        try:
            rel_path = str(file_path.relative_to(directory))
            if not should_skip(rel_path):
                valid_files.append(file_path)
        except ValueError:
            valid_files.append(file_path)
    
    print(f"Found {len(valid_files)} files to check")
    
    # Detect deleted files and remove from index
    indexed_files = get_indexed_files(db)
    current_files = {str(f) for f in valid_files}
    orphaned = indexed_files - current_files
    if orphaned:
        print(f"Removing {len(orphaned)} deleted files from index")
        for path in orphaned:
            delete_source(db, path)
    
    total_chunks = 0
    skipped_files = 0
    indexed_files_count = 0
    
    # Collect all chunks that need embedding
    pending_chunks = []  # (content, source_path, chunk_index, file_mtime)
    
    for file_path in valid_files:
        source_key = str(file_path)
        
        # Incremental: skip unchanged files
        if not force and not file_needs_reindex(db, file_path, source_key):
            skipped_files += 1
            continue
        
        # Delete existing chunks for this file
        deleted = delete_source(db, source_key)
        
        chunks = chunk_file(file_path)
        if not chunks:
            continue
        
        # Deduplication: hash-based
        seen_hashes = set()
        mtime = file_path.stat().st_mtime
        
        for content, idx, source in chunks:
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            pending_chunks.append((content, source, idx, mtime, content_hash))
        
        indexed_files_count += 1
    
    if not pending_chunks:
        print(f"\n✓ No changes detected. Skipped {skipped_files} unchanged files.")
        elapsed = time.time() - start_time
        print(f"  Time: {elapsed:.1f}s")
        return
    
    print(f"  Indexing {len(pending_chunks)} chunks from {indexed_files_count} files (skipped {skipped_files} unchanged)")
    
    # Batch embed
    texts = [c[0] for c in pending_chunks]
    print(f"  Generating embeddings...")
    embed_start = time.time()
    embeddings = embed_batch(texts)
    embed_time = time.time() - embed_start
    print(f"  Embeddings generated in {embed_time:.1f}s")
    
    # Store chunks
    for i, (content, source, idx, mtime, content_hash) in enumerate(pending_chunks):
        if embeddings[i] is None:
            continue
        try:
            store_chunk(db, content, source, idx, embeddings[i], content_hash, mtime)
            total_chunks += 1
        except Exception as e:
            print(f"    Error storing chunk: {e}")
    
    print(f"\n✓ Indexed {total_chunks} chunks from {indexed_files_count} files")
    
    stats = get_stats(db)
    print(f"  Total in database: {stats['total_chunks']} chunks from {stats['total_files']} files")
    
    # Build FAISS index (optimized - no content in metadata)
    print("\nBuilding FAISS index...")
    all_embeddings = get_embeddings_only(db)
    build_index(all_embeddings)
    print("✓ FAISS index ready")
    
    elapsed = time.time() - start_time
    print(f"\n  Total time: {elapsed:.1f}s")

def main():
    parser = argparse.ArgumentParser(description="Index files into semantic memory")
    parser.add_argument("directory", type=Path, help="Directory to index")
    parser.add_argument("--ext", action="append", default=None,
                        help="File extensions to index (default: .md)")
    parser.add_argument("--force", action="store_true",
                        help="Re-index all files (ignore mtime)")
    
    args = parser.parse_args()
    
    if args.ext is None:
        args.ext = [".md"]
    
    if not args.directory.exists():
        print(f"Error: {args.directory} does not exist")
        sys.exit(1)
    
    index_directory(args.directory, args.ext, args.force)

if __name__ == "__main__":
    main()
