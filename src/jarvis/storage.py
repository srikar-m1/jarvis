from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Reminder:
    id: int
    message: str
    due_at: datetime
    completed: bool


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def set_note(self, key: str, value: str) -> None:
        normalized_key = key.strip().casefold()
        if not normalized_key or not value.strip():
            raise ValueError("A note requires both a key and a value.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notes (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (normalized_key, value.strip(), datetime.now(UTC).isoformat()),
            )

    def get_note(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM notes WHERE key = ?",
                (key.strip().casefold(),),
            ).fetchone()
        return None if row is None else str(row["value"])

    def list_notes(self) -> list[tuple[str, str]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT key, value FROM notes ORDER BY key").fetchall()
        return [(str(row["key"]), str(row["value"])) for row in rows]

    def add_reminder(self, message: str, due_at: datetime) -> int:
        if not message.strip():
            raise ValueError("A reminder requires a message.")
        if due_at.tzinfo is None:
            raise ValueError("Reminder times must include a timezone.")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO reminders (message, due_at) VALUES (?, ?)",
                (message.strip(), due_at.astimezone(UTC).isoformat()),
            )
        return int(cursor.lastrowid)

    def list_reminders(self, *, due_before: datetime | None = None) -> list[Reminder]:
        query = "SELECT id, message, due_at, completed FROM reminders WHERE completed = 0"
        params: tuple[str, ...] = ()
        if due_before is not None:
            query += " AND due_at <= ?"
            params = (due_before.astimezone(UTC).isoformat(),)
        query += " ORDER BY due_at, id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            Reminder(
                id=int(row["id"]),
                message=str(row["message"]),
                due_at=datetime.fromisoformat(str(row["due_at"])),
                completed=bool(row["completed"]),
            )
            for row in rows
        ]

    def complete_reminder(self, reminder_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE reminders SET completed = 1 WHERE id = ? AND completed = 0",
                (reminder_id,),
            )
        return cursor.rowcount == 1
