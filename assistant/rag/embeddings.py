# assistant/rag/embeddings.py

import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Union
import numpy as np

from assistant.config import settings
from assistant.utils.logger import setup_logger

logger = setup_logger("Embeddings")


class BaseEmbeddingModel(ABC):
    """Abstract base class for local embedding models."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of the generated embeddings."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of document texts.

        Args:
            texts: List of document strings to embed.

        Returns:
            List of float vector embeddings.
        """
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single search query.

        Args:
            query: The query string to embed.

        Returns:
            Float vector embedding.
        """
        pass


class LocalEmbeddingModel(BaseEmbeddingModel):
    """
    Local embedding model implementation using FastEmbed (ONNX Runtime CPU).
    Operates strictly locally, offloading computation to CPU to reserve GPU VRAM
    for LLM inference.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_dir: Optional[str] = None,
        threads: Optional[int] = None,
    ):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._cache_dir = cache_dir or settings.EMBEDDING_CACHE_DIR
        self._threads = threads
        self._dimension = getattr(settings, "EMBEDDING_DIM", 384)
        self._model = None

        # Check if local files exist in cache to enforce offline mode
        self._ensure_offline_env()
        self._init_model()

    def _ensure_offline_env(self) -> None:
        """Set offline environment flags if model is cached locally."""
        if os.path.isdir(self._cache_dir) and os.listdir(self._cache_dir):
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    def _init_model(self) -> None:
        """Initialize the FastEmbed TextEmbedding instance."""
        try:
            from fastembed import TextEmbedding

            # If cache directory exists, attempt loading with local_files_only
            local_only = os.path.isdir(self._cache_dir) and len(os.listdir(self._cache_dir)) > 0
            try:
                self._model = TextEmbedding(
                    model_name=self._model_name,
                    cache_dir=self._cache_dir,
                    threads=self._threads,
                    local_files_only=local_only,
                )
            except Exception as e:
                if local_only:
                    logger.warning(f"Local-only load failed ({e}), retrying without local_files_only restriction.")
                    self._model = TextEmbedding(
                        model_name=self._model_name,
                        cache_dir=self._cache_dir,
                        threads=self._threads,
                    )
                else:
                    raise

            # Detect dimension from supported models list or probe embedding
            for supported in TextEmbedding.list_supported_models():
                if supported.get("model") == self._model_name:
                    self._dimension = supported.get("dim", self._dimension)
                    break

            logger.info(
                f"Initialized local embedding model '{self._model_name}' "
                f"(dim={self._dimension}, cache='{self._cache_dir}')"
            )
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Embed a collection of text documents in batches.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts per batch.

        Returns:
            List of float vector embeddings.
        """
        if not texts:
            return []

        # Filter out empty or whitespace-only texts while preserving indices
        processed_texts = [t if t.strip() else " " for t in texts]

        results = []
        try:
            embeddings_gen = self._model.embed(
                processed_texts,
                batch_size=batch_size,
                parallel=self._threads,
            )
            for emb in embeddings_gen:
                results.append(emb.tolist())
            return results
        except Exception as e:
            logger.error(f"Error generating document embeddings: {e}")
            raise

    def embed_query(self, query: str) -> List[float]:
        """
        Generate an embedding vector for a single search query.

        Args:
            query: User search query.

        Returns:
            List of floats representing the query embedding.
        """
        cleaned = query.strip() or " "
        try:
            # Query embedding in fastembed
            embeddings = list(self._model.query_embed(cleaned))
            if embeddings:
                return embeddings[0].tolist()
            # Fallback to standard embed
            embeddings = list(self._model.embed([cleaned]))
            return embeddings[0].tolist()
        except Exception as e:
            logger.error(f"Error generating query embedding for '{query}': {e}")
            raise

    @staticmethod
    def cosine_similarity(v1: Union[List[float], np.ndarray], v2: Union[List[float], np.ndarray]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            v1: First vector.
            v2: Second vector.

        Returns:
            Cosine similarity score between -1.0 and 1.0.
        """
        a = np.asarray(v1, dtype=np.float32)
        b = np.asarray(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


_embedding_instance: Optional[LocalEmbeddingModel] = None


def get_embedding_model() -> LocalEmbeddingModel:
    """Return the singleton instance of the local embedding model."""
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = LocalEmbeddingModel()
    return _embedding_instance


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phase 5.1: Local Embedding Model Verification")
    print("=" * 60)

    t0 = time.time()
    embedder = get_embedding_model()
    init_time = time.time() - t0
    print(f"\n[+] Model loaded: {embedder._model_name}")
    print(f"[+] Embedding dimension: {embedder.dimension}")
    print(f"[+] Initialization time: {init_time:.2f}s")

    # Benchmark Document Embeddings
    sample_docs = [
        "def authenticate_user(username, password): return verify_password(password)",
        "def calculate_tax(income, rate=0.2): return income * rate",
        "class DatabaseConnection: def connect(self): pass",
    ]

    t_doc = time.time()
    doc_vectors = embedder.embed_documents(sample_docs)
    doc_time = time.time() - t_doc
    print(f"\n[+] Embedded {len(doc_vectors)} documents in {doc_time:.4f}s ({doc_time/len(sample_docs):.4f}s/doc)")
    print(f"[+] Output vector length: {len(doc_vectors[0])}")

    # Benchmark Query Embeddings
    query_auth = "How to verify user credentials and passwords?"
    query_finance = "Calculate taxes on annual earnings"

    t_query = time.time()
    q_auth_vec = embedder.embed_query(query_auth)
    q_fin_vec = embedder.embed_query(query_finance)
    query_time = time.time() - t_query
    print(f"[+] Embedded 2 queries in {query_time:.4f}s ({query_time/2:.4f}s/query)")

    # Semantic Similarity Tests
    sim_auth_doc0 = embedder.cosine_similarity(q_auth_vec, doc_vectors[0])
    sim_auth_doc1 = embedder.cosine_similarity(q_auth_vec, doc_vectors[1])
    sim_fin_doc1 = embedder.cosine_similarity(q_fin_vec, doc_vectors[1])

    print("\n--- Semantic Similarity Verification ---")
    print(f"Query: '{query_auth}'")
    print(f"  -> Match with authenticate_user(): {sim_auth_doc0:.4f}")
    print(f"  -> Match with calculate_tax():       {sim_auth_doc1:.4f}")
    print(f"\nQuery: '{query_finance}'")
    print(f"  -> Match with calculate_tax():       {sim_fin_doc1:.4f}")

    assert sim_auth_doc0 > sim_auth_doc1, "Semantic similarity failed: Auth query should rank auth doc higher than tax doc"
    assert sim_fin_doc1 > 0.6, "Semantic similarity failed: Finance query should score high on tax doc"
    print("\n[PASS] Sub-Phase 5.1 Verification Complete.")
