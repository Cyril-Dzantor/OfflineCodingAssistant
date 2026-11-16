# assistant/rag/indexer.py

import hashlib
import os
import time
from typing import List, Dict, Any, Optional

from assistant.config import settings
from assistant.rag.chunker import CodeChunk, CodeChunker
from assistant.rag.embeddings import BaseEmbeddingModel, get_embedding_model
from assistant.rag.vector_store import VectorStore
from assistant.repo.scanner import ProjectScanner
from assistant.utils.logger import setup_logger

logger = setup_logger("Indexer")


class RepositoryIndexer:
    """
    Orchestrates repository indexing with incremental updates.
    Scans files, detects changes via hashes, chunks content, generates embeddings,
    and maintains the persistent vector database.
    """

    def __init__(
        self,
        root_dir: Optional[str] = None,
        vector_store: Optional[VectorStore] = None,
        embedding_model: Optional[BaseEmbeddingModel] = None,
        chunker: Optional[CodeChunker] = None,
    ):
        self.root_dir = os.path.abspath(root_dir or ".")
        self.scanner = ProjectScanner(start_path=self.root_dir, root_dir=self.root_dir)
        self.vector_store = vector_store or VectorStore()
        self.embedding_model = embedding_model or get_embedding_model()
        self.chunker = chunker or CodeChunker()

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Calculate SHA256 hash of a file's raw content."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def index_repository(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Perform a full or incremental index of the repository.

        Args:
            force_rebuild: If True, clears existing index and reindexes everything.

        Returns:
            Dictionary containing indexing statistics.
        """
        start_time = time.time()
        logger.info(f"Starting repository indexing (force_rebuild={force_rebuild}) in '{self.root_dir}'")

        if force_rebuild:
            self.vector_store.clear()

        # 1. Discover all active, unignored files
        scanned_files = self.scanner.get_all_files()
        scanned_rel_paths = {
            os.path.relpath(p, self.root_dir).replace("\\", "/"): p for p in scanned_files
        }

        # 2. Identify and handle deleted files
        indexed_files = set(self.vector_store.list_indexed_files())
        deleted_files = indexed_files - set(scanned_rel_paths.keys())

        deleted_count = 0
        for del_path in deleted_files:
            removed = self.vector_store.delete_file_chunks(del_path)
            deleted_count += 1
            logger.info(f"Removed {removed} stale chunks for deleted file: {del_path}")

        # 3. Categorize files: new, modified, or unchanged
        files_to_index: List[str] = []
        file_hashes: Dict[str, str] = {}
        skipped_count = 0
        modified_count = 0
        added_count = 0

        for rel_path, abs_path in scanned_rel_paths.items():
            try:
                curr_hash = self.compute_file_hash(abs_path)
                file_hashes[rel_path] = curr_hash
            except Exception as e:
                logger.warning(f"Could not hash '{rel_path}': {e}")
                continue

            saved_state = self.vector_store.get_file_state(rel_path)
            if saved_state is None:
                added_count += 1
                files_to_index.append(abs_path)
            elif saved_state["file_hash"] != curr_hash:
                modified_count += 1
                files_to_index.append(abs_path)
            else:
                skipped_count += 1

        logger.info(
            f"Index scan status: {len(scanned_files)} files total | "
            f"{added_count} new | {modified_count} modified | "
            f"{skipped_count} unchanged | {deleted_count} deleted"
        )

        # 4. Process files needing indexing
        total_chunks_added = 0
        for abs_path in files_to_index:
            rel_path = os.path.relpath(abs_path, self.root_dir).replace("\\", "/")
            # Clear old chunks if modified
            self.vector_store.delete_file_chunks(rel_path)

            chunks = self.chunker.chunk_file(abs_path, root_dir=self.root_dir)
            if not chunks:
                self.vector_store.update_file_state(rel_path, file_hashes[rel_path], 0)
                continue

            # Generate embeddings for chunk contents
            chunk_texts = [c.content for c in chunks]
            try:
                embeddings = self.embedding_model.embed_documents(chunk_texts)
                inserted = self.vector_store.add_chunks(chunks, embeddings)
                self.vector_store.update_file_state(rel_path, file_hashes[rel_path], len(chunks))
                total_chunks_added += inserted
            except Exception as e:
                logger.error(f"Failed to index chunks for '{rel_path}': {e}")

        duration = time.time() - start_time
        stats = {
            "total_scanned": len(scanned_files),
            "added_files": added_count,
            "modified_files": modified_count,
            "skipped_files": skipped_count,
            "deleted_files": deleted_count,
            "total_chunks_added": total_chunks_added,
            "total_chunks_in_db": self.vector_store.count(),
            "duration_seconds": round(duration, 3),
        }
        logger.info(f"Indexing completed in {duration:.2f}s: {stats}")
        return stats


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phase 5.4: Repository Indexing Verification")
    print("=" * 60)

    test_db = ".cydags/test_repo_index.db"
    store = VectorStore(db_path=test_db)
    store.clear()

    indexer = RepositoryIndexer(root_dir=".", vector_store=store)

    # Initial Indexing Run
    print("\n[*] Running initial repository indexing...")
    stats1 = indexer.index_repository(force_rebuild=True)
    print(f"  -> Total files scanned: {stats1['total_scanned']}")
    print(f"  -> Added files: {stats1['added_files']}")
    print(f"  -> Total chunks indexed: {stats1['total_chunks_added']}")
    print(f"  -> Indexing duration: {stats1['duration_seconds']}s")

    assert stats1["total_chunks_added"] > 0, "No chunks were indexed in initial run"

    # Incremental Indexing Run (Should skip all unchanged files)
    print("\n[*] Running incremental indexing check (zero changes)...")
    stats2 = indexer.index_repository(force_rebuild=False)
    print(f"  -> Skipped files: {stats2['skipped_files']}")
    print(f"  -> Added files: {stats2['added_files']}")
    print(f"  -> Modified files: {stats2['modified_files']}")
    print(f"  -> Incremental duration: {stats2['duration_seconds']}s")

    assert stats2["skipped_files"] == stats1["total_scanned"], "Incremental check failed: Unchanged files were not skipped"
    assert stats2["total_chunks_added"] == 0, "Incremental check failed: Reindexed chunks when no files changed"

    # Cleanup test db
    store.clear()
    if os.path.exists(test_db):
        os.remove(test_db)

    print("\n[PASS] Sub-Phase 5.4 Verification Complete.")

