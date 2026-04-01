"""
SQLite storage for river readings.
Database lives at data/river.db relative to the project root.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

DB_PATH = Path(__file__).parent.parent / "data" / "river.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they do not exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT NOT NULL,
                cfs        REAL,
                height_ft  REAL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_values (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                date      TEXT NOT NULL UNIQUE,
                cfs       REAL,
                height_ft REAL
            )
        """)
        conn.commit()


def insert_reading(timestamp: str, cfs: float | None, height_ft: float | None, fetched_at: str):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO readings (timestamp, cfs, height_ft, fetched_at) VALUES (?, ?, ?, ?)",
            (timestamp, cfs, height_ft, fetched_at),
        )
        conn.commit()


def get_recent_readings(days: int = 7) -> list[dict]:
    """Return up to `days` worth of readings, newest first."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM readings WHERE fetched_at >= ? ORDER BY fetched_at DESC",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_daily_value(date: str, cfs: float | None, height_ft: float | None):
    """Insert or update a single daily record (keyed on date YYYY-MM-DD)."""
    with _connect() as conn:
        conn.execute(
            """INSERT INTO daily_values (date, cfs, height_ft) VALUES (?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET cfs=excluded.cfs, height_ft=excluded.height_ft""",
            (date, cfs, height_ft),
        )
        conn.commit()


def get_daily_values_for_year(year: int) -> list[dict]:
    """All daily_values rows for a given year, sorted ascending."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT date, cfs, height_ft FROM daily_values WHERE date LIKE ? ORDER BY date",
            (f"{year}-%",),
        ).fetchall()
    return [dict(r) for r in rows]


def count_daily_values_for_year(year: int) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM daily_values WHERE date LIKE ?",
            (f"{year}-%",),
        ).fetchone()[0]


def get_yesterday_reading() -> dict | None:
    """Most recent reading stored before today (UTC). Used for change detection."""
    today_start = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM readings WHERE fetched_at < ? ORDER BY fetched_at DESC LIMIT 1",
            (today_start,),
        ).fetchone()
    return dict(row) if row else None
