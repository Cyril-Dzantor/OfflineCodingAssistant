# assistant/core/conversation.py

from assistant.prompts.templates import get_system_message

class ConversationManager:
    def __init__(self, max_messages: int = 20):
        """
        Manages the chat history. 
        max_messages ensures the context window doesn't grow infinitely and crash the GPU.
        """
        self.max_messages = max_messages
        self.messages = []
        self.clear() # Initialize with the system prompt

    def add_user_message(self, content: str):
        """Appends a user message to the history and prunes if necessary."""
        self.messages.append({"role": "user", "content": content})
        self._prune_history()

    def add_assistant_message(self, content: str):
        """Appends the model's response to the history."""
        self.messages.append({"role": "assistant", "content": content})
        self._prune_history()

    def get_messages(self) -> list:
        """Returns the full conversation history to be passed to the model."""
        return self.messages

    def clear(self):
        """Wipes the conversation history and re-inserts the System Prompt."""
        self.messages = [get_system_message()]

    def _prune_history(self):
        """
        Keeps the system prompt intact at index 0, but removes the oldest 
        messages if the total count exceeds max_messages.
        """
        if len(self.messages) > self.max_messages + 1:
            # Pop the oldest user/assistant message (index 1)
            self.messages.pop(1)
