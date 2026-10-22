"""Responsive message cards, suggested prompts, and a compact composer."""

from datetime import datetime
import tkinter as tk

import customtkinter as ctk

from config import MAX_MESSAGE_LENGTH
from ui.theme import ACCENT, BG, BORDER, MUTED, PRIMARY, SURFACE, TEXT, font


class ChatPanel(ctk.CTkFrame):
    def __init__(self, master, mode: str, on_send, on_retry):
        super().__init__(master, corner_radius=0, fg_color=BG)
        self.on_send = on_send
        self.bubbles = []
        self._cards = []
        self._welcome_labels = []
        self.prompt_buttons = []
        self.copy_buttons = []
        self._can_compose = True
        self._busy = self._awaiting = False
        self._last_width = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(22, 16), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="YOUR STUDY SPACE", text_color=ACCENT,
                     font=font(10, True), height=18, anchor="w").grid(row=0, column=0, sticky="w")
        self.title_label = ctk.CTkLabel(header, text="New conversation", width=1,
                                       font=font(23, True), height=34, text_color=TEXT, anchor="w", justify="left")
        self.title_label.grid(row=1, column=0, sticky="ew")
        self.mode_label = ctk.CTkLabel(
            header, text="Online AI" if mode == "online" else "Offline Demo",
            text_color=ACCENT if mode == "online" else "#F4CF83",
            fg_color="#1C3537" if mode == "online" else "#373125",
            corner_radius=12, width=106, height=30, font=font(11, True),
        )
        self.mode_label.grid(row=1, column=1, padx=(12, 0), sticky="ne")
        self.subtitle = ctk.CTkLabel(
            header, text="A little help. A lot of learning." if mode == "online"
            else "Practice with predefined examples. No internet needed.",
            text_color=MUTED, anchor="w", justify="left", width=1, height=22, font=font(12),
        )
        self.subtitle.grid(row=2, column=0, columnspan=2, pady=(4, 0), sticky="ew")

        self.history = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color="#476178",
        )
        self.history.grid(row=1, column=0, padx=(20, 16), sticky="nsew")
        self.history.grid_columnconfigure(0, weight=1)
        # Keep CTk's own Configure handler, which updates the scroll region.
        self.history.bind("<Configure>", self._resize_bubbles, add="+")

        self.status_frame = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10)
        self.status_frame.grid(row=2, column=0, padx=28, pady=(8, 8), sticky="ew")
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(self.status_frame, text="", width=1, anchor="w",
                                        justify="left", wraplength=450, font=font(12))
        self.status_label.grid(row=0, column=0, padx=12, pady=8, sticky="ew")
        self.retry_button = ctk.CTkButton(self.status_frame, text="Retry reply", width=100,
                                         command=on_retry, font=font(12, True), **PRIMARY)
        self.retry_button.grid(row=0, column=1, padx=(0, 10), pady=8)
        self.retry_button.grid_forget()
        self.progress = ctk.CTkProgressBar(self.status_frame, height=3, mode="indeterminate",
                                          progress_color=ACCENT, fg_color=BORDER)
        self.progress.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")
        self.progress.grid_forget()
        self.status_frame.grid_forget()

        self.composer = ctk.CTkFrame(self, corner_radius=14, fg_color=SURFACE,
                                    border_width=1, border_color=BORDER)
        self.composer.grid(row=3, column=0, padx=28, pady=(12, 6), sticky="ew")
        self.composer.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(self.composer, height=56, wrap="word", fg_color="transparent",
                                       text_color=TEXT, border_spacing=4, font=font(14))
        self.input_box.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 0), sticky="ew")
        self.input_box.bind("<Return>", self._enter)
        self.input_box.bind("<FocusIn>", lambda e: self.composer.configure(border_color=ACCENT))
        self.input_box.bind("<FocusOut>", lambda e: self.composer.configure(border_color=BORDER))
        self.input_box.bind("<<Modified>>", self._draft_changed)
        self.placeholder = ctk.CTkLabel(self.input_box, text="Ask a question, or explore an idea...",
                                        text_color=MUTED, fg_color=SURFACE, font=font(14), anchor="w")
        self.placeholder.bind("<Button-1>", lambda e: self.input_box.focus_set())
        self.counter = ctk.CTkLabel(self.composer, text="", text_color=MUTED, font=font(10), anchor="w")
        self.counter.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")
        self.send_button = ctk.CTkButton(self.composer, text="Send", width=104, height=32,
                                        corner_radius=9, command=on_send, font=font(12, True), **PRIMARY)
        self.send_button.grid(row=1, column=1, padx=(8, 12), pady=(2, 10), sticky="e")
        self.footer = ctk.CTkLabel(
            self, text="Enter to send · Shift+Enter for a new line · Check important answers",
            text_color=MUTED, font=font(10), width=1, justify="left", anchor="w",
        )
        self.footer.grid(row=4, column=0, padx=28, pady=(0, 12), sticky="ew")
        self._update_draft()

    def _enter(self, event):
        if event.state & 0x1:
            return None
        self.on_send()
        return "break"

    def text(self) -> str:
        return self.input_box.get("1.0", "end-1c")

    def clear_input(self) -> None:
        self.input_box.delete("1.0", "end")
        self._update_draft()

    def _draft_changed(self, event=None):
        if self.input_box.edit_modified():
            self.input_box.edit_modified(False)
            self._update_draft()

    def _update_draft(self):
        text = self.text()
        count = len(text.strip())
        self.counter.configure(text=f"{count:,} / {MAX_MESSAGE_LENGTH:,}",
                               text_color="#FDA4AF" if count > MAX_MESSAGE_LENGTH else MUTED)
        self.send_button.configure(state="normal" if self._can_compose and 0 < count <= MAX_MESSAGE_LENGTH else "disabled")
        if text or not self._can_compose:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=6, y=3)

    def use_prompt(self, prompt):
        if self._can_compose:
            self.clear_input()
            self.input_box.insert("1.0", prompt)
            self._update_draft()
            self.input_box.focus_set()

    def _show_welcome(self):
        welcome = ctk.CTkFrame(self.history, fg_color="transparent")
        welcome.grid(row=0, column=0, padx=12, pady=(26, 22), sticky="ew")
        welcome.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(welcome, text="SB", width=50, height=48, corner_radius=15,
                     fg_color="#1C3537", text_color=ACCENT, font=font(20, True)).grid(row=0, column=0, sticky="w")
        title = ctk.CTkLabel(welcome, text="Make room for a little discovery.", width=1,
                             text_color=TEXT, font=font(25, True), anchor="w", justify="left")
        title.grid(row=1, column=0, pady=(16, 8), sticky="ew")
        subtitle = ctk.CTkLabel(welcome, text="Break down a tricky topic, test what you know,\nor find your next small step.",
                                width=1, text_color=MUTED, font=font(13), anchor="w", justify="left")
        subtitle.grid(row=2, column=0, pady=(0, 18), sticky="ew")
        self._welcome_labels = [title, subtitle]
        for row, (label, prompt) in enumerate([
            ("01   Understand a concept", "Explain Python classes with a simple example."),
            ("02   Test my knowledge", "Quiz me on Python basics, one question at a time."),
            ("03   Build a study plan", "Help me make a study plan for my next exam."),
        ], start=3):
            button = ctk.CTkButton(welcome, text=label, anchor="w", height=43,
                                   fg_color=SURFACE, hover_color="#223648", border_width=1,
                                   border_color=BORDER, text_color=TEXT, font=font(13),
                                   command=lambda p=prompt: self.use_prompt(p))
            button.grid(row=row, column=0, pady=4, sticky="ew")
            self.prompt_buttons.append(button)

    def show_messages(self, messages: list[dict], title: str) -> None:
        self.title_label.configure(text=(title[:35] + "...") if len(title) > 38 else title)
        for widget in self.history.winfo_children():
            widget.destroy()
        self.bubbles, self._cards, self._welcome_labels = [], [], []
        self.prompt_buttons, self.copy_buttons = [], []
        if not messages:
            self._show_welcome()
        for row, message in enumerate(messages):
            user = message["role"] == "user"
            bubble = ctk.CTkFrame(self.history, corner_radius=14,
                                  fg_color="#1B3B44" if user else SURFACE,
                                  border_width=1, border_color="#2B5058" if user else BORDER)
            bubble.grid(row=row, column=0, padx=(56, 8) if user else (8, 32),
                        pady=(6, 12), sticky="e" if user else "w")
            bubble.grid_columnconfigure(0, weight=1)
            meta = ctk.CTkFrame(bubble, fg_color="transparent")
            meta.grid(row=0, column=0, padx=18, pady=(12, 6), sticky="ew")
            meta.grid_columnconfigure(0, weight=1)
            try:
                timestamp = datetime.fromisoformat(message["created_at"]).astimezone().strftime("%b %d · %H:%M")
            except (ValueError, TypeError):
                timestamp = ""
            ctk.CTkLabel(meta, text="You" if user else "StudyBuddy", text_color=ACCENT if not user else TEXT,
                         font=font(12, True), height=19, anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(meta, text=timestamp, text_color=MUTED, font=font(10), height=18, anchor="w").grid(row=1, column=0, sticky="w")
            if not user:
                copy = ctk.CTkButton(meta, text="Copy", width=56, height=27, fg_color="transparent",
                                     hover_color=BORDER, text_color=MUTED, font=font(11))
                copy.configure(command=lambda t=message["content"], b=copy: self.copy_reply(t, b))
                copy.grid(row=0, column=1, rowspan=2, padx=(16, 0), sticky="ne")
                self.copy_buttons.append(copy)
            label = ctk.CTkLabel(bubble, text=message["content"], justify="left", anchor="w",
                                 width=1, text_color=TEXT, wraplength=300, font=font(14))
            label.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="ew")
            self.bubbles.append(label)
            self._cards.append((label, user))
        self._resize_bubbles()
        # Measure wrapped text before scrolling so the final line is reachable.
        self.history.update_idletasks()
        self.history._parent_canvas.yview_moveto(1.0 if messages else 0.0)

    def copy_reply(self, text, button):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            for copy in self.copy_buttons:
                copy.configure(text="Copy")
            button.configure(text="Copied")
        except tk.TclError:
            self.set_status("Could not copy this reply to the clipboard. Please try again.", True)

    def _resize_bubbles(self, event=None):
        # Configure events are physical pixels. CTk wraplength expects logical
        # pixels and applies display scaling again; convert once at this boundary.
        width = self._reverse_widget_scaling(self.history.winfo_width())
        if event is not None and self._last_width == width:
            return
        self._last_width = width
        for label, user in self._cards:
            label.configure(wraplength=max(120, min(520 if user else 720, width - (104 if user else 80))))
        for label in self._welcome_labels:
            label.configure(wraplength=max(180, width - 40))
        self.title_label.configure(wraplength=max(170, width - 150))
        self.subtitle.configure(wraplength=max(220, width - 20))
        self.status_label.configure(wraplength=max(160, width - 160))
        self.footer.configure(wraplength=max(220, width - 20))
        self.placeholder.configure(wraplength=max(180, width - 70))

    def _update_status_visibility(self):
        if self.status_label.cget("text") or self._busy or self._awaiting:
            self.status_frame.grid(row=2, column=0, padx=28, pady=(8, 8), sticky="ew")
        else:
            # CTk replays its last grid call when DPI changes. Forget hidden
            # widgets completely so moving between monitors cannot reveal them.
            self.status_frame.grid_forget()

    def set_status(self, text: str = "", error: bool = False) -> None:
        self.status_label.configure(text=text, text_color="#FDA4AF" if error else MUTED)
        self._update_status_visibility()

    def set_controls(self, busy: bool, awaiting_reply: bool, has_chat: bool = True) -> None:
        self._busy, self._awaiting = busy, awaiting_reply
        self._can_compose = not busy and not awaiting_reply and has_chat
        self.input_box.configure(state="normal" if self._can_compose else "disabled")
        self.send_button.configure(text="Waiting..." if busy else "Send")
        self._update_draft()
        for button in self.prompt_buttons:
            button.configure(state="normal" if self._can_compose else "disabled")
        self.retry_button.configure(state="disabled" if busy else "normal")
        if awaiting_reply and not busy:
            self.retry_button.grid(row=0, column=1, padx=(0, 10), pady=8)
        else:
            self.retry_button.grid_forget()
        if busy:
            self.progress.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_forget()
        self._update_status_visibility()
