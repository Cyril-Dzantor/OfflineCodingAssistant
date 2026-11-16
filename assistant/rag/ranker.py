# assistant/rag/ranker.py

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

from assistant.rag.chunker import CodeChunk
from assistant.utils.logger import setup_logger

logger = setup_logger("Ranker")


@dataclass
class RankedResult:
    """Represents a ranked and filtered retrieval result."""

    chunk: CodeChunk
    score: float
    sources: List[str] = field(default_factory=list)  # e.g. ["semantic", "keyword"]

    @property
    def citation(self) -> str:
        source_tags = "+".join(self.sources) if self.sources else "retrieval"
        return (
            f"[{self.chunk.symbol_type.upper()}] {self.chunk.file_path}:"
            f"L{self.chunk.start_line}-L{self.chunk.end_line} ({self.chunk.symbol_name}) "
            f"[{source_tags} | score: {self.score:.4f}]"
        )


class ResultRanker:
    """
    Ranks, boosts, and filters retrieved results based on metadata,
    source overlap, path hints, and symbol relevance.
    """

    def __init__(self, symbol_boost: float = 0.25, file_boost: float = 0.20):
        self.symbol_boost = symbol_boost
        self.file_boost = file_boost

    def deduplicate(self, results: List[RankedResult]) -> List[RankedResult]:
        """
        Deduplicate chunks by chunk_id and overlapping line spans within the same file.
        Preserves the highest scoring entry and aggregates sources.
        """
        seen_ids: Set[str] = set()
        deduped: List[RankedResult] = []

        for item in results:
            if item.chunk.chunk_id in seen_ids:
                # Merge sources into existing item
                for existing in deduped:
                    if existing.chunk.chunk_id == item.chunk.chunk_id:
                        for s in item.sources:
                            if s not in existing.sources:
                                existing.sources.append(s)
                        existing.score = max(existing.score, item.score)
                        break
                continue

            # Check for significant line span overlap in same file
            is_redundant = False
            for existing in deduped:
                if existing.chunk.file_path == item.chunk.file_path:
                    overlap_start = max(existing.chunk.start_line, item.chunk.start_line)
                    overlap_end = min(existing.chunk.end_line, item.chunk.end_line)
                    overlap_len = max(0, overlap_end - overlap_start + 1)
                    item_len = max(1, item.chunk.end_line - item.chunk.start_line + 1)

                    # If more than 75% of the item is covered by an existing chunk
                    if (overlap_len / item_len) > 0.75:
                        for s in item.sources:
                            if s not in existing.sources:
                                existing.sources.append(s)
                        is_redundant = True
                        break

            if not is_redundant:
                seen_ids.add(item.chunk.chunk_id)
                deduped.append(item)

        return deduped

    def rank_and_filter(
        self,
        results: List[RankedResult],
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[RankedResult]:
        """
        Apply heuristic boosts (exact symbol match, file name match) and filter results.

        Args:
            results: List of retrieved results.
            query: The original user search query.
            top_k: Max items to return.
            min_score: Minimum final score cutoff.

        Returns:
            Sorted, filtered list of RankedResult items.
        """
        if not results:
            return []

        # Deduplicate first
        unique_results = self.deduplicate(results)

        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        for item in unique_results:
            boost = 0.0
            # 1. Exact symbol match boost
            sym_name_clean = item.chunk.symbol_name.split(".")[-1].lower()
            if sym_name_clean and sym_name_clean in query_words:
                boost += self.symbol_boost

            # 2. File name relevance boost
            base_file = os.path.basename(item.chunk.file_path).lower()
            if base_file in query_lower or any(w in base_file for w in query_words if len(w) > 3):
                boost += self.file_boost

            # 3. Source agreement bonus (found by both semantic AND keyword)
            if len(item.sources) > 1:
                boost += 0.15

            item.score += boost

        # Filter by score
        filtered = [r for r in unique_results if r.score >= min_score]

        # Sort descending by score
        filtered.sort(key=lambda x: x.score, reverse=True)
        return filtered[:top_k]

