from typing import Dict, Any, Optional, List

from assistant.tools.base import BaseTool, ToolResult
from assistant.utils.logger import app_logger


class ToolRegistry:
    """
    Central registry for managing, validating, and executing tools.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Registers a tool instance by its unique name."""
        if not tool.name:
            raise ValueError("Tool name cannot be empty.")
        self._tools[tool.name] = tool
        app_logger.info(f"Registered tool: '{tool.name}' [{tool.permission_level.value}]")

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieves a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """Returns a list of all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Returns the JSON-compatible schemas of all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Validates arguments and executes the requested tool safely.
        Catches unexpected exceptions to prevent agent crashes.
        """
        tool = self.get(name)
        if not tool:
            available = list(self._tools.keys())
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found. Available tools: {available}",
            )

        # 1. Argument validation
        validation_error = tool.validate_arguments(kwargs)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        # 2. Execution with error containment
        try:
            app_logger.info(f"Executing tool '{name}' with arguments: {kwargs}")
            result = tool.execute(**kwargs)
            return result
        except Exception as e:
            app_logger.error(f"Error executing tool '{name}': {e}")
            return ToolResult(success=False, error=str(e))