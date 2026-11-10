from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List


class PermissionLevel(str, Enum):
    """
    Permission tiers defined in Phase 4 Section 10:
    - READ_ONLY: Safe inspection (search, list, read, parse).
    - MODIFICATION: Changes project files (create, write, edit, delete).
    - SENSITIVE: Terminal execution, system commands, destructive actions.
    """
    READ_ONLY = "READ_ONLY"
    MODIFICATION = "MODIFICATION"
    SENSITIVE = "SENSITIVE"


@dataclass
class ToolParameter:
    """Defines a parameter accepted by a tool."""
    name: str
    type: str  # "string", "integer", "boolean", "list", "dict"
    description: str
    required: bool = True
    default: Optional[Any] = None


@dataclass
class ToolResult:
    """Standardized output returned by every tool."""
    success: bool
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }

    def __str__(self) -> str:
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool(ABC):
    """Abstract base class that all tools must implement."""

    name: str = ""
    description: str = ""
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    parameters: List[ToolParameter] = []

    def get_schema(self) -> Dict[str, Any]:
        """Returns the JSON-compatible schema for Qwen / LLM tool-calling."""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {
                "type": p.type,
                "description": p.description,
            }
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "permission_level": self.permission_level.value,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def validate_arguments(self, kwargs: Dict[str, Any]) -> Optional[str]:
        """Validates that all required parameters are provided."""
        for p in self.parameters:
            if p.required and p.name not in kwargs:
                return f"Missing required parameter: '{p.name}'"
        return None

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Executes the tool logic and returns a ToolResult."""
        pass