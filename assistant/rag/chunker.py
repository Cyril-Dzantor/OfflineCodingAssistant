# assistant/rag/chunker.py

import hashlib
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from assistant.repo.parser import CodeParser, Symbol
from assistant.utils.logger import setup_logger

logger = setup_logger("Chunker")


@dataclass
class CodeChunk:
    """Represents a discrete semantic chunk of code or documentation."""

    chunk_id: str
    file_path: str
    language: str
    symbol_name: str
    symbol_type: str  # "function", "method", "class", "documentation", "config", "code_block"
    start_line: int
    end_line: int
    content: str
    content_hash: str
    timestamp: float = field(default_factory=time.time)
    parent_symbol: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    docstring: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeChunk":
        return cls(**data)


class CodeChunker:
    """
    Syntax-aware code and documentation chunker.
    Uses AST symbols for structured code and heading/paragraph chunking for text.
    """

    def __init__(self, max_chunk_lines: int = 80, overlap_lines: int = 10):
        self.parser = CodeParser()
        self.max_chunk_lines = max_chunk_lines
        self.overlap_lines = overlap_lines

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute SHA256 hex digest for a string."""
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def generate_chunk_id(self, file_path: str, start_line: int, end_line: int, content_hash: str) -> str:
        """Create a deterministic unique chunk ID."""
        key = f"{file_path}:{start_line}:{end_line}:{content_hash[:12]}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def chunk_file(self, file_path: str, root_dir: Optional[str] = None) -> List[CodeChunk]:
        """
        Divide a file into semantic chunks based on its extension and structure.

        Args:
            file_path: Absolute or relative path to the file.
            root_dir: Optional project root to compute relative paths.

        Returns:
            List of CodeChunk instances.
        """
        if not os.path.isfile(file_path):
            logger.warning(f"File not found: {file_path}")
            return []

        rel_path = os.path.relpath(file_path, root_dir).replace("\\", "/") if root_dir else file_path.replace("\\", "/")
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read '{file_path}': {e}")
            return []

        lines = content.splitlines()
        if not lines:
            return []

        if ext == ".py":
            return self._chunk_python(rel_path, lines, file_path)
        elif ext in (".md", ".markdown", ".rst", ".txt"):
            return self._chunk_markdown(rel_path, lines)
        elif ext in (".json", ".yaml", ".yml", ".toml", ".ini"):
            return self._chunk_config(rel_path, lines, ext)
        else:
            return self._chunk_generic(rel_path, lines, ext)

    def _chunk_python(self, rel_path: str, lines: List[str], abs_path: str) -> List[CodeChunk]:
        """Syntax-aware chunking for Python code using Tree-sitter AST symbols."""
        chunks: List[CodeChunk] = []
        symbols = self.parser.parse_file(abs_path)

        covered_lines = set()
        imports_lines = []

        # 1. Process symbols (classes, functions, methods, imports)
        for sym in symbols:
            if sym.kind == "import":
                imports_lines.extend(range(sym.start_line, sym.end_line + 1))
                continue

            # Extract source lines for symbol (1-indexed)
            s_idx = max(0, sym.start_line - 1)
            e_idx = min(len(lines), sym.end_line)
            chunk_lines = lines[s_idx:e_idx]
            chunk_content = "\n".join(chunk_lines).strip()
            if not chunk_content:
                continue

            # If it's a class with many lines, we preserve a summary header chunk
            # Individual methods will be separate chunks
            if sym.kind == "class" and (sym.end_line - sym.start_line) > 35:
                # Extract class header, docstring, and constructor if small
                header_lines = chunk_lines[: min(25, len(chunk_lines))]
                header_content = "\n".join(header_lines).strip()
                c_hash = self.compute_hash(header_content)
                cid = self.generate_chunk_id(rel_path, sym.start_line, sym.start_line + len(header_lines) - 1, c_hash)
                chunks.append(
                    CodeChunk(
                        chunk_id=cid,
                        file_path=rel_path,
                        language="python",
                        symbol_name=sym.name,
                        symbol_type="class",
                        start_line=sym.start_line,
                        end_line=sym.start_line + len(header_lines) - 1,
                        content=header_content,
                        content_hash=c_hash,
                        parent_symbol=sym.parent,
                        parameters=sym.parameters,
                        docstring=sym.docstring,
                    )
                )
                continue

            # Record covered lines for functions and methods
            for ln in range(sym.start_line, sym.end_line + 1):
                covered_lines.add(ln)

            qualified_name = f"{sym.parent}.{sym.name}" if sym.parent else sym.name
            c_hash = self.compute_hash(chunk_content)
            cid = self.generate_chunk_id(rel_path, sym.start_line, sym.end_line, c_hash)

            chunks.append(
                CodeChunk(
                    chunk_id=cid,
                    file_path=rel_path,
                    language="python",
                    symbol_name=qualified_name,
                    symbol_type=sym.kind,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    content=chunk_content,
                    content_hash=c_hash,
                    parent_symbol=sym.parent,
                    parameters=sym.parameters,
                    docstring=sym.docstring,
                )
            )

        # 2. Package imports block if non-empty
        if imports_lines:
            min_imp = min(imports_lines)
            max_imp = max(imports_lines)
            imp_slice = lines[min_imp - 1 : max_imp]
            imp_content = "\n".join(imp_slice).strip()
            if imp_content:
                c_hash = self.compute_hash(imp_content)
                cid = self.generate_chunk_id(rel_path, min_imp, max_imp, c_hash)
                chunks.insert(
                    0,
                    CodeChunk(
                        chunk_id=cid,
                        file_path=rel_path,
                        language="python",
                        symbol_name="<imports>",
                        symbol_type="import",
                        start_line=min_imp,
                        end_line=max_imp,
                        content=imp_content,
                        content_hash=c_hash,
                    ),
                )
                for ln in range(min_imp, max_imp + 1):
                    covered_lines.add(ln)

        # 3. Capture module-level code and top-level definitions not covered by classes or functions
        uncovered_spans: List[List[int]] = []
        current_span: List[int] = []
        for i in range(1, len(lines) + 1):
            if i not in covered_lines and lines[i - 1].strip():
                current_span.append(i)
            else:
                if current_span:
                    uncovered_spans.append(current_span)
                    current_span = []
        if current_span:
            uncovered_spans.append(current_span)

        for span in uncovered_spans:
            s_ln = span[0]
            e_ln = span[-1]
            mod_text = "\n".join(lines[s_ln - 1 : e_ln]).strip()
            if mod_text:
                c_hash = self.compute_hash(mod_text)
                cid = self.generate_chunk_id(rel_path, s_ln, e_ln, c_hash)
                chunks.append(
                    CodeChunk(
                        chunk_id=cid,
                        file_path=rel_path,
                        language="python",
                        symbol_name=f"{os.path.basename(rel_path)}:L{s_ln}-L{e_ln}",
                        symbol_type="module",
                        start_line=s_ln,
                        end_line=e_ln,
                        content=mod_text,
                        content_hash=c_hash,
                    )
                )

        # 4. If file has no chunks at all, chunk generic
        if not chunks:
            return self._chunk_generic(rel_path, lines, ".py")

        return chunks

    def _chunk_markdown(self, rel_path: str, lines: List[str]) -> List[CodeChunk]:
        """Heading-aware chunking for Markdown and documentation files."""
        chunks: List[CodeChunk] = []
        heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

        current_heading = os.path.basename(rel_path)
        current_lines: List[str] = []
        start_line = 1

        for i, line in enumerate(lines, start=1):
            match = heading_re.match(line.strip())
            if match:
                # Flush previous section if it has content
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        c_hash = self.compute_hash(text)
                        cid = self.generate_chunk_id(rel_path, start_line, i - 1, c_hash)
                        chunks.append(
                            CodeChunk(
                                chunk_id=cid,
                                file_path=rel_path,
                                language="markdown",
                                symbol_name=current_heading,
                                symbol_type="documentation",
                                start_line=start_line,
                                end_line=i - 1,
                                content=text,
                                content_hash=c_hash,
                            )
                        )
                current_heading = match.group(2).strip()
                current_lines = [line]
                start_line = i
            else:
                current_lines.append(line)
                # Split oversized documentation sections
                if len(current_lines) >= self.max_chunk_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        c_hash = self.compute_hash(text)
                        cid = self.generate_chunk_id(rel_path, start_line, i, c_hash)
                        chunks.append(
                            CodeChunk(
                                chunk_id=cid,
                                file_path=rel_path,
                                language="markdown",
                                symbol_name=current_heading,
                                symbol_type="documentation",
                                start_line=start_line,
                                end_line=i,
                                content=text,
                                content_hash=c_hash,
                            )
                        )
                    current_lines = []
                    start_line = i + 1

        # Flush remainder
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                c_hash = self.compute_hash(text)
                end_line = len(lines)
                cid = self.generate_chunk_id(rel_path, start_line, end_line, c_hash)
                chunks.append(
                    CodeChunk(
                        chunk_id=cid,
                        file_path=rel_path,
                        language="markdown",
                        symbol_name=current_heading,
                        symbol_type="documentation",
                        start_line=start_line,
                        end_line=end_line,
                        content=text,
                        content_hash=c_hash,
                    )
                )

        return chunks

    def _chunk_config(self, rel_path: str, lines: List[str], ext: str) -> List[CodeChunk]:
        """Chunk configuration files by logical blocks or line windows."""
        lang = ext.lstrip(".")
        return self._chunk_generic(rel_path, lines, lang, symbol_type="config")

    def _chunk_generic(
        self,
        rel_path: str,
        lines: List[str],
        lang: str,
        symbol_type: str = "code_block",
    ) -> List[CodeChunk]:
        """Sliding window chunking for generic or fallback files."""
        chunks: List[CodeChunk] = []
        total_lines = len(lines)
        if total_lines == 0:
            return []

        step = max(1, self.max_chunk_lines - self.overlap_lines)
        for i in range(0, total_lines, step):
            end_idx = min(i + self.max_chunk_lines, total_lines)
            chunk_lines = lines[i:end_idx]
            text = "\n".join(chunk_lines).strip()
            if not text:
                continue

            start_line = i + 1
            end_line = end_idx
            c_hash = self.compute_hash(text)
            cid = self.generate_chunk_id(rel_path, start_line, end_line, c_hash)

            chunks.append(
                CodeChunk(
                    chunk_id=cid,
                    file_path=rel_path,
                    language=lang,
                    symbol_name=f"{os.path.basename(rel_path)}:L{start_line}-L{end_line}",
                    symbol_type=symbol_type,
                    start_line=start_line,
                    end_line=end_line,
                    content=text,
                    content_hash=c_hash,
                )
            )
            if end_idx >= total_lines:
                break

        return chunks


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phase 5.2: Code & Document Chunking Verification")
    print("=" * 60)

    chunker = CodeChunker()

    # 1. Test Python Chunking on settings.py
    py_target = "assistant/config/settings.py"
    print(f"\n[*] Testing Python AST chunking on: {py_target}")
    py_chunks = chunker.chunk_file(py_target)
    print(f"  -> Generated {len(py_chunks)} chunks:")
    for ch in py_chunks:
        print(f"     [{ch.symbol_type.upper():<7}] {ch.symbol_name:<25} (L{ch.start_line}-{ch.end_line}, hash: {ch.content_hash[:8]}...)")

    # 2. Test Markdown Chunking on README.md
    md_target = "README.md"
    print(f"\n[*] Testing Markdown Heading chunking on: {md_target}")
    md_chunks = chunker.chunk_file(md_target)
    print(f"  -> Generated {len(md_chunks)} chunks:")
    for ch in md_chunks[:5]:
        print(f"     [{ch.symbol_type.upper():<13}] Section: '{ch.symbol_name}' (L{ch.start_line}-{ch.end_line})")

    assert len(py_chunks) > 0, "Python chunking produced zero chunks"
    assert len(md_chunks) > 0, "Markdown chunking produced zero chunks"
    print("\n[PASS] Sub-Phase 5.2 Verification Complete.")
