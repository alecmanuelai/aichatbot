from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import Mock

from backend.ai_service import AIService, AIServiceError, OFFLINE_PREFIX
from backend.chatbot_service import ChatbotService, InputValidationError
from config import AppConfig, MAX_MESSAGE_LENGTH
from database.database_manager import DatabaseManager


class ChatbotTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = DatabaseManager(Path(self.temp.name) / "test.db")
        self.cid = self.db.create_conversation()
        self.ai = AIService(AppConfig())
        self.chatbot = ChatbotService(self.db, self.ai)

    def test_input_validation_and_boundary(self):
        for text in ("", " \n\t ", None, "x" * (MAX_MESSAGE_LENGTH + 1)):
            with self.subTest(text_length=len(text) if text else 0), self.assertRaises(InputValidationError):
                self.chatbot.submit_user_message(self.cid, text)
        self.assertEqual(self.db.get_messages(self.cid), [])
        self.assertEqual(self.chatbot.validate_message(" hello \n"), "hello")
        self.chatbot.submit_user_message(self.cid, "x" * MAX_MESSAGE_LENGTH)

    def test_failure_and_retry_preserve_exactly_one_question(self):
        self.ai.reply = Mock(side_effect=[AIServiceError("Please retry."), "Successful reply"])
        mid = self.chatbot.submit_user_message(self.cid, "Explain Python")
        with self.assertRaises(AIServiceError):
            self.chatbot.complete_reply(self.cid, mid, Event())
        self.assertEqual(len(self.db.get_messages(self.cid)), 1)
        self.assertTrue(self.chatbot.complete_reply(self.cid, mid, Event()))
        self.assertEqual([m["role"] for m in self.db.get_messages(self.cid)], ["user", "assistant"])
        with self.assertRaises(AIServiceError):
            self.chatbot.complete_reply(self.cid, mid, Event())
        self.assertEqual(self.ai.reply.call_count, 2)

    def test_worker_uses_own_connection_and_original_conversation(self):
        mid = self.chatbot.submit_user_message(self.cid, "SQL")
        other = self.db.create_conversation()
        results = []
        worker = Thread(target=lambda: results.append(self.chatbot.complete_reply(self.cid, mid, Event())))
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [True])
        self.assertTrue(self.db.get_messages(self.cid)[1]["content"].startswith(OFFLINE_PREFIX))
        self.assertEqual(self.db.get_messages(other), [])

    def test_cancellation_before_and_after_request(self):
        mid = self.chatbot.submit_user_message(self.cid, "Question")
        cancelled = Event()
        cancelled.set()
        self.ai.reply = Mock(return_value="Reply")
        self.assertFalse(self.chatbot.complete_reply(self.cid, mid, cancelled))
        self.ai.reply.assert_not_called()
        cancelled.clear()
        def cancel_during_request(messages):
            cancelled.set()
            return "Late reply"
        self.ai.reply.side_effect = cancel_during_request
        self.assertFalse(self.chatbot.complete_reply(self.cid, mid, cancelled))
        self.assertEqual(len(self.db.get_messages(self.cid)), 1)

    def test_deletion_while_request_runs_does_not_resurrect_chat(self):
        mid = self.chatbot.submit_user_message(self.cid, "Question")
        def delete_during_request(messages):
            self.db.delete_conversation(self.cid)
            return "Late reply"
        self.ai.reply = Mock(side_effect=delete_during_request)
        self.assertFalse(self.chatbot.complete_reply(self.cid, mid, Event()))
        self.assertEqual(self.db.list_conversations(), [])
