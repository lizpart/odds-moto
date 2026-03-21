"""
API-Football Client

A comprehensive Python client for the API-Football v3 API.
Provides access to all available endpoints including:
- Countries, Seasons, Leagues, Standings
- Teams, Players, Coaches
- Fixtures, Events, Lineups, Statistics
- Head-to-Head, Predictions
- Injuries, Sidelined
- Transfers, Trophies
- Odds (Pre-match and In-play)
- Top Scorers, Player Statistics
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
import json

logger = logging.getLogger("api_football")


class APIFootballClient:
    """
    Async client for API-Football v3 API.
    
    Base URL: https://v3.football.api-sports.io
    Authentication: x-apisports-key header
    """
    
    BASE_URL = "https://v3.football.api-sports.io"
    
    def __init__(self, api_key: str, rate_limit_per_minute: int = 30):
        """
        Initialize the API-Football client.
        
        Args:
            api_key: Your API-Football API key
            rate_limit_per_minute: Maximum requests per minute (default 30 for free tier)
        """
        self.api_key = api_key
        self.rate_limit = rate_limit_per_minute
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_times: List[float] = []
        
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "x-apisports-key": self.api_key
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session
    
    async def _rate_limit_check(self) -> None:
        """Check and enforce rate limiting."""
        now = datetime.now().timestamp()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        if len(self._request_times) >= self.rate_limit:
            # Wait until oldest request is more than 1 minute old
            wait_time = 60 - (now - self._request_times[0]) + 0.1
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        
        self._request_times.append(now)
    
    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make an API request.
        
        Args:
            endpoint: API endpoint (e.g., '/fixtures')
            params: Query parameters
            
        Returns:
            API response as dictionary
        """
        await self._rate_limit_check()
        
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if response.status != 200:
                    logger.error(f"API error: {response.status} - {data}")
                    return {"errors": data, "response": []}
                
                # Log API usage info if available
                if "errors" in data and data["errors"]:
                    logger.warning(f"API warnings: {data['errors']}")
                
                return data
                
        except Exception as e:
            logger.error(f"Request failed for {endpoint}: {e}")
            return {"errors": {"request": str(e)}, "response": []}
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ==================== STATUS & INFO ====================
    
    async def get_status(self) -> Dict:
        """Get API status and account information."""
        return await self._request("/status")
    
    async def get_timezone(self) -> Dict:
        """Get list of available timezones."""
        return await self._request("/timezone")

    # ==================== COUNTRIES ====================
    
    async def get_countries(self, name: str = None, code: str = None, search: str = None) -> Dict:
        """
        Get available countries.
        
        Args:
            name: Country name (exact match)
            code: Country code (e.g., 'GB', 'FR')
            search: Search term (min 3 chars)
        """
        params = {}
        if name: params["name"] = name
        if code: params["code"] = code
        if search: params["search"] = search
        return await self._request("/countries", params if params else None)

    # ==================== SEASONS ====================
    
    async def get_seasons(self) -> Dict:
        """Get all available seasons."""
        return await self._request("/seasons")

    # ==================== LEAGUES ====================
    
    async def get_leagues(self, id: int = None, name: str = None, country: str = None,
                          code: str = None, season: int = None, team: int = None,
                          type: str = None, current: str = None, search: str = None,
                          last: int = None) -> Dict:
        """
        Get leagues and cups.
        
        Args:
            id: League ID
            name: League name
            country: Country name
            code: Country code
            season: Season year
            team: Team ID
            type: 'league' or 'cup'
            current: 'true' or 'false'
            search: Search term
            last: Last X leagues
        """
        params = {}
        if id: params["id"] = id
        if name: params["name"] = name
        if country: params["country"] = country
        if code: params["code"] = code
        if season: params["season"] = season
        if team: params["team"] = team
        if type: params["type"] = type
        if current: params["current"] = current
        if search: params["search"] = search
        if last: params["last"] = last
        return await self._request("/leagues", params if params else None)

    # ==================== TEAMS ====================

    async def get_teams(self, id: int = None, name: str = None, league: int = None,
                        season: int = None, country: str = None, code: str = None,
                        venue: int = None, search: str = None) -> Dict:
        """
        Get teams information.

        Args:
            id: Team ID
            name: Team name
            league: League ID
            season: Season year
            country: Country name
            code: Country code
            venue: Venue ID
            search: Search term (min 3 chars)
        """
        params = {}
        if id: params["id"] = id
        if name: params["name"] = name
        if league: params["league"] = league
        if season: params["season"] = season
        if country: params["country"] = country
        if code: params["code"] = code
        if venue: params["venue"] = venue
        if search: params["search"] = search
        return await self._request("/teams", params if params else None)

    async def get_team_statistics(self, league: int, season: int, team: int, date: str = None) -> Dict:
        """
        Get team statistics for a league/season.

        Args:
            league: League ID (required)
            season: Season year (required)
            team: Team ID (required)
            date: Limit stats to before this date (YYYY-MM-DD)
        """
        params = {"league": league, "season": season, "team": team}
        if date: params["date"] = date
        return await self._request("/teams/statistics", params)

    async def get_team_seasons(self, team: int) -> Dict:
        """Get all seasons for a team."""
        return await self._request("/teams/seasons", {"team": team})

    async def get_team_countries(self) -> Dict:
        """Get all countries with teams."""
        return await self._request("/teams/countries")

    # ==================== VENUES ====================

    async def get_venues(self, id: int = None, name: str = None, city: str = None,
                         country: str = None, search: str = None) -> Dict:
        """
        Get venues/stadiums information.

        Args:
            id: Venue ID
            name: Venue name
            city: City name
            country: Country name
            search: Search term
        """
        params = {}
        if id: params["id"] = id
        if name: params["name"] = name
        if city: params["city"] = city
        if country: params["country"] = country
        if search: params["search"] = search
        return await self._request("/venues", params if params else None)

    # ==================== STANDINGS ====================

    async def get_standings(self, league: int = None, season: int = None, team: int = None) -> Dict:
        """
        Get league standings.

        Args:
            league: League ID
            season: Season year (required with league)
            team: Team ID (to get standings for specific team)
        """
        params = {}
        if league: params["league"] = league
        if season: params["season"] = season
        if team: params["team"] = team
        return await self._request("/standings", params if params else None)

    # ==================== FIXTURES ====================

    async def get_fixtures(self, id: int = None, ids: str = None, live: str = None,
                           date: str = None, league: int = None, season: int = None,
                           team: int = None, last: int = None, next: int = None,
                           from_date: str = None, to_date: str = None, round: str = None,
                           status: str = None, venue: int = None, timezone: str = None) -> Dict:
        """
        Get fixtures.

        Args:
            id: Fixture ID
            ids: Multiple fixture IDs (comma-separated, max 20)
            live: 'all' or league IDs for live fixtures
            date: Date (YYYY-MM-DD)
            league: League ID
            season: Season year
            team: Team ID
            last: Last X fixtures
            next: Next X fixtures
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            round: Round name
            status: Fixture status
            venue: Venue ID
            timezone: Timezone
        """
        params = {}
        if id: params["id"] = id
        if ids: params["ids"] = ids
        if live: params["live"] = live
        if date: params["date"] = date
        if league: params["league"] = league
        if season: params["season"] = season
        if team: params["team"] = team
        if last: params["last"] = last
        if next: params["next"] = next
        if from_date: params["from"] = from_date
        if to_date: params["to"] = to_date
        if round: params["round"] = round
        if status: params["status"] = status
        if venue: params["venue"] = venue
        if timezone: params["timezone"] = timezone
        return await self._request("/fixtures", params if params else None)

    async def get_fixture_rounds(self, league: int, season: int, current: bool = None) -> Dict:
        """Get rounds for a league/season."""
        params = {"league": league, "season": season}
        if current is not None: params["current"] = str(current).lower()
        return await self._request("/fixtures/rounds", params)

    # ==================== HEAD TO HEAD ====================

    async def get_head_to_head(self, h2h: str, date: str = None, league: int = None,
                               season: int = None, last: int = None, from_date: str = None,
                               to_date: str = None, status: str = None, venue: int = None,
                               timezone: str = None) -> Dict:
        """
        Get head-to-head fixtures between two teams.

        Args:
            h2h: Team IDs separated by '-' (e.g., '33-34')
            date: Date filter (YYYY-MM-DD)
            league: League ID
            season: Season year
            last: Last X fixtures
            from_date: Start date
            to_date: End date
            status: Fixture status
            venue: Venue ID
            timezone: Timezone
        """
        params = {"h2h": h2h}
        if date: params["date"] = date
        if league: params["league"] = league
        if season: params["season"] = season
        if last: params["last"] = last
        if from_date: params["from"] = from_date
        if to_date: params["to"] = to_date
        if status: params["status"] = status
        if venue: params["venue"] = venue
        if timezone: params["timezone"] = timezone
        return await self._request("/fixtures/headtohead", params)

    # ==================== FIXTURE STATISTICS ====================

    async def get_fixture_statistics(self, fixture: int, team: int = None, type: str = None) -> Dict:
        """
        Get statistics for a fixture.

        Args:
            fixture: Fixture ID (required)
            team: Team ID to filter
            type: Statistic type (e.g., 'Shots on Goal', 'Ball Possession')
        """
        params = {"fixture": fixture}
        if team: params["team"] = team
        if type: params["type"] = type
        return await self._request("/fixtures/statistics", params)

    # ==================== FIXTURE EVENTS ====================

    async def get_fixture_events(self, fixture: int, team: int = None, player: int = None,
                                  type: str = None) -> Dict:
        """
        Get events for a fixture (goals, cards, substitutions).

        Args:
            fixture: Fixture ID (required)
            team: Team ID to filter
            player: Player ID to filter
            type: Event type ('Goal', 'Card', 'subst', 'Var')
        """
        params = {"fixture": fixture}
        if team: params["team"] = team
        if player: params["player"] = player
        if type: params["type"] = type
        return await self._request("/fixtures/events", params)

    # ==================== LINEUPS ====================

    async def get_fixture_lineups(self, fixture: int, team: int = None, player: int = None,
                                   type: str = None) -> Dict:
        """
        Get lineups for a fixture.

        Args:
            fixture: Fixture ID (required)
            team: Team ID to filter
            player: Player ID to filter
            type: Player type
        """
        params = {"fixture": fixture}
        if team: params["team"] = team
        if player: params["player"] = player
        if type: params["type"] = type
        return await self._request("/fixtures/lineups", params)

    # ==================== PLAYERS FIXTURE STATISTICS ====================

    async def get_fixture_players(self, fixture: int, team: int = None) -> Dict:
        """
        Get player statistics for a fixture.

        Args:
            fixture: Fixture ID (required)
            team: Team ID to filter
        """
        params = {"fixture": fixture}
        if team: params["team"] = team
        return await self._request("/fixtures/players", params)

    # ==================== PREDICTIONS ====================

    async def get_predictions(self, fixture: int) -> Dict:
        """
        Get predictions for a fixture.

        Args:
            fixture: Fixture ID (required)
        """
        return await self._request("/predictions", {"fixture": fixture})

    # ==================== INJURIES ====================

    async def get_injuries(self, league: int = None, season: int = None, fixture: int = None,
                           team: int = None, player: int = None, date: str = None,
                           timezone: str = None) -> Dict:
        """
        Get injured/suspended players.

        Args:
            league: League ID
            season: Season year
            fixture: Fixture ID
            team: Team ID
            player: Player ID
            date: Date (YYYY-MM-DD)
            timezone: Timezone
        """
        params = {}
        if league: params["league"] = league
        if season: params["season"] = season
        if fixture: params["fixture"] = fixture
        if team: params["team"] = team
        if player: params["player"] = player
        if date: params["date"] = date
        if timezone: params["timezone"] = timezone
        return await self._request("/injuries", params if params else None)

    # ==================== PLAYERS ====================

    async def get_players(self, id: int = None, team: int = None, league: int = None,
                          season: int = None, search: str = None, page: int = None) -> Dict:
        """
        Get players.

        Args:
            id: Player ID
            team: Team ID
            league: League ID
            season: Season year (required with team or league)
            search: Search term (min 4 chars)
            page: Page number for pagination
        """
        params = {}
        if id: params["id"] = id
        if team: params["team"] = team
        if league: params["league"] = league
        if season: params["season"] = season
        if search: params["search"] = search
        if page: params["page"] = page
        return await self._request("/players", params if params else None)

    async def get_player_seasons(self, player: int = None) -> Dict:
        """Get all available seasons for players (or specific player)."""
        params = {"player": player} if player else None
        return await self._request("/players/seasons", params)

    async def get_player_squads(self, player: int = None, team: int = None) -> Dict:
        """
        Get current squad for a team or teams for a player.

        Args:
            player: Player ID (to get all teams for player)
            team: Team ID (to get current squad)
        """
        params = {}
        if player: params["player"] = player
        if team: params["team"] = team
        return await self._request("/players/squads", params if params else None)

    async def get_top_scorers(self, league: int, season: int) -> Dict:
        """Get top scorers for a league/season."""
        return await self._request("/players/topscorers", {"league": league, "season": season})

    async def get_top_assists(self, league: int, season: int) -> Dict:
        """Get top assists for a league/season."""
        return await self._request("/players/topassists", {"league": league, "season": season})

    async def get_top_yellow_cards(self, league: int, season: int) -> Dict:
        """Get players with most yellow cards for a league/season."""
        return await self._request("/players/topyellowcards", {"league": league, "season": season})

    async def get_top_red_cards(self, league: int, season: int) -> Dict:
        """Get players with most red cards for a league/season."""
        return await self._request("/players/topredcards", {"league": league, "season": season})

    # ==================== COACHES ====================

    async def get_coaches(self, id: int = None, team: int = None, search: str = None) -> Dict:
        """
        Get coaches.

        Args:
            id: Coach ID
            team: Team ID
            search: Search term (min 3 chars)
        """
        params = {}
        if id: params["id"] = id
        if team: params["team"] = team
        if search: params["search"] = search
        return await self._request("/coachs", params if params else None)

    # ==================== TRANSFERS ====================

    async def get_transfers(self, player: int = None, team: int = None) -> Dict:
        """
        Get player transfers.

        Args:
            player: Player ID
            team: Team ID
        """
        params = {}
        if player: params["player"] = player
        if team: params["team"] = team
        return await self._request("/transfers", params if params else None)

    # ==================== TROPHIES ====================

    async def get_trophies(self, player: int = None, coach: int = None) -> Dict:
        """
        Get trophies won by a player or coach.

        Args:
            player: Player ID
            coach: Coach ID
        """
        params = {}
        if player: params["player"] = player
        if coach: params["coach"] = coach
        return await self._request("/trophies", params if params else None)

    # ==================== SIDELINED ====================

    async def get_sidelined(self, player: int = None, coach: int = None) -> Dict:
        """
        Get sidelined (injured/suspended) history.

        Args:
            player: Player ID
            coach: Coach ID
        """
        params = {}
        if player: params["player"] = player
        if coach: params["coach"] = coach
        return await self._request("/sidelined", params if params else None)

    # ==================== ODDS ====================

    async def get_odds(self, fixture: int = None, league: int = None, season: int = None,
                       date: str = None, timezone: str = None, page: int = None,
                       bookmaker: int = None, bet: int = None) -> Dict:
        """
        Get pre-match odds.

        Args:
            fixture: Fixture ID
            league: League ID
            season: Season year
            date: Date (YYYY-MM-DD)
            timezone: Timezone
            page: Page number
            bookmaker: Bookmaker ID
            bet: Bet type ID
        """
        params = {}
        if fixture: params["fixture"] = fixture
        if league: params["league"] = league
        if season: params["season"] = season
        if date: params["date"] = date
        if timezone: params["timezone"] = timezone
        if page: params["page"] = page
        if bookmaker: params["bookmaker"] = bookmaker
        if bet: params["bet"] = bet
        return await self._request("/odds", params if params else None)

    async def get_odds_live(self, fixture: int = None, league: int = None, bet: int = None) -> Dict:
        """
        Get live/in-play odds.

        Args:
            fixture: Fixture ID
            league: League ID
            bet: Bet type ID
        """
        params = {}
        if fixture: params["fixture"] = fixture
        if league: params["league"] = league
        if bet: params["bet"] = bet
        return await self._request("/odds/live", params if params else None)

    async def get_odds_mapping(self, page: int = None) -> Dict:
        """Get odds mapping (fixture to bet IDs)."""
        params = {"page": page} if page else None
        return await self._request("/odds/mapping", params)

    async def get_bookmakers(self, id: int = None, search: str = None) -> Dict:
        """Get available bookmakers."""
        params = {}
        if id: params["id"] = id
        if search: params["search"] = search
        return await self._request("/odds/bookmakers", params if params else None)

    async def get_bets(self, id: int = None, search: str = None) -> Dict:
        """Get available bet types."""
        params = {}
        if id: params["id"] = id
        if search: params["search"] = search
        return await self._request("/odds/bets", params if params else None)

    # ==================== CONVENIENCE METHODS ====================

    async def get_team_by_name(self, name: str, country: str = None) -> Optional[Dict]:
        """
        Find a team by name (search).

        Args:
            name: Team name to search
            country: Optional country filter

        Returns:
            First matching team or None
        """
        result = await self.get_teams(search=name, country=country)
        teams = result.get("response", [])
        return teams[0] if teams else None

    async def get_league_by_name(self, name: str, country: str = None, season: int = None) -> Optional[Dict]:
        """
        Find a league by name.

        Args:
            name: League name to search
            country: Optional country filter
            season: Optional season filter

        Returns:
            First matching league or None
        """
        result = await self.get_leagues(search=name, country=country, season=season)
        leagues = result.get("response", [])
        return leagues[0] if leagues else None

    async def get_fixtures_for_date(self, date: str, league: int = None, season: int = None) -> List[Dict]:
        """
        Get all fixtures for a specific date.

        Args:
            date: Date in YYYY-MM-DD format
            league: Optional league filter
            season: Optional season filter (auto-calculated if league is provided)

        Returns:
            List of fixtures
        """
        # If league is provided but season is not, calculate the current season
        if league and not season:
            # Football seasons typically span two years (e.g., 2024-2025)
            # The season year is usually the year the season started
            from datetime import datetime
            current_date = datetime.strptime(date, "%Y-%m-%d")
            # If we're in Jan-Jul, the season started last year; if Aug-Dec, it started this year
            if current_date.month <= 7:
                season = current_date.year - 1
            else:
                season = current_date.year

        result = await self.get_fixtures(date=date, league=league, season=season)
        return result.get("response", [])

    async def get_team_next_fixtures(self, team: int, count: int = 5) -> List[Dict]:
        """Get next X fixtures for a team."""
        result = await self.get_fixtures(team=team, next=count)
        return result.get("response", [])

    async def get_team_last_fixtures(self, team: int, count: int = 5) -> List[Dict]:
        """Get last X fixtures for a team."""
        result = await self.get_fixtures(team=team, last=count)
        return result.get("response", [])

    async def get_live_fixtures(self, league: int = None) -> List[Dict]:
        """
        Get all live fixtures.

        Args:
            league: Optional league filter

        Returns:
            List of live fixtures
        """
        live_param = str(league) if league else "all"
        result = await self.get_fixtures(live=live_param)
        return result.get("response", [])

    async def get_complete_fixture_data(self, fixture_id: int) -> Dict:
        """
        Get complete data for a fixture including statistics, events, lineups, and predictions.

        Args:
            fixture_id: Fixture ID

        Returns:
            Dictionary with all fixture data
        """
        # Fetch all data in parallel
        fixture_task = self.get_fixtures(id=fixture_id)
        stats_task = self.get_fixture_statistics(fixture=fixture_id)
        events_task = self.get_fixture_events(fixture=fixture_id)
        lineups_task = self.get_fixture_lineups(fixture=fixture_id)
        predictions_task = self.get_predictions(fixture=fixture_id)
        players_task = self.get_fixture_players(fixture=fixture_id)

        results = await asyncio.gather(
            fixture_task, stats_task, events_task,
            lineups_task, predictions_task, players_task,
            return_exceptions=True
        )

        return {
            "fixture": results[0].get("response", [{}])[0] if isinstance(results[0], dict) else {},
            "statistics": results[1].get("response", []) if isinstance(results[1], dict) else [],
            "events": results[2].get("response", []) if isinstance(results[2], dict) else [],
            "lineups": results[3].get("response", []) if isinstance(results[3], dict) else [],
            "predictions": results[4].get("response", [{}])[0] if isinstance(results[4], dict) else {},
            "players": results[5].get("response", []) if isinstance(results[5], dict) else []
        }

    async def get_team_injuries(self, team: int, league: int = None, season: int = None) -> List[Dict]:
        """
        Get current injuries for a team.

        Args:
            team: Team ID
            league: Optional league filter
            season: Optional season filter

        Returns:
            List of injuries
        """
        result = await self.get_injuries(team=team, league=league, season=season)
        return result.get("response", [])

    async def get_match_context(self, fixture_id: int) -> Dict:
        """
        Get comprehensive match context data for analysis.

        This method fetches:
        - Fixture details
        - Team statistics for both teams
        - Injuries for both teams
        - Head-to-head history
        - Predictions
        - Standings for both teams

        Args:
            fixture_id: Fixture ID

        Returns:
            Comprehensive match context dictionary
        """
        # First get fixture details to know teams and league
        fixture_result = await self.get_fixtures(id=fixture_id)
        fixtures = fixture_result.get("response", [])

        if not fixtures:
            return {"error": "Fixture not found"}

        fixture = fixtures[0]
        home_team_id = fixture["teams"]["home"]["id"]
        away_team_id = fixture["teams"]["away"]["id"]
        league_id = fixture["league"]["id"]
        season = fixture["league"]["season"]

        # Fetch all context data in parallel
        h2h_task = self.get_head_to_head(h2h=f"{home_team_id}-{away_team_id}", last=10)
        home_stats_task = self.get_team_statistics(league=league_id, season=season, team=home_team_id)
        away_stats_task = self.get_team_statistics(league=league_id, season=season, team=away_team_id)
        home_injuries_task = self.get_injuries(team=home_team_id, league=league_id, season=season)
        away_injuries_task = self.get_injuries(team=away_team_id, league=league_id, season=season)
        predictions_task = self.get_predictions(fixture=fixture_id)
        standings_task = self.get_standings(league=league_id, season=season)
        home_form_task = self.get_fixtures(team=home_team_id, last=5)
        away_form_task = self.get_fixtures(team=away_team_id, last=5)

        results = await asyncio.gather(
            h2h_task, home_stats_task, away_stats_task,
            home_injuries_task, away_injuries_task, predictions_task,
            standings_task, home_form_task, away_form_task,
            return_exceptions=True
        )

        return {
            "fixture": fixture,
            "head_to_head": results[0].get("response", []) if isinstance(results[0], dict) else [],
            "home_team_statistics": results[1].get("response", {}) if isinstance(results[1], dict) else {},
            "away_team_statistics": results[2].get("response", {}) if isinstance(results[2], dict) else {},
            "home_team_injuries": results[3].get("response", []) if isinstance(results[3], dict) else [],
            "away_team_injuries": results[4].get("response", []) if isinstance(results[4], dict) else [],
            "predictions": results[5].get("response", [{}])[0] if isinstance(results[5], dict) else {},
            "standings": results[6].get("response", []) if isinstance(results[6], dict) else [],
            "home_team_form": results[7].get("response", []) if isinstance(results[7], dict) else [],
            "away_team_form": results[8].get("response", []) if isinstance(results[8], dict) else []
        }

