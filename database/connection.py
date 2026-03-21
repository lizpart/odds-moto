"""
database/connection.py

Single source of truth for the aiosqlite connection.
Every connection sets the required PRAGMAs automatically.

Usage:
    from database.connection import get_db

    async with get_db() as db:
        await db.execute("SELECT ...")
"""

import os
import aiosqlite
from contextlib import asynccontextmanager

# ── Resolve DB path ─────────────────────────────────────────────
# Reads DB_PATH from environment, falls back to data/football.db
# relative to the project root (one level above this file).
_HERE       = os.path.dirname(os.path.abspath(__file__))
_PROJECT    = os.path.dirname(_HERE)
_DEFAULT_DB = os.path.join(_PROJECT, "data", "football.db")
DB_PATH     = os.environ.get("DB_PATH", _DEFAULT_DB)


async def _apply_pragmas(db: aiosqlite.Connection) -> None:
    """
    Apply required PRAGMAs on every new connection.
    SQLite PRAGMAs are connection-level, not stored in the file.
    """
    await db.execute("PRAGMA journal_mode = WAL;")
    await db.execute("PRAGMA foreign_keys = ON;")
    await db.execute("PRAGMA synchronous  = NORMAL;")


@asynccontextmanager
async def get_db():
    """
    Async context manager that yields a configured aiosqlite connection.

    Example:
        async with get_db() as db:
            await db.execute("INSERT INTO ...")
            await db.commit()
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row   # rows behave like dicts
        await _apply_pragmas(db)
        yield db
