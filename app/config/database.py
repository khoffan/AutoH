"""SQLite storage for AutoH (modes + logs).

The database file is created lazily on first connection. If it cannot be
opened (no write permission, locked, corrupt), a process-wide in-memory
database is used instead so the app keeps working for the session.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

from config.get_base_dir import get_base_dir, get_data_dir, get_user_data_dir

DB_FILENAME = "autoh.db"
LEGACY_CONFIG_FILENAME = "config.json"
LOG_RETENTION_DAYS = 30
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS modes (
    name   TEXT PRIMARY KEY,
    hotkey TEXT NOT NULL,
    urls   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS mode_apps (
    mode_name TEXT NOT NULL REFERENCES modes(name) ON DELETE CASCADE ON UPDATE CASCADE,
    position  INTEGER NOT NULL,
    app_name  TEXT NOT NULL,
    path      TEXT NOT NULL,
    PRIMARY KEY (mode_name, app_name)
);
CREATE TABLE IF NOT EXISTS logs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
    level   TEXT NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);
"""

_lock = threading.RLock()
_memory_conn: sqlite3.Connection | None = None
_initialized_paths: set[str] = set()


def get_db_path() -> str:
    return os.path.join(get_data_dir(DB_FILENAME), DB_FILENAME)


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 3000")


def _get_memory_conn() -> sqlite3.Connection:
    global _memory_conn
    if _memory_conn is None:
        _memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        _configure(_memory_conn)
        _memory_conn.executescript(_SCHEMA)
    return _memory_conn


class _Connection:
    """Context manager: yields a connection, commits on success, rolls back on error."""

    def __enter__(self) -> sqlite3.Connection:
        _lock.acquire()
        self._close = False
        try:
            path = get_db_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            conn = sqlite3.connect(path, timeout=3)
            self._close = True
            _configure(conn)
            if path not in _initialized_paths:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executescript(_SCHEMA)
                _migrate_legacy_json(conn)
                _prune_logs(conn)
                conn.commit()
                _initialized_paths.add(path)
        except (OSError, sqlite3.Error) as exc:
            print(f"Cannot open database, using in-memory storage: {exc}")
            if self._close:
                conn.close()
                self._close = False
            conn = _get_memory_conn()
        self.conn = conn
        return conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            if self._close:
                self.conn.close()
        finally:
            _lock.release()
        return False


def connect() -> _Connection:
    return _Connection()


# ---------------------------------------------------------------- validation

def normalize_modes(data) -> dict:
    """Validate/normalize a {"modes": {...}} payload. Raises ValueError if invalid."""
    if not isinstance(data, dict) or not isinstance(data.get("modes"), dict):
        raise ValueError('Expected an object like {"modes": {...}}.')

    result = {}
    for name, settings in data["modes"].items():
        name = str(name).strip()
        if not name:
            raise ValueError("Mode name cannot be empty.")
        if not isinstance(settings, dict):
            raise ValueError(f"Mode '{name}' must be an object.")

        hotkey = settings.get("hotkey")
        if not isinstance(hotkey, str) or not hotkey.strip():
            raise ValueError(f"Mode '{name}' needs a hotkey.")

        apps = settings.get("apps", {})
        if not isinstance(apps, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in apps.items()
        ):
            raise ValueError(f"Mode '{name}': apps must map app name to a path string.")

        urls = settings.get("urls", "")
        if isinstance(urls, list):
            urls = ", ".join(str(u).strip() for u in urls if str(u).strip())
        if not isinstance(urls, str):
            raise ValueError(f"Mode '{name}': urls must be text.")

        mode = {"hotkey": hotkey.strip().lower(), "apps": dict(apps)}
        if urls.strip():
            mode["urls"] = urls.strip()
        result[name] = mode
    return result


# ---------------------------------------------------------------- modes

def read_modes(conn: sqlite3.Connection) -> dict:
    modes = {}
    for name, hotkey, urls in conn.execute("SELECT name, hotkey, urls FROM modes ORDER BY name"):
        modes[name] = {"hotkey": hotkey, "apps": {}}
        if urls:
            modes[name]["urls"] = urls
    for mode_name, app_name, path in conn.execute(
        "SELECT mode_name, app_name, path FROM mode_apps ORDER BY mode_name, position"
    ):
        if mode_name in modes:
            modes[mode_name]["apps"][app_name] = path
    return modes


def write_modes(conn: sqlite3.Connection, modes: dict) -> None:
    """Replace all modes in one transaction."""
    conn.execute("DELETE FROM mode_apps")
    conn.execute("DELETE FROM modes")
    for name, settings in modes.items():
        conn.execute(
            "INSERT INTO modes (name, hotkey, urls) VALUES (?, ?, ?)",
            (name, settings["hotkey"], settings.get("urls", "") or ""),
        )
        conn.executemany(
            "INSERT INTO mode_apps (mode_name, position, app_name, path) VALUES (?, ?, ?, ?)",
            [(name, i, app, path) for i, (app, path) in enumerate(settings.get("apps", {}).items())],
        )


# ---------------------------------------------------------------- logs

def _prune_logs(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM logs WHERE ts < strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime', ?)",
        (f"-{LOG_RETENTION_DAYS} days",),
    )


# ---------------------------------------------------------------- migration

def _migrate_legacy_json(conn: sqlite3.Connection) -> None:
    """One-time import of an old config.json, then rename it to config.json.bak."""
    if conn.execute("SELECT 1 FROM meta WHERE key = 'legacy_json_migrated'").fetchone():
        return

    for folder in (get_base_dir(), get_user_data_dir()):
        legacy_path = os.path.join(folder, LEGACY_CONFIG_FILENAME)
        if not os.path.isfile(legacy_path):
            continue
        try:
            with open(legacy_path, "r", encoding="utf-8-sig") as f:
                modes = normalize_modes(json.load(f))
        except (OSError, ValueError) as exc:
            print(f"Skipping legacy config {legacy_path}: {exc}")
            continue

        if not conn.execute("SELECT 1 FROM modes LIMIT 1").fetchone():
            write_modes(conn, modes)
        try:
            os.replace(legacy_path, legacy_path + ".bak")
        except OSError:
            pass
        break

    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('legacy_json_migrated', '1')"
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
