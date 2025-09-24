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

        self.tree = ttk.Treeview(self, columns=("name", "total"), show="headings")
        self.tree.heading("name", text="Название")
        self.tree.heading("total", text="Карточек")
        self.tree.column("name", width=250)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Добавить", command=self.add_deck).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Редактировать", command=self.edit_deck).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Удалить", command=self.delete_deck).pack(side=tk.LEFT, padx=5)

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
