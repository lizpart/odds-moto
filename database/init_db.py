"""
Database initialization and maintenance utilities.

Usage:
    python -m database.init_db
"""

from __future__ import annotations

import asyncio
import logging
import os

import aiosqlite

from database.connection import DB_PATH, _apply_pragmas
from database.migrate_legacy_data import migrate_legacy_data

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


async def _table_exists(db: aiosqlite.Connection, table_name: str) -> bool:
    cur = await db.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    )
    row = await cur.fetchone()
    await cur.close()
    return bool(row)


async def _column_exists(db: aiosqlite.Connection, table_name: str, column_name: str) -> bool:
    cur = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cur.fetchall()
    await cur.close()
    return any(str(row[1]) == column_name for row in rows)


async def _prepare_platform_session_unique_index(db: aiosqlite.Connection) -> None:
    """
    Deduplicate historical rows before enforcing one session per
    (subscription_id, platform).
    """
    if not await _table_exists(db, "platform_sessions"):
        return

    try:
        await db.execute(
            """
            DELETE FROM platform_sessions
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM platform_sessions
                GROUP BY subscription_id, platform
            )
            """
        )
    except Exception:
        logger.exception("Could not deduplicate platform_sessions prior to unique-index migration.")


async def _run_incremental_migrations(db: aiosqlite.Connection) -> None:
    """
    Apply additive schema migrations that CREATE TABLE IF NOT EXISTS
    cannot enforce on existing tables.
    """
    if await _table_exists(db, "activation_attempts"):
        if not await _column_exists(db, "activation_attempts", "failure_reason"):
            await db.execute(
                """
                ALTER TABLE activation_attempts
                ADD COLUMN failure_reason TEXT
                """
            )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attempts_lockout
            ON activation_attempts(platform, platform_user_id, success, attempted_at)
            """
        )

    if await _table_exists(db, "platform_sessions"):
        await _prepare_platform_session_unique_index(db)
        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_session_sub_platform
            ON platform_sessions(subscription_id, platform)
            """
        )


async def init_db() -> None:
    """
    Create all tables, indexes, and triggers defined in schema.sql.
    Safe to run repeatedly.
    """
    logger.info("Initialising database at: %s", DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        await _prepare_platform_session_unique_index(db)
        await db.executescript(schema_sql)
        await _run_incremental_migrations(db)
        await db.commit()

    auto_migrate = os.getenv("AUTO_MIGRATE_LEGACY", "true").strip().lower()
    if auto_migrate not in {"0", "false", "no", "off"}:
        try:
            migration_summary = await migrate_legacy_data()
            logger.info("Legacy migration summary: %s", migration_summary)
        except Exception:
            logger.exception("Legacy data migration failed; continuing startup.")

    logger.info("Database initialised successfully.")


async def cleanup_old_data() -> None:
    """
    Prune stale data based on retention thresholds.
    """
    from database.connection import get_db

    logger.info("Running startup data cleanup")

    # First phase: regular deletes in one transaction.
    async with get_db() as db:
        await db.execute(
            """
            DELETE FROM predictions
            WHERE created_at < datetime('now', '-30 days')
            """
        )
        await db.execute(
            """
            DELETE FROM match_context
            WHERE fetched_at < datetime('now', '-30 days')
            """
        )
        await db.execute(
            """
            DELETE FROM activation_attempts
            WHERE attempted_at < datetime('now', '-7 days')
            """
        )
        await db.execute(
            """
            DELETE FROM user_states
            WHERE updated_at < datetime('now', '-30 days')
            """
        )
        await db.execute(
            """
            DELETE FROM payment_transactions
            WHERE updated_at < datetime('now', '-90 days')
              AND lower(ifnull(status, '')) IN ('completed', 'confirmed', 'failed', 'cancelled')
            """
        )
        await db.commit()

    # Second phase: maintenance commands that must run outside write transactions.
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        await db.execute("PRAGMA optimize;")
        await db.commit()

    logger.info("Startup data cleanup complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    asyncio.run(init_db())
    asyncio.run(cleanup_old_data())
    print(f"\nDatabase ready at: {DB_PATH}")
