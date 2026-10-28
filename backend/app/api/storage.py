"""
SQLite storage layer for WasmBox plugins.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# Default database stored locally in backend directory (gitignored)
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "wasmbox_plugins.db"


def _get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create a fresh SQLite connection for the request."""
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Initialize the plugins table if it does not exist."""
    with _get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plugins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_plugin(name: str, code: str, db_path: str | Path | None = None) -> dict[str, Any]:
    """
    Save a new plugin to SQLite database using parameterized query.
    Returns: {"id": int, "name": str}
    """
    init_db(db_path)
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO plugins (name, code) VALUES (?, ?)",
            (name, code),
        )
        conn.commit()
        plugin_id = cursor.lastrowid
        return {"id": plugin_id, "name": name}


def list_plugins(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """
    List all saved plugins (id and name).
    Returns: [{"id": int, "name": str}]
    """
    init_db(db_path)
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM plugins ORDER BY id ASC")
        rows = cursor.fetchall()
        return [{"id": row["id"], "name": row["name"]} for row in rows]


def get_plugin(plugin_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    """
    Fetch a single plugin by ID.
    Returns: {"id": int, "name": str, "code": str} or None if not found.
    """
    init_db(db_path)
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, code FROM plugins WHERE id = ?",
            (plugin_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row["id"], "name": row["name"], "code": row["code"]}
