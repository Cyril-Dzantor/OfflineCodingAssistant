import os
import subprocess
import shlex
from typing import Optional

from assistant.tools.base import BaseTool, ToolParameter, ToolResult, PermissionLevel
from assistant.repo.detector import RepositoryDetector
from assistant.tools.file_tools import _resolve_safe_path


class ExecuteCommandTool(BaseTool):
    name = "execute_command"
    description = "Executes a shell command locally within the project directory, capturing output, errors, and exit code."
    permission_level = PermissionLevel.SENSITIVE
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="The command string to execute (e.g. 'python tests/test_validation.py').",
            required=True,
        ),
        ToolParameter(
            name="cwd",
            type="string",
            description="Optional relative sub-directory to run the command in.",
            required=False,
            default="",
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds (default: 30).",
            required=False,
            default=30,
        ),
    ]

    # Explicitly blocked commands that could damage the operating system
    BLOCKED_PATTERNS = [
        "rmdir /s /q c:", "del /s /q c:", "format c:", "mkfs",
        ":(){ :|:& };:", "shutdown", "reboot", "poweroff"
    ]

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or RepositoryDetector().find_project_root()

    def _is_dangerous(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        return any(pattern in cmd_lower for pattern in self.BLOCKED_PATTERNS)

    def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "").strip()
        rel_cwd = kwargs.get("cwd", "") or ""
        timeout = kwargs.get("timeout") or 30

        if not command:
            return ToolResult(success=False, error="No command provided.")

        # 1. Security Check: Block destructive OS commands
        if self._is_dangerous(command):
            return ToolResult(
                success=False,
                error=f"Security Violation: Command '{command}' is recognized as potentially destructive and is blocked."
            )

        # 2. Working Directory Sandbox
        target_dir, err = _resolve_safe_path(self.root_dir, rel_cwd)
        if err:
            return ToolResult(success=False, error=err)
        if not os.path.isdir(target_dir):
            return ToolResult(success=False, error=f"Working directory does not exist: '{rel_cwd}'")

        # 3. Subprocess execution with timeout & output capture
        try:
            result = subprocess.run(
                command,
                cwd=target_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            exit_code = result.returncode

            return ToolResult(
                success=(exit_code == 0),
                output={
                    "command": command,
                    "cwd": rel_cwd or ".",
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                },
                error=stderr if exit_code != 0 and not stdout else None
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command execution timed out after {timeout} seconds."
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to execute command: {e}")


if __name__ == "__main__":
    from assistant.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(ExecuteCommandTool())

    print("\n--- Testing Blocked Destructive Command ---")
    bad_res = registry.execute("execute_command", command="format C: /y")
    print(f"Blocked: {not bad_res.success} -> {bad_res.error}")

    print("\n--- Testing Safe Command: Python version ---")
    py_res = registry.execute("execute_command", command="python --version")
    print(f"Success: {py_res.success}")
    print(f"Stdout:  {py_res.output['stdout']}")

    print("\n--- Testing Safe Command: Run Phase 3 Validation Suite ---")
    suite_res = registry.execute("execute_command", command="python tests/test_validation.py")
    print(f"Suite Exit Code: {suite_res.output['exit_code']}")
    if suite_res.success:
        print("Suite Summary:")
        # Print last 3 lines of output
        lines = suite_res.output['stdout'].splitlines()
        for line in lines[-4:]:
            print(f"  {line}")

    print("\n--- Testing Timeout Enforcement ---")
    # Ping or sleep to test timeout
    time_res = registry.execute("execute_command", command="powershell -Command Start-Sleep -Seconds 3", timeout=1)
    print(f"Timeout Triggered: {not time_res.success} -> {time_res.error}")