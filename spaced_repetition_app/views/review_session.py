"""Окно сессии повторения."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

import models


class ReviewSessionWindow(tk.Toplevel):
    def __init__(self, parent: "MainWindow", user: Dict[str, str], deck_id: Optional[str]):
        super().__init__(parent)
        self.parent_view = parent
        self.user = user
        self.deck_id = deck_id
        self.queue: List[Dict[str, str]] = []
        self.current_card: Optional[Dict[str, str]] = None
        self.answer_visible = False

        self.title("Сессия повторения")
        self.geometry("600x420")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status_var = tk.StringVar(value="")

        self._build_ui()
        self._load_queue()
        self._next_card()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=10)
        deck_name = "Все колоды" if not self.deck_id else self._deck_name()
        ttk.Label(header, text=f"Колода: {deck_name}", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        card_frame = ttk.Frame(self)
        card_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(card_frame, text="Front:").pack(anchor="w")
        self.front_label = ttk.Label(card_frame, text="", wraplength=560, font=("TkDefaultFont", 14))
        self.front_label.pack(fill="x", pady=5)

        ttk.Label(card_frame, text="Back:").pack(anchor="w")
        self.back_label = ttk.Label(card_frame, text="", wraplength=560, font=("TkDefaultFont", 12))
        self.back_label.pack(fill="x", pady=5)

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls, text="Показать ответ", command=self.show_answer).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Пропустить", command=self.skip_card).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Пауза карточки", command=self.suspend_card).pack(side=tk.LEFT, padx=5)

        quality_frame = ttk.LabelFrame(self, text="Оценка качества (0-5)")
        quality_frame.pack(fill="x", padx=10, pady=10)

        for quality in range(6):
            ttk.Button(
                quality_frame,
                text=str(quality),
                command=lambda q=quality: self.answer_card(q),
            ).pack(side=tk.LEFT, expand=True, fill="x", padx=5, pady=5)

        status_bar = ttk.Frame(self)
        status_bar.pack(fill="x", padx=10, pady=5)
        ttk.Label(status_bar, textvariable=self.status_var).pack(anchor="w")

    def _deck_name(self) -> str:
        for deck in self.parent_view.decks:
            if deck["id"] == self.deck_id:
                return deck["name"]
        return ""

    def _load_queue(self) -> None:
        try:
            self.queue = models.get_due_queue(self.user["id"], deck_id=self.deck_id)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить очередь: {exc}")
            self.queue = []
        self.status_var.set(f"В очереди: {len(self.queue)}")

    def _next_card(self) -> None:
        if not self.queue:
            self.current_card = None
            self.front_label.config(text="Нет карточек к повторению")
            self.back_label.config(text="")
            return
        self.current_card = self.queue.pop(0)
        self.answer_visible = False
        self.front_label.config(text=self.current_card.get("front", ""))
        self.back_label.config(text="")
        self.status_var.set(f"Осталось: {len(self.queue) + 1}")

    def show_answer(self) -> None:
        if not self.current_card:
            return
        self.answer_visible = True
        self.back_label.config(text=self.current_card.get("back", ""))

    def answer_card(self, quality: int) -> None:
        if not self.current_card:
            return
        if not self.answer_visible:
            messagebox.showinfo("Ответ", "Сначала покажите ответ")
            return
        try:
            models.record_review(self.user["id"], self.current_card["card_id"], quality)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось записать результат: {exc}")
            return
        self.parent_view.refresh_from_child()
        self._load_queue()
        self._next_card()

    def skip_card(self) -> None:
        if not self.current_card:
            return
        self.queue.append(self.current_card)
        self._next_card()

    def suspend_card(self) -> None:
        if not self.current_card:
            return
        if not messagebox.askyesno("Пауза", "Приостановить показ этой карточки?"):
            return
        try:
            models.suspend_card(self.user["id"], self.current_card["card_id"], True)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось обновить карточку: {exc}")
            return
        self.parent_view.refresh_from_child()
        self._load_queue()
        self._next_card()

    def on_close(self) -> None:
        self.destroy()
        self.parent_view._review_window = None
