import os
import re
from dataclasses import dataclass
from typing import List, Optional

from assistant.repo.scanner import ProjectScanner
from assistant.repo.search import SearchEngine
from assistant.repo.parser import CodeParser, Symbol


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
    def __init__(
        self,
        scanner: Optional[ProjectScanner] = None,
        max_budget_chars: int = 6000
    ):
        self.scanner = scanner or ProjectScanner()
        self.search_engine = SearchEngine(self.scanner)
        self.parser = CodeParser()
        self.max_budget_chars = max_budget_chars

    def extract_keywords(self, query: str) -> List[str]:
        """Extracts meaningful identifiers/keywords from user query."""
        # Split on non-alphanumeric characters, ignore tiny words
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
                        
                        # Extract exact symbol lines
                        start = max(1, sym.start_line)
                        end = min(len(lines), sym.end_line)
                        code = "".join(lines[start - 1 : end]).strip()
                        rel_path = os.path.relpath(file_path, self.scanner.root_dir)

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
                rel_path = os.path.relpath(f_path, self.scanner.root_dir)

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
            # Sort by start_line
            snip_list.sort(key=lambda s: s.start_line)
            current = snip_list[0]

            for next_snip in snip_list[1:]:
                # If overlapping or adjacent (within 2 lines)
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

    def build_context(self, query: str) -> str:
        """
        Main entry point: given a user query, locates relevant symbols and code lines,
        assembles them within the character budget, and returns formatted markdown.
        """
        keywords = self.extract_keywords(query)
        if not keywords:
            return ""

        all_files = self.scanner.get_all_files()
        
        # 1. Gather symbol snippets (high priority)
        symbol_snippets = self.get_symbol_snippets(keywords, all_files)
        
        # 2. Gather text search snippets (supplementary)
        search_snippets = self.get_search_snippets(keywords)

        # 3. Combine and merge overlapping ranges
        all_snippets = self._merge_snippets(symbol_snippets + search_snippets)
        
        # 4. Sort by relevance score descending
        all_snippets.sort(key=lambda s: s.score, reverse=True)

        # 5. Apply context budget
        selected = []
        current_chars = 0
        header = f"### Relevant Project Context ({self.scanner.project_info['project_name']}):\n\n"
        current_chars += len(header)

        for snip in all_snippets:
            snippet_str = f"File `{snip.rel_path}` (Lines {snip.start_line}-{snip.end_line}):\n```python\n{snip.code}\n```\n\n"
            if current_chars + len(snippet_str) <= self.max_budget_chars:
                selected.append(snippet_str)
                current_chars += len(snippet_str)
            else:
                break

        if not selected:
            return ""

        return header + "".join(selected)


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "How does repository root detection work?"
    print(f"\nBuilding context for query: '{query}'\n")

    builder = ContextBuilder()
    context = builder.build_context(query)
    
    if context:
        print(context)
        print(f"Total context characters: {len(context)}")
    else:
        print("No relevant context found.")