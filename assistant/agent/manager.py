import re
import os 
from typing import Optional, List, Dict, Any

from assistant.core.model import ModelInterface
from assistant.core.conversation import ConversationManager
from assistant.repo.context import ContextBuilder
from assistant.agent.state import AgentState, AgentStatus, RequestType
from assistant.agent.planner import TaskPlanner, ExecutionPlan, TaskStatus
from assistant.agent.tool_caller import ToolCallHandler
from assistant.agent.control import ExecutionController
from assistant.tools import ToolRegistry, get_default_registry
from assistant.utils.logger import app_logger


class AgentManager:
    """
    Central orchestrator coordinating the user interface,
    the local model, repository context, task planning, and tool execution.
    """

    def __init__(
        self,
        model: Optional[ModelInterface] = None,
        conversation: Optional[ConversationManager] = None,
        context_builder: Optional[ContextBuilder] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.model = model
        self.conversation = conversation or ConversationManager()
        self.context_builder = context_builder or ContextBuilder()
        self.registry = registry or get_default_registry()
        
        # Sub-systems
        self.planner = TaskPlanner(model=self.model)
        self.tool_handler = ToolCallHandler(registry=self.registry)
        self.controller = ExecutionController(registry=self.registry)
        self.state: Optional[AgentState] = None

    def classify_request(self, user_input: str) -> RequestType:
        """
        Determines whether the request needs project interaction (ACTION)
        or is a pure informational query (CONVERSATION).
        """
        explanation_patterns = [
            r"\bexplain\b", r"\bwhere is\b", r"\bhow does\b",
            r"\bwhat is\b", r"\bwhich class\b", r"\bwhich file\b"
        ]
        for pattern in explanation_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return RequestType.CONVERSATION

        action_patterns = [
            r"\bcreate\b", r"\bwrite\b", r"\bmake\b", r"\bgenerate\b",
            r"\badd\b", r"\bmodify\b", r"\bedit\b", r"\bupdate\b",
            r"\bdelete\b", r"\bremove\b", r"\brefactor\b", r"\brun\b",
            r"\bexecute\b", r"\btest\b", r"\binstall\b", r"\bfix\b", r"\bchange\b"
        ]
        for pattern in action_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return RequestType.ACTION

        return RequestType.CONVERSATION

    def process_request(self, user_input: str) -> AgentState:
        """
        Main entry point: manages the lifecycle of a request from start to completion.
        """
        req_type = self.classify_request(user_input)
        self.state = AgentState(user_request=user_input, request_type=req_type)
        self.state.status = AgentStatus.ANALYZING

        if req_type == RequestType.CONVERSATION:
            return self._handle_conversation(user_input)
        else:
            return self._handle_action(user_input)

    def _handle_conversation(self, user_input: str) -> AgentState:
        """Handles informational Q&A and code explanation requests."""
        if not self.model:
            self.model = ModelInterface()

        repo_ctx = self.context_builder.build_context(user_input)
        prompt = f"{repo_ctx}\nUser Question: {user_input}" if repo_ctx else user_input

        self.conversation.add_user_message(prompt)
        messages = self.conversation.get_messages()

        response = ""
        for token in self.model.generate_stream(messages):
            response += token

        self.conversation.add_assistant_message(response)
        self.state.final_response = response
        self.state.status = AgentStatus.COMPLETED
        return self.state

    def _handle_action(self, user_input: str) -> AgentState:
        """
        Multi-step execution workflow:
        1. Breaks request into an ExecutionPlan.
        2. Iterates through tasks, prompting the model with available tools.
        3. Validates and executes tool calls with user approval.
        4. Verifies results and produces an execution summary.
        """
        if not self.model:
            self.model = ModelInterface()

        self.state.status = AgentStatus.PLANNING
        
        # 1. Create plan
        available_tool_names = [t.name for t in self.registry.list_tools()]
        plan: ExecutionPlan = self.planner.create_plan(user_input, available_tool_names)
        
        print("\n" + plan.format_plan() + "\n")

        self.state.status = AgentStatus.EXECUTING
        tool_system_prompt = self.tool_handler.format_tool_prompt()

        # 2. Execute plan steps
        for task in plan.tasks:
            task.status = TaskStatus.RUNNING
            print(f"[*] Executing Step {task.id}: {task.title}...")

            step_prompt = (
                f"Overall Goal: {user_input}\n"
                f"Current Step {task.id}: {task.title} ({task.description})\n"
                f"Suggested tool: {task.tool_hint or 'any'}\n"
                "Please call the required tool to perform this step."
            )

            messages = [
                {"role": "system", "content": tool_system_prompt},
                {"role": "user", "content": step_prompt},
            ]

            # Model tool execution loop (max 3 turns per step)
            for turn in range(3):
                model_response = "".join(list(self.model.generate_stream(messages)))
                tool_call = self.tool_handler.extract_tool_call(model_response)

                if not tool_call:
                    # Model produced prose without a tool call (finished step)
                    task.result = model_response.strip()
                    task.status = TaskStatus.COMPLETED
                    break

                tool_name, arguments = tool_call
                
                # Execute with permission and validation
                result = self.controller.controlled_execute(tool_name, arguments)
                self.state.record_action(tool_name, arguments, str(result.output), result.success, result.error)

                if result.success:
                    task.result = str(result.output)
                    task.status = TaskStatus.COMPLETED
                    print(f"  [+] Step {task.id} Succeeded.")
                    break
                else:
                    task.error = result.error
                    print(f"  [-] Step {task.id} Error: {result.error}")
                    # Feed error back to model for potential self-correction
                    feedback_msg = self.tool_handler.format_tool_result_message(tool_name, result)
                    messages.append({"role": "assistant", "content": model_response})
                    messages.append({"role": "user", "content": feedback_msg})

            if task.status != TaskStatus.COMPLETED:
                task.status = TaskStatus.FAILED
                app_logger.warning(f"Task step {task.id} failed: {task.error}")

        # 3. Final summary
        if plan.has_failed():
            self.state.status = AgentStatus.FAILED
        else:
            self.state.status = AgentStatus.COMPLETED

        self.state.final_response = (
            f"Execution finished.\n\n"
            f"{plan.format_plan()}\n\n"
            f"Actions Recorded: {len(self.state.actions_taken)}"
        )
        return self.state


if __name__ == "__main__":
    from assistant.tools import get_default_registry

    # Test the agent with auto-approved modifications in a controlled run
    agent = AgentManager()
    agent.controller.auto_approve_modifications = True

    print("\n========================================================")
    print("      Sub-Phase 4.8: Multi-Step Action Execution Test   ")
    print("========================================================\n")

    test_request = "Create a file called sample_math.py with an add function"
    state = agent.process_request(test_request)
    
    print("\n--- Final Agent Summary ---")
    print(state.final_response)

    # Clean up test artifact
    if os.path.exists("sample_math.py"):
        os.remove("sample_math.py")
        print("[*] Cleaned up temporary test file 'sample_math.py'.")