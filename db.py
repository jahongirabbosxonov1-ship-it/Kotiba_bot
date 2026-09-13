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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tur TEXT NOT NULL CHECK (tur IN ('men_qarzdorman', 'mendan_qarzdor')),
                ism TEXT NOT NULL,
                summa REAL NOT NULL,
                sana_berilgan TEXT NOT NULL,
                muddat TEXT,
                holat TEXT NOT NULL DEFAULT 'tolanmagan' CHECK (holat IN ('tolanmagan', 'tolangan')),
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


def get_totals(user_id: int, sana_dan: str | None = None, sana_gacha: str | None = None):
    """(jami_kirim, jami_chiqim) qaytaradi. sana_dan/sana_gacha 'YYYY-MM-DD' shaklida,
    sana_gacha oxirgi kunni o'z ichiga olmaydi (exclusive)."""
    query = "SELECT tur, COALESCE(SUM(summa), 0) AS jami FROM transactions WHERE user_id = ?"
    params: list = [user_id]
    if sana_dan is not None:
        query += " AND sana >= ?"
        params.append(sana_dan)
    if sana_gacha is not None:
        query += " AND sana < ?"
        params.append(sana_gacha)
    query += " GROUP BY tur"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    jami_kirim = 0.0
    jami_chiqim = 0.0
    for row in rows:
        if row["tur"] == "kirim":
            jami_kirim = row["jami"]
        elif row["tur"] == "chiqim":
            jami_chiqim = row["jami"]
    return jami_kirim, jami_chiqim


def get_debts(user_id: int, tur: str, faqat_tolanmagan: bool = True):
    query = "SELECT * FROM debts WHERE user_id = ? AND tur = ?"
    params: list = [user_id, tur]
    if faqat_tolanmagan:
        query += " AND holat = 'tolanmagan'"
    query += " ORDER BY id"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
