"""
Async helpers to persist fixture/context payloads into SQLite tables.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from database.connection import get_db

logger = logging.getLogger(__name__)


def _text_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value)


def _json_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


async def upsert_match_context_payload(match_data: Dict[str, Any], md_report_path: Optional[str] = None) -> None:
    """
    Persist league/team/fixture/match_context data from collector payload.

    This is best-effort and should never break request flow.
    """
    try:
        api_data = match_data.get("api_data", {}) if isinstance(match_data, dict) else {}
        fixture_bundle = api_data.get("fixture", {}) if isinstance(api_data, dict) else {}
        fixture_info = fixture_bundle.get("fixture", {}) if isinstance(fixture_bundle, dict) else {}
        teams_info = fixture_bundle.get("teams", {}) if isinstance(fixture_bundle, dict) else {}
        league_info = fixture_bundle.get("league", {}) if isinstance(fixture_bundle, dict) else {}
        goals_info = fixture_bundle.get("goals", {}) if isinstance(fixture_bundle, dict) else {}

        fixture_id = match_data.get("fixture_id") or fixture_info.get("id")
        if fixture_id is None:
            return
        fixture_id = int(fixture_id)

        kickoff_utc = _text_or_none(fixture_info.get("date")) or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        status = (
            _text_or_none((fixture_info.get("status") or {}).get("short"))
            if isinstance(fixture_info.get("status"), dict)
            else _text_or_none(fixture_info.get("status"))
        ) or "NS"

        league_id = league_info.get("id")
        home_team = teams_info.get("home", {}) if isinstance(teams_info.get("home"), dict) else {}
        away_team = teams_info.get("away", {}) if isinstance(teams_info.get("away"), dict) else {}
        home_team_id = home_team.get("id")
        away_team_id = away_team.get("id")

        venue = fixture_info.get("venue", {}) if isinstance(fixture_info.get("venue"), dict) else {}
        venue_name = _text_or_none(venue.get("name"))
        round_name = _text_or_none(league_info.get("round"))

        scraped_data = match_data.get("scraped_data", {}) if isinstance(match_data, dict) else {}
        weather_payload = scraped_data.get("weather_forecast")
        pitch_payload = scraped_data.get("pitch_conditions")
        home_news_payload = scraped_data.get("home_team_news")
        away_news_payload = scraped_data.get("away_team_news")

        home_injuries = api_data.get("home_team_injuries", []) if isinstance(api_data, dict) else []
        away_injuries = api_data.get("away_team_injuries", []) if isinstance(api_data, dict) else []
        key_injuries = {
            "home": home_injuries if isinstance(home_injuries, list) else [],
            "away": away_injuries if isinstance(away_injuries, list) else [],
        }

        async with get_db() as db:
            if league_id is not None:
                await db.execute(
                    """
                    INSERT INTO leagues (id, name, country, logo_url, season)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        country = excluded.country,
                        logo_url = excluded.logo_url,
                        season = excluded.season
                    """,
                    (
                        int(league_id),
                        _text_or_none(league_info.get("name")) or "Unknown",
                        _text_or_none(league_info.get("country")),
                        _text_or_none(league_info.get("logo")),
                        league_info.get("season"),
                    ),
                )

            if home_team_id is not None:
                await db.execute(
                    """
                    INSERT INTO teams (id, name, short_name, logo_url, country)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        short_name = excluded.short_name,
                        logo_url = excluded.logo_url,
                        country = excluded.country
                    """,
                    (
                        int(home_team_id),
                        _text_or_none(home_team.get("name")) or "Unknown",
                        _text_or_none(home_team.get("name")),
                        _text_or_none(home_team.get("logo")),
                        _text_or_none(league_info.get("country")),
                    ),
                )

            if away_team_id is not None:
                await db.execute(
                    """
                    INSERT INTO teams (id, name, short_name, logo_url, country)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        short_name = excluded.short_name,
                        logo_url = excluded.logo_url,
                        country = excluded.country
                    """,
                    (
                        int(away_team_id),
                        _text_or_none(away_team.get("name")) or "Unknown",
                        _text_or_none(away_team.get("name")),
                        _text_or_none(away_team.get("logo")),
                        _text_or_none(league_info.get("country")),
                    ),
                )

            await db.execute(
                """
                INSERT INTO fixtures (
                    id, league_id, home_team_id, away_team_id, kickoff_utc, status,
                    home_score, away_score, round, venue_name, md_report_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    league_id = excluded.league_id,
                    home_team_id = excluded.home_team_id,
                    away_team_id = excluded.away_team_id,
                    kickoff_utc = excluded.kickoff_utc,
                    status = excluded.status,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    round = excluded.round,
                    venue_name = excluded.venue_name,
                    md_report_path = COALESCE(excluded.md_report_path, fixtures.md_report_path)
                """,
                (
                    fixture_id,
                    int(league_id) if league_id is not None else None,
                    int(home_team_id) if home_team_id is not None else None,
                    int(away_team_id) if away_team_id is not None else None,
                    kickoff_utc,
                    status,
                    goals_info.get("home") if isinstance(goals_info, dict) else None,
                    goals_info.get("away") if isinstance(goals_info, dict) else None,
                    round_name,
                    venue_name,
                    md_report_path,
                ),
            )

            await db.execute(
                """
                INSERT INTO match_context (
                    fixture_id,
                    weather_json,
                    pitch_condition,
                    team_news_home,
                    team_news_away,
                    key_injuries,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(fixture_id) DO UPDATE SET
                    weather_json = excluded.weather_json,
                    pitch_condition = excluded.pitch_condition,
                    team_news_home = excluded.team_news_home,
                    team_news_away = excluded.team_news_away,
                    key_injuries = excluded.key_injuries,
                    fetched_at = datetime('now')
                """,
                (
                    fixture_id,
                    _json_or_none(weather_payload),
                    _text_or_none((pitch_payload or {}).get("content") if isinstance(pitch_payload, dict) else pitch_payload),
                    _text_or_none((home_news_payload or {}).get("content") if isinstance(home_news_payload, dict) else home_news_payload),
                    _text_or_none((away_news_payload or {}).get("content") if isinstance(away_news_payload, dict) else away_news_payload),
                    _json_or_none(key_injuries),
                ),
            )

            await db.commit()
    except Exception as exc:
        logger.debug("Skipping match payload persistence due to error: %s", exc)
