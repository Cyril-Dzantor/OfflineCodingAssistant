from assistant.tools.base import BaseTool, ToolParameter, ToolResult, PermissionLevel
from assistant.tools.registry import ToolRegistry
from assistant.tools.repo_tools import SearchCodeTool, ListFilesTool, GetFileSymbolsTool


def get_default_registry() -> ToolRegistry:
    """Creates a pre-configured registry with standard repository tools."""
    registry = ToolRegistry()
    registry.register(SearchCodeTool())
    registry.register(ListFilesTool())
    registry.register(GetFileSymbolsTool())
    return registry


__all__ = [
    "BaseTool",
    "ToolParameter",
    "ToolResult",
    "PermissionLevel",
    "ToolRegistry",
    "get_default_registry",
]

