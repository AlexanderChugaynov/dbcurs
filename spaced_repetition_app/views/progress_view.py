"""Окно отображения прогресса."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import models


class ProgressWindow(tk.Toplevel):
    def __init__(self, parent: "MainWindow", user: Dict[str, str]):
        super().__init__(parent)
        self.parent_view = parent
        self.user = user
        self.title("Прогресс")
        self.geometry("720x600")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.figure = Figure(figsize=(7, 6), dpi=100)
        self.ax_daily = self.figure.add_subplot(211)
        self.ax_decks = self.figure.add_subplot(212)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True, padx=10, pady=10)

        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(control_frame, text="Обновить", command=self.refresh_charts).pack(side=tk.RIGHT)

        self.refresh_charts()

    def refresh_charts(self) -> None:
        daily_stats = models.get_daily_stats(self.user["id"], days=30)
        deck_stats = models.get_deck_progress(self.user["id"])

        self.ax_daily.clear()
        self.ax_decks.clear()

        if daily_stats:
            days = [row["day"].strftime("%d.%m") for row in daily_stats]
            reviews = [row["reviews_count"] for row in daily_stats]
            success = [row["success_rate"] * 100 for row in daily_stats]

            bars = self.ax_daily.bar(days, reviews, color="#4e79a7", label="Ревью")
            self.ax_daily.set_ylabel("Количество")
            self.ax_daily.tick_params(axis="x", rotation=45)

            ax2 = self.ax_daily.twinx()
            ax2.plot(days, success, color="#e15759", marker="o", label="Успешность, %")
            ax2.set_ylim(0, 100)
            ax2.set_ylabel("Успешность, %")

            lines, labels = self.ax_daily.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.ax_daily.legend(lines + lines2, labels + labels2, loc="upper left")
            self.ax_daily.set_title("Ревью по дням")
        else:
            self.ax_daily.text(0.5, 0.5, "Нет данных", ha="center", va="center")
            self.ax_daily.set_axis_off()

        if deck_stats:
            names = [row["name"] for row in deck_stats]
            total = [row["total_cards"] for row in deck_stats]
            learned = [row["learned_cards"] for row in deck_stats]
            due = [row["due_now"] for row in deck_stats]
            indices = range(len(names))

            width = 0.25
            self.ax_decks.bar([i - width for i in indices], total, width=width, label="Всего", color="#59a14f")
            self.ax_decks.bar(indices, learned, width=width, label="Выучено", color="#edc948")
            self.ax_decks.bar([i + width for i in indices], due, width=width, label="Due", color="#af7aa1")
            self.ax_decks.set_xticks(list(indices))
            self.ax_decks.set_xticklabels(names, rotation=30, ha="right")
            self.ax_decks.set_ylabel("Карточки")
            self.ax_decks.legend()
            self.ax_decks.set_title("Прогресс по колодам")
        else:
            self.ax_decks.text(0.5, 0.5, "Нет данных", ha="center", va="center")
            self.ax_decks.set_axis_off()

        self.figure.tight_layout()
        self.canvas.draw()

    def on_close(self) -> None:
        self.destroy()
        self.parent_view._progress_window = None
