# assistant/rag/semantic_search.py

import os
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

from assistant.config import settings
from assistant.rag.chunker import CodeChunk
from assistant.rag.embeddings import BaseEmbeddingModel, get_embedding_model
from assistant.rag.vector_store import VectorStore
from assistant.utils.logger import setup_logger

logger = setup_logger("SemanticSearch")


@dataclass
class SemanticSearchResult:
    """Represents a scored chunk retrieved via semantic vector similarity."""

    chunk: CodeChunk
    score: float

    @property
    def citation(self) -> str:
        """Formatted human-readable citation with line references."""
        return (
            f"[{self.chunk.symbol_type.upper()}] {self.chunk.file_path}:"
            f"L{self.chunk.start_line}-L{self.chunk.end_line} ({self.chunk.symbol_name}) "
            f"[Relevance: {self.score:.4f}]"
        )


class SemanticSearchEngine:
    """
    Performs natural-language semantic code search against local vector storage.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_model: Optional[BaseEmbeddingModel] = None,
    ):
        self.vector_store = vector_store or VectorStore()
        self.embedding_model = embedding_model or get_embedding_model()

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.30,
        language: Optional[str] = None,
        symbol_type: Optional[str] = None,
        file_path_prefix: Optional[str] = None,
    ) -> List[SemanticSearchResult]:
        """
        Embed a natural-language query and retrieve top matching code chunks.

        Args:
            query: Natural-language query string.
            top_k: Maximum results to return.
            min_score: Cosine similarity cutoff.
            language: Filter by language (e.g. 'python', 'markdown').
            symbol_type: Filter by symbol type ('function', 'class', etc.).
            file_path_prefix: Filter by directory or file path prefix.

        Returns:
            List of SemanticSearchResult objects sorted by relevance.
        """
        if not query or not query.strip():
            return []

        start_time = time.time()
        # Generate query embedding vector
        q_vec = self.embedding_model.embed_query(query)

        # Query vector store
        matches = self.vector_store.search(
            query_embedding=q_vec,
            top_k=top_k,
            min_score=min_score,
            file_path_prefix=file_path_prefix,
            language=language,
            symbol_type=symbol_type,
        )

        results = [SemanticSearchResult(chunk=ch, score=score) for ch, score in matches]
        duration = time.time() - start_time
        logger.info(f"Semantic search for '{query[:40]}...' found {len(results)} results in {duration:.3f}s")
        return results


if __name__ == "__main__":
    from assistant.rag.indexer import RepositoryIndexer

    print("=" * 60)
    print("      Sub-Phase 5.5: Semantic Search Verification")
    print("=" * 60)

    # Ensure repository is indexed into the main database
    store = VectorStore()
    if store.count() == 0:
        print("[*] Vector store empty. Performing initial index...")
        indexer = RepositoryIndexer(root_dir=".", vector_store=store)
        indexer.index_repository()
    else:
        print(f"[*] Using existing vector store with {store.count()} chunks.")

    search_engine = SemanticSearchEngine(vector_store=store)

    queries = [
        "Where is the terminal command execution tool defined?",
        "Where are user approval checks and confirmation prompts handled?",
        "How is the context budget calculated and assembled?",
    ]

    for q in queries:
        print(f"\n--- Query: '{q}' ---")
        results = search_engine.search(q, top_k=3, min_score=0.40)
        if not results:
            print("  [!] No matching chunks found above threshold.")
        for r in results:
            print(f"  • {r.citation}")
            first_line = r.chunk.content.splitlines()[0] if r.chunk.content else ""
            print(f"    Snippet: {first_line[:80]}...")

    print("\n[PASS] Sub-Phase 5.5 Verification Complete.")

