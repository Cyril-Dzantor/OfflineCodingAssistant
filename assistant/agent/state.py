import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class AgentStatus(str, Enum):
    """The lifecycle states of an agent execution."""
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RequestType(str, Enum):
    """Classifies what kind of task the user is asking for."""
    CONVERSATION = "CONVERSATION"  # Q&A, explanations, general chat
    ACTION = "ACTION"              # Creating files, editing code, terminal commands


@dataclass
class ActionRecord:
    """Records the execution of a single tool action."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentState:
    """Tracks the state and action history for a single user turn."""
    user_request: str
    request_type: RequestType = RequestType.CONVERSATION
    status: AgentStatus = AgentStatus.IDLE
    actions_taken: List[ActionRecord] = field(default_factory=list)
    final_response: Optional[str] = None
    error_message: Optional[str] = None

    def record_action(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: str,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """Appends a completed action to the history."""
        self.actions_taken.append(
            ActionRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                success=success,
                error=error,
            )
        )

    def get_summary(self) -> str:
        """Returns a human-readable execution summary."""
        lines = [
            f"Request: {self.user_request}",
            f"Type:    {self.request_type.value}",
            f"Status:  {self.status.value}",
            f"Actions: {len(self.actions_taken)} executed",
        ]
        for idx, act in enumerate(self.actions_taken, 1):
            status_str = "SUCCESS" if act.success else "FAILED"
            lines.append(f"  {idx}. [{status_str}] {act.tool_name}({act.arguments})")
        return "\n".join(lines)