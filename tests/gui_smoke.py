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

    def test_starter_draft_counter_copy_and_search(self):
        app = self.app
        panel = app.panel
        panel.prompt_buttons[0].invoke()
        app.update()
        self.assertIn("Python classes", panel.text())
        self.assertFalse(app.busy, "A starter should fill a draft without sending it")
        self.assertEqual(self.db.get_messages(app.current_id), [])
        self.assertEqual(panel.send_button.cget("state"), "normal")
        panel.clear_input()
        panel.input_box.insert("1.0", "x" * 4001)
        app.update()
        self.assertEqual(panel.counter.cget("text"), "4,001 / 4,000")
        self.assertEqual(panel.send_button.cget("state"), "disabled")
        panel.clear_input()
        panel.use_prompt("Explain Python classes")
        app.send_message()
        self.wait_for(lambda: not app.busy)
        first = app.current_id
        answer = self.db.get_messages(first)[1]["content"]
        panel.copy_buttons[0].invoke()
        self.assertEqual(app.clipboard_get(), answer)
        self.assertEqual(panel.copy_buttons[0].cget("text"), "Copied")
        app.new_chat()
        app.sidebar.search_box.focus_force()
        app.update()
        app.sidebar.search_box.insert(0, "PYTHON")
        app.sidebar.search_box._entry.event_generate("<KeyRelease>")
        app.update()
        self.assertEqual(len(app.sidebar.buttons), 1)
        app.sidebar.buttons[0].invoke()
        self.assertEqual(app.current_id, first)
        app.sidebar.search_box.delete(0, "end")
        app.sidebar.search_box.insert(0, "no matches")
        app.sidebar.search_box._entry.event_generate("<KeyRelease>")
        app.update()
        self.assertEqual(app.sidebar.buttons, [])
        app.sidebar.new_button.invoke()
        self.assertEqual(app.sidebar.search_box.get(), "")
        self.assertEqual(len(app.sidebar.buttons), 3)

    def test_long_replies_fit_at_different_sizes_and_display_scales(self):
        app = self.app
        panel = app.panel
        paragraph = "A class is a blueprint for objects. Each object can hold its own data. "
        content = paragraph * 18 + "\n\n" + "long_identifier_" * 40 + "\nFinal line is visible."
        panel.show_messages([
            dict(role="user", content="Explain Python classes " * 8, created_at="2026-10-22T10:00:00+00:00"),
            dict(role="assistant", content=content, created_at="2026-10-22T10:00:01+00:00"),
        ], "A long conversation title for layout testing")
        try:
            for scale in (1.0, 1.25, 1.5):
                ctk.set_widget_scaling(scale)
                ctk.set_window_scaling(scale)
                # CTk temporarily locks window dimensions during a DPI change.
                deadline = time.monotonic() + 1.1
                while time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.01)
                for size in ("860x580", "1100x760"):
                    with self.subTest(scale=scale, size=size):
                        app.geometry(size)
                        app.update()
                        expected_width, expected_height = map(int, size.split("x"))
                        self.assertAlmostEqual(app.winfo_width(), expected_width * scale, delta=1)
                        self.assertAlmostEqual(app.winfo_height(), expected_height * scale, delta=1)
                        canvas = panel.history._parent_canvas
                        canvas.yview_moveto(1.0)
                        app.update()
                        self.assertFalse(panel.status_frame.winfo_ismapped())
                        for label in panel.bubbles:
                            self.assertLessEqual(label._label.winfo_reqwidth(), label._label.winfo_width() + 1)
                            self.assertLessEqual(label._label.winfo_reqheight(), label._label.winfo_height() + 1)
                            self.assertGreaterEqual(label.winfo_rootx(), canvas.winfo_rootx())
                            self.assertLessEqual(label.winfo_rootx() + label.winfo_width(),
                                                 canvas.winfo_rootx() + canvas.winfo_width())
                        last = panel.bubbles[-1]
                        self.assertLessEqual(last.winfo_rooty() + last.winfo_height(),
                                             canvas.winfo_rooty() + canvas.winfo_height())
                        self.assertLessEqual(panel.footer.winfo_rooty() + panel.footer.winfo_height(),
                                             app.winfo_rooty() + app.winfo_height())
                        self.assertLessEqual(panel.send_button.winfo_rootx() + panel.send_button.winfo_width(),
                                             app.winfo_rootx() + app.winfo_width())
        finally:
            ctk.set_widget_scaling(1.0)
            ctk.set_window_scaling(1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
