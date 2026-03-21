"""
User State Manager - SQLite-backed conversation/session state persistence.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from database.sync_connection import get_sync_db


class UserState(Enum):
    """User conversation states."""

    INITIAL = "initial"
    GREETING_SENT = "greeting_sent"
    AWAITING_CHOICE = "awaiting_choice"
    CHOICE_RECEIVED = "choice_received"
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_FAILED = "payment_failed"
    PREDICTIONS_SENT = "predictions_sent"
    SESSION_EXPIRED = "session_expired"


class UserStateManager:
    """Manages user session states and transaction records in SQLite."""

    def __init__(self, data_dir: str = "data"):
        # `data_dir` retained for backward compatibility; SQLite path is centralized.
        self.data_dir = data_dir
        self._ensure_tables_exist()

    @staticmethod
    def _json_load(value: Optional[str]) -> Dict[str, Any]:
        if not value:
            return {}
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _json_dump(value: Dict[str, Any]) -> str:
        return json.dumps(value or {}, ensure_ascii=False)

    def _ensure_tables_exist(self) -> None:
        # Safety net if schema initialization has not been executed yet.
        with get_sync_db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_states (
                    platform         TEXT NOT NULL,
                    user_id          TEXT NOT NULL,
                    state            TEXT NOT NULL,
                    state_timestamp  TEXT NOT NULL,
                    metadata_json    TEXT,
                    created_at       TEXT DEFAULT (datetime('now')),
                    updated_at       TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY(platform, user_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_transactions (
                    transaction_id   TEXT PRIMARY KEY,
                    platform         TEXT,
                    user_id          TEXT,
                    amount           REAL,
                    package          TEXT,
                    status           TEXT,
                    reference        TEXT,
                    phone_number     TEXT,
                    created_at       TEXT,
                    verified_at      TEXT,
                    metadata_json    TEXT,
                    updated_at       TEXT DEFAULT (datetime('now'))
                )
                """
            )

    # ---------------------------
    # WhatsApp-compatible methods
    # ---------------------------
    def get_user_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT state, state_timestamp, metadata_json
                FROM user_states
                WHERE platform = 'whatsapp' AND user_id = ?
                LIMIT 1
                """,
                (str(user_id),),
            ).fetchone()
        if not row:
            return None
        return {
            "state": row["state"],
            "timestamp": row["state_timestamp"],
            "metadata": self._json_load(row["metadata_json"]),
        }

    def set_user_state(self, user_id: str, state: UserState, **metadata: Any) -> None:
        ts = datetime.now().isoformat()
        with get_sync_db() as conn:
            conn.execute(
                """
                INSERT INTO user_states (
                    platform, user_id, state, state_timestamp, metadata_json
                )
                VALUES ('whatsapp', ?, ?, ?, ?)
                ON CONFLICT(platform, user_id) DO UPDATE SET
                    state = excluded.state,
                    state_timestamp = excluded.state_timestamp,
                    metadata_json = excluded.metadata_json
                """,
                (str(user_id), state.value, ts, self._json_dump(metadata)),
            )

    def is_session_expired(self, user_id: str, timeout_seconds: int = 300) -> bool:
        user_data = self.get_user_state(user_id)
        if not user_data:
            return False
        try:
            last_activity = datetime.fromisoformat(user_data["timestamp"])
        except Exception:
            return True
        elapsed = (datetime.now() - last_activity).total_seconds()
        return elapsed > timeout_seconds

    def get_user_choice(self, user_id: str) -> Optional[str]:
        user_data = self.get_user_state(user_id)
        if user_data:
            return user_data.get("metadata", {}).get("choice")
        return None

    def set_user_choice(self, user_id: str, choice: str) -> None:
        user_data = self.get_user_state(user_id) or {}
        metadata = user_data.get("metadata", {})
        metadata["choice"] = choice
        self.set_user_state(user_id, UserState.CHOICE_RECEIVED, **metadata)

    def save_transaction(
        self,
        user_id: str,
        transaction_id: str,
        amount: int,
        package: str,
        status: str = "pending",
    ) -> Dict[str, Any]:
        transaction = {
            "user_id": user_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "package": package,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "verified_at": None,
        }
        with get_sync_db() as conn:
            conn.execute(
                """
                INSERT INTO payment_transactions (
                    transaction_id, platform, user_id, amount, package, status,
                    reference, created_at, verified_at, metadata_json
                )
                VALUES (?, 'whatsapp', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    platform = excluded.platform,
                    user_id = excluded.user_id,
                    amount = excluded.amount,
                    package = excluded.package,
                    status = excluded.status,
                    reference = excluded.reference,
                    created_at = excluded.created_at,
                    verified_at = excluded.verified_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    transaction_id,
                    str(user_id),
                    float(amount),
                    str(package),
                    status,
                    transaction_id,
                    transaction["timestamp"],
                    None,
                    self._json_dump(transaction),
                ),
            )
        return transaction

    def update_transaction(self, transaction_id: str, status: str, **updates: Any) -> None:
        with get_sync_db() as conn:
            existing = conn.execute(
                """
                SELECT metadata_json
                FROM payment_transactions
                WHERE transaction_id = ?
                """,
                (transaction_id,),
            ).fetchone()
            metadata = self._json_load(existing["metadata_json"]) if existing else {}
            metadata.update(updates)
            metadata["status"] = status
            metadata["verified_at"] = datetime.now().isoformat()
            conn.execute(
                """
                UPDATE payment_transactions
                SET status = ?,
                    verified_at = ?,
                    metadata_json = ?
                WHERE transaction_id = ?
                """,
                (
                    status,
                    metadata["verified_at"],
                    self._json_dump(metadata),
                    transaction_id,
                ),
            )

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT transaction_id, user_id, amount, package, status, created_at, verified_at, metadata_json
                FROM payment_transactions
                WHERE transaction_id = ?
                LIMIT 1
                """,
                (transaction_id,),
            ).fetchone()
        if not row:
            return None
        payload = self._json_load(row["metadata_json"])
        payload.setdefault("transaction_id", row["transaction_id"])
        payload.setdefault("user_id", row["user_id"])
        payload.setdefault("amount", row["amount"])
        payload.setdefault("package", row["package"])
        payload.setdefault("status", row["status"])
        payload.setdefault("timestamp", row["created_at"])
        payload.setdefault("verified_at", row["verified_at"])
        return payload

    def get_user_transactions(self, user_id: str) -> list:
        with get_sync_db() as conn:
            rows = conn.execute(
                """
                SELECT metadata_json
                FROM payment_transactions
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (str(user_id),),
            ).fetchall()
        return [self._json_load(row["metadata_json"]) for row in rows]

    def reset_user_session(self, user_id: str) -> None:
        self.set_user_state(user_id, UserState.SESSION_EXPIRED)

    def cleanup_expired_sessions(self, timeout_seconds: int = 300) -> None:
        cutoff = datetime.now().timestamp() - timeout_seconds
        with get_sync_db() as conn:
            rows = conn.execute(
                """
                SELECT user_id, state_timestamp
                FROM user_states
                WHERE platform = 'whatsapp'
                """
            ).fetchall()
            for row in rows:
                try:
                    ts = datetime.fromisoformat(row["state_timestamp"]).timestamp()
                except Exception:
                    ts = 0
                if ts <= cutoff:
                    conn.execute(
                        """
                        DELETE FROM user_states
                        WHERE platform = 'whatsapp' AND user_id = ?
                        """,
                        (row["user_id"],),
                    )

    # -------------------------
    # Generic platform helpers
    # -------------------------
    def get_platform_state(self, platform: str, user_id: str) -> Optional[Dict[str, Any]]:
        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT state, state_timestamp, metadata_json
                FROM user_states
                WHERE platform = ? AND user_id = ?
                LIMIT 1
                """,
                (platform, str(user_id)),
            ).fetchone()
        if not row:
            return None
        metadata = self._json_load(row["metadata_json"])
        return {
            "state": row["state"],
            "updated_at": row["state_timestamp"],
            **metadata,
        }

    def set_platform_state(self, platform: str, user_id: str, payload: Dict[str, Any]) -> None:
        payload = dict(payload or {})
        state = str(payload.get("state") or "initial")
        state_timestamp = str(payload.get("updated_at") or datetime.now().isoformat())
        metadata = dict(payload)
        metadata.pop("state", None)
        metadata.pop("updated_at", None)

        with get_sync_db() as conn:
            conn.execute(
                """
                INSERT INTO user_states (
                    platform, user_id, state, state_timestamp, metadata_json
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(platform, user_id) DO UPDATE SET
                    state = excluded.state,
                    state_timestamp = excluded.state_timestamp,
                    metadata_json = excluded.metadata_json
                """,
                (
                    platform,
                    str(user_id),
                    state,
                    state_timestamp,
                    self._json_dump(metadata),
                ),
            )
