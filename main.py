"""Run StudyBuddy from any working directory: python /path/to/main.py."""

import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from backend.ai_service import AIService
from backend.chatbot_service import ChatbotService
from backend.conversation_service import ConversationService
from config import AppConfig, ConfigurationError
from database.database_manager import DatabaseManager
from ui.main_window import MainWindow


def show_startup_error(message: str) -> None:
    """Show only a safe message, even when no desktop display is available."""
    print(f"StudyBuddy: {message}", file=sys.stderr)
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("StudyBuddy could not start", message, parent=root)
        root.destroy()
    except tk.TclError:
        pass


def main() -> int:
    try:
        config = AppConfig.load()
        database = DatabaseManager()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        app = MainWindow(config, ConversationService(database), ChatbotService(database, AIService(config)))
        app.mainloop()
    except ConfigurationError as exc:
        show_startup_error(str(exc))
        return 1
    except (sqlite3.Error, OSError):
        show_startup_error("Cannot open the database. Check free disk space and write permissions for the project's data folder.")
        return 1
    except tk.TclError:
        show_startup_error("A desktop display with Tk is required. Run this app on your Windows desktop, or a Linux desktop session.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
