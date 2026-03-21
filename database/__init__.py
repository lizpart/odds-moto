"""
database/

Exports:
    get_db               - async context manager for DB connections
    get_sync_db          - sync context manager for DB connections
    init_db              - creates all tables/indexes/triggers from schema.sql
    cleanup_old_data     - prunes stale rows on startup
    migrate_legacy_data  - one-time import from legacy JSON/cache files
    DB_PATH              - resolved path to the SQLite file
"""

from __future__ import annotations

from database.connection import DB_PATH, get_db
from database.sync_connection import get_sync_db


async def init_db():
    from database.init_db import init_db as _init_db

    return await _init_db()


async def cleanup_old_data():
    from database.init_db import cleanup_old_data as _cleanup_old_data

    return await _cleanup_old_data()


async def migrate_legacy_data(force: bool = False):
    from database.migrate_legacy_data import migrate_legacy_data as _migrate_legacy_data

    return await _migrate_legacy_data(force=force)


__all__ = [
    "get_db",
    "get_sync_db",
    "DB_PATH",
    "init_db",
    "cleanup_old_data",
    "migrate_legacy_data",
]
