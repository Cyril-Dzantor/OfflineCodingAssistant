import os
from typing import Optional

from assistant.tools.base import BaseTool, ToolParameter, ToolResult, PermissionLevel
from assistant.repo.scanner import ProjectScanner
from assistant.repo.search import SearchEngine
from assistant.repo.parser import CodeParser


class SearchCodeTool(BaseTool):
    name = "search_code"
    description = "Searches project files for a keyword or regex pattern."
    permission_level = PermissionLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="The keyword or pattern to search for.",
            required=True,
        ),
        ToolParameter(
            name="is_regex",
            type="boolean",
            description="Whether the query is a regular expression.",
            required=False,
            default=False,
        ),
    ]

    def __init__(self, scanner: Optional[ProjectScanner] = None):
        self.scanner = scanner or ProjectScanner()
        self.search_engine = SearchEngine(self.scanner)

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        is_regex = kwargs.get("is_regex", False)
        hits = self.search_engine.search(query, is_regex=is_regex)

        formatted = []
        for h in hits[:15]:
            rel_path = os.path.relpath(h["file"], self.scanner.root_dir)
            formatted.append({"file": rel_path, "line": h["line_num"], "content": h["content"]})

        return ToolResult(success=True, output=formatted)


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "Lists all indexed project files in the repository."
    permission_level = PermissionLevel.READ_ONLY
    parameters = []

    def __init__(self, scanner: Optional[ProjectScanner] = None):
        self.scanner = scanner or ProjectScanner()

    def execute(self, **kwargs) -> ToolResult:
        files = self.scanner.get_all_files()
        rel_files = [os.path.relpath(f, self.scanner.root_dir) for f in files]
        return ToolResult(success=True, output=rel_files)


class GetFileSymbolsTool(BaseTool):
    name = "get_file_symbols"
    description = "Parses a file and returns its structural symbols (classes, functions, methods, imports)."
    permission_level = PermissionLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Relative or absolute path to the file to parse.",
            required=True,
        )
    ]

    def __init__(self, scanner: Optional[ProjectScanner] = None):
        self.scanner = scanner or ProjectScanner()
        self.parser = CodeParser()

    def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.scanner.root_dir, file_path)

        if not os.path.exists(file_path):
            return ToolResult(success=False, error=f"File not found: '{file_path}'")

        symbols = self.parser.parse_file(file_path)
        return ToolResult(success=True, output=[s.to_dict() for s in symbols])


if __name__ == "__main__":
    from assistant.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(SearchCodeTool())
    registry.register(ListFilesTool())
    registry.register(GetFileSymbolsTool())

    print("\n--- Registered Tools Schemas ---")
    for schema in registry.get_schemas():
        print(f"Tool: {schema['name']} [{schema['permission_level']}] - {schema['description']}")

    print("\n--- Testing 'search_code' Execution ---")
    res = registry.execute("search_code", query="ProjectScanner")
    print(f"Success: {res.success}")
    print(f"Found {len(res.output)} matches.")