import os
from typing import Dict, Any, Optional, Callable

from assistant.tools.base import BaseTool, ToolResult, PermissionLevel
from assistant.tools.registry import ToolRegistry
from assistant.utils.logger import app_logger


class ExecutionController:
    """
    Enforces user approvals, permissions, and validates post-execution results.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        approval_callback: Optional[Callable[[BaseTool, Dict[str, Any]], bool]] = None,
        auto_approve_modifications: bool = False,
    ):
        self.registry = registry
        self.approval_callback = approval_callback or self._default_cli_approval
        self.auto_approve_modifications = auto_approve_modifications
        self.previous_calls = set()

    def _default_cli_approval(self, tool: BaseTool, arguments: Dict[str, Any]) -> bool:
        """Prompts the user via CLI for approval."""
        print(f"\n[APPROVAL REQUIRED] The agent wants to execute:")
        print(f"  Tool:       {tool.name} [{tool.permission_level.value}]")
        print(f"  Arguments:  {arguments}")
        
        try:
            choice = input("Approve this action? (y/n) [default: y]: ").strip().lower()
            return choice in ("", "y", "yes")
        except (KeyboardInterrupt, EOFError):
            print("\nAction cancelled.")
            return False

    def request_permission(self, tool: BaseTool, arguments: Dict[str, Any]) -> bool:
        """Determines if the action can proceed based on permission level."""
        # 1. READ_ONLY actions always pass
        if tool.permission_level == PermissionLevel.READ_ONLY:
            return True

        # 2. MODIFICATION actions pass if auto-approve is enabled
        if tool.permission_level == PermissionLevel.MODIFICATION and self.auto_approve_modifications:
            return True

        # 3. Otherwise, prompt user for confirmation
        return self.approval_callback(tool, arguments)

    def validate_result(self, tool_name: str, arguments: Dict[str, Any], result: ToolResult) -> ToolResult:
        """Performs sanity verification on the tool result."""
        if not result.success:
            return result

        # Validate file creation
        if tool_name == "create_file":
            path = arguments.get("path", "")
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                return ToolResult(success=False, error=f"Post-execution verification failed: '{path}' was not written.")

        # Validate file editing
        elif tool_name == "edit_file":
            diff = result.output.get("diff", "") if isinstance(result.output, dict) else ""
            if not diff.strip():
                return ToolResult(success=False, error="Post-execution verification failed: No diff produced.")

        # Validate command execution
        elif tool_name == "execute_command":
            exit_code = result.output.get("exit_code", 1) if isinstance(result.output, dict) else 1
            if exit_code != 0:
                stderr = result.output.get("stderr", "") if isinstance(result.output, dict) else ""
                return ToolResult(success=False, error=f"Command failed with exit code {exit_code}: {stderr}")

        return result

    def controlled_execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Executes a tool with permission checks, loop protection, and result validation.
        """
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: '{tool_name}'")

        # 1. Prevent exact duplicate loops
        call_signature = (tool_name, frozenset(arguments.items()))
        if call_signature in self.previous_calls:
            app_logger.warning(f"Repeated identical tool call detected: {tool_name}")
            return ToolResult(
                success=False,
                error=f"Duplicate action rejected: '{tool_name}' was already executed with identical arguments."
            )

        # 2. Check permission
        approved = self.request_permission(tool, arguments)
        if not approved:
            app_logger.info(f"User rejected tool execution: {tool_name}")
            return ToolResult(success=False, error=f"Action '{tool_name}' was denied by user approval.")

        # 3. Execute tool
        result = self.registry.execute(tool_name, **arguments)
        self.previous_calls.add(call_signature)

        # 4. Validate output
        validated_result = self.validate_result(tool_name, arguments, result)
        return validated_result


if __name__ == "__main__":
    from assistant.tools import get_default_registry

    registry = get_default_registry()

    print("\n--- Test 1: Automatic Approval for READ_ONLY ---")
    controller = ExecutionController(registry)
    res1 = controller.controlled_execute("list_files", {})
    print(f"Read-only executed without prompt: {res1.success} (Files: {len(res1.output)})\n")

    print("--- Test 2: Simulated Denial of SENSITIVE Action ---")
    denying_controller = ExecutionController(
        registry,
        approval_callback=lambda tool, args: False  # Simulates user typing 'n'
    )
    res2 = denying_controller.controlled_execute("execute_command", {"command": "git status"})
    print(f"Sensitive action blocked: {not res2.success}")
    print(f"Message: {res2.error}\n")

    print("--- Test 3: Duplicate Call Prevention ---")
    res3_first = controller.controlled_execute("search_code", {"query": "settings"})
    res3_second = controller.controlled_execute("search_code", {"query": "settings"})
    print(f"First call:  Success={res3_first.success}")
    print(f"Second call: Blocked as duplicate={not res3_second.success} -> {res3_second.error}")