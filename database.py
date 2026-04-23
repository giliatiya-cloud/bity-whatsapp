import psycopg2
import psycopg2.extras
import sqlite3
from datetime import datetime
from pathlib import Path

import config

_USE_PG = bool(config.DATABASE_URL)


def _pg_connect():
    return psycopg2.connect(config.DATABASE_URL)


def _sqlite_connect():
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    if _USE_PG:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id BIGSERIAL PRIMARY KEY,
                        chat_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_chat
                    ON conversations (chat_id, created_at)
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS processed_messages (
                        id_message TEXT PRIMARY KEY
                    )
                """)
    else:
        with _sqlite_connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    id_message TEXT PRIMARY KEY
                )
            """)
            conn.commit()


def is_processed(id_message: str) -> bool:
    if _USE_PG:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM processed_messages WHERE id_message = %s", (id_message,))
                return cur.fetchone() is not None
    else:
        with _sqlite_connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_messages WHERE id_message = ?", (id_message,)
            ).fetchone()
            return row is not None


def mark_processed(id_message: str) -> None:
    if _USE_PG:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO processed_messages (id_message) VALUES (%s) ON CONFLICT DO NOTHING",
                    (id_message,)
                )
    else:
        with _sqlite_connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_messages (id_message) VALUES (?)", (id_message,)
            )
            conn.commit()


def append(chat_id: str, role: str, content: str) -> None:
    if _USE_PG:
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversations (chat_id, role, content) VALUES (%s, %s, %s)",
                    (chat_id, role, content)
                )
    else:
        with _sqlite_connect() as conn:
            conn.execute(
                "INSERT INTO conversations (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, role, content, datetime.utcnow().isoformat())
            )
            conn.commit()


def tail(chat_id: str, n: int = config.MAX_HISTORY) -> list[dict]:
    if _USE_PG:
        with _pg_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT role, content FROM (
                        SELECT role, content, created_at
                        FROM conversations
                        WHERE chat_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    ) sub ORDER BY created_at ASC
                """, (chat_id, n))
                return [{"role": r["role"], "content": r["content"]} for r in cur.fetchall()]
    else:
        with _sqlite_connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, created_at
                    FROM conversations
                    WHERE chat_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) ORDER BY created_at ASC
                """,
                (chat_id, n),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]
