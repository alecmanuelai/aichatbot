"""Opt-in real-window tests: python -m tests.gui_smoke (requires a display)."""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
import unittest
from unittest.mock import Mock, patch

import customtkinter as ctk

from backend.ai_service import AIService, AIServiceError, OFFLINE_PREFIX
from backend.chatbot_service import ChatbotService
from backend.conversation_service import ConversationService
from config import AppConfig
from database.database_manager import DatabaseManager
from ui.main_window import MainWindow


class DesktopSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = DatabaseManager(Path(self.temp.name) / "smoke.db")
        self.ai = AIService(AppConfig())
        self.chatbot = ChatbotService(self.db, self.ai)
        self.callback_errors = []
        self.app = self.open_window()

    def open_window(self):
        ctk.set_appearance_mode("dark")
        app = MainWindow(AppConfig(), ConversationService(self.db), self.chatbot)
        app.report_callback_exception = lambda *args: self.callback_errors.append(args)
        app.update()
        return app

    def tearDown(self):
        if not self.app.closing:
            with patch("ui.main_window.messagebox.askyesno", return_value=True):
                self.app.close()
        if self.app.worker:
            self.app.worker.join(timeout=3)
        self.temp.cleanup()
        self.assertEqual(self.callback_errors, [], "Tk callback errors occurred")

    def wait_for(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("The GUI did not reach the expected state")

    def enter_text(self, text):
        self.app.panel.input_box.insert("1.0", text)

    def test_offline_send_keyboard_history_resize_and_delete(self):
        app = self.app
        first = app.current_id
        self.assertEqual(app.panel.mode_label.cget("text"), "Offline Demo")
        app.send_message()
        self.assertIn("Type a message", app.panel.status_label.cget("text"))
        self.enter_text("Explain Python classes")
        app.panel.input_box.focus_force()
        app.update()
        app.panel.input_box._textbox.event_generate("<Shift-Return>")
        app.update()
        self.assertIn("\n", app.panel.text())
        self.assertEqual(self.db.get_messages(first), [])
        app.panel.input_box._textbox.event_generate("<Return>")
        self.wait_for(lambda: not app.busy and len(self.db.get_messages(first)) == 2)
        messages = self.db.get_messages(first)
        self.assertTrue(messages[1]["content"].startswith(OFFLINE_PREFIX))
        self.assertEqual(len(app.panel.bubbles), 2)
        self.assertEqual(app.panel.text(), "")
        app.geometry("900x620")
        app.update()
        self.assertGreater(app.panel.bubbles[0].winfo_width(), 50)
        app.new_chat()
        second = app.current_id
        self.assertNotEqual(first, second)
        app.select_chat(first)
        self.assertEqual(len(app.panel.bubbles), 2)
        with patch("ui.main_window.messagebox.askyesno", return_value=False):
            app.delete_chat()
        self.assertEqual(len(self.db.get_messages(first)), 2)
        with patch("ui.main_window.messagebox.askyesno", return_value=True):
            app.delete_chat()
        self.assertEqual(self.db.get_messages(first), [])
        self.assertEqual(app.current_id, second)

    def test_pending_controls_retry_and_reopen(self):
        app = self.app
        cid = app.current_id
        release = Event()
        self.addCleanup(release.set)
        def failed_reply(messages):
            release.wait(timeout=3)
            raise AIServiceError("Provider unavailable. Please retry.")
        self.ai.reply = Mock(side_effect=failed_reply)
        self.enter_text("How does SQLite work?")
        app.send_message()
        self.assertTrue(app.busy)
        self.assertEqual(app.sidebar.new_button.cget("state"), "disabled")
        self.assertEqual(app.sidebar.delete_button.cget("state"), "disabled")
        self.assertEqual(app.panel.send_button.cget("state"), "disabled")
        app.send_message()
        app.new_chat()
        app.select_chat("not-a-real-chat")
        self.assertEqual(app.current_id, cid)
        self.assertEqual(len(self.db.get_messages(cid)), 1)
        with patch("ui.main_window.messagebox.askyesno", return_value=False):
            app.close()
        self.assertFalse(app.closing)
        release.set()
        self.wait_for(lambda: not app.busy)
        self.assertIn("Provider unavailable", app.panel.status_label.cget("text"))
        self.assertTrue(app.panel.retry_button.winfo_ismapped())
        app.close()
        self.app = app = self.open_window()
        self.assertEqual(app.current_id, cid)
        self.assertIsNotNone(app.pending_message_id)
        self.ai.reply = Mock(return_value=OFFLINE_PREFIX + "\nRecovered answer")
        app.panel.retry_button.invoke()
        self.wait_for(lambda: not app.busy)
        self.assertEqual([m["role"] for m in self.db.get_messages(cid)], ["user", "assistant"])
        self.assertIsNone(app.pending_message_id)

    def test_confirmed_close_during_request_preserves_question(self):
        release = Event()
        self.addCleanup(release.set)
        def delayed_reply(messages):
            release.wait(timeout=3)
            return "Late answer"
        self.ai.reply = Mock(side_effect=delayed_reply)
        cid = self.app.current_id
        self.enter_text("Question to preserve")
        self.app.send_message()
        with patch("ui.main_window.messagebox.askyesno", return_value=True):
            self.app.close()
        release.set()
        self.app.worker.join(timeout=3)
        self.assertFalse(self.app.worker.is_alive())
        self.assertEqual([m["role"] for m in self.db.get_messages(cid)], ["user"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
