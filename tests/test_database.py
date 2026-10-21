from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

from backend.conversation_service import ConversationService
from database.database_manager import DatabaseManager


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested" / "test.db"
        self.db = DatabaseManager(self.path)
        self.service = ConversationService(self.db)
        self.cid = self.service.create()

    def test_tables_and_uuid(self):
        self.assertEqual(str(UUID(self.cid)), self.cid)
        with self.db.connection() as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"conversations", "messages"}.issubset(tables))

    def test_round_trip_title_order_and_parameterized_content(self):
        first = self.db.add_user_message(self.cid, "What's SQL? '); DROP TABLE messages; --")
        self.assertTrue(self.db.add_assistant_reply(self.cid, first, "A query language."))
        second = self.db.add_user_message(self.cid, "And SQLite?")
        messages = self.service.messages(self.cid)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "user"])
        self.assertEqual(messages[0]["content"], "What's SQL? '); DROP TABLE messages; --")
        self.assertEqual(messages[-1]["id"], second)
        self.assertEqual(self.service.list_all()[0]["title"], messages[0]["content"])
        self.assertTrue(all(m["created_at"].endswith("+00:00") for m in messages))

    def test_long_title_is_compact_and_only_first_message_sets_it(self):
        self.db.add_user_message(self.cid, "Long title " * 20)
        title = self.service.list_all()[0]["title"]
        self.assertEqual(len(title), 44)
        self.db.add_user_message(self.cid, "Another title")
        self.assertEqual(self.service.list_all()[0]["title"], title)

    def test_foreign_keys_on_every_connection_and_cascade(self):
        self.db.add_user_message(self.cid, "Hello")
        for _ in range(2):
            with self.db.connection() as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_user_message("missing-conversation", "Must fail")
        self.service.delete(self.cid)
        self.assertEqual(self.service.messages(self.cid), [])
        self.assertEqual(self.service.list_all(), [])

    def test_persistence_after_reopening(self):
        message_id = self.db.add_user_message(self.cid, "Remember this")
        reopened = DatabaseManager(self.path)
        self.assertEqual(reopened.get_messages(self.cid)[0]["id"], message_id)
        self.assertEqual(reopened.list_conversations()[0]["title"], "Remember this")

    def test_transaction_rolls_back_and_connection_closes(self):
        with self.assertRaises(RuntimeError):
            with self.db.connection() as conn:
                conn.execute("UPDATE conversations SET title = ? WHERE id = ?", ("Should roll back", self.cid))
                raise RuntimeError("rollback")
        self.assertEqual(self.service.list_all()[0]["title"], "New conversation")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_duplicate_and_stale_replies_do_not_change_history(self):
        first = self.db.add_user_message(self.cid, "First")
        second = self.db.add_user_message(self.cid, "Second")
        self.assertFalse(self.db.add_assistant_reply(self.cid, first, "Stale"))
        self.assertTrue(self.db.add_assistant_reply(self.cid, second, "Current"))
        self.assertFalse(self.db.add_assistant_reply(self.cid, second, "Duplicate"))
        self.assertEqual(len(self.service.messages(self.cid)), 3)

    def test_reply_cannot_recreate_deleted_conversation(self):
        message_id = self.db.add_user_message(self.cid, "Hello")
        self.service.delete(self.cid)
        self.assertFalse(self.db.add_assistant_reply(self.cid, message_id, "Late reply"))
        self.assertEqual(self.service.list_all(), [])
