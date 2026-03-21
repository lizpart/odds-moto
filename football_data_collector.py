"""
Unified Football Data Collector

This module provides a unified interface for collecting football match data.
It uses API-Football as the PRIMARY and ONLY data source for fixtures.
Web scraping is used only for supplementary data not available through the API
(weather, pitch conditions, latest news).

Usage Examples:
    # Get all fixtures for today
    python football_data_collector.py --date 2025-12-16 --process

    # Get all fixtures for a specific league today
    python football_data_collector.py --date 2025-12-16 --league 39 --process

    # Get fixtures for multiple leagues
    python football_data_collector.py --date 2025-12-16 --leagues 39,135,140 --process

    # Process a single fixture
    python football_data_collector.py --fixture 12345

    # Get next 5 fixtures for a team
    python football_data_collector.py --team "Liverpool" --next 5 --process
"""

import asyncio
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from api_football_client import APIFootballClient

# Try to import scraper (optional dependency)
try:
    from football_data_scraper import FootballDataScraper, GoogleSearchClient
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False

logger = logging.getLogger("football_data_collector")


# Common league IDs for quick reference
POPULAR_LEAGUES = {
    # England
    "premier_league": 39,
    "championship": 40,
    "league_one": 41,
    "league_two": 42,
    "fa_cup": 45,
    "efl_cup": 48,
    # Spain
    "la_liga": 140,
    "la_liga_2": 141,
    "copa_del_rey": 143,
    # Italy
    "serie_a": 135,
    "serie_b": 136,
    "coppa_italia": 137,
    # Germany
    "bundesliga": 78,
    "bundesliga_2": 79,
    "dfb_pokal": 81,
    # France
    "ligue_1": 61,
    "ligue_2": 62,
    "coupe_de_france": 66,
    # Champions League & Europa
    "champions_league": 2,
    "europa_league": 3,
    "conference_league": 848,
    # Other top leagues
    "eredivisie": 88,
    "primeira_liga": 94,
    "scottish_premiership": 179,
    "mls": 253,
}


class FootballDataCollector:
    """
    Unified data collector that combines API-Football data with web scraping.
    
    API-Football provides:
    - Countries, Seasons, Leagues, Standings
    - Teams, Players, Coaches
    - Fixtures, Events, Lineups, Statistics
    - Head-to-Head, Predictions
    - Injuries, Sidelined, Transfers, Trophies
    - Odds (Pre-match and In-play)
    
    Web Scraping provides (complementary):
    - Weather forecasts
    - Pitch conditions
    - Latest team news (real-time updates)
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the data collector.

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)

        # Initialize API-Football client
        api_config = self.config.get("api_football", {})
        self.api_client = APIFootballClient(
            api_key=api_config.get("api_key", ""),
            rate_limit_per_minute=api_config.get("rate_limit_per_minute", 30)
        )
        self.api_enabled = api_config.get("enabled", True)

        # Initialize scraper for complementary data (if available)
        self.scraper = None
        self.search_client = None
        self.scraper_available = SCRAPER_AVAILABLE

        if SCRAPER_AVAILABLE:
            try:
                self.scraper = FootballDataScraper(config_path)
                self.search_client = GoogleSearchClient(
                    sleep_interval=self.config.get("search", {}).get("sleep_interval", 5)
                )
            except Exception as e:
                logger.warning(f"Could not initialize scraper: {e}")
                self.scraper_available = False

        # Data source configuration
        self.data_sources = self.config.get("data_sources", {})
        self.scraper_only_data = self.data_sources.get("scraper_only_data", [
            "weather_forecast", "pitch_conditions", "latest_news"
        ])

        # Cache directory
        self.cache_dir = Path(self.config.get("cache_dir", "cache"))
        self.cache_dir.mkdir(exist_ok=True)

        # Output directory
        self.output_dir = Path(self.config.get("output_dir", "output"))
        self.output_dir.mkdir(exist_ok=True)

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    async def close(self) -> None:
        """Close all clients and clean up resources."""
        await self.api_client.close()
        if self.scraper:
            await self.scraper.close()

    # ==================== API STATUS ====================
    
    async def check_api_status(self) -> Dict:
        """Check API-Football status and account information."""
        return await self.api_client.get_status()

    # ==================== LEAGUES & COMPETITIONS ====================
    
    async def get_available_leagues(self, country: str = None, season: int = None) -> List[Dict]:
        """Get all available leagues, optionally filtered by country or season."""
        result = await self.api_client.get_leagues(country=country, season=season)
        return result.get("response", [])
    
    async def get_league_standings(self, league_id: int, season: int) -> Dict:
        """Get standings for a specific league and season."""
        result = await self.api_client.get_standings(league=league_id, season=season)
        standings = result.get("response", [])
        return standings[0] if standings else {}

    # ==================== TEAMS ====================
    
    async def search_team(self, name: str, country: str = None) -> Optional[Dict]:
        """Search for a team by name."""
        return await self.api_client.get_team_by_name(name, country)
    
    async def get_team_info(self, team_id: int) -> Dict:
        """Get complete team information."""
        result = await self.api_client.get_teams(id=team_id)
        teams = result.get("response", [])
        return teams[0] if teams else {}
    
    async def get_team_squad(self, team_id: int) -> List[Dict]:
        """Get current squad for a team."""
        result = await self.api_client.get_player_squads(team=team_id)
        return result.get("response", [])

    # ==================== FIXTURES ====================

    async def get_fixtures_by_date(self, date: str, league_id: int = None,
                                    season: int = None) -> List[Dict]:
        """Get fixtures for a specific date."""
        return await self.api_client.get_fixtures_for_date(date, league_id, season)

    async def get_fixtures_for_leagues(self, date: str, league_ids: List[int],
                                        season: int = None) -> List[Dict]:
        """
        Get fixtures for multiple leagues on a specific date.

        Args:
            date: Date in YYYY-MM-DD format
            league_ids: List of league IDs
            season: Season year (optional)

        Returns:
            List of all fixtures across the specified leagues
        """
        all_fixtures = []
        for league_id in league_ids:
            fixtures = await self.api_client.get_fixtures_for_date(date, league_id, season)
            all_fixtures.extend(fixtures)
            logger.info(f"Found {len(fixtures)} fixtures for league {league_id} on {date}")
        return all_fixtures

    async def get_live_fixtures(self, league_id: int = None) -> List[Dict]:
        """Get all currently live fixtures."""
        return await self.api_client.get_live_fixtures(league_id)

    async def get_team_fixtures(self, team_id: int, next_count: int = None,
                                 last_count: int = None) -> List[Dict]:
        """Get fixtures for a team."""
        if next_count:
            return await self.api_client.get_team_next_fixtures(team_id, next_count)
        elif last_count:
            return await self.api_client.get_team_last_fixtures(team_id, last_count)
        else:
            result = await self.api_client.get_fixtures(team=team_id)
            return result.get("response", [])

    # ==================== BATCH PROCESSING ====================

    async def process_fixtures(self, fixtures: List[Dict], include_scraper_data: bool = True,
                               save_reports: bool = True) -> List[Dict]:
        """
        Process multiple fixtures and generate reports.

        Args:
            fixtures: List of fixture data from API
            include_scraper_data: Whether to collect weather, pitch, news data
            save_reports: Whether to save markdown reports

        Returns:
            List of processed match data dictionaries
        """
        results = []
        total = len(fixtures)

        for i, fixture in enumerate(fixtures, 1):
            fixture_info = fixture.get("fixture", {})
            fixture_id = fixture_info.get("id")
            teams = fixture.get("teams", {})
            home_team = teams.get("home", {}).get("name", "Unknown")
            away_team = teams.get("away", {}).get("name", "Unknown")

            print(f"[{i}/{total}] Processing {home_team} vs {away_team} (ID: {fixture_id})")

            try:
                match_data = await self.get_match_context(fixture_id, include_scraper_data)

                if save_reports:
                    output_path = await self.save_match_report(match_data)
                    print(f"        → Report saved: {output_path}")

                results.append(match_data)
            except Exception as e:
                logger.error(f"Error processing fixture {fixture_id}: {e}")
                print(f"        → Error: {e}")

        return results

    async def process_date(self, date: str, league_id: int = None,
                           league_ids: List[int] = None, include_scraper_data: bool = True,
                           save_reports: bool = True) -> List[Dict]:
        """
        Process all fixtures for a given date.

        Args:
            date: Date in YYYY-MM-DD format
            league_id: Single league ID (optional)
            league_ids: List of league IDs (optional)
            include_scraper_data: Whether to collect supplementary data
            save_reports: Whether to save markdown reports

        Returns:
            List of processed match data
        """
        print(f"\n{'='*60}")
        print(f"Processing fixtures for {date}")
        print(f"{'='*60}\n")

        # Get fixtures
        if league_ids:
            fixtures = await self.get_fixtures_for_leagues(date, league_ids)
            print(f"Found {len(fixtures)} fixtures across {len(league_ids)} leagues\n")
        elif league_id:
            fixtures = await self.get_fixtures_by_date(date, league_id)
            print(f"Found {len(fixtures)} fixtures for league {league_id}\n")
        else:
            fixtures = await self.get_fixtures_by_date(date)
            print(f"Found {len(fixtures)} fixtures\n")

        if not fixtures:
            print("No fixtures found for the specified criteria.")
            return []

        return await self.process_fixtures(fixtures, include_scraper_data, save_reports)

    async def process_team_fixtures(self, team_id: int, next_count: int = None,
                                     last_count: int = None, include_scraper_data: bool = True,
                                     save_reports: bool = True) -> List[Dict]:
        """
        Process fixtures for a specific team.

        Args:
            team_id: Team ID
            next_count: Number of upcoming fixtures
            last_count: Number of past fixtures
            include_scraper_data: Whether to collect supplementary data
            save_reports: Whether to save markdown reports

        Returns:
            List of processed match data
        """
        fixtures = await self.get_team_fixtures(team_id, next_count, last_count)

        if not fixtures:
            print(f"No fixtures found for team {team_id}")
            return []

        print(f"\nFound {len(fixtures)} fixtures for team {team_id}\n")
        return await self.process_fixtures(fixtures, include_scraper_data, save_reports)

    async def process_live_fixtures(self, league_id: int = None,
                                     include_scraper_data: bool = True,
                                     save_reports: bool = True) -> List[Dict]:
        """
        Process all currently live fixtures.

        Args:
            league_id: Filter by league ID (optional)
            include_scraper_data: Whether to collect supplementary data
            save_reports: Whether to save markdown reports

        Returns:
            List of processed match data
        """
        fixtures = await self.get_live_fixtures(league_id)

        if not fixtures:
            print("No live fixtures found")
            return []

        print(f"\nFound {len(fixtures)} live fixtures\n")
        return await self.process_fixtures(fixtures, include_scraper_data, save_reports)

    # ==================== COMPREHENSIVE MATCH DATA ====================

    async def get_match_context(self, fixture_id: int, include_scraper_data: bool = True) -> Dict:
        """
        Get comprehensive match context data.

        This combines:
        - API-Football data (fixture, teams, stats, injuries, h2h, predictions, odds)
        - Scraped data (weather, pitch conditions, latest news)

        Args:
            fixture_id: API-Football fixture ID
            include_scraper_data: Whether to include scraped data

        Returns:
            Comprehensive match data dictionary
        """
        logger.info(f"Collecting comprehensive data for fixture {fixture_id}")

        # Get API-Football data
        api_data = await self.api_client.get_match_context(fixture_id)

        if "error" in api_data:
            return api_data

        fixture = api_data.get("fixture", {})

        # Get venue and team info for scraping
        venue_info = fixture.get("fixture", {}).get("venue", {})
        venue_name = venue_info.get("name", "Unknown")
        venue_city = venue_info.get("city", "Unknown")
        match_date = fixture.get("fixture", {}).get("date", "")[:10]  # YYYY-MM-DD

        home_team = fixture.get("teams", {}).get("home", {}).get("name", "Unknown")
        away_team = fixture.get("teams", {}).get("away", {}).get("name", "Unknown")

        # Initialize result with API data
        result = {
            "fixture_id": fixture_id,
            "source": "api_football",
            "collected_at": datetime.now().isoformat(),
            "api_data": api_data,
            "scraped_data": {}
        }

        # Add scraped data if enabled and available
        if include_scraper_data and self.scraper_available and self.data_sources.get("fallback_to_scraper", True):
            scraped = await self._collect_scraper_data(
                home_team=home_team,
                away_team=away_team,
                venue_name=venue_name,
                venue_city=venue_city,
                match_date=match_date
            )
            result["scraped_data"] = scraped

        return result

    async def _collect_scraper_data(self, home_team: str, away_team: str,
                                     venue_name: str, venue_city: str,
                                     match_date: str) -> Dict:
        """
        Collect complementary data via web scraping.

        This data is not available in API-Football:
        - Weather forecasts
        - Pitch conditions
        - Latest breaking news
        """
        if not self.scraper_available or not self.scraper:
            logger.info("Scraper not available, skipping scraped data collection")
            return {}

        logger.info(f"Collecting scraped data for {home_team} vs {away_team}")

        scraped_data = {}

        try:
            # Weather forecast
            if "weather_forecast" in self.scraper_only_data:
                weather = await self.scraper._collect_weather_forecast(venue_city, match_date)
                scraped_data["weather_forecast"] = weather

            # Pitch conditions
            if "pitch_conditions" in self.scraper_only_data:
                pitch = await self.scraper._collect_pitch_conditions(venue_name)
                scraped_data["pitch_conditions"] = pitch

            # Latest news (more real-time than API)
            if "latest_news" in self.scraper_only_data:
                home_news = await self.scraper._collect_team_news(home_team, "home")
                away_news = await self.scraper._collect_team_news(away_team, "away")
                scraped_data["home_team_news"] = home_news
                scraped_data["away_team_news"] = away_news
        except Exception as e:
            logger.warning(f"Error collecting scraped data: {e}")

        return scraped_data

    # ==================== INJURIES & SUSPENSIONS ====================

    async def get_team_injuries(self, team_id: int, league_id: int = None,
                                 season: int = None) -> List[Dict]:
        """Get current injuries for a team."""
        result = await self.api_client.get_injuries(
            team=team_id, league=league_id, season=season
        )
        return result.get("response", [])

    async def get_fixture_injuries(self, fixture_id: int) -> List[Dict]:
        """Get injuries for a specific fixture."""
        result = await self.api_client.get_injuries(fixture=fixture_id)
        return result.get("response", [])

    # ==================== PREDICTIONS & ODDS ====================

    async def get_match_predictions(self, fixture_id: int) -> Dict:
        """Get predictions for a fixture."""
        result = await self.api_client.get_predictions(fixture=fixture_id)
        predictions = result.get("response", [])
        return predictions[0] if predictions else {}

    async def get_match_odds(self, fixture_id: int, bookmaker_id: int = None) -> List[Dict]:
        """Get pre-match odds for a fixture."""
        result = await self.api_client.get_odds(fixture=fixture_id, bookmaker=bookmaker_id)
        return result.get("response", [])

    async def get_live_odds(self, fixture_id: int = None, league_id: int = None) -> List[Dict]:
        """Get live/in-play odds."""
        result = await self.api_client.get_odds_live(fixture=fixture_id, league=league_id)
        return result.get("response", [])

    # ==================== HEAD TO HEAD ====================

    async def get_head_to_head(self, team1_id: int, team2_id: int, last: int = 10) -> List[Dict]:
        """Get head-to-head history between two teams."""
        h2h_string = f"{team1_id}-{team2_id}"
        result = await self.api_client.get_head_to_head(h2h=h2h_string, last=last)
        return result.get("response", [])

    # ==================== PLAYERS & STATISTICS ====================

    async def get_top_scorers(self, league_id: int, season: int) -> List[Dict]:
        """Get top scorers for a league/season."""
        result = await self.api_client.get_top_scorers(league=league_id, season=season)
        return result.get("response", [])

    async def get_top_assists(self, league_id: int, season: int) -> List[Dict]:
        """Get top assists for a league/season."""
        result = await self.api_client.get_top_assists(league=league_id, season=season)
        return result.get("response", [])

    async def get_player_info(self, player_id: int, season: int = None) -> Dict:
        """Get player information."""
        result = await self.api_client.get_players(id=player_id, season=season)
        players = result.get("response", [])
        return players[0] if players else {}

    async def search_player(self, name: str, team_id: int = None,
                            league_id: int = None, season: int = None) -> List[Dict]:
        """Search for a player by name."""
        result = await self.api_client.get_players(
            search=name, team=team_id, league=league_id, season=season
        )
        return result.get("response", [])

    # ==================== COACHES ====================

    async def get_coach_info(self, coach_id: int = None, team_id: int = None) -> Dict:
        """Get coach information."""
        result = await self.api_client.get_coaches(id=coach_id, team=team_id)
        coaches = result.get("response", [])
        return coaches[0] if coaches else {}

    # ==================== TRANSFERS ====================

    async def get_team_transfers(self, team_id: int) -> List[Dict]:
        """Get transfers for a team."""
        result = await self.api_client.get_transfers(team=team_id)
        return result.get("response", [])

    async def get_player_transfers(self, player_id: int) -> List[Dict]:
        """Get transfer history for a player."""
        result = await self.api_client.get_transfers(player=player_id)
        return result.get("response", [])

    # ==================== TROPHIES ====================

    async def get_player_trophies(self, player_id: int) -> List[Dict]:
        """Get trophies won by a player."""
        result = await self.api_client.get_trophies(player=player_id)
        return result.get("response", [])

    async def get_coach_trophies(self, coach_id: int) -> List[Dict]:
        """Get trophies won by a coach."""
        result = await self.api_client.get_trophies(coach=coach_id)
        return result.get("response", [])

    # ==================== FIXTURE DETAILS ====================

    async def get_fixture_lineups(self, fixture_id: int) -> List[Dict]:
        """Get lineups for a fixture."""
        result = await self.api_client.get_fixture_lineups(fixture=fixture_id)
        return result.get("response", [])

    async def get_fixture_events(self, fixture_id: int) -> List[Dict]:
        """Get events (goals, cards, subs) for a fixture."""
        result = await self.api_client.get_fixture_events(fixture=fixture_id)
        return result.get("response", [])

    async def get_fixture_statistics(self, fixture_id: int) -> List[Dict]:
        """Get statistics for a fixture."""
        result = await self.api_client.get_fixture_statistics(fixture=fixture_id)
        return result.get("response", [])

    async def get_fixture_player_stats(self, fixture_id: int) -> List[Dict]:
        """Get player statistics for a fixture."""
        result = await self.api_client.get_fixture_players(fixture=fixture_id)
        return result.get("response", [])

    # ==================== MARKDOWN GENERATION ====================

    def generate_match_report(self, match_data: Dict) -> str:
        """
        Generate a comprehensive markdown report from match data.

        Args:
            match_data: Data from get_match_context()

        Returns:
            Markdown formatted report
        """
        api_data = match_data.get("api_data", {})
        scraped_data = match_data.get("scraped_data", {})

        fixture = api_data.get("fixture", {})

        # Extract team info
        teams = fixture.get("teams", {})
        home_team = teams.get("home", {}).get("name", "Home Team")
        away_team = teams.get("away", {}).get("name", "Away Team")

        # Extract venue info
        venue = fixture.get("fixture", {}).get("venue", {})
        venue_name = venue.get("name", "Unknown Venue")

        # Extract league info
        league = fixture.get("league", {})
        league_name = league.get("name", "Unknown League")
        season = league.get("season", "")

        # Build markdown
        md = f"# {home_team} vs {away_team}\n\n"
        md += f"**League:** {league_name} ({season})\n"
        md += f"**Venue:** {venue_name}\n"
        md += f"**Fixture ID:** {match_data.get('fixture_id')}\n"
        md += f"**Report Generated:** {match_data.get('collected_at')}\n\n"
        md += "---\n\n"

        # Table of Contents
        md += "## Table of Contents\n\n"
        md += "1. [Match Predictions](#predictions)\n"
        md += "2. [Team Statistics](#team-statistics)\n"
        md += "3. [Injuries & Suspensions](#injuries)\n"
        md += "4. [Head to Head](#head-to-head)\n"
        md += "5. [Recent Form](#recent-form)\n"
        md += "6. [Weather & Conditions](#weather-conditions)\n"
        md += "7. [Latest News](#latest-news)\n\n"
        md += "---\n\n"

        # Predictions
        md += "## Predictions\n\n"
        predictions = api_data.get("predictions", {})
        if predictions:
            pred = predictions.get("predictions", {})
            md += f"**Winner Prediction:** {pred.get('winner', {}).get('name', 'N/A')}\n"
            md += f"**Win/Draw Probability:** {pred.get('percent', {})}\n"
            md += f"**Advice:** {pred.get('advice', 'N/A')}\n\n"
        else:
            md += "No predictions available.\n\n"

        # Team Statistics
        md += "## Team Statistics\n\n"
        md += "### Home Team\n\n"
        home_stats = api_data.get("home_team_statistics", {})
        if home_stats:
            md += self._format_team_stats(home_stats)
        else:
            md += "No statistics available.\n\n"

        md += "### Away Team\n\n"
        away_stats = api_data.get("away_team_statistics", {})
        if away_stats:
            md += self._format_team_stats(away_stats)
        else:
            md += "No statistics available.\n\n"

        # Injuries
        md += "## Injuries\n\n"
        md += "### Home Team Injuries\n\n"
        home_injuries = api_data.get("home_team_injuries", [])
        md += self._format_injuries(home_injuries)

        md += "### Away Team Injuries\n\n"
        away_injuries = api_data.get("away_team_injuries", [])
        md += self._format_injuries(away_injuries)

        # Head to Head
        md += "## Head to Head\n\n"
        h2h = api_data.get("head_to_head", [])
        md += self._format_h2h(h2h)

        # Recent Form
        md += "## Recent Form\n\n"
        md += "### Home Team Recent Matches\n\n"
        home_form = api_data.get("home_team_form", [])
        md += self._format_recent_form(home_form)

        md += "### Away Team Recent Matches\n\n"
        away_form = api_data.get("away_team_form", [])
        md += self._format_recent_form(away_form)

        # Weather (from scraper)
        md += "## Weather Conditions\n\n"
        weather = scraped_data.get("weather_forecast", {})
        if weather and weather.get("content"):
            md += weather.get("content", "No weather data available.") + "\n\n"
        else:
            md += "No weather data available.\n\n"

        # Pitch Conditions (from scraper)
        md += "## Pitch Conditions\n\n"
        pitch = scraped_data.get("pitch_conditions", {})
        if pitch and pitch.get("content"):
            md += pitch.get("content", "No pitch data available.") + "\n\n"
        else:
            md += "No pitch condition data available.\n\n"

        # Latest News (from scraper)
        md += "## Latest News\n\n"
        md += "### Home Team News\n\n"
        home_news = scraped_data.get("home_team_news", {})
        if home_news and home_news.get("content"):
            md += home_news.get("content", "No news available.") + "\n\n"
        else:
            md += "No home team news available.\n\n"

        md += "### Away Team News\n\n"
        away_news = scraped_data.get("away_team_news", {})
        if away_news and away_news.get("content"):
            md += away_news.get("content", "No news available.") + "\n\n"
        else:
            md += "No away team news available.\n\n"

        return md

    def _format_team_stats(self, stats: Dict) -> str:
        """Format team statistics as markdown."""
        md = ""
        if not stats:
            return "No statistics available.\n\n"

        # Goals
        goals = stats.get("goals", {})
        if goals:
            md += f"**Goals For:** {goals.get('for', {}).get('total', {}).get('total', 'N/A')}\n"
            md += f"**Goals Against:** {goals.get('against', {}).get('total', {}).get('total', 'N/A')}\n"

        # Form
        form = stats.get("form", "")
        if form:
            md += f"**Current Form:** {form}\n"

        # Fixtures played
        fixtures = stats.get("fixtures", {})
        if fixtures:
            played = fixtures.get("played", {})
            wins = fixtures.get("wins", {})
            draws = fixtures.get("draws", {})
            loses = fixtures.get("loses", {})
            md += f"**Played:** {played.get('total', 'N/A')} (H: {played.get('home', 'N/A')}, A: {played.get('away', 'N/A')})\n"
            md += f"**Wins:** {wins.get('total', 'N/A')} | **Draws:** {draws.get('total', 'N/A')} | **Losses:** {loses.get('total', 'N/A')}\n"

        md += "\n"
        return md

    def _format_injuries(self, injuries: List[Dict]) -> str:
        """Format injuries list as markdown."""
        if not injuries:
            return "No injuries reported.\n\n"

        md = "| Player | Team | Type | Reason |\n"
        md += "|--------|------|------|--------|\n"

        for injury in injuries[:10]:  # Limit to 10
            player = injury.get("player", {})
            team = injury.get("team", {})
            md += f"| {player.get('name', 'N/A')} | {team.get('name', 'N/A')} | "
            md += f"{injury.get('fixture', {}).get('type', 'N/A')} | {injury.get('reason', 'N/A')} |\n"

        md += "\n"
        return md

    def _format_h2h(self, h2h: List[Dict]) -> str:
        """Format head-to-head results as markdown."""
        if not h2h:
            return "No head-to-head data available.\n\n"

        md = "| Date | Home | Score | Away | Venue |\n"
        md += "|------|------|-------|------|-------|\n"

        for match in h2h[:10]:  # Limit to 10
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            goals = match.get("goals", {})

            date = fixture.get("date", "")[:10]
            home = teams.get("home", {}).get("name", "N/A")
            away = teams.get("away", {}).get("name", "N/A")
            home_goals = goals.get("home", "?")
            away_goals = goals.get("away", "?")
            venue = fixture.get("venue", {}).get("name", "N/A")

            md += f"| {date} | {home} | {home_goals}-{away_goals} | {away} | {venue} |\n"

        md += "\n"
        return md

    def _format_recent_form(self, matches: List[Dict]) -> str:
        """Format recent matches as markdown."""
        if not matches:
            return "No recent matches available.\n\n"

        md = "| Date | Opponent | Result | Score |\n"
        md += "|------|----------|--------|-------|\n"

        for match in matches[:5]:  # Limit to 5
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            goals = match.get("goals", {})

            date = fixture.get("date", "")[:10]
            home_team = teams.get("home", {})
            away_team = teams.get("away", {})
            home_goals = goals.get("home", "?")
            away_goals = goals.get("away", "?")

            # Determine result
            if home_team.get("winner"):
                result = "W" if home_team.get("winner") else "L"
            elif away_team.get("winner"):
                result = "L" if away_team.get("winner") else "W"
            else:
                result = "D"

            opponent = away_team.get("name", "N/A")
            md += f"| {date} | {opponent} | {result} | {home_goals}-{away_goals} |\n"

        md += "\n"
        return md

    # ==================== SAVE OUTPUT ====================

    async def save_match_report(self, match_data: Dict, output_path: str = None) -> str:
        """
        Save match report to file.

        Args:
            match_data: Data from get_match_context()
            output_path: Optional output file path

        Returns:
            Path where the file was saved
        """
        markdown = self.generate_match_report(match_data)

        if not output_path:
            fixture_id = match_data.get("fixture_id", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"match_{fixture_id}_{timestamp}.md"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        logger.info(f"Report saved to {output_path}")
        return str(output_path)


# ==================== MAIN ENTRY POINT ====================

def parse_league_ids(leagues_str: str) -> List[int]:
    """Parse comma-separated league IDs or league names."""
    if not leagues_str:
        return []

    result = []
    for item in leagues_str.split(","):
        item = item.strip()
        # Check if it's a number
        if item.isdigit():
            result.append(int(item))
        # Check if it's a known league name
        elif item.lower() in POPULAR_LEAGUES:
            result.append(POPULAR_LEAGUES[item.lower()])
        else:
            logger.warning(f"Unknown league: {item}")

    return result


async def main():
    """Command-line entry point for the unified data collector."""
    parser = argparse.ArgumentParser(
        description="Football Data Collector - API-Football + Web Scraping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check API status
  python football_data_collector.py --status

  # List fixtures for today
  python football_data_collector.py --date 2025-12-20

  # Process all fixtures for a date (generate reports)
  python football_data_collector.py --date 2025-12-20 --process

  # Process Premier League fixtures for a date
  python football_data_collector.py --date 2025-12-20 --league 39 --process

  # Process multiple leagues
  python football_data_collector.py --date 2025-12-20 --leagues 39,135,140 --process
  python football_data_collector.py --date 2025-12-20 --leagues premier_league,serie_a,la_liga --process

  # Process a single fixture
  python football_data_collector.py --fixture 1379132

  # Process live fixtures
  python football_data_collector.py --live --process

  # Process team fixtures
  python football_data_collector.py --team-id 42 --next 5 --process

Popular League IDs:
  Premier League: 39    | La Liga: 140      | Serie A: 135
  Bundesliga: 78        | Ligue 1: 61       | Eredivisie: 88
  Champions League: 2   | Europa League: 3  | FA Cup: 45
        """
    )

    # Data retrieval arguments
    parser.add_argument("--fixture", type=int, help="Get data for a specific fixture ID")
    parser.add_argument("--date", help="Get fixtures for a date (YYYY-MM-DD), use 'today' for current date")
    parser.add_argument("--league", type=int, help="Filter by single league ID")
    parser.add_argument("--leagues", type=str, help="Comma-separated league IDs or names (e.g., '39,135,140' or 'premier_league,serie_a')")
    parser.add_argument("--season", type=int, help="Season year (e.g., 2024)")
    parser.add_argument("--team", help="Search for a team by name")
    parser.add_argument("--team-id", type=int, help="Team ID for fixtures")
    parser.add_argument("--next", type=int, help="Get next N fixtures for a team")
    parser.add_argument("--last", type=int, help="Get last N fixtures for a team")
    parser.add_argument("--live", action="store_true", help="Get live fixtures")

    # Action arguments
    parser.add_argument("--process", action="store_true", help="Process fixtures and generate reports")
    parser.add_argument("--status", action="store_true", help="Check API status")
    parser.add_argument("--list-leagues", action="store_true", help="List available leagues")
    parser.add_argument("--standings", action="store_true", help="Get league standings")

    # Configuration arguments
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--output", help="Output file path (for single fixture)")
    parser.add_argument("--no-scraper", action="store_true", help="Skip web scraping (weather, news)")

    args = parser.parse_args()

    # Handle 'today' date shorthand
    if args.date and args.date.lower() == "today":
        args.date = datetime.now().strftime("%Y-%m-%d")

    # Initialize collector
    collector = FootballDataCollector(config_path=args.config)
    include_scraper = not args.no_scraper

    try:
        # Check API status
        if args.status:
            status = await collector.check_api_status()
            print(json.dumps(status, indent=2))
            return

        # List leagues
        if args.list_leagues:
            print("\nAvailable Leagues:\n")
            leagues = await collector.get_available_leagues(season=args.season)
            for league in leagues[:50]:
                l = league.get("league", {})
                c = league.get("country", {})
                print(f"  [{l.get('id'):>4}] {l.get('name')} ({c.get('name')})")
            print(f"\n  Showing first 50 leagues. Use --season to filter.\n")
            return

        # Get standings
        if args.standings and args.league and args.season:
            standings = await collector.get_league_standings(args.league, args.season)
            print(json.dumps(standings, indent=2))
            return

        # Process live fixtures
        if args.live:
            if args.process:
                results = await collector.process_live_fixtures(
                    args.league, include_scraper_data=include_scraper
                )
                print(f"\n✅ Processed {len(results)} live fixtures")
            else:
                fixtures = await collector.get_live_fixtures(args.league)
                print(f"\nLive Fixtures ({len(fixtures)}):\n")
                for f in fixtures:
                    teams = f.get("teams", {})
                    goals = f.get("goals", {})
                    fixture_info = f.get("fixture", {})
                    status = fixture_info.get("status", {}).get("short", "")
                    print(f"  [{fixture_info.get('id')}] {teams['home']['name']} {goals['home']}-{goals['away']} {teams['away']['name']} ({status})")
            return

        # Process fixtures by date
        if args.date:
            # Parse multiple leagues if provided
            league_ids = parse_league_ids(args.leagues) if args.leagues else None

            if args.process:
                results = await collector.process_date(
                    args.date,
                    league_id=args.league,
                    league_ids=league_ids,
                    include_scraper_data=include_scraper
                )
                print(f"\n✅ Processed {len(results)} fixtures for {args.date}")
            else:
                # Just list fixtures
                if league_ids:
                    fixtures = await collector.get_fixtures_for_leagues(args.date, league_ids)
                else:
                    fixtures = await collector.get_fixtures_by_date(args.date, args.league, args.season)

                print(f"\nFixtures for {args.date} ({len(fixtures)}):\n")
                for f in fixtures:
                    teams = f.get("teams", {})
                    fixture_info = f.get("fixture", {})
                    venue = fixture_info.get("venue", {})
                    time_str = fixture_info.get("date", "")[11:16]  # HH:MM
                    print(f"  [{fixture_info.get('id')}] {time_str} {teams['home']['name']} vs {teams['away']['name']} @ {venue.get('name', 'TBD')}")

                print(f"\n  Use --process to generate reports for all fixtures.\n")
            return

        # Search team
        if args.team:
            team = await collector.search_team(args.team)
            if team:
                team_info = team.get("team", {})
                venue_info = team.get("venue", {})
                print(f"\nTeam Found:")
                print(f"  ID: {team_info.get('id')}")
                print(f"  Name: {team_info.get('name')}")
                print(f"  Country: {team_info.get('country')}")
                print(f"  Stadium: {venue_info.get('name')} ({venue_info.get('city')})")
                print(f"\n  Use --team-id {team_info.get('id')} to get fixtures\n")
            else:
                print(f"Team '{args.team}' not found")
            return

        # Process team fixtures
        if args.team_id:
            if args.process:
                results = await collector.process_team_fixtures(
                    args.team_id,
                    next_count=args.next,
                    last_count=args.last,
                    include_scraper_data=include_scraper
                )
                print(f"\n✅ Processed {len(results)} fixtures for team {args.team_id}")
            else:
                if args.next:
                    fixtures = await collector.get_team_fixtures(args.team_id, next_count=args.next)
                elif args.last:
                    fixtures = await collector.get_team_fixtures(args.team_id, last_count=args.last)
                else:
                    fixtures = await collector.get_team_fixtures(args.team_id)

                print(f"\nFixtures for team {args.team_id} ({len(fixtures)}):\n")
                for f in fixtures:
                    teams = f.get("teams", {})
                    fixture_info = f.get("fixture", {})
                    date = fixture_info.get("date", "")[:10]
                    print(f"  [{fixture_info.get('id')}] {date}: {teams['home']['name']} vs {teams['away']['name']}")

                print(f"\n  Use --process to generate reports.\n")
            return

        # Process single fixture
        if args.fixture:
            print(f"Processing fixture {args.fixture}...")
            match_data = await collector.get_match_context(args.fixture, include_scraper_data=include_scraper)
            output_path = await collector.save_match_report(match_data, args.output)
            print(f"✅ Report saved to: {output_path}")
            return

        # Show usage if no action specified
        parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())

