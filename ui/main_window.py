"""Coordinate UI events and a worker queue without touching Tk from workers."""

from queue import Empty, Queue
import sqlite3
from threading import Event, Thread
from tkinter import messagebox

import customtkinter as ctk

from backend.ai_service import AIServiceError
from backend.chatbot_service import ChatbotService, InputValidationError
from backend.conversation_service import ConversationService
from config import AppConfig
from ui.chat_panel import ChatPanel
from ui.sidebar import Sidebar


def run_reply(chatbot, conversation_id, message_id, cancelled, results):
    """Worker entry point. Arguments contain no widgets, and SQLite opens here."""
    try:
        saved = chatbot.complete_reply(conversation_id, message_id, cancelled)
        error = None if saved else "The reply was not saved because the conversation changed. Reopen the chat."
    except AIServiceError as exc:
        error = str(exc)  # This exception contains only our deliberately safe messages.
    except (sqlite3.Error, OSError):
        error = "The reply could not be saved. Check free disk space and database permissions, then retry."
    except Exception:
        error = "The request could not be completed. Your message is saved; please retry."
    results.put((conversation_id, message_id, error))


class MainWindow(ctk.CTk):
    def __init__(self, config: AppConfig, conversations: ConversationService, chatbot: ChatbotService):
        super().__init__()
        self.conversations = conversations
        self.chatbot = chatbot
        self.current_id = None
        self.pending_message_id = None
        self.busy = False
        self.closing = False
        self.cancelled = Event()
        self.results = Queue()
        self.worker = None
        self.poll_id = None

        self.title("StudyBuddy · Your study companion")
        self.geometry("1100x760")
        self.minsize(860, 580)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.sidebar = Sidebar(self, self.new_chat, self.select_chat, self.delete_chat)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.panel = ChatPanel(self, config.mode, self.send_message, self.retry_reply)
        self.panel.grid(row=0, column=1, sticky="nsew")
        self.protocol("WM_DELETE_WINDOW", self.close)

        try:
            existing = self.conversations.list_all()
            self.current_id = existing[0]["id"] if existing else self.conversations.create()
            self.refresh()
        except (sqlite3.Error, OSError):
            self.show_storage_error()
        self.poll_id = self.after(75, self.poll_results)

    def refresh(self) -> None:
        conversations = self.conversations.list_all()
        messages = self.conversations.messages(self.current_id) if self.current_id else []
        title = next((c["title"] for c in conversations if c["id"] == self.current_id), "New conversation")
        self.pending_message_id = messages[-1]["id"] if messages and messages[-1]["role"] == "user" else None
        self.sidebar.refresh(conversations, self.current_id)
        self.panel.show_messages(messages, title)
        self.update_controls()
        self.panel.set_status("This message is saved and awaiting a reply. Retry, or start a new chat."
                              if self.pending_message_id else "")

    def update_controls(self) -> None:
        self.sidebar.set_busy(self.busy)
        self.panel.set_controls(self.busy, self.pending_message_id is not None, self.current_id is not None)

    def show_storage_error(self) -> None:
        self.panel.set_status("Cannot access chat history. Check free disk space and permissions for the data folder.", True)
        self.update_controls()

    def new_chat(self) -> None:
        if self.busy:
            return
        try:
            self.current_id = self.conversations.create()
            self.refresh()
            self.panel.clear_input()
            self.panel.input_box.focus_set()
        except (sqlite3.Error, OSError):
            self.show_storage_error()

    def select_chat(self, conversation_id: str) -> None:
        if self.busy or conversation_id == self.current_id:
            return
        try:
            self.current_id = conversation_id
            # Clear the old draft before the destination can disable the composer.
            self.panel.input_box.configure(state="normal")
            self.panel.clear_input()
            self.refresh()
        except (sqlite3.Error, OSError):
            self.show_storage_error()

    def delete_chat(self) -> None:
        if self.busy or self.current_id is None:
            return
        if not messagebox.askyesno("Delete conversation?", "Permanently delete this conversation and all its messages?", parent=self):
            return
        try:
            self.conversations.delete(self.current_id)
            remaining = self.conversations.list_all()
            self.current_id = remaining[0]["id"] if remaining else self.conversations.create()
            self.panel.input_box.configure(state="normal")
            self.panel.clear_input()
            self.refresh()
        except (sqlite3.Error, OSError):
            self.show_storage_error()

    def send_message(self) -> None:
        if self.busy or self.pending_message_id is not None or self.current_id is None:
            return
        try:
            message_id = self.chatbot.submit_user_message(self.current_id, self.panel.text())
            self.pending_message_id = message_id
            self.panel.clear_input()
            self.refresh()
        except InputValidationError as exc:
            self.panel.set_status(str(exc), True)
            return
        except (sqlite3.Error, OSError):
            self.show_storage_error()
            return
        self.start_reply(message_id)

    def retry_reply(self) -> None:
        if not self.busy and self.current_id and self.pending_message_id is not None:
            self.start_reply(self.pending_message_id)

    def start_reply(self, message_id: int) -> None:
        self.busy = True
        self.cancelled = Event()
        self.update_controls()
        self.panel.set_status("StudyBuddy is preparing a reply…")
        # Capture the original IDs. Workers receive services and a queue, never self.
        self.worker = Thread(
            target=run_reply,
            args=(self.chatbot, self.current_id, message_id, self.cancelled, self.results),
            daemon=True,
        )
        self.worker.start()

    def poll_results(self) -> None:
        if self.closing:
            return
        try:
            while True:
                conversation_id, message_id, error = self.results.get_nowait()
                self.busy = False
                try:
                    if conversation_id == self.current_id:
                        self.refresh()
                        if error:
                            self.panel.set_status(error, True)
                        elif self.pending_message_id is None:
                            self.panel.input_box.focus_set()
                    self.update_controls()
                except (sqlite3.Error, OSError):
                    self.show_storage_error()
        except Empty:
            pass
        self.poll_id = self.after(75, self.poll_results)

    def close(self) -> None:
        if self.busy and not messagebox.askyesno(
            "Close StudyBuddy?", "A reply is in progress. Close now? Your saved question can be retried next time.", parent=self
        ):
            return
        self.closing = True
        self.cancelled.set()
        self.panel.progress.stop()
        # The entire root is closing. Cancel library animation/scaling timers too,
        # so no callback can target a widget after its Tcl command is destroyed.
        for timer_id in self.tk.call("after", "info"):
            # Leave each callback command for its owning widget to clean up.
            self.tk.call("after", "cancel", timer_id)
        self.destroy()
