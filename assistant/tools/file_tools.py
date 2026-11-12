import os
import difflib
from typing import Optional, Tuple

from assistant.tools.base import BaseTool, ToolParameter, ToolResult, PermissionLevel
from assistant.repo.detector import RepositoryDetector


def _resolve_safe_path(root_dir: str, rel_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Prevents path traversal attacks by ensuring the target path
    resolves strictly within the project root directory.
    """
    abs_root = os.path.abspath(root_dir)
    target = os.path.abspath(os.path.join(abs_root, rel_path))

    # Check that target starts with root path
    try:
        common = os.path.commonpath([abs_root, target])
        if common != abs_root:
            return None, f"Security Violation: Path '{rel_path}' escapes project root."
    except ValueError:
        return None, f"Security Violation: Path is on a different drive."

    return target, None


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Reads the content of a project file, with optional line range."
    permission_level = PermissionLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Relative path of the file to read.",
            required=True,
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="Optional 1-indexed starting line.",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="Optional 1-indexed ending line.",
            required=False,
            default=None,
        ),
    ]

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or RepositoryDetector().find_project_root()

    def execute(self, **kwargs) -> ToolResult:
        rel_path = kwargs.get("path", "")
        target, err = _resolve_safe_path(self.root_dir, rel_path)
        if err:
            return ToolResult(success=False, error=err)

        if not os.path.exists(target):
            return ToolResult(success=False, error=f"File not found: '{rel_path}'")
        if not os.path.isfile(target):
            return ToolResult(success=False, error=f"Path is not a regular file: '{rel_path}'")

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            start = max(1, kwargs.get("start_line") or 1)
            end = kwargs.get("end_line")
            if end is not None:
                end = min(len(lines), end)
                selected = lines[start - 1 : end]
            else:
                selected = lines[start - 1 :]

            content = "".join(selected)
            return ToolResult(
                success=True,
                output={
                    "path": rel_path,
                    "total_lines": len(lines),
                    "start_line": start,
                    "end_line": end or len(lines),
                    "content": content,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read file: {e}")


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Creates a new file in the project with the specified content."
    permission_level = PermissionLevel.MODIFICATION
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Relative path of the file to create.",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Text content to write into the file.",
            required=True,
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Whether to overwrite if file already exists.",
            required=False,
            default=False,
        ),
    ]

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or RepositoryDetector().find_project_root()

    def execute(self, **kwargs) -> ToolResult:
        rel_path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        overwrite = kwargs.get("overwrite", False)

        target, err = _resolve_safe_path(self.root_dir, rel_path)
        if err:
            return ToolResult(success=False, error=err)

        if os.path.exists(target) and not overwrite:
            return ToolResult(
                success=False,
                error=f"File '{rel_path}' already exists. Use overwrite=True to replace it.",
            )

        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            # Verification: Confirm file exists and has content
            if not os.path.exists(target):
                return ToolResult(success=False, error="Verification failed: file was not created.")

            return ToolResult(
                success=True,
                output=f"Successfully created '{rel_path}' ({len(content)} characters written).",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create file: {e}")


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Performs exact string replacement in a file and returns a unified diff."
    permission_level = PermissionLevel.MODIFICATION
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Relative path of the file to edit.",
            required=True,
        ),
        ToolParameter(
            name="old_str",
            type="string",
            description="Exact text snippet to find and replace.",
            required=True,
        ),
        ToolParameter(
            name="new_str",
            type="string",
            description="Replacement text.",
            required=True,
        ),
    ]

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or RepositoryDetector().find_project_root()

    def execute(self, **kwargs) -> ToolResult:
        rel_path = kwargs.get("path", "")
        old_str = kwargs.get("old_str", "")
        new_str = kwargs.get("new_str", "")

        target, err = _resolve_safe_path(self.root_dir, rel_path)
        if err:
            return ToolResult(success=False, error=err)

        if not os.path.exists(target):
            return ToolResult(success=False, error=f"File not found: '{rel_path}'")

        try:
            with open(target, "r", encoding="utf-8") as f:
                original = f.read()

            if old_str not in original:
                return ToolResult(
                    success=False,
                    error=f"Target snippet not found in '{rel_path}'. Verify whitespace and line numbers.",
                )

            count = original.count(old_str)
            if count > 1:
                return ToolResult(
                    success=False,
                    error=f"Target snippet occurs {count} times in '{rel_path}'. Provide more surrounding context.",
                )

            # Apply replacement
            updated = original.replace(old_str, new_str, 1)

            # Generate unified diff for verification
            orig_lines = original.splitlines(keepends=True)
            upd_lines = updated.splitlines(keepends=True)
            diff = "".join(
                difflib.unified_diff(orig_lines, upd_lines, fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}")
            )

            # Write updated content
            with open(target, "w", encoding="utf-8") as f:
                f.write(updated)

            return ToolResult(
                success=True,
                output={
                    "path": rel_path,
                    "diff": diff,
                    "message": f"Successfully updated '{rel_path}'.",
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to edit file: {e}")


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Safely deletes a file after saving a recoverable backup (.bak)."
    permission_level = PermissionLevel.SENSITIVE
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Relative path of the file to delete.",
            required=True,
        )
    ]

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or RepositoryDetector().find_project_root()

    def execute(self, **kwargs) -> ToolResult:
        rel_path = kwargs.get("path", "")
        target, err = _resolve_safe_path(self.root_dir, rel_path)
        if err:
            return ToolResult(success=False, error=err)

        if not os.path.exists(target):
            return ToolResult(success=False, error=f"File not found: '{rel_path}'")

        try:
            # Create a backup before deleting
            backup_path = target + ".bak"
            with open(target, "rb") as src, open(backup_path, "wb") as dst:
                dst.write(src.read())

            os.remove(target)
            return ToolResult(
                success=True,
                output=f"File '{rel_path}' deleted. Backup saved to '{rel_path}.bak'.",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to delete file: {e}")


if __name__ == "__main__":
    from assistant.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(CreateFileTool())
    registry.register(EditFileTool())
    registry.register(DeleteFileTool())

    print("\n--- Testing Sandbox Path Security ---")
    bad_res = registry.execute("read_file", path="../../Windows/System32/drivers/etc/hosts")
    print(f"Path Traversal Blocked: {not bad_res.success} -> {bad_res.error}")

    print("\n--- Testing Read File ---")
    read_res = registry.execute("read_file", path="assistant/config/settings.py", start_line=1, end_line=10)
    print(f"Read Success: {read_res.success}")
    if read_res.success:
        print(f"Lines read:\n{read_res.output['content']}")

    print("\n--- Testing Create & Edit & Delete Cycle ---")
    test_path = "scratch_test_file.txt"
    c_res = registry.execute("create_file", path=test_path, content="Hello World\nLine 2\n")
    print(f"Create: {c_res}")

    e_res = registry.execute("edit_file", path=test_path, old_str="Line 2", new_str="Line Two (Updated)")
    print(f"Edit Success: {e_res.success}")
    if e_res.success:
        print(f"Diff:\n{e_res.output['diff']}")

    d_res = registry.execute("delete_file", path=test_path)
    print(f"Delete: {d_res}")