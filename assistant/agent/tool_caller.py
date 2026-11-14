import json
import re
from typing import Dict, Any, Optional, List, Tuple

from assistant.tools.registry import ToolRegistry
from assistant.tools.base import ToolResult
from assistant.utils.logger import app_logger


class ToolCallHandler:
    """
    Parses, validates, and manages model-driven tool execution loops.
    """

    def __init__(self, registry: ToolRegistry, max_iterations: int = 5):
        self.registry = registry
        self.max_iterations = max_iterations

    def format_tool_prompt(self) -> str:
        """Constructs system prompt instructions containing all registered tool schemas."""
        schemas = self.registry.get_schemas()
        schemas_json = json.dumps(schemas, indent=2)

        return (
            "\n### Available Tools\n"
            "You have access to the following local development tools:\n"
            f"```json\n{schemas_json}\n```\n\n"
            "### How to Use Tools\n"
            "If you need to search code, read files, edit files, or execute commands to satisfy the user request, "
            "respond with a tool call block using this exact format:\n\n"
            "```tool_call\n"
            '{"tool": "<tool_name>", "arguments": {<arguments>}}\n'
            "```\n\n"
            "Rules:\n"
            "1. Emit ONLY ONE tool call per response when an action is needed.\n"
            "2. When the tool result is returned to you, explain the result or make the next tool call.\n"
            "3. If no further tool is needed, respond directly to the user without a tool_call block.\n"
        )

    def extract_tool_call(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Extracts a tool name and arguments dictionary from model output.
        Handles both ```tool_call blocks and fallback JSON structures.
        """
        # 1. Match fenced ```tool_call ... ```
        fenced_match = re.search(r"```(?:tool_call|json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidate = fenced_match.group(1) if fenced_match else None

        # 2. Fallback: Search for any raw JSON containing "tool" and "arguments"
        if not candidate:
            raw_match = re.search(r'\{\s*"tool"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}', text, re.DOTALL)
            if raw_match:
                candidate = raw_match.group(0)

        if not candidate:
            return None

        try:
            data = json.loads(candidate)
            tool_name = data.get("tool")
            arguments = data.get("arguments", {})
            if tool_name and isinstance(arguments, dict):
                return tool_name, arguments
        except json.JSONDecodeError:
            app_logger.warning(f"Failed to parse JSON from candidate: {candidate}")

        return None

    def execute_call(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Validates and executes a parsed tool call against the registry."""
        app_logger.info(f"Agent dispatching tool: {tool_name} with {arguments}")
        return self.registry.execute(tool_name, **arguments)

    def format_tool_result_message(self, tool_name: str, result: ToolResult) -> str:
        """Formats a tool result as a follow-up user message for the model."""
        if result.success:
            content_str = json.dumps(result.output, indent=2) if isinstance(result.output, (dict, list)) else str(result.output)
            return f"[Tool Result for '{tool_name}'] (Status: Success):\n{content_str}"
        else:
            return f"[Tool Result for '{tool_name}'] (Status: Failed):\nError: {result.error}\nPlease correct your arguments or approach."


if __name__ == "__main__":
    from assistant.tools import get_default_registry

    registry = get_default_registry()
    handler = ToolCallHandler(registry)

    print("\n--- Test 1: Tool Prompt Generation ---")
    prompt = handler.format_tool_prompt()
    print(f"Generated prompt length: {len(prompt)} characters.")
    print(prompt[:350] + "...\n")

    print("--- Test 2: Parsing Fenced Tool Call ---")
    sample_model_output = (
        "I need to read the settings file to check the model path.\n"
        "```tool_call\n"
        '{"tool": "read_file", "arguments": {"path": "assistant/config/settings.py", "start_line": 1, "end_line": 6}}\n'
        "```"
    )
    parsed = handler.extract_tool_call(sample_model_output)
    print(f"Extracted: {parsed}")

    if parsed:
        tool_name, args = parsed
        res = handler.execute_call(tool_name, args)
        print(f"\n--- Test 3: Tool Execution & Result Message ---")
        msg = handler.format_tool_result_message(tool_name, res)
        print(msg)