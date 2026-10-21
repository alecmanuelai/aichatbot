"""Short-lived connections: no SQLite connection crosses a thread boundary."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from config import PROJECT_DIR


class DatabaseManager:
    def __init__(self, path: Path = PROJECT_DIR / "data" / "studybuddy.db"):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)")

    @staticmethod
    def timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def create_conversation(self) -> str:
        conversation_id = str(uuid4())
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO conversations(id, title, created_at) VALUES (?, ?, ?)",
                (conversation_id, "New conversation", self.timestamp()),
            )
        return conversation_id

    def list_conversations(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM conversations ORDER BY created_at DESC, rowid DESC").fetchall()
            return [dict(row) for row in rows]

    def get_messages(self, conversation_id: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conversation_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_user_message(self, conversation_id: str, content: str) -> int:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            first_message = connection.execute(
                "SELECT 1 FROM messages WHERE conversation_id = ? LIMIT 1", (conversation_id,),
            ).fetchone() is None
            cursor = connection.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, "user", content, self.timestamp()),
            )
            if first_message:
                title = " ".join(content.split())
                title = title if len(title) <= 44 else title[:41] + "..."
                connection.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
            return cursor.lastrowid

    def add_assistant_reply(self, conversation_id: str, user_message_id: int, content: str) -> bool:
        with self.connection() as connection:
            # Lock before checking: deleted chats and already-answered retries are not recreated.
            connection.execute("BEGIN IMMEDIATE")
            last = connection.execute(
                "SELECT id, role FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if last is None or last["id"] != user_message_id or last["role"] != "user":
                return False
            connection.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, "assistant", content, self.timestamp()),
            )
            return True

    def delete_conversation(self, conversation_id: str) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
