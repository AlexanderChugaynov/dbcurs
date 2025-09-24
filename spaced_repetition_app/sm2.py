"""Реализация алгоритма SM-2 для локальных вычислений."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple


@dataclass
class CardState:
    """Состояние карточки для вычисления алгоритма SM-2."""

    ease_factor: float = 2.5
    interval_days: int = 0
    reps: int = 0
    lapses: int = 0
    due_at: datetime | None = None


def sm2(schedule: CardState, quality: int, now: datetime | None = None) -> Tuple[CardState, int]:
    """Возвращает новое состояние карточки и количество дней до следующего показа."""
    if quality < 0 or quality > 5:
        raise ValueError("Оценка качества должна быть между 0 и 5")

    now = now or datetime.utcnow()
    ease_factor = schedule.ease_factor
    reps = schedule.reps
    lapses = schedule.lapses

    if quality < 3:
        reps = 0
        lapses += 1
        interval = 1
        ease_factor = max(1.3, ease_factor - 0.2)
    else:
        reps += 1
        if schedule.reps == 0:
            interval = 1
        elif schedule.reps == 1:
            interval = 6
        else:
            interval = int(round(schedule.interval_days * ease_factor))
            interval = max(interval, 1)
        ease_factor = max(
            1.3,
            ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
        )

    due_at = now + timedelta(days=interval)
    new_state = CardState(
        ease_factor=ease_factor,
        interval_days=interval,
        reps=reps,
        lapses=lapses,
        due_at=due_at,
    )
    return new_state, interval
