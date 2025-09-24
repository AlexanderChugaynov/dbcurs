"""Окно управления колодами."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict

import models


class DeckManagerWindow(tk.Toplevel):
    def __init__(self, parent: "MainWindow", user: Dict[str, str]):
        super().__init__(parent)
        self.parent_view = parent
        self.user = user
        self.title("Менеджер колод")
        self.geometry("480x360")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.configure(bg="#eef1f7")

        container = ttk.Frame(self, style="App.TFrame", padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Мои колоды", style="Title.TLabel").pack(anchor="w", pady=(0, 12))

        tree_frame = ttk.Frame(container, style="Card.TFrame", padding=10)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("name", "total"), show="headings", style="Dashboard.Treeview")
        self.tree.heading("name", text="Название")
        self.tree.heading("total", text="Карточек")
        self.tree.column("name", width=250)
        self.tree.pack(fill="both", expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        button_frame = ttk.Frame(container, style="Toolbar.TFrame")
        button_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(button_frame, text="Добавить", command=self.add_deck, style="Accent.TButton").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Редактировать", command=self.edit_deck, style="Secondary.TButton").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Удалить", command=self.delete_deck, style="Secondary.TButton").pack(
            side=tk.LEFT, padx=5
        )

        # контекстное меню
        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(label="Добавить", command=self.add_deck)
        self._context_menu.add_command(label="Переименовать", command=self.edit_deck)
        self._context_menu.add_command(label="Удалить", command=self.delete_deck)

        # бинды
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.bind("<Control-n>", lambda _e: self.add_deck())
        self.bind("<F2>", lambda _e: self.edit_deck())
        self.bind("<Delete>", lambda _e: self.delete_deck())

        self.refresh_decks()

    def refresh_decks(self) -> None:
        try:
            decks = models.list_decks(self.user["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить колоды: {exc}")
            return
        self.tree.delete(*self.tree.get_children())
        for deck in decks:
            self.tree.insert("", tk.END, iid=deck["id"], values=(deck["name"], deck["total_cards"]))

    def add_deck(self) -> None:
        name = simpledialog.askstring("Новая колода", "Название колоды:", parent=self)
        if not name:
            return
        description = simpledialog.askstring("Описание", "Описание колоды (опционально):", parent=self)
        try:
            models.create_deck(self.user["id"], name, description)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось создать колоду: {exc}")
            return
        self.refresh_decks()
        self.parent_view.refresh_from_child()

    def edit_deck(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Выбор", "Выберите колоду для редактирования")
            return
        deck_id = selection[0]
        current_name = self.tree.set(deck_id, "name")
        new_name = simpledialog.askstring("Редактирование", "Название:", initialvalue=current_name, parent=self)
        if not new_name:
            return
        description = simpledialog.askstring("Описание", "Описание (опционально):", parent=self)
        try:
            models.update_deck(deck_id, self.user["id"], new_name, description)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось обновить колоду: {exc}")
            return
        self.refresh_decks()
        self.parent_view.refresh_from_child()

    def delete_deck(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Удаление", "Выберите колоду для удаления")
            return
        deck_id = selection[0]
        if not messagebox.askyesno(
            "Удаление", "Удалить выбранную колоду и связанные карточки?",
        ):
            return
        try:
            models.delete_deck(deck_id, self.user["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось удалить колоду: {exc}")
            return
        self.refresh_decks()
        self.parent_view.refresh_from_child()

    def on_close(self) -> None:
        self.destroy()
        self.parent_view._deck_manager = None

    def _on_tree_double_click(self, event: tk.Event) -> None:
        # переименовываем по даблклику по строке
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        self.edit_deck()

    def _on_tree_right_click(self, event: tk.Event) -> None:
        # показываем контекстное меню
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()
