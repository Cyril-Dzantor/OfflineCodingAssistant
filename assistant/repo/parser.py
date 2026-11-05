import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import tree_sitter
import tree_sitter_python


@dataclass
class Symbol:
    name: str
    kind: str  # "class", "function", "method", "import"
    file_path: str
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed
    parent: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    docstring: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent": self.parent,
            "parameters": self.parameters,
            "docstring": self.docstring,
        }


class TreeSitterPythonParser:
    def __init__(self):
        self.language = tree_sitter.Language(tree_sitter_python.language())
        self.parser = tree_sitter.Parser(self.language)

    def parse(self, file_path: str, code_bytes: bytes) -> List[Symbol]:
        tree = self.parser.parse(code_bytes)
        symbols: List[Symbol] = []
        self._traverse(tree.root_node, file_path, symbols, current_class=None)
        return symbols

    def _extract_docstring(self, body_node: Optional[tree_sitter.Node]) -> Optional[str]:
        if not body_node:
            return None
        # In Python grammar, docstring is typically an expression_statement containing a string
        for child in body_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        raw_text = sub.text.decode("utf-8", errors="ignore").strip()
                        # Strip standard quotes
                        for quote in ('"""', "'''", '"', "'"):
                            if raw_text.startswith(quote) and raw_text.endswith(quote):
                                return raw_text[len(quote):-len(quote)].strip()
                        return raw_text
                break
        return None

    def _extract_parameters(self, params_node: Optional[tree_sitter.Node]) -> List[str]:
        if not params_node:
            return []
        params = []
        for child in params_node.children:
            # Skip punctuation tokens like '(', ')', ','
            if child.type not in ("(", ")", ","):
                param_text = child.text.decode("utf-8", errors="ignore").strip()
                if param_text:
                    params.append(param_text)
        return params

    def _traverse(
        self,
        node: tree_sitter.Node,
        file_path: str,
        symbols: List[Symbol],
        current_class: Optional[str] = None,
    ):
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = name_node.text.decode("utf-8") if name_node else "AnonymousClass"
            body_node = node.child_by_field_name("body")
            docstring = self._extract_docstring(body_node)

            symbols.append(
                Symbol(
                    name=class_name,
                    kind="class",
                    file_path=file_path,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                    parent=current_class,
                    docstring=docstring,
                )
            )

            # Recurse children with this class as parent
            for child in node.children:
                if child.type == "block" or child == body_node:
                    for body_child in child.children:
                        self._traverse(body_child, file_path, symbols, current_class=class_name)
                else:
                    self._traverse(child, file_path, symbols, current_class=class_name)
            return

        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            func_name = name_node.text.decode("utf-8") if name_node else "anonymous"
            params_node = node.child_by_field_name("parameters")
            body_node = node.child_by_field_name("body")
            
            docstring = self._extract_docstring(body_node)
            parameters = self._extract_parameters(params_node)
            kind = "method" if current_class else "function"

            symbols.append(
                Symbol(
                    name=func_name,
                    kind=kind,
                    file_path=file_path,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                    parent=current_class,
                    parameters=parameters,
                    docstring=docstring,
                )
            )

            # Recurse inside the function (for nested functions)
            for child in node.children:
                self._traverse(child, file_path, symbols, current_class=current_class)
            return

        elif node.type in ("import_statement", "import_from_statement"):
            import_text = node.text.decode("utf-8", errors="ignore").strip()
            symbols.append(
                Symbol(
                    name=import_text,
                    kind="import",
                    file_path=file_path,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                    parent=current_class,
                )
            )
            return

        # Default recursive traversal for other container nodes
        for child in node.children:
            self._traverse(child, file_path, symbols, current_class=current_class)


class CodeParser:
    """Multi-language parser dispatcher."""

    def __init__(self):
        self._parsers = {
            ".py": TreeSitterPythonParser(),
        }

    def parse_file(self, file_path: str) -> List[Symbol]:
        """Parses a single file and extracts its symbols."""
        if not os.path.exists(file_path):
            return []

        _, ext = os.path.splitext(file_path)
        parser = self._parsers.get(ext.lower())
        if not parser:
            return []

        try:
            with open(file_path, "rb") as f:
                code_bytes = f.read()
            return parser.parse(file_path, code_bytes)
        except Exception:
            return []

    def parse_files(self, file_paths: List[str]) -> Dict[str, List[Symbol]]:
        """Parses multiple files into a mapping of file_path -> symbols."""
        return {path: self.parse_file(path) for path in file_paths}


if __name__ == "__main__":
    import sys

    parser = CodeParser()
    target_file = sys.argv[1] if len(sys.argv) > 1 else "assistant/repo/detector.py"

    print(f"\n🔍 Parsing: {target_file}")
    symbols = parser.parse_file(target_file)
    print(f"Discovered {len(symbols)} symbols:\n")

    for s in symbols:
        parent_str = f" [Class: {s.parent}]" if s.parent else ""
        params_str = f"({', '.join(s.parameters)})" if s.parameters else "()"
        doc_str = f"\n      Doc: {s.docstring.splitlines()[0]}" if s.docstring else ""

        print(f"  • [{s.kind.upper():<6}] Lines {s.start_line:>2}-{s.end_line:<2} : {s.name}{params_str}{parent_str}{doc_str}")
    print()