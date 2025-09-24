"""Главное окно приложения."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

import models
from views.deck_manager import DeckManagerWindow
from views.note_editor import NoteEditorWindow
from views.progress_view import ProgressWindow
from views.review_session import ReviewSessionWindow


class MainWindow(ttk.Frame):
    """Основное окно с навигацией и показом метрик."""

    def __init__(self, master: tk.Misc, user: Dict[str, str]):
        super().__init__(master)
        self.user = user
        self.decks: List[Dict[str, str]] = []
        self.selected_deck_id: Optional[str] = None

        self.configure(style="App.TFrame", padding=15)

        self.stats_vars = {
            "reviewed_today": tk.StringVar(value="0"),
            "due_now": tk.StringVar(value="0"),
            "learned": tk.StringVar(value="0"),
            "success_7": tk.StringVar(value="0%"),
            "success_30": tk.StringVar(value="0%"),
            "time": tk.StringVar(value=""),
        }

        self._deck_manager: Optional[DeckManagerWindow] = None
        self._note_editor: Optional[NoteEditorWindow] = None
        self._progress_window: Optional[ProgressWindow] = None
        self._review_window: Optional[ReviewSessionWindow] = None

        self._build_ui()
        self.refresh_data()
        self._tick_clock()

    def _build_ui(self) -> None:
        header = ttk.Frame(self, style="Toolbar.TFrame")
        header.pack(fill="x", pady=(0, 10))

        ttk.Label(
            header,
            text=f"Пользователь: {self.user['email']}",
            style="Subtitle.TLabel",
        ).pack(side=tk.LEFT)

        ttk.Button(header, text="Обновить", command=self.refresh_data, style="Secondary.TButton").pack(
            side=tk.RIGHT
        )

        stats_frame = ttk.LabelFrame(self, text="Статистика", style="Card.TLabelframe")
        stats_frame.pack(fill="x", pady=(0, 15))

        for idx, (key, label) in enumerate(
            [
                ("reviewed_today", "Сегодня повторено"),
                ("due_now", "Невыученные"),
                ("learned", "Выучено"),
                ("success_7", "Успешность 7 дней"),
                ("success_30", "Успешность 30 дней"),
            ]
        ):
            frame = ttk.Frame(stats_frame, style="Card.TFrame")
            frame.grid(row=0, column=idx, padx=10, pady=5, sticky="nsew")
            stats_frame.columnconfigure(idx, weight=1)
            ttk.Label(frame, text=label, style="MetricCaption.TLabel").pack(anchor="center")
            ttk.Label(frame, textvariable=self.stats_vars[key], style="MetricValue.TLabel").pack(
                anchor="center", pady=(6, 0)
            )

        decks_wrapper = ttk.Frame(self, style="Card.TFrame", padding=10)
        decks_wrapper.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(decks_wrapper, text="Колоды", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 8))

        tree_frame = ttk.Frame(decks_wrapper, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)

        self.deck_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "total", "learned", "due"),
            show="headings",
            height=10,
            style="Dashboard.Treeview",
        )
        self.deck_tree.heading("name", text="Название")
        self.deck_tree.heading("total", text="Всего")
        self.deck_tree.heading("learned", text="Выучено")
        self.deck_tree.heading("due", text="Невыученные")
        self.deck_tree.column("name", width=220)
        self.deck_tree.bind("<<TreeviewSelect>>", self._on_deck_select)
        self.deck_tree.pack(fill="both", expand=True, side=tk.LEFT, padx=(0, 5))

        # визуальное улучшение: полосатые строки
        self.deck_tree.tag_configure("evenrow", background="#ffffff")
        self.deck_tree.tag_configure("oddrow", background="#f7f9fc")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.deck_tree.yview)
        self.deck_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        buttons_frame = ttk.Frame(self, style="Toolbar.TFrame")
        buttons_frame.pack(fill="x", pady=(5, 10))

        ttk.Button(
            buttons_frame,
            text="Менеджер колод",
            command=self.open_deck_manager,
            style="Secondary.TButton",
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame,
            text="Редактор карточек",
            command=self.open_note_editor,
            style="Secondary.TButton",
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame,
            text="Сессия повторения",
            command=self.open_review_session,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame,
            text="Прогресс",
            command=self.open_progress_window,
            style="Secondary.TButton",
        ).pack(side=tk.LEFT, padx=5)

        status_bar = ttk.Frame(self, style="StatusBar.TFrame", padding=8)
        status_bar.pack(fill="x", side=tk.BOTTOM)
        ttk.Label(status_bar, textvariable=self.stats_vars["time"], style="Status.TLabel").pack(
            side=tk.RIGHT
        )

    def refresh_data(self) -> None:
        self._load_decks()
        self._load_stats()

    def _load_decks(self) -> None:
        try:
            self.decks = models.list_decks(self.user["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить колоды: {exc}")
            self.decks = []
            return

        self.deck_tree.delete(*self.deck_tree.get_children())
        for idx, deck in enumerate(self.decks):
            self.deck_tree.insert(
                "",
                tk.END,
                iid=deck["id"],
                values=(deck["name"], deck["total_cards"], deck["learned_cards"], deck["due_now"]),
                tags=(("evenrow") if idx % 2 == 0 else ("oddrow")),
            )
        if self.decks:
            first_id = self.decks[0]["id"]
            self.deck_tree.selection_set(first_id)
            self.selected_deck_id = first_id
        else:
            self.selected_deck_id = None

    def _load_stats(self) -> None:
        try:
            stats = models.get_summary_counts(self.user["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить статистику: {exc}")
            stats = {"reviewed_today": 0, "due_now": 0, "learned": 0, "success_7": 0, "success_30": 0}
        self.stats_vars["reviewed_today"].set(str(stats.get("reviewed_today", 0)))
        self.stats_vars["due_now"].set(str(stats.get("due_now", 0)))
        self.stats_vars["learned"].set(str(stats.get("learned", 0)))
        self.stats_vars["success_7"].set(f"{round(stats.get('success_7', 0) * 100):.0f}%")
        self.stats_vars["success_30"].set(f"{round(stats.get('success_30', 0) * 100):.0f}%")

    def _tick_clock(self) -> None:
        self.stats_vars["time"].set(datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _on_deck_select(self, _event: tk.Event) -> None:
        selection = self.deck_tree.selection()
        if selection:
            self.selected_deck_id = selection[0]

    def open_deck_manager(self) -> None:
        if self._deck_manager and self._deck_manager.winfo_exists():
            self._deck_manager.focus()
            return
        self._deck_manager = DeckManagerWindow(self, self.user)

    def open_note_editor(self) -> None:
        if not self.decks:
            messagebox.showinfo("Нет колод", "Создайте колоду, прежде чем добавлять карточки")
            return
        if self._note_editor and self._note_editor.winfo_exists():
            self._note_editor.focus()
            return
        self._note_editor = NoteEditorWindow(self, self.user, self.decks, self.selected_deck_id)

    def open_review_session(self) -> None:
        if self._review_window and self._review_window.winfo_exists():
            self._review_window.focus()
            return
        self._review_window = ReviewSessionWindow(self, self.user, self.selected_deck_id)

    def open_progress_window(self) -> None:
        if self._progress_window and self._progress_window.winfo_exists():
            self._progress_window.focus()
            return
        self._progress_window = ProgressWindow(self, self.user)

    def refresh_from_child(self) -> None:
        """Обновляет данные после изменений из дочерних окон."""
        self.refresh_data()


def show_error(message: str) -> None:
    messagebox.showerror("Ошибка", message)
