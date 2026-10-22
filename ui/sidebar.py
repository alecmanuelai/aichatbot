"""Searchable, persistent conversation navigation."""

from collections.abc import Callable

import customtkinter as ctk

from ui.theme import ACCENT, BORDER, INK, MUTED, PRIMARY, SIDEBAR, TEXT, font


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_new: Callable, on_select: Callable, on_delete: Callable):
        super().__init__(master, width=236, corner_radius=0, fg_color=SIDEBAR)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.on_select = on_select
        self.buttons = []
        self.has_selection = False
        self._conversations = []
        self._selected_id = None
        self._busy = False

        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, padx=20, pady=(28, 0), sticky="w")
        ctk.CTkLabel(brand, text="SB", width=34, height=34, corner_radius=10,
                     fg_color=ACCENT, text_color=INK, font=font(13, True)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(brand, text="StudyBuddy", text_color=TEXT, font=font(19, True)).pack(side="left")
        ctk.CTkLabel(self, text="A space for curious minds.", text_color=MUTED, anchor="w", font=font(11)).grid(
            row=1, column=0, padx=20, pady=(6, 24), sticky="ew")
        self.new_button = ctk.CTkButton(self, text="+   New chat", height=40, corner_radius=10,
                                       command=self._new_chat, font=font(13, True), **PRIMARY)
        self._on_new = on_new
        self.new_button.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="ew")
        self.search_box = ctk.CTkEntry(self, placeholder_text="Search conversations...",
                                      height=34, fg_color="#0E1723", border_color=BORDER,
                                      border_width=1, text_color=TEXT, font=font(11))
        self.search_box.grid(row=3, column=0, padx=18, pady=(0, 16), sticky="ew")
        self.history_label = ctk.CTkLabel(self, text="CONVERSATIONS", text_color=MUTED,
                                         font=font(10, True), anchor="w")
        self.history_label.grid(row=4, column=0, padx=22, pady=(0, 4), sticky="ew")
        self.history = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0,
                                             scrollbar_button_color=BORDER, scrollbar_button_hover_color="#476178")
        self.history.grid(row=5, column=0, padx=(10, 6), sticky="nsew")
        self.history.grid_columnconfigure(0, weight=1)
        self.delete_button = ctk.CTkButton(
            self, text="Delete conversation", command=on_delete, fg_color="transparent", text_color=MUTED,
            hover_color="#492B38", border_color=BORDER, border_width=1, height=33, font=font(11))
        self.delete_button.grid(row=6, column=0, padx=18, pady=(16, 12), sticky="ew")
        ctk.CTkLabel(self, text="History is saved on this computer.", text_color=MUTED, font=font(10)).grid(
            row=7, column=0, padx=12, pady=(0, 18))
        self.search_box.bind("<KeyRelease>", lambda e: self._render())
        self.search_box.bind("<<Paste>>", lambda e: self.after_idle(self._render))
        self.search_box.bind("<<Cut>>", lambda e: self.after_idle(self._render))

    def _new_chat(self):
        if not self._busy:
            self.search_box.delete(0, "end")
            self._on_new()

    def refresh(self, conversations: list[dict], selected_id: str | None) -> None:
        self._conversations = conversations
        self._selected_id = selected_id
        self.has_selection = selected_id is not None
        self._render()

    def _render(self):
        for widget in self.history.winfo_children():
            widget.destroy()
        self.buttons = []
        query = self.search_box.get().strip().casefold()
        conversations = [c for c in self._conversations if query in c["title"].casefold()]
        self.history_label.configure(text=f"CONVERSATIONS  ·  {len(conversations)}")
        if not conversations:
            ctk.CTkLabel(self.history, text="No matching conversations" if query else "Your chats will appear here.",
                         text_color=MUTED, font=font(11), wraplength=170).grid(row=0, column=0, pady=14)
        for row, conversation in enumerate(conversations):
            cid, title = conversation["id"], conversation["title"]
            label = title if len(title) <= 23 else title[:20] + "..."
            selected = cid == self._selected_id
            button = ctk.CTkButton(
                self.history, text=label, anchor="w", height=42,
                corner_radius=9, font=font(12), text_color=ACCENT if selected else TEXT,
                fg_color="#203A40" if selected else "transparent", hover_color="#243444",
                command=lambda conversation_id=cid: self.on_select(conversation_id))
            button.grid(row=row, column=0, padx=2, pady=3, sticky="ew")
            self.buttons.append(button)
        self.set_busy(self._busy)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.new_button.configure(state=state)
        self.search_box.configure(state=state)
        self.delete_button.configure(state="normal" if not busy and self.has_selection else "disabled")
        for button in self.buttons:
            button.configure(state=state)
