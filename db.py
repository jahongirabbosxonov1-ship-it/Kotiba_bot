import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "kotiba.db"


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sana TEXT NOT NULL,
                tur TEXT NOT NULL CHECK (tur IN ('kirim', 'chiqim')),
                summa REAL NOT NULL,
                tavsif TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def add_transaction(user_id: int, sana: str, tur: str, summa: float, tavsif: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO transactions (user_id, sana, tur, summa, tavsif) VALUES (?, ?, ?, ?, ?)",
            (user_id, sana, tur, summa, tavsif),
        )
        return cur.lastrowid


def get_recent_transactions(user_id: int, limit: int = 5):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
