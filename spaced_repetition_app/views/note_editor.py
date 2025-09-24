"""Окно управления карточками."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import models


class NoteEditorWindow(tk.Toplevel):
    def __init__(
        self,
        parent: "MainWindow",
        user: Dict[str, str],
        decks: List[Dict[str, str]],
        initial_deck_id: Optional[str],
    ):
        super().__init__(parent)
        self.parent_view = parent
        self.user = user
        self.decks = decks
        self.deck_map = {deck["name"]: deck["id"] for deck in decks}
        self.notes: List[Dict[str, Any]] = []

        self.title("Карточки")
        self.geometry("800x500")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.configure(bg="#eef1f7")

        self.container = ttk.Frame(self, style="App.TFrame", padding=15)
        self.container.pack(fill="both", expand=True)

        ttk.Label(self.container, text="Карточки", style="Title.TLabel").pack(anchor="w", pady=(0, 10))

        self.deck_var = tk.StringVar()
        if initial_deck_id:
            name = next((deck["name"] for deck in decks if deck["id"] == initial_deck_id), "")
            self.deck_var.set(name)

        self.search_var = tk.StringVar()
        self.tags_var = tk.StringVar()

        self._build_filters()
        self._build_table()
        self._build_buttons()

        self.refresh_notes()

    def _build_filters(self) -> None:
        frame = ttk.LabelFrame(self.container, text="Фильтры", style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 12))

        ttk.Label(frame, text="Колода:", style="FormLabel.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.deck_combo = ttk.Combobox(
            frame,
            textvariable=self.deck_var,
            values=list(self.deck_map.keys()),
            state="readonly",
        )
        self.deck_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.deck_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_notes())

        ttk.Label(frame, text="Поиск:", style="FormLabel.TLabel").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        entry_search = ttk.Entry(frame, textvariable=self.search_var)
        entry_search.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        entry_search.bind("<Return>", lambda _e: self.refresh_notes())

        ttk.Label(frame, text="Теги (через запятую):", style="FormLabel.TLabel").grid(
            row=0, column=4, padx=5, pady=5, sticky="w"
        )
        entry_tags = ttk.Entry(frame, textvariable=self.tags_var)
        entry_tags.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        entry_tags.bind("<Return>", lambda _e: self.refresh_notes())

        ttk.Button(frame, text="Применить", command=self.refresh_notes, style="Accent.TButton").grid(
            row=0, column=6, padx=5, pady=5
        )
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(5, weight=1)

    def _build_table(self) -> None:
        tree_frame = ttk.Frame(self.container, style="Card.TFrame", padding=10)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("front", "back", "deck", "tags", "updated"),
            show="headings",
            style="Dashboard.Treeview",
        )
        self.tree.heading("front", text="Front")
        self.tree.heading("back", text="Back")
        self.tree.heading("deck", text="Колода")
        self.tree.heading("tags", text="Теги")
        self.tree.heading("updated", text="Обновлено")
        self.tree.column("front", width=200)
        self.tree.column("back", width=200)
        self.tree.column("deck", width=120)
        self.tree.column("tags", width=120)
        self.tree.pack(fill="both", expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill="y")

    def _build_buttons(self) -> None:
        frame = ttk.Frame(self.container, style="Toolbar.TFrame")
        frame.pack(fill="x", pady=(10, 0))
        ttk.Button(frame, text="Добавить", command=self.add_note, style="Accent.TButton").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(frame, text="Редактировать", command=self.edit_note, style="Secondary.TButton").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(frame, text="Удалить", command=self.delete_note, style="Secondary.TButton").pack(
            side=tk.LEFT, padx=5
        )

    def _current_deck_id(self) -> Optional[str]:
        name = self.deck_var.get()
        return self.deck_map.get(name) if name else None

    def refresh_notes(self) -> None:
        deck_id = self._current_deck_id()
        tags = [tag.strip() for tag in self.tags_var.get().split(",") if tag.strip()]
        search = self.search_var.get().strip() or None
        try:
            self.notes = models.list_notes(self.user["id"], deck_id=deck_id, tags=tags or None, search=search)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить карточки: {exc}")
            return
        self.tree.delete(*self.tree.get_children())
        for note in self.notes:
            tags_str = ", ".join(note.get("tags", []))
            self.tree.insert(
                "",
                tk.END,
                iid=note["id"],
                values=(note["front"], note["back"], note.get("deck_name", ""), tags_str, note["updated_at"]),
            )

    def add_note(self) -> None:
        NoteForm(self, self.user, self.decks, on_saved=self._on_note_saved)

    def edit_note(self) -> None:
        note_id = self._selected_note_id()
        if not note_id:
            messagebox.showinfo("Редактирование", "Выберите карточку для редактирования")
            return
        try:
            note = models.get_note_details(note_id, self.user["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить карточку: {exc}")
            return
        if not note:
            messagebox.showerror("Ошибка", "Карточка не найдена")
            return
        NoteForm(self, self.user, self.decks, note=note, on_saved=self._on_note_saved)

    def delete_note(self) -> None:
        note_id = self._selected_note_id()
        if not note_id:
            messagebox.showinfo("Удаление", "Выберите карточку для удаления")
            return
        if not messagebox.askyesno("Удаление", "Удалить выбранную карточку?"):
            return
        try:
            models.delete_note(note_id, self.user["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось удалить карточку: {exc}")
            return
        self.refresh_notes()
        self.parent_view.refresh_from_child()

    def _selected_note_id(self) -> Optional[str]:
        selection = self.tree.selection()
        if selection:
            return selection[0]
        return None

    def _on_note_saved(self) -> None:
        self.refresh_notes()
        self.parent_view.refresh_from_child()

    def on_close(self) -> None:
        self.destroy()
        self.parent_view._note_editor = None


class NoteForm(tk.Toplevel):
    def __init__(
        self,
        parent: NoteEditorWindow,
        user: Dict[str, str],
        decks: List[Dict[str, str]],
        note: Optional[Dict[str, Any]] = None,
        on_saved: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.parent_editor = parent
        self.user = user
        self.decks = decks
        self.note = note
        self.on_saved = on_saved

        self.title("Новая карточка" if note is None else "Редактирование карточки")
        self.geometry("500x450")
        self.resizable(False, False)
        self.configure(bg="#eef1f7")

        self.deck_var = tk.StringVar()
        deck_name = ""
        if note:
            deck_name = next((d["name"] for d in decks if d["id"] == note.get("deck_id")), "")
        elif parent._current_deck_id():
            deck_name = next((d["name"] for d in decks if d["id"] == parent._current_deck_id()), "")
        self.deck_var.set(deck_name)

        self.tags_var = tk.StringVar()
        if note:
            self.tags_var.set(", ".join(note.get("tags", [])))

        self._build_form()

        if note:
            self.front_text.insert("1.0", note.get("front", ""))
            self.back_text.insert("1.0", note.get("back", ""))
        self.front_text.focus_set()
        self.transient(parent)
        self.grab_set()

    def _build_form(self) -> None:
        frame = ttk.Frame(self, style="App.TFrame", padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Колода:", style="FormLabel.TLabel").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        combo = ttk.Combobox(
            frame,
            textvariable=self.deck_var,
            values=[d["name"] for d in self.decks],
            state="readonly",
        )
        combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(frame, text="Front:", style="FormLabel.TLabel").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        self.front_text = tk.Text(
            frame,
            height=6,
            relief="flat",
            bg="#ffffff",
            font=("Segoe UI", 11),
            wrap="word",
        )
        self.front_text.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(frame, text="Back:", style="FormLabel.TLabel").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        self.back_text = tk.Text(
            frame,
            height=6,
            relief="flat",
            bg="#ffffff",
            font=("Segoe UI", 11),
            wrap="word",
        )
        self.back_text.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(frame, text="Теги:", style="FormLabel.TLabel").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.tags_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)

        button_frame = ttk.Frame(frame, style="Toolbar.TFrame")
        button_frame.grid(row=4, column=1, sticky="e", padx=5, pady=15)
        ttk.Button(button_frame, text="Сохранить", command=self.save, style="Accent.TButton").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Отмена", command=self.cancel, style="Secondary.TButton").pack(
            side=tk.LEFT, padx=5
        )

        frame.columnconfigure(1, weight=1)

    def save(self) -> None:
        deck_name = self.deck_var.get()
        deck_id = next((d["id"] for d in self.decks if d["name"] == deck_name), None)
        if not deck_id:
            messagebox.showerror("Ошибка", "Выберите колоду")
            return
        front = self.front_text.get("1.0", tk.END).strip()
        back = self.back_text.get("1.0", tk.END).strip()
        if not front or not back:
            messagebox.showerror("Ошибка", "Заполните поля front и back")
            return
        tags = [t.strip() for t in self.tags_var.get().split(",") if t.strip()]
        try:
            if self.note:
                models.update_note(
                    self.note["id"],
                    self.user["id"],
                    deck_id,
                    front,
                    back,
                    tags,
                )
            else:
                models.create_note(self.user["id"], deck_id, front, back, tags)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить карточку: {exc}")
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def cancel(self) -> None:
        self.destroy()

    def destroy(self) -> None:  # type: ignore[override]
        if isinstance(self.parent_editor, NoteEditorWindow):
            try:
                self.grab_release()
            except tk.TclError:
                pass
        super().destroy()
