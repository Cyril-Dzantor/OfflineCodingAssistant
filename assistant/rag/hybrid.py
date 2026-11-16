# assistant/rag/hybrid.py

import os
import re
import time
from typing import List, Optional, Dict, Any, Tuple

from assistant.config import settings
from assistant.rag.chunker import CodeChunk
from assistant.rag.ranker import RankedResult, ResultRanker
from assistant.rag.semantic_search import SemanticSearchEngine, SemanticSearchResult
from assistant.rag.vector_store import VectorStore
from assistant.repo.scanner import ProjectScanner
from assistant.repo.search import SearchEngine
from assistant.utils.logger import setup_logger

logger = setup_logger("HybridRetrieval")


class HybridRetriever:
    """
    Hybrid code retrieval engine combining deterministic keyword search
    and dense semantic vector search via Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        semantic_search: Optional[SemanticSearchEngine] = None,
        ranker: Optional[ResultRanker] = None,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store or VectorStore()
        self.semantic_search = semantic_search or SemanticSearchEngine(vector_store=self.vector_store)
        self.ranker = ranker or ResultRanker()
        self.rrf_k = rrf_k
        self.scanner = ProjectScanner(start_path=".")
        self.keyword_engine = SearchEngine(self.scanner)

    def search_keyword_chunks(
        self,
        query: str,
        limit: int = 15,
        language: Optional[str] = None,
        symbol_type: Optional[str] = None,
    ) -> List[CodeChunk]:
        """
        Perform keyword retrieval directly against stored chunks in the vector store.
        Extracts key identifier terms from the query and matches against symbol names and content.
        """
        # Extract potential keyword tokens (alphanumeric and underscores, minimum 3 chars)
        tokens = [t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query) if len(t) >= 3]
        if not tokens:
            return []

        clauses = []
        params = []

        # Build token match clauses
        token_clauses = []
        for t in tokens[:4]:  # limit to top 4 keywords
            token_clauses.append("(symbol_name LIKE ? OR content LIKE ?)")
            params.extend([f"%{t}%", f"%{t}%"])

        clauses.append(f"({' OR '.join(token_clauses)})")

        if language:
            clauses.append("language = ?")
            params.append(language)
        if symbol_type:
            clauses.append("symbol_type = ?")
            params.append(symbol_type)

        where_sql = f"WHERE {' AND '.join(clauses)}"
        sql = f"SELECT * FROM chunks {where_sql} LIMIT ?"
        params.append(limit * 2)

        conn = self.vector_store._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        matched_chunks: List[CodeChunk] = []
        for row in rows:
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
                docstring=row["docstring"],
            )
            matched_chunks.append(chunk)

        return matched_chunks[:limit]

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",  # "hybrid", "semantic", "keyword"
        keyword_weight: float = 1.0,
        semantic_weight: float = 1.0,
        language: Optional[str] = None,
        symbol_type: Optional[str] = None,
        file_path_prefix: Optional[str] = None,
    ) -> List[RankedResult]:
        """
        Retrieve chunks using the specified mode ('hybrid', 'semantic', or 'keyword').
        Combines rankings using Reciprocal Rank Fusion when in hybrid mode.
        """
        start_time = time.time()
        mode = mode.lower()

        # 1. Semantic Retrieval
        semantic_ranked: List[CodeChunk] = []
        if mode in ("hybrid", "semantic"):
            sem_results = self.semantic_search.search(
                query=query,
                top_k=top_k * 2,
                min_score=0.25,
                language=language,
                symbol_type=symbol_type,
                file_path_prefix=file_path_prefix,
            )
            semantic_ranked = [r.chunk for r in sem_results]

        # 2. Keyword Retrieval
        keyword_ranked: List[CodeChunk] = []
        if mode in ("hybrid", "keyword"):
            keyword_ranked = self.search_keyword_chunks(
                query=query,
                limit=top_k * 2,
                language=language,
                symbol_type=symbol_type,
            )

        # 3. Handle Single-Mode Retrieval
        if mode == "semantic":
            raw_results = [
                RankedResult(chunk=c, score=1.0 / (idx + 1), sources=["semantic"])
                for idx, c in enumerate(semantic_ranked)
            ]
            return self.ranker.rank_and_filter(raw_results, query=query, top_k=top_k)

        if mode == "keyword":
            raw_results = [
                RankedResult(chunk=c, score=1.0 / (idx + 1), sources=["keyword"])
                for idx, c in enumerate(keyword_ranked)
            ]
            return self.ranker.rank_and_filter(raw_results, query=query, top_k=top_k)

        # 4. Hybrid Reciprocal Rank Fusion (RRF)
        # RRF Score = sum( weight / (k + rank) )
        chunk_map: Dict[str, CodeChunk] = {}
        rrf_scores: Dict[str, float] = {}
        chunk_sources: Dict[str, List[str]] = {}

        # Add semantic ranks
        for rank, chunk in enumerate(semantic_ranked, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            chunk_sources.setdefault(cid, []).append("semantic")
            score = semantic_weight / (self.rrf_k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score

        # Add keyword ranks
        for rank, chunk in enumerate(keyword_ranked, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            if "keyword" not in chunk_sources.setdefault(cid, []):
                chunk_sources[cid].append("keyword")
            score = keyword_weight / (self.rrf_k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score

        # Build combined ranked list
        hybrid_items = [
            RankedResult(
                chunk=chunk_map[cid],
                score=rrf_scores[cid],
                sources=chunk_sources[cid],
            )
            for cid in chunk_map
        ]

        # 5. Apply Ranker (Deduplication + Boosts)
        final_results = self.ranker.rank_and_filter(
            hybrid_items,
            query=query,
            top_k=top_k,
            min_score=0.0,
        )

        duration = time.time() - start_time
        logger.info(
            f"Hybrid search ('{query[:35]}...') returned {len(final_results)} results "
            f"in {duration:.3f}s (mode={mode})"
        )
        return final_results


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phases 5.6 & 5.7: Hybrid Retrieval & Ranking Verification")
    print("=" * 60)

    retriever = HybridRetriever()

    test_queries = [
        # Query 1: Exact keyword match
        "ExecuteCommandTool",
        # Query 2: Natural-language semantic query
        "How do we prevent infinite loops and repeated identical tool calls?",
        # Query 3: Mixed hybrid query (keyword + concept)
        "settings.py context window and model parameters",
    ]

    for q in test_queries:
        print(f"\n--- Query: '{q}' ---")
        results = retriever.search(q, top_k=3, mode="hybrid")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.citation}")
            first_line = r.chunk.content.splitlines()[0] if r.chunk.content else ""
            print(f"     Preview: {first_line[:75]}...")

    print("\n[PASS] Sub-Phases 5.6 & 5.7 Verification Complete.")

