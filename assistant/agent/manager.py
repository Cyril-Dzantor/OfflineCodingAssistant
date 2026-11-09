import re
from typing import Optional

from assistant.core.model import ModelInterface
from assistant.core.conversation import ConversationManager
from assistant.repo.context import ContextBuilder
from assistant.agent.state import AgentState, AgentStatus, RequestType


class AgentManager:
    """
    Central orchestrator coordinating the user interface,
    the local model, repository context, and execution tools.
    """

    def __init__(
        self,
        model: Optional[ModelInterface] = None,
        conversation: Optional[ConversationManager] = None,
        context_builder: Optional[ContextBuilder] = None,
    ):
        self.model = model
        self.conversation = conversation or ConversationManager()
        self.context_builder = context_builder or ContextBuilder()
        self.state: Optional[AgentState] = None

    def classify_request(self, user_input: str) -> RequestType:
        """
        Determines whether the request needs project interaction (ACTION)
        or is a pure informational query (CONVERSATION).
        """
        # Keywords that indicate pure Q&A / explanations
        explanation_patterns = [
            r"\bexplain\b", r"\bwhere is\b", r"\bhow does\b",
            r"\bwhat is\b", r"\bwhich class\b", r"\bwhich file\b"
        ]
        for pattern in explanation_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return RequestType.CONVERSATION

        # Keywords that indicate development action
        action_patterns = [
            r"\bcreate\b", r"\bwrite\b", r"\bmake\b", r"\bgenerate\b",
            r"\badd\b", r"\bmodify\b", r"\bedit\b", r"\bupdate\b",
            r"\bdelete\b", r"\bremove\b", r"\brefactor\b", r"\brun\b",
            r"\bexecute\b", r"\btest\b", r"\binstall\b", r"\bfix\b"
        ]
        for pattern in action_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return RequestType.ACTION

        return RequestType.CONVERSATION

    def process_request(self, user_input: str) -> AgentState:
        """
        Executes the agent lifecycle for a user request.
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
        Placeholder for action workflow.
        Will be connected to ToolDispatcher in Sub-Phase 4.2.
        """
        self.state.status = AgentStatus.PLANNING
        self.state.final_response = (
            f"[Agent Action Detected]: '{user_input}'\n"
            f"Action workflow will be dispatched to tools in Sub-Phase 4.2."
        )
        self.state.status = AgentStatus.COMPLETED
        return self.state


if __name__ == "__main__":
    # Test harness for classification and lifecycle tracking
    agent = AgentManager()

    test_queries = [
        "Where is project root detection implemented?",
        "Create a calculator.py file with add and subtract functions.",
        "Explain how the API handles authentication.",
        "Run the unit tests for this project.",
        "What is the difference between a list and a tuple in Python?",
        "Modify the login function to validate password length.",
    ]

    print("\n========================================================")
    print("      Sub-Phase 4.1: Agent Request Classification       ")
    print("========================================================\n")

    for q in test_queries:
        classification = agent.classify_request(q)
        print(f"Query:  \"{q}\"")
        print(f"Result: [{classification.value}]\n")