import sqlite3
from datetime import datetime

from config import database


def write_log(msg, level="INFO"):
    """Store a log line in the database; never raises (falls back to console)."""
    try:
        with database.connect() as conn:
            conn.execute("INSERT INTO logs (level, message) VALUES (?, ?)", (level, str(msg)))
    except sqlite3.Error:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{level}] {msg}")


def read_logs(limit=500):
    """Most recent logs first: list of (ts, level, message)."""
    try:
        with database.connect() as conn:
            return conn.execute(
                "SELECT ts, level, message FROM logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    except sqlite3.Error:
        return []
