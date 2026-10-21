"""Message bubbles, composer, and visible request status."""

from datetime import datetime

import customtkinter as ctk

from config import MAX_MESSAGE_LENGTH


class ChatPanel(ctk.CTkFrame):
    def __init__(self, master, mode: str, on_send, on_retry):
        super().__init__(master, corner_radius=0, fg_color="#0b1220")
        self.on_send = on_send
        self.bubbles = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=26, pady=(24, 16), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(header, text="New conversation", font=("Arial", 21, "bold"), anchor="w")
        self.title_label.grid(row=0, column=0, sticky="ew")
        self.mode_label = ctk.CTkLabel(
            header, text="Online AI" if mode == "online" else "Offline Demo",
            text_color="#7dd3fc" if mode == "online" else "#fcd34d",
            fg_color="#1e293b", corner_radius=12, padx=14, pady=6, font=("Arial", 12, "bold"),
        )
        self.mode_label.grid(row=0, column=1, padx=(16, 0))
        ctk.CTkLabel(
            header, text="External model · verify important answers" if mode == "online"
            else "Predefined educational examples · no AI service contacted",
            text_color="#94a3b8", anchor="w", font=("Arial", 12),
        ).grid(row=1, column=0, columnspan=2, pady=(7, 0), sticky="ew")

        self.history = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.history.grid(row=1, column=0, padx=16, sticky="nsew")
        self.history.grid_columnconfigure(0, weight=1)
        self.history.bind("<Configure>", self._resize_bubbles)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=2, column=0, padx=26, pady=(6, 8), sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(status_frame, text="", anchor="w", justify="left", wraplength=550, font=("Arial", 13))
        self.status_label.grid(row=0, column=0, sticky="ew")
        self.retry_button = ctk.CTkButton(status_frame, text="Retry reply", width=105, command=on_retry, font=("Arial", 13))
        self.retry_button.grid(row=0, column=1, padx=(12, 0))
        self.retry_button.grid_remove()
        self.progress = ctk.CTkProgressBar(status_frame, height=3, mode="indeterminate")
        self.progress.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky="ew")
        self.progress.grid_remove()

        composer = ctk.CTkFrame(self, corner_radius=16, fg_color="#182338")
        composer.grid(row=3, column=0, padx=26, pady=(0, 8), sticky="ew")
        composer.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(composer, height=90, wrap="word", fg_color="transparent", font=("Arial", 14))
        self.input_box.grid(row=0, column=0, padx=10, pady=8, sticky="ew")
        self.input_box.bind("<Return>", self._enter)
        self.send_button = ctk.CTkButton(composer, text="Send", width=80, height=38, command=on_send, font=("Arial", 14, "bold"))
        self.send_button.grid(row=0, column=1, padx=(6, 14), pady=12, sticky="se")
        ctk.CTkLabel(
            self, text=f"Enter to send  ·  Shift+Enter for a new line  ·  {MAX_MESSAGE_LENGTH:,} characters max",
            text_color="#94a3b8", font=("Arial", 11),
        ).grid(row=4, column=0, padx=26, pady=(0, 18), sticky="w")

    def _enter(self, event):
        if event.state & 0x1:  # Tk's Shift modifier; leave the normal newline binding intact.
            return None
        self.on_send()
        return "break"

    def text(self) -> str:
        return self.input_box.get("1.0", "end-1c")

    def clear_input(self) -> None:
        self.input_box.delete("1.0", "end")

    def show_messages(self, messages: list[dict], title: str) -> None:
        self.title_label.configure(text=title if len(title) <= 38 else title[:35] + "...")
        for widget in self.history.winfo_children():
            widget.destroy()
        self.bubbles = []
        if not messages:
            ctk.CTkLabel(
                self.history, text="What will you learn today?", font=("Arial", 27, "bold")
            ).grid(row=0, column=0, pady=(70, 12))
            ctk.CTkLabel(
                self.history, text="Try: Explain Python classes\nHow does SQLite store messages?\nHelp me plan for an exam",
                text_color="#a7b7cc", font=("Arial", 15), justify="center",
            ).grid(row=1, column=0, pady=8)
        for row, message in enumerate(messages):
            user = message["role"] == "user"
            bubble = ctk.CTkFrame(self.history, corner_radius=16, fg_color="#1e4961" if user else "#1b283b")
            bubble.grid(row=row, column=0, padx=(65, 8) if user else (8, 65), pady=8, sticky="e" if user else "w")
            try:
                timestamp = datetime.fromisoformat(message["created_at"]).astimezone().strftime("%b %d · %H:%M")
            except (ValueError, TypeError):
                timestamp = ""
            ctk.CTkLabel(
                bubble, text=f"{'You' if user else 'StudyBuddy'}  ·  {timestamp}",
                text_color="#aac6da", font=("Arial", 11, "bold"), anchor="w",
            ).pack(fill="x", padx=16, pady=(12, 3))
            label = ctk.CTkLabel(
                bubble, text=message["content"], justify="left", anchor="w",
                wraplength=max(240, self.history.winfo_width() - 130), font=("Arial", 14),
            )
            label.pack(fill="x", padx=16, pady=(0, 14))
            self.bubbles.append(label)
        # Geometry must settle before the scroll region is measured.
        self.history.update_idletasks()
        self.history._parent_canvas.yview_moveto(1.0)

    def _resize_bubbles(self, event) -> None:
        width = max(200, event.width - 130)
        for label in self.bubbles:
            label.configure(wraplength=width)
        self.status_label.configure(wraplength=max(200, event.width - 150))

    def set_status(self, text: str = "", error: bool = False) -> None:
        self.status_label.configure(text=text, text_color="#fda4af" if error else "#a7b7cc")

    def set_controls(self, busy: bool, awaiting_reply: bool, has_chat: bool = True) -> None:
        can_send = not busy and not awaiting_reply and has_chat
        self.send_button.configure(state="normal" if can_send else "disabled")
        self.input_box.configure(state="normal" if can_send else "disabled")
        self.retry_button.configure(state="disabled" if busy else "normal")
        if awaiting_reply and not busy:
            self.retry_button.grid()
        else:
            self.retry_button.grid_remove()
        if busy:
            self.progress.grid()
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_remove()
