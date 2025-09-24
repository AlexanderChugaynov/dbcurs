"""Точка входа в приложение."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, Optional

import models
from db import apply_migrations, close_pool
from views.main_window import MainWindow


class LoginFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, on_login: Callable[[Dict[str, str]], None]):
        super().__init__(master)
        self.on_login = on_login
        self.email_var = tk.StringVar()
        self.users_list: list[Dict[str, str]] = []

        self._build_ui()
        self.refresh_users()

    def _build_ui(self) -> None:
        ttk.Label(self, text="Вход", font=("TkDefaultFont", 14, "bold")).pack(pady=10)

        form = ttk.Frame(self)
        form.pack(padx=20, pady=10, fill="x")

        ttk.Label(form, text="Email:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_entry = ttk.Entry(form, textvariable=self.email_var, width=30)
        email_entry.grid(row=0, column=1, padx=5, pady=5)
        email_entry.bind("<Return>", lambda _e: self.login())

        ttk.Label(form, text="Существующие пользователи:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.user_combo = ttk.Combobox(form, state="readonly")
        self.user_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.user_combo.bind("<<ComboboxSelected>>", self._on_user_selected)

        buttons = ttk.Frame(self)
        buttons.pack(pady=10)
        ttk.Button(buttons, text="Обновить список", command=self.refresh_users).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Войти", command=self.login).pack(side=tk.LEFT, padx=5)

        form.columnconfigure(1, weight=1)

    def refresh_users(self) -> None:
        try:
            self.users_list = models.list_users()
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить пользователей: {exc}")
            self.users_list = []
        self.user_combo["values"] = [user["email"] for user in self.users_list]

    def _on_user_selected(self, _event: tk.Event) -> None:
        selection = self.user_combo.get()
        self.email_var.set(selection)

    def login(self) -> None:
        email = self.email_var.get().strip()
        if not email:
            messagebox.showerror("Ошибка", "Введите email")
            return
        try:
            user = models.get_or_create_user(email)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось войти: {exc}")
            return
        self.on_login(user)


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Интервальные повторения")
        self.geometry("900x600")
        self.minsize(800, 500)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.login_frame: Optional[LoginFrame] = None
        self.main_window: Optional[MainWindow] = None

        self.show_login()

    def show_login(self) -> None:
        if self.main_window:
            self.main_window.destroy()
            self.main_window = None
        self.login_frame = LoginFrame(self, self.on_login_success)
        self.login_frame.pack(fill="both", expand=True)

    def on_login_success(self, user: Dict[str, str]) -> None:
        if self.login_frame:
            self.login_frame.destroy()
            self.login_frame = None
        self.main_window = MainWindow(self, user)
        self.main_window.pack(fill="both", expand=True)

    def on_close(self) -> None:
        if messagebox.askokcancel("Выход", "Закрыть приложение?"):
            close_pool()
            self.destroy()


def main() -> None:
    try:
        apply_migrations()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Ошибка", f"Не удалось применить миграции: {exc}")
        root.destroy()
        sys.exit(1)

    app = Application()
    app.mainloop()
    close_pool()


if __name__ == "__main__":
    main()
