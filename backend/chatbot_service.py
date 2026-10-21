"""Validate input, save it once, and safely attach a reply to its original chat."""

from threading import Event

from backend.ai_service import AIService, AIServiceError
from config import MAX_MESSAGE_LENGTH
from database.database_manager import DatabaseManager


class InputValidationError(ValueError):
    pass


class ChatbotService:
    def __init__(self, database: DatabaseManager, ai: AIService):
        self.database = database
        self.ai = ai

    @staticmethod
    def validate_message(content: str) -> str:
        if not isinstance(content, str) or not content.strip():
            raise InputValidationError("Type a message before sending.")
        content = content.strip()
        if len(content) > MAX_MESSAGE_LENGTH:
            raise InputValidationError(f"Keep your message to {MAX_MESSAGE_LENGTH:,} characters or fewer.")
        return content

    def submit_user_message(self, conversation_id: str, content: str) -> int:
        content = self.validate_message(content)
        return self.database.add_user_message(conversation_id, content)

    def complete_reply(self, conversation_id: str, user_message_id: int, cancelled: Event) -> bool:
        if cancelled.is_set():
            return False
        messages = self.database.get_messages(conversation_id)
        if not messages or messages[-1]["id"] != user_message_id or messages[-1]["role"] != "user":
            raise AIServiceError("That message is no longer awaiting a reply. Open the conversation again.")
        reply = self.ai.reply(messages)
        if cancelled.is_set():
            return False
        return self.database.add_assistant_reply(conversation_id, user_message_id, reply)
