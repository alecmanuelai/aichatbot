"""A small, readable interface between the UI and persistence."""

from database.database_manager import DatabaseManager


class ConversationService:
    def __init__(self, database: DatabaseManager):
        self.database = database

    def create(self) -> str:
        return self.database.create_conversation()

    def list_all(self) -> list[dict]:
        return self.database.list_conversations()

    def messages(self, conversation_id: str) -> list[dict]:
        return self.database.get_messages(conversation_id)

    def delete(self, conversation_id: str) -> None:
        self.database.delete_conversation(conversation_id)
