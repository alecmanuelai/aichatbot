"""Conversation navigation, kept separate from chat rendering."""

from collections.abc import Callable

import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_new: Callable, on_select: Callable, on_delete: Callable):
        super().__init__(master, width=250, corner_radius=0, fg_color="#111827")
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.on_select = on_select
        self.buttons = []
        self.has_selection = False

        ctk.CTkLabel(self, text="StudyBuddy", font=("Arial", 25, "bold"), anchor="w").grid(
            row=0, column=0, padx=22, pady=(28, 2), sticky="ew"
        )
        ctk.CTkLabel(self, text="A little help. A lot of learning.", text_color="#94a3b8", anchor="w", font=("Arial", 12)).grid(
            row=1, column=0, padx=22, pady=(0, 24), sticky="ew"
        )
        self.new_button = ctk.CTkButton(self, text="+  New Chat", height=40, command=on_new, font=("Arial", 14))
        self.new_button.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="ew")
        self.history = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="YOUR CONVERSATIONS", label_font=("Arial", 11, "bold"), label_fg_color="transparent")
        self.history.grid(row=3, column=0, padx=8, sticky="nsew")
        self.history.grid_columnconfigure(0, weight=1)
        self.delete_button = ctk.CTkButton(
            self, text="Delete Chat", command=on_delete, fg_color="#263244", hover_color="#7f3341", height=36, font=("Arial", 13)
        )
        self.delete_button.grid(row=4, column=0, padx=18, pady=18, sticky="ew")
        ctk.CTkLabel(self, text="Learn one question at a time.", text_color="#94a3b8", font=("Arial", 11)).grid(
            row=5, column=0, padx=14, pady=(0, 20)
        )

    def refresh(self, conversations: list[dict], selected_id: str | None) -> None:
        for widget in self.history.winfo_children():
            widget.destroy()
        self.buttons = []
        self.has_selection = selected_id is not None
        for row, conversation in enumerate(conversations):
            conversation_id = conversation["id"]
            title = conversation["title"]
            label = title if len(title) <= 25 else title[:22] + "..."
            button = ctk.CTkButton(
                self.history, text=label, anchor="w", height=40, font=("Arial", 12),
                fg_color="#284760" if conversation_id == selected_id else "transparent",
                hover_color="#243246",
                command=lambda cid=conversation_id: self.on_select(cid),
            )
            button.grid(row=row, column=0, padx=3, pady=3, sticky="ew")
            self.buttons.append(button)
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.new_button.configure(state=state)
        self.delete_button.configure(state="normal" if not busy and self.has_selection else "disabled")
        for button in self.buttons:
            button.configure(state=state)
