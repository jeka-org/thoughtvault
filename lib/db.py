"""
SQLite vector storage
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Tuple, Optional

DB_PATH = Path(__file__).parent.parent / "memory.db"

def get_db() -> sqlite3.Connection:
    """Get database connection, creating tables if needed."""
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            source_path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_path, chunk_index)
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_source ON chunks(source_path)
    """)
    db.commit()
    return db

def store_chunk(db: sqlite3.Connection, content: str, source_path: str, 
                chunk_index: int, embedding: List[float]) -> int:
    """Store a chunk with its embedding. Returns chunk id."""
    embedding_blob = json.dumps(embedding).encode()
    cursor = db.execute("""
        INSERT OR REPLACE INTO chunks (content, source_path, chunk_index, embedding)
        VALUES (?, ?, ?, ?)
    """, (content, source_path, chunk_index, embedding_blob))
    db.commit()
    return cursor.lastrowid

def get_all_embeddings(db: sqlite3.Connection) -> List[Tuple[int, str, str, int, List[float]]]:
    """Get all chunks with embeddings for similarity search."""
    cursor = db.execute("""
        SELECT id, content, source_path, chunk_index, embedding FROM chunks
    """)
    results = []
    for row in cursor:
        embedding = json.loads(row[4])
        results.append((row[0], row[1], row[2], row[3], embedding))
    return results

def delete_source(db: sqlite3.Connection, source_path: str) -> int:
    """Delete all chunks from a source file. Returns count deleted."""
    cursor = db.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
    db.commit()
    return cursor.rowcount

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
