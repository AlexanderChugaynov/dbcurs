"""Слой доступа к данным и сервисные функции."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from db import get_connection


def _dict_fetchall(cursor: RealDictCursor) -> List[Dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def get_or_create_user(email: str) -> Dict[str, Any]:
    email = email.strip().lower()
    if not email:
        raise ValueError("Email не может быть пустым")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO users(email) VALUES (%s) ON CONFLICT(email) DO UPDATE SET email = EXCLUDED.email RETURNING *",
                (email,),
            )
            conn.commit()
            return dict(cur.fetchone())


def list_users() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, email FROM users ORDER BY email")
            return _dict_fetchall(cur)


def list_decks(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.name,
                       d.description,
                       COALESCE(dp.total_cards, 0) AS total_cards,
                       COALESCE(dp.learned_cards, 0) AS learned_cards,
                       COALESCE(dp.due_now, 0) AS due_now
                FROM decks d
                LEFT JOIN v_deck_progress dp ON dp.deck_id = d.id
                WHERE d.user_id = %s
                ORDER BY d.created_at
                """,
                (user_id,),
            )
            return _dict_fetchall(cur)


def create_deck(user_id: str, name: str, description: str | None = None) -> Dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO decks(user_id, name, description) VALUES (%s, %s, %s) RETURNING *",
                (user_id, name, description),
            )
            deck = dict(cur.fetchone())
            conn.commit()
            return deck


def update_deck(deck_id: str, user_id: str, name: str, description: str | None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE decks SET name = %s, description = %s WHERE id = %s AND user_id = %s",
                (name, description, deck_id, user_id),
            )
            conn.commit()


def delete_deck(deck_id: str, user_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM decks WHERE id = %s AND user_id = %s", (deck_id, user_id))
            conn.commit()


def list_notes(
    user_id: str,
    deck_id: str | None = None,
    tags: Iterable[str] | None = None,
    search: str | None = None,
) -> List[Dict[str, Any]]:
    filters = [sql.SQL("n.user_id = %s")]
    params: List[Any] = [user_id]

    if deck_id:
        filters.append(sql.SQL("n.deck_id = %s"))
        params.append(deck_id)
    if search:
        filters.append(sql.SQL("(n.front ILIKE %s OR n.back ILIKE %s)"))
        params.extend([f"%{search}%", f"%{search}%"])
    if tags:
        tag_list = list({t.strip().lower() for t in tags if t.strip()})
        if tag_list:
            filters.append(
                sql.SQL(
                    "n.id IN (SELECT nt.note_id FROM note_tags nt JOIN tags t ON t.id = nt.tag_id WHERE lower(t.name) = ANY(%s))"
                )
            )
            params.append(tag_list)

    where_clause = sql.SQL(" AND ").join(filters)
    query = sql.SQL(
        """
        SELECT n.id,
               n.deck_id,
               n.front,
               n.back,
               n.updated_at,
               d.name AS deck_name,
               COALESCE(array_agg(DISTINCT t.name) FILTER (WHERE t.name IS NOT NULL), ARRAY[]::text[]) AS tags
        FROM notes n
        JOIN decks d ON d.id = n.deck_id
        LEFT JOIN note_tags nt ON nt.note_id = n.id
        LEFT JOIN tags t ON t.id = nt.tag_id
        WHERE {where}
        GROUP BY n.id, d.name
        ORDER BY n.updated_at DESC
        """
    ).format(where=where_clause)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return _dict_fetchall(cur)


def create_note(user_id: str, deck_id: str, front: str, back: str, tags: Iterable[str] | None) -> str:
    tags_array = _prepare_tags(tags)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT add_note_with_card(%s, %s, %s, %s, %s)",
                (user_id, deck_id, front, back, tags_array),
            )
            card_id = cur.fetchone()[0]
            conn.commit()
            return str(card_id)


def update_note(
    note_id: str,
    user_id: str,
    deck_id: str,
    front: str,
    back: str,
    tags: Iterable[str] | None,
) -> None:
    tags_array = _prepare_tags(tags)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notes SET deck_id = %s, front = %s, back = %s WHERE id = %s AND user_id = %s",
                (deck_id, front, back, note_id, user_id),
            )
            cur.execute("DELETE FROM note_tags WHERE note_id = %s", (note_id,))
            if tags_array:
                cur.execute(
                    "SELECT ensure_tag(x) FROM unnest(%s) AS x",
                    (tags_array,),
                )
                cur.execute(
                    "INSERT INTO note_tags(note_id, tag_id) SELECT %s, t.id FROM tags t WHERE lower(t.name) = ANY(%s)",
                    (note_id, [tag.lower() for tag in tags_array]),
                )
            conn.commit()


def delete_note(note_id: str, user_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notes WHERE id = %s AND user_id = %s", (note_id, user_id))
            conn.commit()


def get_due_queue(user_id: str, deck_id: str | None = None, limit: int = 50) -> List[Dict[str, Any]]:
    params: List[Any] = [user_id]
    deck_filter = ""
    if deck_id:
        deck_filter = " AND dq.deck_id = %s"
        params.append(deck_id)
    query = (
        "SELECT dq.card_id, dq.deck_id, dq.note_id, dq.front, dq.back, dq.due_at, dq.deck_name "
        "FROM v_due_queue dq WHERE dq.user_id = %s AND dq.due_at <= now() + interval '7 days'"
        + deck_filter
        + " ORDER BY dq.due_at LIMIT %s"
    )
    params.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return _dict_fetchall(cur)


def record_review(user_id: str, card_id: str, quality: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT apply_sm2(%s::uuid, %s::uuid, %s::smallint)",
                (user_id, card_id, quality),
            )
            conn.commit()


def suspend_card(user_id: str, card_id: str, suspended: bool = True) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE card_state SET suspended = %s WHERE card_id = %s AND user_id = %s",
                (suspended, card_id, user_id),
            )
            conn.commit()


def get_summary_counts(user_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN due_at <= now() AND suspended = false THEN 1 ELSE 0 END), 0) AS due_now,
                    COALESCE(SUM(CASE WHEN reps > 0 THEN 1 ELSE 0 END), 0) AS learned
                FROM card_state
                WHERE user_id = %s
                """,
                (user_id,),
            )
            summary = dict(cur.fetchone())

            cur.execute(
                """
                SELECT
                    COALESCE(COUNT(*) FILTER (WHERE reviewed_at::date = CURRENT_DATE), 0) AS reviewed_today,
                    COALESCE(AVG((quality >= 3)::int) FILTER (WHERE reviewed_at >= now() - interval '7 days'), 0) AS success_7,
                    COALESCE(AVG((quality >= 3)::int) FILTER (WHERE reviewed_at >= now() - interval '30 days'), 0) AS success_30
                FROM reviews
                WHERE user_id = %s
                """,
                (user_id,),
            )
            rates = dict(cur.fetchone())
            summary.update(rates)
            return summary


def get_daily_stats(user_id: str, days: int = 30) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH span AS (
                    SELECT generate_series(
                        (CURRENT_DATE - (%s::int - 1))::date,
                        CURRENT_DATE,
                        interval '1 day'
                    ) AS day
                ), stats AS (
                    SELECT
                        (date_trunc('day', reviewed_at))::date AS day,
                        COUNT(*) AS reviews_count,
                        AVG(CASE WHEN quality >= 3 THEN 1.0 ELSE 0.0 END) AS success_rate
                    FROM reviews
                    WHERE user_id = %s AND reviewed_at >= (CURRENT_DATE - (%s::int - 1))
                    GROUP BY 1
                )
                SELECT
                    span.day::date AS day,
                    COALESCE(stats.reviews_count, 0) AS reviews_count,
                    COALESCE(stats.success_rate, 0) AS success_rate
                FROM span
                LEFT JOIN stats ON stats.day = span.day::date
                ORDER BY span.day
                """,
                (days, user_id, days),
            )
            return _dict_fetchall(cur)


def get_deck_progress(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT deck_id, name, total_cards, learned_cards, due_now FROM v_deck_progress WHERE user_id = %s",
                (user_id,),
            )
            return _dict_fetchall(cur)


def get_note_details(note_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT n.id,
                       n.deck_id,
                       n.front,
                       n.back,
                       COALESCE(array_agg(t.name) FILTER (WHERE t.name IS NOT NULL), ARRAY[]::text[]) AS tags
                FROM notes n
                LEFT JOIN note_tags nt ON nt.note_id = n.id
                LEFT JOIN tags t ON t.id = nt.tag_id
                WHERE n.id = %s AND n.user_id = %s
                GROUP BY n.id
                """,
                (note_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _prepare_tags(tags: Iterable[str] | None) -> List[str] | None:
    if not tags:
        return None
    normalized = [tag.strip() for tag in tags if tag and tag.strip()]
    return list({t for t in normalized}) or None
