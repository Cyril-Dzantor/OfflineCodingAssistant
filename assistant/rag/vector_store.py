# assistant/rag/vector_store.py

import json
import os
import sqlite3
import time
from dataclasses import asdict
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from assistant.config import settings
from assistant.rag.chunker import CodeChunk
from assistant.utils.logger import setup_logger

logger = setup_logger("VectorStore")


class VectorStore:
    """
    Local persistent vector store backed by SQLite and NumPy vector operations.
    Stores chunks, metadata, and normalized float32 embeddings for fast cosine similarity search.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or getattr(settings, "VECTOR_DB_PATH", ".cydags/vector_store.db")
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        """Create parent directory for the database if it doesn't exist."""
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Open a SQLite connection with row factory enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite tables and indexes."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chunks (
                        chunk_id TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        language TEXT NOT NULL,
                        symbol_name TEXT NOT NULL,
                        symbol_type TEXT NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        parent_symbol TEXT,
                        parameters_json TEXT,
                        docstring TEXT,
                        timestamp REAL NOT NULL,
                        embedding BLOB NOT NULL
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_symbol_type ON chunks(symbol_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_language ON chunks(language)")

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_index_state (
                        file_path TEXT PRIMARY KEY,
                        file_hash TEXT NOT NULL,
                        chunk_count INTEGER NOT NULL,
                        last_indexed REAL NOT NULL
                    )
                    """
                )
            logger.info(f"Initialized persistent VectorStore at '{self.db_path}'")
        finally:
            conn.close()

    def add_chunks(self, chunks: List[CodeChunk], embeddings: List[List[float]]) -> int:
        """
        Store chunks and their corresponding embedding vectors in the database.

        Args:
            chunks: List of CodeChunk objects.
            embeddings: Corresponding list of float embeddings.

        Returns:
            Number of successfully inserted/updated chunks.
        """
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunk count ({len(chunks)}) does not match embedding count ({len(embeddings)})")

        inserted = 0
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                for chunk, emb in zip(chunks, embeddings):
                    vec = np.asarray(emb, dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    if norm > 0.0:
                        vec = vec / norm
                    emb_blob = vec.tobytes()

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO chunks (
                            chunk_id, file_path, language, symbol_name, symbol_type,
                            start_line, end_line, content, content_hash, parent_symbol,
                            parameters_json, docstring, timestamp, embedding
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.file_path,
                            chunk.language,
                            chunk.symbol_name,
                            chunk.symbol_type,
                            chunk.start_line,
                            chunk.end_line,
                            chunk.content,
                            chunk.content_hash,
                            chunk.parent_symbol,
                            json.dumps(chunk.parameters),
                            chunk.docstring,
                            chunk.timestamp,
                            emb_blob,
                        ),
                    )
                    inserted += 1
        finally:
            conn.close()
        return inserted

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_score: float = 0.0,
        file_path_prefix: Optional[str] = None,
        language: Optional[str] = None,
        symbol_type: Optional[str] = None,
    ) -> List[Tuple[CodeChunk, float]]:
        """
        Perform vector cosine similarity search against stored chunks.
        """
        q_vec = np.asarray(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0.0:
            return []
        q_vec = q_vec / q_norm

        clauses = []
        params = []
        if file_path_prefix:
            clauses.append("file_path LIKE ?")
            params.append(f"{file_path_prefix}%")
        if language:
            clauses.append("language = ?")
            params.append(language)
        if symbol_type:
            clauses.append("symbol_type = ?")
            params.append(symbol_type)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM chunks {where_clause}"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        results: List[Tuple[CodeChunk, float]] = []
        for row in rows:
            emb_blob = row["embedding"]
            c_vec = np.frombuffer(emb_blob, dtype=np.float32)
            sim = float(np.dot(q_vec, c_vec))
            if sim >= min_score:
                params_list = json.loads(row["parameters_json"]) if row["parameters_json"] else []
                chunk = CodeChunk(
                    chunk_id=row["chunk_id"],
                    file_path=row["file_path"],
                    language=row["language"],
                    symbol_name=row["symbol_name"],
                    symbol_type=row["symbol_type"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    content=row["content"],
                    content_hash=row["content_hash"],
                    timestamp=row["timestamp"],
                    parent_symbol=row["parent_symbol"],
                    parameters=params_list,
                    docstring=row["docstring"],
                )
                results.append((chunk, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete_file_chunks(self, file_path: str) -> int:
        """Remove all chunks associated with a specific file."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chunks WHERE file_path = ?", (file_path,))
                deleted = cursor.rowcount
                cursor.execute("DELETE FROM file_index_state WHERE file_path = ?", (file_path,))
            return deleted
        finally:
            conn.close()

    def update_file_state(self, file_path: str, file_hash: str, chunk_count: int) -> None:
        """Record or update incremental indexing state for a file."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO file_index_state (file_path, file_hash, chunk_count, last_indexed)
                    VALUES (?, ?, ?, ?)
                    """,
                    (file_path, file_hash, chunk_count, time.time()),
                )
        finally:
            conn.close()

    def get_file_state(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve incremental indexing state for a file."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM file_index_state WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def list_indexed_files(self) -> List[str]:
        """Return a list of all file paths currently recorded in the index."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM file_index_state")
            return [row["file_path"] for row in cursor.fetchall()]
        finally:
            conn.close()

    def count(self) -> int:
        """Return the total number of chunks stored in the vector database."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM chunks")
            return cursor.fetchone()["count"]
        finally:
            conn.close()

    def clear(self) -> None:
        """Wipe all chunks and file states from the vector database."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chunks")
                cursor.execute("DELETE FROM file_index_state")
            logger.info("Cleared VectorStore")
        finally:
            conn.close()


if __name__ == "__main__":
    import shutil

    print("=" * 60)
    print("      Sub-Phase 5.3: Vector Database Verification")
    print("=" * 60)

    test_db = ".cydags/test_vector_store.db"
    store = VectorStore(db_path=test_db)
    store.clear()

    # Create dummy chunks and dummy 384-d vectors
    chunk1 = CodeChunk(
        chunk_id="chk1",
        file_path="src/auth.py",
        language="python",
        symbol_name="login",
        symbol_type="function",
        start_line=1,
        end_line=10,
        content="def login(user, pwd): pass",
        content_hash="h1",
    )
    chunk2 = CodeChunk(
        chunk_id="chk2",
        file_path="docs/setup.md",
        language="markdown",
        symbol_name="Setup Guide",
        symbol_type="documentation",
        start_line=1,
        end_line=20,
        content="# Setup Guide\nRun python install",
        content_hash="h2",
    )

    vec1 = [0.1] * 384
    vec2 = [0.9] * 384

    store.add_chunks([chunk1, chunk2], [vec1, vec2])
    store.update_file_state("src/auth.py", "hash1", 1)
    store.update_file_state("docs/setup.md", "hash2", 1)

    print(f"\n[+] Stored {store.count()} chunks in test vector DB.")
    assert store.count() == 2, "Expected 2 chunks in store"

    # Search with exact vec1
    results = store.search(query_embedding=vec1, top_k=2)
    print(f"[+] Top match for vec1: {results[0][0].symbol_name} (Score: {results[0][1]:.4f})")
    assert results[0][0].chunk_id == "chk1", "Search did not return top matching vector"

    # Search with metadata filter
    filtered = store.search(query_embedding=vec1, language="markdown")
    print(f"[+] Metadata filtered (language='markdown'): {len(filtered)} result -> {filtered[0][0].symbol_name}")
    assert len(filtered) == 1 and filtered[0][0].language == "markdown", "Metadata filter failed"

    # Delete file chunks
    deleted = store.delete_file_chunks("src/auth.py")
    print(f"[+] Deleted {deleted} chunks for 'src/auth.py'. Remaining count: {store.count()}")
    assert store.count() == 1, "Expected 1 chunk remaining"

    # Cleanup test db
    if os.path.exists(test_db):
        os.remove(test_db)
    print("\n[PASS] Sub-Phase 5.3 Verification Complete.")
