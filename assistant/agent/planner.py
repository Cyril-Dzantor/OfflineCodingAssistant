import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from assistant.core.model import ModelInterface


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TaskItem:
    id: int
    title: str
    description: str
    tool_hint: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tool_hint": self.tool_hint,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ExecutionPlan:
    goal: str
    tasks: List[TaskItem] = field(default_factory=list)
    current_index: int = 0

    def get_current_task(self) -> Optional[TaskItem]:
        if 0 <= self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None

    def advance(self, status: TaskStatus = TaskStatus.COMPLETED, result: Optional[str] = None, error: Optional[str] = None):
        """Marks the current task and advances the pointer to the next pending task."""
        current = self.get_current_task()
        if current:
            current.status = status
            current.result = result
            current.error = error
            self.current_index += 1

    def is_complete(self) -> bool:
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for t in self.tasks)

    def has_failed(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def format_plan(self) -> str:
        """Returns a formatted checklist view of the plan."""
        icons = {
            TaskStatus.PENDING: "[ ]",
            TaskStatus.RUNNING: "[>]",
            TaskStatus.AWAITING_APPROVAL: "[?]",
            TaskStatus.COMPLETED: "[x]",
            TaskStatus.FAILED: "[!]",
            TaskStatus.SKIPPED: "[-]",
        }
        lines = [f"Goal: {self.goal}\nPlan:"]
        for t in self.tasks:
            icon = icons.get(t.status, "[ ]")
            hint = f" ({t.tool_hint})" if t.tool_hint else ""
            lines.append(f"  {icon} {t.id}. {t.title}{hint}")
            if t.error:
                lines.append(f"      Error: {t.error}")
        return "\n".join(lines)


class TaskPlanner:
    """
    Deconstructs user objectives into ordered execution plans
    using structured prompt engineering and fallback heuristics.
    """

    def __init__(self, model: Optional[ModelInterface] = None):
        self.model = model

    def _build_planning_prompt(self, goal: str, available_tools: List[str]) -> List[Dict[str, str]]:
        tools_str = ", ".join(available_tools)
        system_instruction = (
            "You are a software engineering planner. Given a development objective, break it down "
            "into 2 to 5 concrete, sequential steps. For each step, suggest the best tool to use from: "
            f"[{tools_str}].\n"
            "Respond ONLY with a JSON array of objects with keys: 'id', 'title', 'description', and 'tool_hint'.\n"
            "Example format:\n"
            '[\n  {"id": 1, "title": "Create module", "description": "Write code to file", "tool_hint": "create_file"}\n]'
        )
        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Objective: {goal}"},
        ]

    def _parse_plan_json(self, raw_text: str, goal: str) -> Optional[ExecutionPlan]:
        """Extracts JSON array of tasks from the model's output."""
        try:
            # Look for JSON array brackets [...]
            match = re.search(r"\[\s*\{.*?\}\s*\]", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                tasks = []
                for item in data:
                    tasks.append(
                        TaskItem(
                            id=int(item.get("id", len(tasks) + 1)),
                            title=str(item.get("title", f"Step {len(tasks) + 1}")),
                            description=str(item.get("description", "")),
                            tool_hint=item.get("tool_hint"),
                        )
                    )
                if tasks:
                    return ExecutionPlan(goal=goal, tasks=tasks)
        except Exception:
            pass
        return None

    def _heuristic_fallback_plan(self, goal: str) -> ExecutionPlan:
        """Deterministic fallback if model output is not parseable."""
        tasks = []
        lower = goal.lower()

        if "create" in lower or "write" in lower or "add" in lower:
            tasks.append(TaskItem(id=1, title="Inspect target directory", description="Check existing files", tool_hint="list_files"))
            tasks.append(TaskItem(id=2, title="Create new file", description=f"Implement: {goal}", tool_hint="create_file"))
            tasks.append(TaskItem(id=3, title="Verify file created", description="Read back file to confirm contents", tool_hint="read_file"))
        elif "test" in lower or "run" in lower:
            tasks.append(TaskItem(id=1, title="Inspect test directory", description="Check tests", tool_hint="list_files"))
            tasks.append(TaskItem(id=2, title="Execute command", description=f"Run command for: {goal}", tool_hint="execute_command"))
        else:
            tasks.append(TaskItem(id=1, title="Locate relevant code", description="Search project", tool_hint="search_code"))
            tasks.append(TaskItem(id=2, title="Analyze code", description="Read file contents", tool_hint="read_file"))
            tasks.append(TaskItem(id=3, title="Apply changes", description=f"Fulfill: {goal}", tool_hint="edit_file"))

        return ExecutionPlan(goal=goal, tasks=tasks)

    def create_plan(self, goal: str, available_tools: Optional[List[str]] = None) -> ExecutionPlan:
        """
        Creates an ordered execution plan for a goal.
        Attempts model generation first; falls back to heuristic planner if needed.
        """
        tools = available_tools or ["search_code", "list_files", "read_file", "create_file", "edit_file", "execute_command"]

        if self.model:
            try:
                messages = self._build_planning_prompt(goal, tools)
                raw_response = "".join(list(self.model.generate_stream(messages)))
                plan = self._parse_plan_json(raw_response, goal)
                if plan:
                    return plan
            except Exception:
                pass

        # Fallback to deterministic structured planner
        return self._heuristic_fallback_plan(goal)


if __name__ == "__main__":
    planner = TaskPlanner()  # Test deterministic heuristic flow first

    print("\n--- Test 1: Plan for creating a calculator module ---")
    plan1 = planner.create_plan("Create a calculator.py module with add and subtract functions")
    print(plan1.format_plan())

    print("\n--- Test 2: Plan for running tests ---")
    plan2 = planner.create_plan("Run the unit test suite")
    print(plan2.format_plan())

    print("\n--- Test 3: Plan Lifecycle Tracking ---")
    plan1.advance(status=TaskStatus.COMPLETED, result="Found target folder")
    plan1.get_current_task().status = TaskStatus.RUNNING
    print(plan1.format_plan())