"""
SQLite vector storage with binary embeddings and incremental indexing.
"""
import sqlite3
import struct
import hashlib
import json
from pathlib import Path
from typing import List, Tuple, Optional

DB_PATH = Path(__file__).parent.parent / "memory.db"

EMBEDDING_DIM = 768  # nomic-embed-text dimension

def _pack_embedding(embedding: List[float]) -> bytes:
    """Pack embedding as binary float32 array (~3KB vs ~16KB JSON)."""
    return struct.pack(f'{len(embedding)}f', *embedding)

def _unpack_embedding(blob: bytes) -> List[float]:
    """Unpack binary embedding."""
    n = len(blob) // 4
    return list(struct.unpack(f'{n}f', blob))

def get_db() -> sqlite3.Connection:
    """Get database connection, creating tables if needed."""
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            source_path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            content_hash TEXT,
            file_mtime REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_path, chunk_index)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_source ON chunks(source_path)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON chunks(content_hash)")
    
    # Analytics table
    db.execute("""
        CREATE TABLE IF NOT EXISTS search_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            top_score REAL,
            num_results INTEGER,
            search_time_ms REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db

def store_chunk(db: sqlite3.Connection, content: str, source_path: str, 
                chunk_index: int, embedding: List[float], 
                content_hash: str = None, file_mtime: float = None) -> int:
    """Store a chunk with binary embedding."""
    embedding_blob = _pack_embedding(embedding)
    if content_hash is None:
        content_hash = hashlib.md5(content.encode()).hexdigest()
    cursor = db.execute("""
        INSERT OR REPLACE INTO chunks (content, source_path, chunk_index, embedding, content_hash, file_mtime)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (content, source_path, chunk_index, embedding_blob, content_hash, file_mtime))
    db.commit()
    return cursor.lastrowid

def get_all_embeddings(db: sqlite3.Connection) -> List[Tuple[int, str, str, int, List[float]]]:
    """Get all chunks with embeddings."""
    cursor = db.execute("SELECT id, content, source_path, chunk_index, embedding FROM chunks")
    results = []
    for row in cursor:
        blob = row[4]
        # Handle both JSON (legacy) and binary formats
        try:
            if isinstance(blob, bytes) and len(blob) > 0 and blob[0:1] == b'[':
                embedding = json.loads(blob)
            else:
                embedding = _unpack_embedding(blob)
        except Exception:
            embedding = _unpack_embedding(blob)
        results.append((row[0], row[1], row[2], row[3], embedding))
    return results

def get_embeddings_only(db: sqlite3.Connection) -> List[Tuple[int, str, str, int, List[float]]]:
    """Get id, source, chunk_index, and embedding only (no content for FAISS build)."""
    cursor = db.execute("SELECT id, source_path, chunk_index, embedding FROM chunks")
    results = []
    for row in cursor:
        blob = row[3]
        try:
            if isinstance(blob, bytes) and len(blob) > 0 and blob[0:1] == b'[':
                embedding = json.loads(blob)
            else:
                embedding = _unpack_embedding(blob)
        except Exception:
            embedding = _unpack_embedding(blob)
        results.append((row[0], row[1], row[2], embedding))
    return results

def get_chunk_by_id(db: sqlite3.Connection, chunk_id: int) -> Optional[Tuple]:
    """Get a single chunk by ID."""
    cursor = db.execute("SELECT id, content, source_path, chunk_index FROM chunks WHERE id = ?", (chunk_id,))
    return cursor.fetchone()

def get_chunks_by_ids(db: sqlite3.Connection, chunk_ids: List[int]) -> dict:
    """Get multiple chunks by IDs. Returns {id: (content, source_path, chunk_index)}."""
    if not chunk_ids:
        return {}
    placeholders = ','.join('?' * len(chunk_ids))
    cursor = db.execute(f"SELECT id, content, source_path, chunk_index FROM chunks WHERE id IN ({placeholders})", chunk_ids)
    return {row[0]: (row[1], row[2], row[3]) for row in cursor}

def delete_source(db: sqlite3.Connection, source_path: str) -> int:
    """Delete all chunks from a source file."""
    cursor = db.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
    db.commit()
    return cursor.rowcount

def get_file_mtime(db: sqlite3.Connection, source_path: str) -> Optional[float]:
    """Get stored mtime for a file."""
    cursor = db.execute("SELECT file_mtime FROM chunks WHERE source_path = ? LIMIT 1", (source_path,))
    row = cursor.fetchone()
    return row[0] if row else None

def get_content_hashes(db: sqlite3.Connection, source_path: str) -> List[str]:
    """Get all content hashes for a source file."""
    cursor = db.execute("SELECT content_hash FROM chunks WHERE source_path = ? ORDER BY chunk_index", (source_path,))
    return [row[0] for row in cursor]

def get_indexed_files(db: sqlite3.Connection) -> set:
    """Get set of all indexed source paths."""
    cursor = db.execute("SELECT DISTINCT source_path FROM chunks")
    return {row[0] for row in cursor}

def log_search(db: sqlite3.Connection, query: str, top_score: float, num_results: int, search_time_ms: float):
    """Log a search query for analytics."""
    try:
        db.execute("INSERT INTO search_log (query, top_score, num_results, search_time_ms) VALUES (?, ?, ?, ?)",
                   (query, top_score, num_results, search_time_ms))
        db.commit()
    except Exception:
        pass  # Don't let logging break search

def get_stats(db: sqlite3.Connection) -> dict:
    """Get database statistics."""
    cursor = db.execute("SELECT COUNT(*), COUNT(DISTINCT source_path) FROM chunks")
    row = cursor.fetchone()
    return {
        "total_chunks": row[0],
        "total_files": row[1],
        "db_path": str(DB_PATH)
    }

if __name__ == "__main__":
    db = get_db()
    stats = get_stats(db)
    print(f"Database stats: {stats}")
