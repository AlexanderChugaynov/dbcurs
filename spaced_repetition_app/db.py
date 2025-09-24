"""Модуль управления подключением к PostgreSQL и миграциями."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg2
from dotenv import load_dotenv
from psycopg2.pool import SimpleConnectionPool

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "spaced_repetition")
DB_USER = os.getenv("DB_USER", "spaced_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "spaced_password")

_pool: SimpleConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 10) -> SimpleConnectionPool:
    """Создаёт пул соединений при первом обращении."""
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn,
            maxconn,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    return _pool


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Предоставляет соединение из пула."""
    pool = init_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def apply_migrations() -> None:
    """Применяет SQL-скрипты из каталога sql/ в алфавитном порядке."""
    sql_dir = Path(__file__).resolve().parent / "sql"
    if not sql_dir.exists():
        return

    with get_connection() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()

        scripts = sorted(sql_dir.glob("*.sql"))
        for script in scripts:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM schema_migrations WHERE filename = %s", (script.name,))
                if cur.fetchone():
                    continue
                sql = script.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations(filename) VALUES (%s)", (script.name,)
                )
                conn.commit()


def close_pool() -> None:
    """Закрывает пул соединений при завершении работы."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
