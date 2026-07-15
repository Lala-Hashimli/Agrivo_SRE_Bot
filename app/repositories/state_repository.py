from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class StateRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_sync(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS user_preferences (
                    telegram_user_id INTEGER PRIMARY KEY,
                    preferred_language TEXT NOT NULL DEFAULT 'en'
                        CHECK (preferred_language IN ('en', 'az')),
                    last_interaction_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alert_deduplication (
                    deduplication_key TEXT PRIMARY KEY,
                    last_notified_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bot_state (
                    state_key TEXT PRIMARY KEY,
                    state_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    async def ping(self) -> bool:
        return await asyncio.to_thread(self._ping_sync)

    def _ping_sync(self) -> bool:
        try:
            with self._connection() as connection:
                row = connection.execute("SELECT 1 AS ok").fetchone()
                return bool(row and row["ok"] == 1)
        except sqlite3.Error:
            return False

    async def get_language(self, telegram_user_id: int) -> str:
        return await asyncio.to_thread(self._get_language_sync, telegram_user_id)

    def _get_language_sync(self, telegram_user_id: int) -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT preferred_language FROM user_preferences "
                "WHERE telegram_user_id = ?",
                (telegram_user_id,),
            ).fetchone()
        return str(row["preferred_language"]) if row else "en"

    async def set_language(self, telegram_user_id: int, language: str) -> None:
        if language not in {"en", "az"}:
            raise ValueError("Unsupported language")
        await asyncio.to_thread(self._set_language_sync, telegram_user_id, language)

    def _set_language_sync(self, telegram_user_id: int, language: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences (
                    telegram_user_id, preferred_language, last_interaction_at
                ) VALUES (?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    preferred_language = excluded.preferred_language,
                    last_interaction_at = excluded.last_interaction_at
                """,
                (telegram_user_id, language, now),
            )

    async def touch_user(self, telegram_user_id: int) -> None:
        await asyncio.to_thread(self._touch_user_sync, telegram_user_id)

    def _touch_user_sync(self, telegram_user_id: int) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences (
                    telegram_user_id, preferred_language, last_interaction_at
                ) VALUES (?, 'en', ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    last_interaction_at = excluded.last_interaction_at
                """,
                (telegram_user_id, now),
            )
