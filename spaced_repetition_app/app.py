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

        self.configure(style="App.TFrame", padding=30)
        self.columnconfigure(0, weight=1)

        self._build_ui()
        self.refresh_users()

    def _build_ui(self) -> None:
        ttk.Label(self, text="Добро пожаловать", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Введите email для входа или выберите существующего пользователя",
            style="Subtitle.TLabel",
            wraplength=360,
        ).grid(row=1, column=0, sticky="w", pady=(4, 20))

        form = ttk.Frame(self, style="Card.TFrame", padding=20)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Email:", style="FormLabel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=6
        )
        email_entry = ttk.Entry(form, textvariable=self.email_var, width=30)
        email_entry.grid(row=0, column=1, sticky="ew", padx=0, pady=6)
        email_entry.bind("<Return>", lambda _e: self.login())

        ttk.Label(form, text="Существующие пользователи:", style="FormLabel.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=6
        )
        self.user_combo = ttk.Combobox(form, state="readonly")
        self.user_combo.grid(row=1, column=1, sticky="ew", padx=0, pady=6)
        self.user_combo.bind("<<ComboboxSelected>>", self._on_user_selected)

        buttons = ttk.Frame(self, style="App.TFrame")
        buttons.grid(row=3, column=0, pady=25, sticky="ew")
        ttk.Button(
            buttons,
            text="Обновить список",
            command=self.refresh_users,
            style="Secondary.TButton",
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Войти", command=self.login, style="Accent.TButton").pack(
            side=tk.RIGHT, padx=5
        )

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

        self._configure_style()

        self.login_frame: Optional[LoginFrame] = None
        self.main_window: Optional[MainWindow] = None

        self.show_login()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        base_bg = "#eef1f7"
        card_bg = "#ffffff"
        accent = "#4e79a7"
        accent_hover = "#5b8cc0"
        accent_pressed = "#3f5f82"

        self.configure(bg=base_bg)

        style.configure("App.TFrame", background=base_bg)
        style.configure("Title.TLabel", background=base_bg, font=("Segoe UI", 18, "bold"), foreground="#1f2933")
        style.configure(
            "Subtitle.TLabel",
            background=base_bg,
            font=("Segoe UI", 11),
            foreground="#4a5568",
        )
        style.configure("FormLabel.TLabel", background=card_bg, font=("Segoe UI", 10), foreground="#4a5568")
        style.configure("MetricCaption.TLabel", background=card_bg, font=("Segoe UI", 10), foreground="#4a5568")
        style.configure("MetricValue.TLabel", background=card_bg, font=("Segoe UI", 16, "bold"), foreground=accent)
        style.configure("Card.TFrame", background=card_bg, relief="flat", borderwidth=1)
        style.configure(
            "Card.TLabelframe",
            background=card_bg,
            borderwidth=0,
            padding=12,
            relief="ridge",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=base_bg,
            foreground="#1f2933",
            font=("Segoe UI", 11, "bold"),
        )
        style.configure("StatusBar.TFrame", background="#dbeafe")
        style.configure("Status.TLabel", background="#dbeafe", foreground="#1f2933", font=("Segoe UI", 10))

        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 8),
            background=accent,
            foreground="white",
        )
        style.map(
            "Accent.TButton",
            background=[("pressed", accent_pressed), ("active", accent_hover)],
            foreground=[("disabled", "#d4d4d4"), ("!disabled", "white")],
        )
        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10),
            padding=(14, 8),
            background="#ffffff",
            foreground=accent,
        )
        style.map(
            "Secondary.TButton",
            background=[("pressed", "#cbd5f5"), ("active", "#e0e7ff")],
            foreground=[("disabled", "#9ca3af"), ("!disabled", accent)],
            bordercolor=[("focus", accent)],
        )

        style.configure(
            "Dashboard.Treeview",
            background=card_bg,
            fieldbackground=card_bg,
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.map(
            "Dashboard.Treeview",
            background=[("selected", "#cbd5f5")],
            foreground=[("selected", "#1f2933")],
        )
        style.configure(
            "Dashboard.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=accent,
            foreground="white",
            relief="flat",
            padding=8,
        )
        style.map(
            "Dashboard.Treeview.Heading",
            background=[("active", accent_hover)],
        )
        style.layout(
            "Dashboard.Treeview.Heading",
            [
                (
                    "Treeheading.cell",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Treeheading.border",
                                {
                                    "sticky": "nswe",
                                    "children": [("Treeheading.padding", {"sticky": "nswe"})],
                                },
                            )
                        ],
                    },
                )
            ],
        )

        style.configure(
            "Flashcard.TFrame",
            background=card_bg,
            relief="flat",
            padding=18,
        )
        style.configure(
            "FlashcardFront.TLabel",
            background=card_bg,
            foreground="#1f2933",
            font=("Segoe UI", 16, "bold"),
            wraplength=540,
            anchor="center",
            padding=10,
        )
        style.configure(
            "FlashcardBack.TLabel",
            background="#fdf8e1",
            foreground="#1f2933",
            font=("Segoe UI", 13),
            wraplength=540,
            anchor="center",
            padding=10,
        )

        style.configure("Toolbar.TFrame", background=base_bg)

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
