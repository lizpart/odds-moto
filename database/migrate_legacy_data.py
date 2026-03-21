"""
One-time migration helpers for legacy file-based data.

This migrates:
- cache/predictions/**/*.json -> predictions table
- data/user_states.json -> user_states table (platform=whatsapp)
- frontend/telegram/memory/*.json -> user_states table (platform=telegram)
- data/transactions.json -> payment_transactions table
"""

from __future__ import annotations

import asyncio
import glob
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from database.sync_connection import DB_PATH, get_sync_db

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
_MIGRATION_MARKER = os.path.join(_PROJECT, "data", ".legacy_migration_v1.done")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _safe_load_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Skipping unreadable JSON file %s: %s", path, exc)
        return None


def _extract_fixture_id(path: str, payload: Dict[str, Any]) -> Optional[int]:
    fixture_id = payload.get("fixture_id")
    if fixture_id is not None:
        try:
            return int(fixture_id)
        except Exception:
            pass

    name = os.path.basename(path)
    match = re.search(r"(\d+)", name)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _extract_analysis_type(path: str, payload: Dict[str, Any]) -> str:
    analysis_type = str(payload.get("analysis_type") or "").strip().lower()
    if analysis_type in {"basic", "enhanced"}:
        return analysis_type

    name = os.path.basename(path).lower()
    if "_basic" in name:
        return "basic"
    return "enhanced"


def _pick_probabilities(data: Dict[str, Any]) -> Dict[str, Optional[float]]:
    probs = data.get("probabilities", {}) if isinstance(data, dict) else {}
    home = probs.get("home")
    draw = probs.get("draw")
    away = probs.get("away")
    return {
        "home": float(home) if isinstance(home, (int, float)) else None,
        "draw": float(draw) if isinstance(draw, (int, float)) else None,
        "away": float(away) if isinstance(away, (int, float)) else None,
    }


def _pick_winner(probabilities: Dict[str, Optional[float]]) -> Optional[str]:
    valid = {k: v for k, v in probabilities.items() if v is not None}
    if not valid:
        return None
    top = max(valid.items(), key=lambda x: x[1])[0]
    if top == "home":
        return "home"
    if top == "away":
        return "away"
    return "draw"


def _normalize_match_date(match_date: Optional[str]) -> Optional[str]:
    if not match_date:
        return None
    if not isinstance(match_date, str):
        return None
    match_date = match_date.strip()
    if not match_date:
        return None
    try:
        # Accept YYYY-MM-DD directly.
        if re.match(r"^\d{4}-\d{2}-\d{2}$", match_date):
            return match_date
        # Fallback for ISO timestamps.
        return datetime.fromisoformat(match_date.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def _kickoff_from_date(match_date: Optional[str]) -> str:
    normalized = _normalize_match_date(match_date)
    if normalized:
        return f"{normalized}T00:00:00Z"
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_subscription_for_transaction(
    conn,
    transaction_id: str,
    platform: Optional[str],
    user_id: Optional[str],
    phone_number: Optional[str],
    package: Optional[str],
    created_at: Optional[str],
    metadata: Dict[str, Any],
) -> None:
    if not phone_number:
        return

    plan = "daily"
    if str(package) == "2":
        plan = "daily"

    starts_at = created_at or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_at = metadata.get("subscription_expires_at")
    if not expires_at:
        try:
            starts_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        except Exception:
            starts_dt = datetime.utcnow()
        expires_at = (starts_dt + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    pin_seed = hashlib.sha1(transaction_id.encode("utf-8")).hexdigest()
    pin = str(int(pin_seed[:10], 16) % 900000 + 100000)

    # Ensure pin uniqueness by probing small deterministic variants.
    for attempt in range(10):
        candidate_pin = str((int(pin) + attempt) % 900000 + 100000)
        try:
            conn.execute(
                """
                INSERT INTO subscriptions (
                    payment_phone, paystack_ref, amount, currency, plan,
                    pin, starts_at, expires_at, status, initiated_from
                )
                VALUES (?, ?, ?, 'KES', ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(paystack_ref) DO UPDATE SET
                    payment_phone = excluded.payment_phone,
                    amount = excluded.amount,
                    plan = excluded.plan,
                    starts_at = excluded.starts_at,
                    expires_at = excluded.expires_at,
                    status = 'active',
                    initiated_from = excluded.initiated_from
                """,
                (
                    phone_number,
                    transaction_id,
                    float(metadata.get("amount") or 0.0),
                    plan,
                    candidate_pin,
                    starts_at,
                    expires_at,
                    platform,
                ),
            )
            break
        except Exception:
            continue

    if platform and user_id:
        row = conn.execute(
            "SELECT id, plan, expires_at FROM subscriptions WHERE paystack_ref = ?",
            (transaction_id,),
        ).fetchone()
        if row:
            conn.execute(
                """
                DELETE FROM platform_sessions
                WHERE (subscription_id = ? AND platform = ?)
                   OR (platform = ? AND platform_user_id = ?)
                """,
                (int(row["id"]), platform, platform, user_id),
            )
            conn.execute(
                """
                INSERT INTO platform_sessions (
                    subscription_id, platform, platform_user_id, plan, expires_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (int(row["id"]), platform, user_id, row["plan"], row["expires_at"]),
            )


def _migrate_sync(force: bool = False) -> Dict[str, int]:
    if os.path.exists(_MIGRATION_MARKER) and not force:
        logger.info("Legacy migration marker present; skipping migration.")
        return {
            "predictions": 0,
            "user_states": 0,
            "payment_transactions": 0,
            "subscriptions": 0,
            "skipped": 1,
        }

    imported_predictions = 0
    imported_states = 0
    imported_transactions = 0
    imported_subscriptions = 0

    with get_sync_db() as conn:
        # 1) Prediction cache files -> predictions table
        cache_root = os.path.join(_PROJECT, "cache", "predictions")
        for path in glob.glob(os.path.join(cache_root, "**", "*.json"), recursive=True):
            payload = _safe_load_json(path)
            if not isinstance(payload, dict):
                continue

            fixture_id = _extract_fixture_id(path, payload)
            if not fixture_id:
                continue

            analysis_type = _extract_analysis_type(path, payload)
            messaging_payload = payload.get("data", payload)
            if not isinstance(messaging_payload, dict):
                continue

            probabilities = _pick_probabilities(messaging_payload)
            predicted_winner = _pick_winner(probabilities)
            top_bets = messaging_payload.get("top_bets")
            recommended_bet = None
            if isinstance(top_bets, list) and top_bets:
                first = top_bets[0]
                if isinstance(first, dict):
                    recommended_bet = first.get("bet")

            match_date = _normalize_match_date(payload.get("match_date"))
            kickoff_utc = _kickoff_from_date(match_date)

            conn.execute(
                """
                INSERT OR IGNORE INTO fixtures (id, kickoff_utc, status)
                VALUES (?, ?, 'NS')
                """,
                (fixture_id, kickoff_utc),
            )
            if match_date:
                conn.execute(
                    """
                    UPDATE fixtures
                    SET kickoff_utc = ?
                    WHERE id = ?
                    """,
                    (kickoff_utc, fixture_id),
                )

            conn.execute(
                """
                INSERT INTO predictions (
                    fixture_id, analysis_type, predicted_winner,
                    home_win_prob, draw_prob, away_win_prob,
                    confidence, recommended_bet, messaging_json,
                    is_valid, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
                ON CONFLICT(fixture_id, analysis_type) DO UPDATE SET
                    predicted_winner = excluded.predicted_winner,
                    home_win_prob = excluded.home_win_prob,
                    draw_prob = excluded.draw_prob,
                    away_win_prob = excluded.away_win_prob,
                    confidence = excluded.confidence,
                    recommended_bet = excluded.recommended_bet,
                    messaging_json = excluded.messaging_json,
                    is_valid = 1,
                    created_at = datetime('now')
                """,
                (
                    fixture_id,
                    analysis_type,
                    predicted_winner,
                    probabilities["home"],
                    probabilities["draw"],
                    probabilities["away"],
                    None,
                    recommended_bet,
                    _json_dumps(messaging_payload),
                ),
            )
            imported_predictions += 1

        # 2) WhatsApp legacy state file -> user_states
        legacy_state_path = os.path.join(_PROJECT, "data", "user_states.json")
        legacy_states = _safe_load_json(legacy_state_path)
        if isinstance(legacy_states, dict):
            for user_id, state_payload in legacy_states.items():
                if not isinstance(state_payload, dict):
                    continue
                state = str(state_payload.get("state") or "initial")
                ts = str(
                    state_payload.get("timestamp")
                    or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                )
                metadata = state_payload.get("metadata") or {}
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
                    (str(user_id), state, ts, _json_dumps(metadata)),
                )
                imported_states += 1

        # 3) Telegram memory files -> user_states
        telegram_memory_glob = os.path.join(
            _PROJECT, "frontend", "telegram", "memory", "*.json"
        )
        for path in glob.glob(telegram_memory_glob):
            payload = _safe_load_json(path)
            if not isinstance(payload, dict):
                continue

            user_id = os.path.splitext(os.path.basename(path))[0]
            state = str(payload.get("state") or "initial")
            ts = str(payload.get("updated_at") or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
            metadata = dict(payload)
            metadata.pop("state", None)

            conn.execute(
                """
                INSERT INTO user_states (
                    platform, user_id, state, state_timestamp, metadata_json
                )
                VALUES ('telegram', ?, ?, ?, ?)
                ON CONFLICT(platform, user_id) DO UPDATE SET
                    state = excluded.state,
                    state_timestamp = excluded.state_timestamp,
                    metadata_json = excluded.metadata_json
                """,
                (user_id, state, ts, _json_dumps(metadata)),
            )
            imported_states += 1

        # 4) Legacy transactions file -> payment_transactions (+ subscriptions when possible)
        legacy_txn_path = os.path.join(_PROJECT, "data", "transactions.json")
        legacy_txns = _safe_load_json(legacy_txn_path)
        if isinstance(legacy_txns, dict):
            for transaction_id, payload in legacy_txns.items():
                if not isinstance(payload, dict):
                    continue

                tx_id = str(transaction_id)
                status = str(payload.get("status") or "pending")
                platform = payload.get("platform")
                user_id = str(payload.get("user_id")) if payload.get("user_id") is not None else None
                amount = payload.get("amount")
                package = str(payload.get("package")) if payload.get("package") is not None else None
                reference = str(payload.get("reference") or tx_id)
                created_at = payload.get("timestamp")
                verified_at = payload.get("verified_at")
                phone_number = payload.get("phone_number")

                conn.execute(
                    """
                    INSERT INTO payment_transactions (
                        transaction_id, platform, user_id, amount, package, status,
                        reference, phone_number, created_at, verified_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(transaction_id) DO UPDATE SET
                        platform = excluded.platform,
                        user_id = excluded.user_id,
                        amount = excluded.amount,
                        package = excluded.package,
                        status = excluded.status,
                        reference = excluded.reference,
                        phone_number = excluded.phone_number,
                        created_at = excluded.created_at,
                        verified_at = excluded.verified_at,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        tx_id,
                        platform,
                        user_id,
                        float(amount) if isinstance(amount, (int, float)) else None,
                        package,
                        status,
                        reference,
                        phone_number,
                        created_at,
                        verified_at,
                        _json_dumps(payload),
                    ),
                )
                imported_transactions += 1

                if status.lower() in {"confirmed", "completed", "success"}:
                    before = conn.total_changes
                    _ensure_subscription_for_transaction(
                        conn=conn,
                        transaction_id=reference,
                        platform=platform,
                        user_id=user_id,
                        phone_number=phone_number,
                        package=package,
                        created_at=created_at,
                        metadata=payload,
                    )
                    if conn.total_changes > before:
                        imported_subscriptions += 1

    os.makedirs(os.path.dirname(_MIGRATION_MARKER), exist_ok=True)
    with open(_MIGRATION_MARKER, "w", encoding="utf-8") as marker:
        marker.write(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))

    logger.info(
        "Legacy migration complete: predictions=%s, user_states=%s, payment_transactions=%s, subscriptions=%s",
        imported_predictions,
        imported_states,
        imported_transactions,
        imported_subscriptions,
    )
    return {
        "predictions": imported_predictions,
        "user_states": imported_states,
        "payment_transactions": imported_transactions,
        "subscriptions": imported_subscriptions,
        "skipped": 0,
    }


async def migrate_legacy_data(force: bool = False) -> Dict[str, int]:
    """
    Run one-time migration from legacy file storage into SQLite.
    """
    return await asyncio.to_thread(_migrate_sync, force)
