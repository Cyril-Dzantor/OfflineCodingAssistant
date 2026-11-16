# assistant/repo/context.py

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from assistant.repo.scanner import ProjectScanner
from assistant.repo.search import SearchEngine
from assistant.repo.parser import CodeParser, Symbol
from assistant.rag.memory import ProjectMemory
from assistant.rag.hybrid import HybridRetriever
from assistant.rag.ranker import RankedResult
from assistant.utils.logger import setup_logger

logger = setup_logger("ContextBuilder")


@dataclass
class ContextSnippet:
    file_path: str
    rel_path: str
    start_line: int
    end_line: int
    code: str
    score: float
    reason: str


class ContextBuilder:
    """
    Advanced multi-source context manager for Qwen2.5-Coder.
    Coordinates hybrid retrieval, AST symbol analysis, persistent project memory,
    and tool outputs within a strict character/token budget.
    """

    def __init__(
        self,
        scanner: Optional[ProjectScanner] = None,
        max_budget_chars: int = 6000,
        retriever: Optional[HybridRetriever] = None,
        memory: Optional[ProjectMemory] = None,
    ):
        self.scanner = scanner or ProjectScanner()
        self.search_engine = SearchEngine(self.scanner)
        self.parser = CodeParser()
        self.max_budget_chars = max_budget_chars
        self._retriever = retriever
        self._memory = memory

    @property
    def retriever(self) -> Optional[HybridRetriever]:
        """Lazy load HybridRetriever to avoid unnecessary overhead."""
        if self._retriever is None:
            try:
                self._retriever = HybridRetriever()
            except Exception as e:
                logger.warning(f"Could not initialize HybridRetriever: {e}")
                self._retriever = None
        return self._retriever

    @property
    def memory(self) -> Optional[ProjectMemory]:
        """Lazy load ProjectMemory."""
        if self._memory is None:
            try:
                self._memory = ProjectMemory()
            except Exception as e:
                logger.warning(f"Could not initialize ProjectMemory: {e}")
                self._memory = None
        return self._memory

    def extract_keywords(self, query: str) -> List[str]:
        """Extracts meaningful identifiers/keywords from user query."""
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query)
        stop_words = {
            "where", "how", "what", "which", "is", "are", "the", "in", "this",
            "project", "code", "file", "files", "class", "function", "does",
            "can", "you", "explain", "find", "show", "me", "a", "an", "to"
        }
        return [w for w in words if w.lower() not in stop_words and len(w) > 2]

    def _read_file_lines(self, file_path: str) -> List[str]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.readlines()
        except Exception:
            return []

    def get_symbol_snippets(self, keywords: List[str], all_files: List[str]) -> List[ContextSnippet]:
        """Extracts snippets corresponding to matching classes and functions."""
        snippets = []
        for file_path in all_files:
            symbols = self.parser.parse_file(file_path)
            lines = None

            for sym in symbols:
                if sym.kind not in ("class", "function", "method"):
                    continue

                for kw in keywords:
                    if kw.lower() in sym.name.lower():
                        if lines is None:
                            lines = self._read_file_lines(file_path)

                        start = max(1, sym.start_line)
                        end = min(len(lines), sym.end_line)
                        code = "".join(lines[start - 1 : end]).strip()
                        rel_path = os.path.relpath(file_path, self.scanner.root_dir).replace("\\", "/")

                        snippets.append(
                            ContextSnippet(
                                file_path=file_path,
                                rel_path=rel_path,
                                start_line=start,
                                end_line=end,
                                code=code,
                                score=10.0 if kw.lower() == sym.name.lower() else 5.0,
                                reason=f"Symbol match: {sym.kind} '{sym.name}'",
                            )
                        )
                        break
        return snippets

    def get_search_snippets(self, keywords: List[str], window: int = 4) -> List[ContextSnippet]:
        """Extracts snippets around keyword search hits."""
        snippets = []
        file_lines_cache = {}

        for kw in keywords:
            hits = self.search_engine.search(kw)
            for hit in hits:
                f_path = hit["file"]
                line_no = hit["line_num"]

                if f_path not in file_lines_cache:
                    file_lines_cache[f_path] = self._read_file_lines(f_path)
                lines = file_lines_cache[f_path]

                start = max(1, line_no - window)
                end = min(len(lines), line_no + window)
                code = "".join(lines[start - 1 : end]).strip()
                rel_path = os.path.relpath(f_path, self.scanner.root_dir).replace("\\", "/")

                snippets.append(
                    ContextSnippet(
                        file_path=f_path,
                        rel_path=rel_path,
                        start_line=start,
                        end_line=end,
                        code=code,
                        score=2.0,
                        reason=f"Search hit: '{kw}'",
                    )
                )
        return snippets

    def _merge_snippets(self, snippets: List[ContextSnippet]) -> List[ContextSnippet]:
        """Deduplicates overlapping snippets within the same file."""
        by_file = {}
        for snip in snippets:
            by_file.setdefault(snip.file_path, []).append(snip)

        merged = []
        for f_path, snip_list in by_file.items():
            snip_list.sort(key=lambda s: s.start_line)
            current = snip_list[0]

            for next_snip in snip_list[1:]:
                if next_snip.start_line <= current.end_line + 2:
                    lines = self._read_file_lines(f_path)
                    new_start = min(current.start_line, next_snip.start_line)
                    new_end = max(current.end_line, next_snip.end_line)
                    new_code = "".join(lines[new_start - 1 : new_end]).strip()

                    current = ContextSnippet(
                        file_path=f_path,
                        rel_path=current.rel_path,
                        start_line=new_start,
                        end_line=new_end,
                        code=new_code,
                        score=max(current.score, next_snip.score) + 1.0,
                        reason=f"{current.reason}; {next_snip.reason}",
                    )
                else:
                    merged.append(current)
                    current = next_snip
            merged.append(current)
        return merged

    def build_context(
        self,
        query: str,
        include_memory: bool = True,
        tool_results: Optional[List[str]] = None,
        mode: str = "hybrid",
    ) -> str:
        """
        Main entry point: assembles multi-source context from hybrid retrieval,
        AST analysis, project memory, and tool outputs within character budget.
        """
        current_chars = 0
        context_parts: List[str] = []

        # 1. Include Persistent Project Memory
        if include_memory and self.memory:
            try:
                mem_str = self.memory.format_memory_summary(max_chars=1000)
                if mem_str:
                    context_parts.append(mem_str + "\n\n")
                    current_chars += len(mem_str) + 2
            except Exception as e:
                logger.warning(f"Error reading project memory: {e}")

        # 2. Include Tool Execution Results (if available)
        if tool_results:
            tool_block = ["### Recent Tool Execution Results:"]
            for tr in tool_results[-3:]:  # limit to last 3 tool results
                tool_block.append(f"```\n{tr.strip()}\n```")
            tool_str = "\n".join(tool_block) + "\n\n"
            if current_chars + len(tool_str) <= self.max_budget_chars:
                context_parts.append(tool_str)
                current_chars += len(tool_str)

        # 3. Retrieve Code and Documentation
        # Check if HybridRetriever can retrieve chunks from persistent vector store
        retrieved_content: List[str] = []

        # Only use retriever if the scanner root is current project root (i.e. vector db matches)
        is_current_proj = os.path.abspath(self.scanner.root_dir) == os.path.abspath(".")
        if is_current_proj and self.retriever and self.retriever.vector_store.count() > 0:
            try:
                ranked_items: List[RankedResult] = self.retriever.search(
                    query=query,
                    top_k=5,
                    mode=mode,
                )
                for item in ranked_items:
                    snippet = (
                        f"File `{item.chunk.file_path}` (Lines {item.chunk.start_line}-{item.chunk.end_line}, "
                        f"{item.chunk.symbol_type} '{item.chunk.symbol_name}'):\n"
                        f"```{item.chunk.language}\n{item.chunk.content}\n```\n\n"
                    )
                    if current_chars + len(snippet) <= self.max_budget_chars:
                        retrieved_content.append(snippet)
                        current_chars += len(snippet)
                    else:
                        break
            except Exception as e:
                logger.warning(f"Hybrid retrieval failed ({e}), falling back to AST/keyword search.")

        # 4. Fallback to AST symbol + Keyword search if no vector results retrieved
        if not retrieved_content:
            keywords = self.extract_keywords(query)
            if keywords:
                all_files = self.scanner.get_all_files()
                symbol_snippets = self.get_symbol_snippets(keywords, all_files)
                search_snippets = self.get_search_snippets(keywords)
                all_snippets = self._merge_snippets(symbol_snippets + search_snippets)
                all_snippets.sort(key=lambda s: s.score, reverse=True)

                for snip in all_snippets:
                    snippet_str = f"File `{snip.rel_path}` (Lines {snip.start_line}-{snip.end_line}):\n```python\n{snip.code}\n```\n\n"
                    if current_chars + len(snippet_str) <= self.max_budget_chars:
                        retrieved_content.append(snippet_str)
                        current_chars += len(snippet_str)
                    else:
                        break

        # 5. Assemble final context
        if retrieved_content:
            header = f"### Relevant Project Context ({self.scanner.project_info.get('project_name', 'Project')}):\n\n"
            context_parts.append(header + "".join(retrieved_content))

        return "".join(context_parts).strip()


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phase 5.8: Advanced Context Management Verification")
    print("=" * 60)

    builder = ContextBuilder()

    # Test context build with hybrid retrieval and persistent memory
    test_query = "Where is the local LLM model loaded and inference configured?"
    print(f"\n[*] Building context for: '{test_query}'")

    context = builder.build_context(
        query=test_query,
        include_memory=True,
        tool_results=["[read_file] Successfully read assistant/config/settings.py"],
    )

    print(f"\n[+] Generated context length: {len(context)} characters")
    print("\n--- Context Output Preview ---")
    print(context[:600] + "\n...")

    assert len(context) > 0, "Context output is empty"
    assert "settings.py" in context or "model.py" in context, "Expected settings.py or model.py in context"
    assert "Recent Tool Execution Results" in context, "Tool results missing from context"

    print("\n[PASS] Sub-Phase 5.8 Verification Complete.")
