"""
SQLite-backed cache service for prediction payloads.

This replaces filesystem JSON cache files while preserving the public methods
used by the API endpoints and prediction service.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.sync_connection import get_sync_db

logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing prediction cache in SQLite."""

    def __init__(self, cache_dir: str = "cache"):
        # Retained for compatibility with existing constructor signature.
        self.cache_dir = cache_dir

    @staticmethod
    def get_cache_path(fixture_id: int, analysis_type: str) -> str:
        """
        Legacy-compatible pseudo path for callers that log a "cache path".
        """
        return f"db://predictions/{fixture_id}/{analysis_type}"

    @staticmethod
    def _normalize_analysis_type(analysis_type: str) -> str:
        return (analysis_type or "enhanced").strip().lower()

    @staticmethod
    def _safe_parse_json(value: str) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    @staticmethod
    def _extract_probabilities(data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        probs = data.get("probabilities", {}) if isinstance(data, dict) else {}
        home = probs.get("home")
        draw = probs.get("draw")
        away = probs.get("away")
        return {
            "home": float(home) if isinstance(home, (int, float)) else None,
            "draw": float(draw) if isinstance(draw, (int, float)) else None,
            "away": float(away) if isinstance(away, (int, float)) else None,
        }

    @staticmethod
    def _pick_winner(probabilities: Dict[str, Optional[float]]) -> Optional[str]:
        valid = {k: v for k, v in probabilities.items() if v is not None}
        if not valid:
            return None
        top = max(valid.items(), key=lambda x: x[1])[0]
        return top if top in {"home", "draw", "away"} else None

    @staticmethod
    def _normalize_match_date(match_date: Optional[str]) -> Optional[str]:
        if not match_date or not isinstance(match_date, str):
            return None
        match_date = match_date.strip()
        if not match_date:
            return None
        try:
            # YYYY-MM-DD
            if len(match_date) == 10 and match_date[4] == "-" and match_date[7] == "-":
                return match_date
            return datetime.fromisoformat(match_date.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            return None

    @classmethod
    def _kickoff_utc_for_date(cls, match_date: Optional[str]) -> str:
        normalized = cls._normalize_match_date(match_date)
        if normalized:
            return f"{normalized}T00:00:00Z"
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def cache_exists(self, fixture_id: int, analysis_type: str) -> bool:
        analysis_type = self._normalize_analysis_type(analysis_type)
        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM predictions
                WHERE fixture_id = ?
                  AND analysis_type = ?
                  AND is_valid = 1
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
                LIMIT 1
                """,
                (fixture_id, analysis_type),
            ).fetchone()
            return row is not None

    def get_cached_analysis(self, fixture_id: int, analysis_type: str) -> Optional[Dict[str, Any]]:
        analysis_type = self._normalize_analysis_type(analysis_type)
        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT messaging_json
                FROM predictions
                WHERE fixture_id = ?
                  AND analysis_type = ?
                  AND is_valid = 1
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (fixture_id, analysis_type),
            ).fetchone()
            if not row:
                logger.debug("Cache miss for fixture %s (%s)", fixture_id, analysis_type)
                return None

            parsed = self._safe_parse_json(row["messaging_json"])
            if not parsed:
                logger.warning("Invalid cached JSON payload for fixture %s (%s)", fixture_id, analysis_type)
                return None

            logger.debug("Cache hit for fixture %s (%s)", fixture_id, analysis_type)
            return parsed

    def save_cached_analysis(
        self,
        fixture_id: int,
        analysis_type: str,
        data: Dict[str, Any],
        match_date: Optional[str] = None,
    ) -> str:
        analysis_type = self._normalize_analysis_type(analysis_type)
        probabilities = self._extract_probabilities(data)
        predicted_winner = self._pick_winner(probabilities)
        confidence = max(
            [v for v in probabilities.values() if isinstance(v, (int, float))],
            default=None,
        )

        recommended_bet = None
        top_bets = data.get("top_bets")
        if isinstance(top_bets, list) and top_bets:
            first = top_bets[0]
            if isinstance(first, dict):
                recommended_bet = first.get("bet")

        kickoff_utc = self._kickoff_utc_for_date(match_date)
        payload_json = json.dumps(data, ensure_ascii=False)

        with get_sync_db() as conn:
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
                    fixture_id,
                    analysis_type,
                    predicted_winner,
                    home_win_prob,
                    draw_prob,
                    away_win_prob,
                    confidence,
                    recommended_bet,
                    messaging_json,
                    is_valid,
                    created_at
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
                    confidence,
                    recommended_bet,
                    payload_json,
                ),
            )

        logger.info("Cached analysis for fixture %s (%s)", fixture_id, analysis_type)
        return self.get_cache_path(fixture_id, analysis_type)

    def invalidate_cache(self, fixture_id: int, analysis_type: Optional[str] = None) -> bool:
        with get_sync_db() as conn:
            if analysis_type:
                analysis_type = self._normalize_analysis_type(analysis_type)
                cursor = conn.execute(
                    "DELETE FROM predictions WHERE fixture_id = ? AND analysis_type = ?",
                    (fixture_id, analysis_type),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM predictions WHERE fixture_id = ?",
                    (fixture_id,),
                )
            invalidated = cursor.rowcount > 0
            if invalidated:
                logger.info("Invalidated cache for fixture %s (%s)", fixture_id, analysis_type or "all")
            return invalidated

    def invalidate_cache_batch(
        self,
        fixture_ids: List[int],
        analysis_type: Optional[str] = None,
    ) -> Dict[str, int]:
        invalidated = 0
        errors = 0
        for fixture_id in fixture_ids:
            try:
                if self.invalidate_cache(fixture_id, analysis_type):
                    invalidated += 1
            except Exception as exc:
                logger.error("Error invalidating cache for fixture %s: %s", fixture_id, exc)
                errors += 1
        return {"invalidated": invalidated, "errors": errors}

    def invalidate_cache_by_date(
        self,
        date: str,
        analysis_type: Optional[str] = None,
    ) -> Dict[str, int]:
        normalized_date = self._normalize_match_date(date)
        if not normalized_date:
            return {"invalidated": 0, "errors": 1}

        with get_sync_db() as conn:
            try:
                if analysis_type:
                    analysis_type = self._normalize_analysis_type(analysis_type)
                    cursor = conn.execute(
                        """
                        DELETE FROM predictions
                        WHERE analysis_type = ?
                          AND fixture_id IN (
                              SELECT id
                              FROM fixtures
                              WHERE substr(kickoff_utc, 1, 10) = ?
                          )
                        """,
                        (analysis_type, normalized_date),
                    )
                else:
                    cursor = conn.execute(
                        """
                        DELETE FROM predictions
                        WHERE fixture_id IN (
                            SELECT id
                            FROM fixtures
                            WHERE substr(kickoff_utc, 1, 10) = ?
                        )
                        """,
                        (normalized_date,),
                    )
                return {"invalidated": max(cursor.rowcount, 0), "errors": 0}
            except Exception as exc:
                logger.error("Error invalidating cache by date %s: %s", normalized_date, exc)
                return {"invalidated": 0, "errors": 1}

    def invalidate_cache_by_league(
        self,
        league_id: int,
        date: Optional[str] = None,
        analysis_type: Optional[str] = None,
    ) -> Dict[str, int]:
        filters = ["f.league_id = ?"]
        params: List[Any] = [league_id]

        normalized_date = self._normalize_match_date(date) if date else None
        if normalized_date:
            filters.append("substr(f.kickoff_utc, 1, 10) = ?")
            params.append(normalized_date)

        if analysis_type:
            filters.append("p.analysis_type = ?")
            params.append(self._normalize_analysis_type(analysis_type))

        where_clause = " AND ".join(filters)

        with get_sync_db() as conn:
            try:
                cursor = conn.execute(
                    f"""
                    DELETE FROM predictions
                    WHERE id IN (
                        SELECT p.id
                        FROM predictions p
                        JOIN fixtures f ON f.id = p.fixture_id
                        WHERE {where_clause}
                    )
                    """,
                    tuple(params),
                )
                return {"invalidated": max(cursor.rowcount, 0), "errors": 0}
            except Exception as exc:
                logger.error(
                    "Error invalidating cache by league %s (date=%s, analysis_type=%s): %s",
                    league_id,
                    date,
                    analysis_type,
                    exc,
                )
                return {"invalidated": 0, "errors": 1}

    def get_all_cached_fixtures(self, analysis_type: Optional[str] = None) -> List[int]:
        with get_sync_db() as conn:
            if analysis_type:
                rows = conn.execute(
                    """
                    SELECT DISTINCT fixture_id
                    FROM predictions
                    WHERE analysis_type = ?
                      AND is_valid = 1
                    ORDER BY fixture_id
                    """,
                    (self._normalize_analysis_type(analysis_type),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT fixture_id
                    FROM predictions
                    WHERE is_valid = 1
                    ORDER BY fixture_id
                    """
                ).fetchall()
        return [int(row["fixture_id"]) for row in rows]

