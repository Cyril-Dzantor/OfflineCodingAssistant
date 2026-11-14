from assistant.tools.base import BaseTool, ToolParameter, ToolResult, PermissionLevel
from assistant.tools.registry import ToolRegistry
from assistant.tools.repo_tools import SearchCodeTool, ListFilesTool, GetFileSymbolsTool
from assistant.tools.file_tools import ReadFileTool, CreateFileTool, EditFileTool, DeleteFileTool


def get_default_registry() -> ToolRegistry:
    """Creates a pre-configured registry with standard repository and file tools."""
    registry = ToolRegistry()
    # Repository tools
    registry.register(SearchCodeTool())
    registry.register(ListFilesTool())
    registry.register(GetFileSymbolsTool())
    # File tools
    registry.register(ReadFileTool())
    registry.register(CreateFileTool())
    registry.register(EditFileTool())
    registry.register(DeleteFileTool())
    return registry


__all__ = [
    "BaseTool",
    "ToolParameter",
    "ToolResult",
    "PermissionLevel",
    "ToolRegistry",
    "SearchCodeTool",
    "ListFilesTool",
    "GetFileSymbolsTool",
    "ReadFileTool",
    "CreateFileTool",
    "EditFileTool",
    "DeleteFileTool",
    "get_default_registry",
]

