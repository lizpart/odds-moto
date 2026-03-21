import asyncio
import os
import json
import logging
import datetime
import re
import argparse
import random
import time
import hashlib
import requests
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import aiohttp

from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Serper.dev API for Google Search (more reliable than DuckDuckGo or direct Google)
import warnings
warnings.filterwarnings("ignore", message="This package.*has been renamed")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('football_scraper.log')
    ]
)
logger = logging.getLogger("football_scraper")


class GoogleSearchClient:
    """Search client using Serper.dev API (Google Search API - fast and reliable)"""

    def __init__(self, sleep_interval: int = 1, max_retries: int = 3, api_key: str = None):
        """
        Initialize the Serper Search client

        Args:
            sleep_interval: Time to sleep between searches to avoid rate limiting
            max_retries: Maximum number of retry attempts if search fails
            api_key: Serper.dev API key (optional, will load from config if not provided)
        """
        self.sleep_interval = sleep_interval
        self.max_retries = max_retries
        self._last_search_time = 0
        self.base_url = "https://google.serper.dev"

        # Load API key from config if not provided
        if api_key:
            self.api_key = api_key
        else:
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    self.api_key = config.get('serper', {}).get('api_key', '')
            except Exception:
                self.api_key = ''

        if not self.api_key:
            logger.warning("Serper API key not found. Search functionality will be limited.")

    async def _make_serper_request(self, endpoint: str, payload: Dict) -> Dict:
        """
        Make a request to the Serper.dev API.

        Args:
            endpoint: API endpoint (e.g., '/search', '/news')
            payload: Request payload

        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Serper API error {response.status}: {error_text}")
                        return {}
        except Exception as e:
            logger.error(f"Error making Serper request: {e}")
            return {}

    async def search(self, query: str, num_results: int = 5, lang: str = 'en') -> List[Dict]:
        """
        Perform a Google search via Serper.dev API and return the results.

        Args:
            query: Search query
            num_results: Number of results to return
            lang: Language code (e.g., 'en')

        Returns:
            List of search result dictionaries with title and link
        """
        if not self.api_key:
            logger.warning("Serper API key not configured. Skipping search.")
            return []

        logger.info(f"Searching Serper (Google) for: {query}")

        # Enforce minimum time between searches
        current_time = time.time()
        time_since_last = current_time - self._last_search_time
        if time_since_last < self.sleep_interval:
            wait_time = self.sleep_interval - time_since_last
            await asyncio.sleep(wait_time)

        results = []

        # Map language to Google location
        gl_map = {
            'en': 'uk',
            'es': 'es',
            'it': 'it',
            'de': 'de',
            'fr': 'fr',
        }
        gl = gl_map.get(lang, 'uk')

        for attempt in range(self.max_retries):
            payload = {
                "q": query,
                "gl": gl,
                "hl": lang,
                "num": num_results
            }

            response = await self._make_serper_request("/search", payload)
            self._last_search_time = time.time()

            # Process organic results from Serper response
            organic_results = response.get('organic', [])
            for result in organic_results[:num_results]:
                results.append({
                    "title": result.get('title', ''),
                    "link": result.get('link', ''),
                    "description": result.get('snippet', '')
                })

            if results:
                logger.info(f"Found {len(results)} search results via Serper")
                break
            else:
                if attempt < self.max_retries - 1:
                    backoff_time = (2 ** attempt) * 2 + random.uniform(0.5, 1.5)
                    logger.warning(f"No results found, retrying in {backoff_time:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(backoff_time)

        if not results:
            logger.warning(f"No search results after {self.max_retries} attempts for: {query}")

        return results

    async def search_news(self, query: str, num_results: int = 5) -> List[Dict]:
        """
        Perform a Google News search via Serper.dev API and return the results.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of news result dictionaries with title, link, date, and source
        """
        if not self.api_key:
            logger.warning("Serper API key not configured. Skipping news search.")
            return []

        logger.info(f"Searching Serper News for: {query}")

        # Enforce minimum time between searches
        current_time = time.time()
        time_since_last = current_time - self._last_search_time
        if time_since_last < self.sleep_interval:
            wait_time = self.sleep_interval - time_since_last
            await asyncio.sleep(wait_time)

        results = []

        for attempt in range(self.max_retries):
            payload = {
                "q": query,
                "gl": "uk",
                "hl": "en",
                "num": num_results
            }

            response = await self._make_serper_request("/news", payload)
            self._last_search_time = time.time()

            # Process news results from Serper response
            news_results = response.get('news', [])
            for result in news_results[:num_results]:
                results.append({
                    "title": result.get('title', ''),
                    "link": result.get('link', ''),
                    "description": result.get('snippet', ''),
                    "date": result.get('date', ''),
                    "source": result.get('source', '')
                })

            if results:
                logger.info(f"Found {len(results)} news results via Serper")
                break
            else:
                if attempt < self.max_retries - 1:
                    backoff_time = (2 ** attempt) * 2 + random.uniform(0.5, 1.5)
                    logger.warning(f"No news results found, retrying in {backoff_time:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(backoff_time)

        if not results:
            logger.warning(f"No news results after {self.max_retries} attempts for: {query}")

        return results


class FootballFixtureManager:
    """Manages football fixture data from various leagues"""

    def __init__(self, data_dir: str = None):
        """
        Initialize the football fixture manager

        Args:
            data_dir: Directory containing league fixture JSON files
        """
        self.data_dir = data_dir or os.path.dirname(os.path.abspath(__file__))
        self.leagues = {}
        self.load_fixture_data()

    def load_fixture_data(self) -> None:
        """Load fixture data from JSON files in the data directory"""
        try:
            # Look for *-*.json files in the data directory that might contain fixture data
            fixture_files = list(Path(self.data_dir).glob("*-*.json"))

            for file_path in fixture_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Check if this file contains fixture data in an expected format
                    if "league" in data and ("fixtures" in data or "matchday" in data):
                        league_name = data["league"]
                        self.leagues[league_name] = data
                        logger.info(f"Loaded fixture data for {league_name} from {file_path}")
                except Exception as e:
                    logger.error(f"Error loading fixture data from {file_path}: {e}")

            logger.info(f"Loaded fixture data for {len(self.leagues)} leagues")

        except Exception as e:
            logger.error(f"Error scanning for fixture data: {e}")

    def get_fixtures_for_date(self, target_date: str = None, league_name: str = None) -> List[Dict]:
        """
        Get fixtures scheduled for a specific date

        Args:
            target_date: Date in YYYY-MM-DD format, or None for today's date
            league_name: Optional filter for a specific league

        Returns:
            List of fixture dictionaries
        """
        # Use today's date if not specified
        if not target_date:
            target_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Format date as string if it's a datetime object
        if isinstance(target_date, datetime.datetime):
            target_date = target_date.strftime("%Y-%m-%d")

        fixtures = []

        # Iterate through leagues
        for name, league_data in self.leagues.items():
            # Skip if we're filtering for a specific league and this isn't it
            if league_name and name != league_name:
                continue

            # Handle different fixture data structures
            if "fixtures" in league_data:
                # Premier League and Serie A style
                if isinstance(league_data["fixtures"], list):
                    for fixture in league_data["fixtures"]:
                        if "date" in fixture and fixture["date"] == target_date:
                            fixture_copy = fixture.copy()
                            fixture_copy["league"] = name
                            fixtures.append(fixture_copy)

                        # For Premier League structure
                        elif "matches" in fixture:
                            for match in fixture["matches"]:
                                if match["date"] == target_date:
                                    match_copy = match.copy()
                                    match_copy["league"] = name
                                    match_copy["matchday"] = fixture.get("matchday", "Unknown")
                                    fixtures.append(match_copy)

            # La Liga style
            elif "fixtures" in league_data:
                for matchday in league_data["fixtures"]:
                    if "matches" in matchday:
                        for match in matchday["matches"]:
                            if match["date"] == target_date:
                                match_copy = match.copy()
                                match_copy["league"] = name
                                match_copy["matchday"] = matchday.get("matchday", "Unknown")
                                fixtures.append(match_copy)

        logger.info(f"Found {len(fixtures)} fixtures for {target_date}")
        return fixtures

    def get_leagues(self) -> List[str]:
        """Get list of available leagues"""
        return list(self.leagues.keys())


class FootballDataScraper:
    """Production-ready football match contextual data scraper"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the scraper

        Args:
            config_path: Path to configuration file (optional)
        """
        # Load configuration
        self.config = self._load_config(config_path)

        # Initialize search client
        self.search_client = GoogleSearchClient(
            sleep_interval=self.config.get("search", {}).get("sleep_interval", 5)
        )

        # Initialize fixture manager
        self.fixture_manager = FootballFixtureManager()

        # Initialize browser config
        self.browser_config = BrowserConfig(
            headless=self.config["browser"].get("headless", True),
            viewport_width=self.config["browser"].get("viewport_width", 1280),
            viewport_height=self.config["browser"].get("viewport_height", 720),
            user_agent=self.config["browser"].get("user_agent")
            # timeout and js_timeout parameters commented out as they may cause issues
            # timeout=self.config["browser"].get("timeout", 30000),
            # js_timeout=self.config["browser"].get("js_timeout", 30000)
        )

        # Initialize the crawler
        self.crawler = None

        # Set up cache directory
        self.cache_dir = Path(self.config.get("cache_dir", "cache"))
        self.cache_dir.mkdir(exist_ok=True)

    def _load_config(self, config_path: Optional[str]) -> Dict:
        """
        Load configuration from file or use defaults

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        default_config = {
            "browser": {
                "headless": True,
                "viewport_width": 1280,
                "viewport_height": 720,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                "timeout": 30000,
                "js_timeout": 30000
            },
            "search": {
                "sleep_interval": 5,  # Sleep between searches to avoid rate limiting
                "num_results": 3,
                "queries": {
                    "player_health": "{team_name} injury news Premier League football",
                    "weather_forecast": "{venue_city} UK weather forecast site:bbc.co.uk OR site:metoffice.gov.uk OR site:weather.com",
                    "pitch_conditions": "{venue_name} pitch condition grass surface Premier League",
                    "team_news": "{team_name} latest news transfer injury Premier League",
                    "head_to_head": "{home_team} vs {away_team} head to head Premier League history"
                }
            },
            "markdown": {
                "pruning_threshold": 0.45,
                "threshold_type": "dynamic",
                "min_word_threshold": 5,
                "body_width": 80
            },
            "cache": {
                "enabled": True,
                "expiry_seconds": 3600
            },
            "cache_dir": "cache",
            "output_dir": "output",
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 2
            },
            "sleep": {
                "between_requests": 1,
                "jitter": 0.5
            }
        }

        if not config_path:
            logger.info("Using default configuration")
            return default_config

        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)

            # Merge user config with defaults (simple, non-recursive merge)
            for key, value in user_config.items():
                if isinstance(value, dict) and key in default_config and isinstance(default_config[key], dict):
                    # Merge nested dictionaries
                    default_config[key].update(value)
                else:
                    # Replace entire key
                    default_config[key] = value

            logger.info(f"Loaded configuration from {config_path}")
            return default_config

        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            logger.info("Using default configuration")
            return default_config

    async def get_crawler(self) -> AsyncWebCrawler:
        """
        Get or create an AsyncWebCrawler instance

        Returns:
            AsyncWebCrawler instance
        """
        if self.crawler is None:
            self.crawler = AsyncWebCrawler(config=self.browser_config)
        return self.crawler

    async def scrape_url(self, url: str) -> Dict:
        """
        Scrape a URL and return the content as markdown

        Args:
            url: URL to scrape

        Returns:
            Dictionary with scraped content
        """
        # Create a pruning filter for better markdown output
        pruning_filter = PruningContentFilter(
            threshold=self.config["markdown"]["pruning_threshold"],
            threshold_type=self.config["markdown"]["threshold_type"],
            min_word_threshold=self.config["markdown"]["min_word_threshold"]
        )

        # Create markdown generator with the filter
        md_generator = DefaultMarkdownGenerator(
            content_filter=pruning_filter,
            options={"body_width": self.config["markdown"]["body_width"]}
        )

        # Create run configuration
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED if self.config["cache"]["enabled"] else CacheMode.BYPASS,
            markdown_generator=md_generator
        )

        # Get the crawler
        crawler = await self.get_crawler()

        # Retry logic
        max_attempts = self.config["retry"]["max_attempts"]
        delay_seconds = self.config["retry"]["delay_seconds"]

        for attempt in range(max_attempts):
            try:
                result = await crawler.arun(url=url, config=run_config)

                if result.success:
                    return {
                        "url": url,
                        "success": True,
                        "raw_markdown": result.markdown.raw_markdown if hasattr(result.markdown,
                                                                                'raw_markdown') else result.markdown,
                        "fit_markdown": result.markdown.fit_markdown if hasattr(result.markdown,
                                                                                'fit_markdown') else "",
                        "links": result.links
                    }
                else:
                    logger.error(f"Failed to scrape {url}: {result.error_message}")

                    if attempt < max_attempts - 1:
                        # Sleep before retry with exponential backoff
                        retry_delay = delay_seconds * (2 ** attempt)
                        logger.info(f"Retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_attempts})")
                        await asyncio.sleep(retry_delay)
                    else:
                        return {
                            "url": url,
                            "success": False,
                            "error": result.error_message
                        }
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")

                if attempt < max_attempts - 1:
                    # Sleep before retry with exponential backoff
                    retry_delay = delay_seconds * (2 ** attempt)
                    logger.info(f"Retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(retry_delay)
                else:
                    return {
                        "url": url,
                        "success": False,
                        "error": str(e)
                    }

        # This should not be reached, but just in case
        return {
            "url": url,
            "success": False,
            "error": "Max retry attempts reached"
        }

    async def collect_fixture_data(self, target_date: str = None, league_name: str = None) -> List[Dict]:
        """
        Collect data for all fixtures on a specific date

        Args:
            target_date: Date in YYYY-MM-DD format (defaults to today)
            league_name: Optional league name to filter fixtures

        Returns:
            List of fixture data dictionaries
        """
        # Use today's date if not specified
        if not target_date:
            target_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Get fixtures for the target date
        fixtures = self.fixture_manager.get_fixtures_for_date(target_date, league_name)

        if not fixtures:
            logger.warning(f"No fixtures found for {target_date}")
            return []

        # Process each fixture
        result = []
        for fixture in fixtures:
            try:
                # Extract match details
                home_team = fixture["home_team"]
                away_team = fixture["away_team"]
                venue_name = fixture.get("stadium", f"{home_team} Stadium")
                venue_city = self._extract_city_from_stadium(venue_name)
                match_time = fixture.get("time", "TBD")

                # Generate a match ID
                match_id = generate_match_id(home_team, away_team, target_date)

                # Collect match data
                match_data = await self.collect_match_data(
                    match_id=match_id,
                    home_team=home_team,
                    away_team=away_team,
                    venue_name=venue_name,
                    venue_city=venue_city,
                    match_date=target_date
                )

                # Add fixture-specific information
                match_data["league"] = fixture.get("league", "Unknown")
                match_data["matchday"] = fixture.get("matchday", "Unknown")
                match_data["match_time"] = match_time

                # Save the output
                output_path = await self.save_output(match_data)

                # Add to results
                result.append({
                    "match_id": match_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "league": fixture.get("league", "Unknown"),
                    "match_date": target_date,
                    "match_time": match_time,
                    "venue": venue_name,
                    "output_path": output_path
                })

                # Sleep between fixtures to avoid rate limiting
                sleep_time = self.config["sleep"]["between_requests"]
                jitter = random.uniform(-self.config["sleep"]["jitter"], self.config["sleep"]["jitter"])
                await asyncio.sleep(max(0, sleep_time + jitter))

            except Exception as e:
                logger.error(f"Error processing fixture {fixture}: {e}")

        return result

    def _extract_city_from_stadium(self, stadium_name: str) -> str:
        """
        Extract city name from stadium name or use a fallback

        Args:
            stadium_name: Name of the stadium

        Returns:
            City name
        """
        # Dictionary of known stadiums and their cities
        stadium_cities = {
            "Anfield": "Liverpool",
            "Old Trafford": "Manchester",
            "Emirates Stadium": "London",
            "Stamford Bridge": "London",
            "Etihad Stadium": "Manchester",
            "Tottenham Hotspur Stadium": "London",
            "London Stadium": "London",
            "Selhurst Park": "London",
            "Goodison Park": "Liverpool",
            "St James' Park": "Newcastle",
            "Villa Park": "Birmingham",
            "Estadio Santiago Bernabéu": "Madrid",
            "Camp Nou": "Barcelona",
            "Estadi Olímpic Lluís Companys": "Barcelona",
            "Estadio Cívitas Metropolitano": "Madrid",
            "Estadio Benito Villamarín": "Seville",
            "San Mamés Stadium": "Bilbao",
            "Estadio de Mestalla": "Valencia",
            "Estadio Ramón Sánchez-Pizjuán": "Seville",
            "Stadio Giuseppe Meazza": "Milan",
            "Allianz Stadium": "Turin",
            "Stadio Olimpico": "Rome",
            "Stadio Diego Armando Maradona": "Naples"
        }

        # Try to find the city for this stadium
        if stadium_name in stadium_cities:
            return stadium_cities[stadium_name]

        # If we can't find it, extract the first part of the stadium name as a guess
        # or return a generic name
        words = stadium_name.split()
        if len(words) > 1:
            return words[0]
        else:
            return "Unknown City"

    async def collect_match_data(self, match_id: str, home_team: str, away_team: str,
                                 venue_name: str = None, venue_city: str = None,
                                 match_date: str = None) -> Dict:
        """
        Collect all contextual data for a match

        Args:
            match_id: Match identifier
            home_team: Home team name
            away_team: Away team name
            venue_name: Stadium name (optional)
            venue_city: City where the match is played (optional)
            match_date: Date of the match (optional)

        Returns:
            Dictionary with all collected data in markdown format
        """
        logger.info(f"Collecting match data: {home_team} vs {away_team}")

        # Check if we have cached data
        cache_file = self.cache_dir / f"match_{match_id}.json"

        if cache_file.exists() and self.config["cache"]["enabled"]:
            cache_age = datetime.datetime.now().timestamp() - cache_file.stat().st_mtime

            if cache_age < self.config["cache"]["expiry_seconds"]:
                logger.info(f"Using cached data for match {match_id}")

                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)

                return cache_data

        # Prepare result structure
        result = {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "venue_name": venue_name,
            "venue_city": venue_city,
            "match_date": match_date,
            "collection_time": datetime.datetime.now().isoformat(),
            "sections": {}
        }

        # Set default venue info if not provided
        if not venue_name:
            venue_name = f"{home_team} Stadium"

        if not venue_city:
            venue_city = home_team  # Use team name as a fallback

        if not match_date:
            # Use current date as fallback
            match_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Create tasks for parallel scraping
        tasks = [
            self._collect_player_health(home_team, "home"),
            self._collect_player_health(away_team, "away"),
            self._collect_weather_forecast(venue_city, match_date),
            self._collect_pitch_conditions(venue_name),
            self._collect_team_news(home_team, "home"),
            self._collect_team_news(away_team, "away"),
            self._collect_head_to_head(home_team, away_team)
        ]

        # Sleep between requests to avoid rate limiting
        sleep_time = self.config["sleep"]["between_requests"]
        sleep_jitter = self.config["sleep"]["jitter"]

        # Execute tasks with random sleep between them
        all_results = []
        for task in tasks:
            # Add random jitter to sleep time
            jitter = random.uniform(-sleep_jitter, sleep_jitter)
            actual_sleep = max(0, sleep_time + jitter)

            if actual_sleep > 0:
                await asyncio.sleep(actual_sleep)

            task_result = await task
            all_results.append(task_result)

        # Process results
        result["sections"]["player_health_home"] = all_results[0]
        result["sections"]["player_health_away"] = all_results[1]
        result["sections"]["weather_forecast"] = all_results[2]
        result["sections"]["pitch_conditions"] = all_results[3]
        result["sections"]["team_news_home"] = all_results[4]
        result["sections"]["team_news_away"] = all_results[5]
        result["sections"]["head_to_head"] = all_results[6]

        # Generate consolidated markdown
        result["markdown"] = self._generate_markdown(result)

        # Cache the results
        if self.config["cache"]["enabled"]:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)

        return result

    async def _collect_player_health(self, team_name: str, team_side: str) -> Dict:
        """
        Collect player health information for a team

        Args:
            team_name: Name of the team
            team_side: "home" or "away"

        Returns:
            Dictionary with player health information
        """
        logger.info(f"Collecting player health data for {team_name}")

        # Prepare search query
        query_template = self.config["search"]["queries"]["player_health"]
        query = query_template.replace("{team_name}", team_name)

        # Search for relevant pages
        search_results = await self.search_client.search(
            query,
            num_results=self.config["search"]["num_results"]
        )

        if not search_results:
            logger.warning(f"No search results found for {team_name} player health")
            return {
                "title": f"{team_name} Player Health",
                "team": team_name,
                "team_side": team_side,
                "sources": [],
                "content": "No player health information found."
            }

        # Scrape each URL
        scraped_results = []

        for result in search_results:
            url = result["link"]

            # Skip if URL is empty or invalid
            if not url or not url.startswith(("http://", "https://")):
                continue

            scraped_result = await self.scrape_url(url)

            if scraped_result["success"]:
                scraped_results.append({
                    "url": url,
                    "title": result["title"],
                    "snippet": result.get("description", ""),
                    "content": scraped_result.get("fit_markdown", "") or scraped_result.get("raw_markdown", "")
                })

        # Generate combined content
        sources = [{"url": r["url"], "title": r["title"]} for r in scraped_results]

        content_parts = []
        for result in scraped_results:
            content_parts.append(f"## {result['title']}\n\n{result['content']}\n\n")

        combined_content = "\n".join(content_parts) if content_parts else "No player health information found."

        return {
            "title": f"{team_name} Player Health",
            "team": team_name,
            "team_side": team_side,
            "sources": sources,
            "content": combined_content
        }

    async def _get_city_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """
        Get coordinates for a city using Open-Meteo geocoding API.

        Args:
            city_name: Name of the city

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=en&format=json"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    return (results[0]["latitude"], results[0]["longitude"])
        except Exception as e:
            logger.debug(f"Geocoding error for {city_name}: {e}")

        return None

    async def _collect_weather_forecast(self, venue_city: str, match_date: str) -> Dict:
        """
        Collect weather forecast information using Open-Meteo API (free, no API key required)

        Args:
            venue_city: City where the match is played
            match_date: Date of the match

        Returns:
            Dictionary with weather forecast information
        """
        logger.info(f"Collecting weather forecast for {venue_city} on {match_date}")

        # Comprehensive city coordinates for major football cities worldwide
        city_coords = {
            # England
            "london": (51.5074, -0.1278),
            "manchester": (53.4808, -2.2426),
            "liverpool": (53.4084, -2.9916),
            "birmingham": (52.4862, -1.8904),
            "leeds": (53.8008, -1.5491),
            "newcastle": (54.9783, -1.6178),
            "newcastle upon tyne": (54.9783, -1.6178),
            "sheffield": (53.3811, -1.4701),
            "nottingham": (52.9548, -1.1581),
            "leicester": (52.6369, -1.1398),
            "brighton": (50.8225, -0.1372),
            "brighton and hove": (50.8225, -0.1372),
            "southampton": (50.9097, -1.4044),
            "wolverhampton": (52.5870, -2.1288),
            "bournemouth": (50.7192, -1.8808),
            "brentford": (51.4882, -0.3089),
            "fulham": (51.4749, -0.2217),
            "ipswich": (52.0567, 1.1482),
            "luton": (51.8787, -0.4200),
            "burnley": (53.7897, -2.2481),
            "crystal palace": (51.3983, -0.0857),
            "selhurst": (51.3983, -0.0857),
            "west ham": (51.5387, 0.0166),
            "stratford": (51.5430, -0.0098),
            # Scotland
            "glasgow": (55.8642, -4.2518),
            "edinburgh": (55.9533, -3.1883),
            # Spain
            "madrid": (40.4168, -3.7038),
            "barcelona": (41.3851, 2.1734),
            "seville": (37.3891, -5.9845),
            "sevilla": (37.3891, -5.9845),
            "valencia": (39.4699, -0.3763),
            "bilbao": (43.2630, -2.9350),
            "san sebastian": (43.3183, -1.9812),
            "san sebastián": (43.3183, -1.9812),
            "malaga": (36.7213, -4.4214),
            "vigo": (42.2406, -8.7207),
            "pamplona": (42.8169, -1.6432),
            "las palmas": (28.1235, -15.4363),
            "santa cruz de tenerife": (28.4636, -16.2518),
            # Italy
            "milan": (45.4642, 9.1900),
            "milano": (45.4642, 9.1900),
            "rome": (41.9028, 12.4964),
            "roma": (41.9028, 12.4964),
            "turin": (45.0703, 7.6869),
            "torino": (45.0703, 7.6869),
            "naples": (40.8518, 14.2681),
            "napoli": (40.8518, 14.2681),
            "florence": (43.7696, 11.2558),
            "firenze": (43.7696, 11.2558),
            "genoa": (44.4056, 8.9463),
            "genova": (44.4056, 8.9463),
            "bologna": (44.4949, 11.3426),
            "verona": (45.4384, 10.9916),
            "bergamo": (45.6983, 9.6773),
            "udine": (46.0711, 13.2346),
            "cagliari": (39.2238, 9.1217),
            "lecce": (40.3516, 18.1718),
            "parma": (44.8015, 10.3279),
            "empoli": (43.7187, 10.9506),
            "monza": (45.5845, 9.2744),
            "como": (45.8100, 9.0852),
            # Germany
            "munich": (48.1351, 11.5820),
            "münchen": (48.1351, 11.5820),
            "dortmund": (51.5136, 7.4653),
            "berlin": (52.5200, 13.4050),
            "frankfurt": (50.1109, 8.6821),
            "leipzig": (51.3397, 12.3731),
            "cologne": (50.9375, 6.9603),
            "köln": (50.9375, 6.9603),
            "hamburg": (53.5511, 9.9937),
            "bremen": (53.0793, 8.8017),
            "stuttgart": (48.7758, 9.1829),
            "gelsenkirchen": (51.5177, 7.0857),
            "wolfsburg": (52.4227, 10.7865),
            "leverkusen": (51.0459, 7.0192),
            "freiburg": (47.9990, 7.8421),
            "mainz": (49.9929, 8.2473),
            "augsburg": (48.3705, 10.8978),
            "hoffenheim": (49.2388, 8.8881),
            "sinsheim": (49.2388, 8.8881),
            "bochum": (51.4818, 7.2162),
            "mönchengladbach": (51.1805, 6.4428),
            # France
            "paris": (48.8566, 2.3522),
            "marseille": (43.2965, 5.3698),
            "lyon": (45.7640, 4.8357),
            "lille": (50.6292, 3.0573),
            "nice": (43.7102, 7.2620),
            "monaco": (43.7384, 7.4246),
            "bordeaux": (44.8378, -0.5792),
            "toulouse": (43.6047, 1.4442),
            "nantes": (47.2184, -1.5536),
            "strasbourg": (48.5734, 7.7521),
            "montpellier": (43.6108, 3.8767),
            "rennes": (48.1173, -1.6778),
            "lens": (50.4295, 2.8256),
            "reims": (49.2583, 4.0317),
            "brest": (48.3904, -4.4861),
            "le havre": (49.4944, 0.1079),
            "saint-etienne": (45.4397, 4.3872),
            "angers": (47.4784, -0.5632),
            # Netherlands
            "amsterdam": (52.3676, 4.9041),
            "rotterdam": (51.9244, 4.4777),
            "eindhoven": (51.4416, 5.4697),
            "the hague": (52.0705, 4.3007),
            "utrecht": (52.0907, 5.1214),
            "tilburg": (51.5555, 5.0913),
            "groningen": (53.2194, 6.5665),
            "enschede": (52.2215, 6.8937),
            "arnhem": (51.9851, 5.8987),
            "alkmaar": (52.6324, 4.7534),
            # Portugal
            "lisbon": (38.7223, -9.1393),
            "lisboa": (38.7223, -9.1393),
            "porto": (41.1579, -8.6291),
            "braga": (41.5454, -8.4265),
            "guimaraes": (41.4425, -8.2918),
            "setubal": (38.5244, -8.8882),
            "funchal": (32.6669, -16.9241),
            # Belgium
            "brussels": (50.8503, 4.3517),
            "bruxelles": (50.8503, 4.3517),
            "antwerp": (51.2194, 4.4025),
            "antwerpen": (51.2194, 4.4025),
            "bruges": (51.2093, 3.2247),
            "brugge": (51.2093, 3.2247),
            "ghent": (51.0543, 3.7174),
            "gent": (51.0543, 3.7174),
            "liege": (50.6326, 5.5797),
            "charleroi": (50.4108, 4.4446),
            # Austria
            "vienna": (48.2082, 16.3738),
            "wien": (48.2082, 16.3738),
            "salzburg": (47.8095, 13.0550),
            "graz": (47.0707, 15.4395),
            # Switzerland
            "zurich": (47.3769, 8.5417),
            "zürich": (47.3769, 8.5417),
            "bern": (46.9480, 7.4474),
            "basel": (47.5596, 7.5886),
            "geneva": (46.2044, 6.1432),
            # Turkey
            "istanbul": (41.0082, 28.9784),
            "ankara": (39.9334, 32.8597),
            # Greece
            "athens": (37.9838, 23.7275),
            "thessaloniki": (40.6401, 22.9444),
            "piraeus": (37.9422, 23.6466),
            # Other European cities
            "moscow": (55.7558, 37.6173),
            "saint petersburg": (59.9311, 30.3609),
            "kiev": (50.4501, 30.5234),
            "kyiv": (50.4501, 30.5234),
            "warsaw": (52.2297, 21.0122),
            "prague": (50.0755, 14.4378),
            "budapest": (47.4979, 19.0402),
            "bucharest": (44.4268, 26.1025),
            "belgrade": (44.7866, 20.4489),
            "zagreb": (45.8150, 15.9819),
            "copenhagen": (55.6761, 12.5683),
            "stockholm": (59.3293, 18.0686),
            "oslo": (59.9139, 10.7522),
            "helsinki": (60.1699, 24.9384),
            # South America
            "buenos aires": (-34.6037, -58.3816),
            "sao paulo": (-23.5505, -46.6333),
            "são paulo": (-23.5505, -46.6333),
            "rio de janeiro": (-22.9068, -43.1729),
            "bogota": (4.7110, -74.0721),
            "lima": (-12.0464, -77.0428),
            "santiago": (-33.4489, -70.6693),
            "montevideo": (-34.9011, -56.1645),
        }

        # Get coordinates for the city
        city_lower = venue_city.lower().strip()
        coords = city_coords.get(city_lower)

        if not coords:
            # Try to find a partial match
            for city_name, city_coord in city_coords.items():
                if city_name in city_lower or city_lower in city_name:
                    coords = city_coord
                    break

        if not coords:
            # Try geocoding API as fallback
            coords = await self._get_city_coordinates(venue_city)

        if not coords:
            # Default to London if city not found
            coords = city_coords["london"]
            logger.warning(f"City '{venue_city}' not found in coordinates, using London as default")

        lat, lon = coords

        try:
            # Use Open-Meteo API (free, no API key required)
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max,weathercode&timezone=Europe%2FLondon&start_date={match_date}&end_date={match_date}"

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))

            if response.status_code == 200:
                data = response.json()
                daily = data.get("daily", {})

                if daily:
                    # Weather code descriptions
                    weather_codes = {
                        0: "Clear sky",
                        1: "Mainly clear",
                        2: "Partly cloudy",
                        3: "Overcast",
                        45: "Fog",
                        48: "Depositing rime fog",
                        51: "Light drizzle",
                        53: "Moderate drizzle",
                        55: "Dense drizzle",
                        61: "Slight rain",
                        63: "Moderate rain",
                        65: "Heavy rain",
                        71: "Slight snow",
                        73: "Moderate snow",
                        75: "Heavy snow",
                        80: "Slight rain showers",
                        81: "Moderate rain showers",
                        82: "Violent rain showers",
                        95: "Thunderstorm",
                        96: "Thunderstorm with slight hail",
                        99: "Thunderstorm with heavy hail",
                    }

                    temp_max = daily.get("temperature_2m_max", [None])[0]
                    temp_min = daily.get("temperature_2m_min", [None])[0]
                    precip = daily.get("precipitation_sum", [None])[0]
                    precip_prob = daily.get("precipitation_probability_max", [None])[0]
                    wind = daily.get("windspeed_10m_max", [None])[0]
                    weather_code = daily.get("weathercode", [None])[0]

                    weather_desc = weather_codes.get(weather_code, "Unknown")

                    content = f"""### Weather Forecast for {venue_city} on {match_date}

| Condition | Value |
|-----------|-------|
| **Weather** | {weather_desc} |
| **Temperature** | {temp_min}°C - {temp_max}°C |
| **Precipitation** | {precip} mm |
| **Rain Probability** | {precip_prob}% |
| **Max Wind Speed** | {wind} km/h |

*Data from Open-Meteo API*
"""
                    return {
                        "title": f"Weather Forecast for {venue_city}",
                        "venue_city": venue_city,
                        "match_date": match_date,
                        "sources": [{"url": "https://open-meteo.com/", "title": "Open-Meteo Weather API"}],
                        "content": content
                    }

        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")

        return {
            "title": f"Weather Forecast for {venue_city}",
            "venue_city": venue_city,
            "match_date": match_date,
            "sources": [],
            "content": "No weather forecast information found."
        }

    async def _collect_pitch_conditions(self, venue_name: str) -> Dict:
        """
        Collect pitch condition information based on known stadium data

        Args:
            venue_name: Name of the stadium

        Returns:
            Dictionary with pitch condition information
        """
        logger.info(f"Collecting pitch condition data for {venue_name}")

        # Known stadium pitch information for Premier League and major European stadiums
        stadium_info = {
            # Premier League
            "emirates stadium": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "60,704"},
            "etihad stadium": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "53,400"},
            "anfield": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "101m x 68m", "capacity": "61,276"},
            "old trafford": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "74,310"},
            "stamford bridge": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "103m x 67m", "capacity": "40,341"},
            "tottenham hotspur stadium": {"surface": "Natural grass (retractable)", "dimensions": "105m x 68m", "capacity": "62,850"},
            "goodison park": {"surface": "Natural grass", "dimensions": "100.48m x 68m", "capacity": "39,414"},
            "hill dickinson stadium": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "52,888"},
            "st james' park": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "52,305"},
            "villa park": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "42,682"},
            "london stadium": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "62,500"},
            "king power stadium": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "32,312"},
            "molineux stadium": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "32,050"},
            "elland road": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "37,890"},
            "city ground": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "30,445"},
            "vitality stadium": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "11,307"},
            "gtech community stadium": {"surface": "Natural grass (hybrid)", "dimensions": "105m x 68m", "capacity": "17,250"},
            "craven cottage": {"surface": "Natural grass", "dimensions": "100m x 65m", "capacity": "29,600"},
            "amex stadium": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "31,800"},
            "st mary's stadium": {"surface": "Natural grass (Desso GrassMaster hybrid)", "dimensions": "105m x 68m", "capacity": "32,384"},
            "selhurst park": {"surface": "Natural grass", "dimensions": "101m x 68m", "capacity": "25,486"},
            "portman road": {"surface": "Natural grass", "dimensions": "102m x 66m", "capacity": "30,311"},
            # Serie A
            "san siro": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "75,923"},
            "allianz stadium": {"surface": "Natural grass (hybrid)", "dimensions": "105m x 68m", "capacity": "41,507"},
            "stadio olimpico": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "70,634"},
            "diego armando maradona": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "54,726"},
            # La Liga
            "santiago bernabeu": {"surface": "Natural grass (retractable)", "dimensions": "105m x 68m", "capacity": "81,044"},
            "camp nou": {"surface": "Natural grass", "dimensions": "105m x 68m", "capacity": "99,354"},
            "wanda metropolitano": {"surface": "Natural grass (hybrid)", "dimensions": "105m x 68m", "capacity": "68,456"},
        }

        # Try to find stadium info
        venue_lower = venue_name.lower()
        info = stadium_info.get(venue_lower)

        if not info:
            # Try partial match
            for stadium_name, stadium_data in stadium_info.items():
                if stadium_name in venue_lower or venue_lower in stadium_name:
                    info = stadium_data
                    break

        if info:
            content = f"""### Pitch Information for {venue_name}

| Property | Value |
|----------|-------|
| **Surface** | {info['surface']} |
| **Dimensions** | {info['dimensions']} |
| **Capacity** | {info['capacity']} |

*Note: All Premier League pitches are maintained to high standards. Actual match-day conditions may vary based on weather and recent usage.*
"""
        else:
            content = f"""### Pitch Information for {venue_name}

Standard professional football pitch with natural grass surface.

*Note: Specific pitch information not available for this venue.*
"""

        return {
            "title": f"Pitch Conditions at {venue_name}",
            "venue_name": venue_name,
            "sources": [],
            "content": content
        }

    async def _collect_team_news(self, team_name: str, team_side: str) -> Dict:
        """
        Collect team news information

        Args:
            team_name: Name of the team
            team_side: "home" or "away"

        Returns:
            Dictionary with team news information
        """
        logger.info(f"Collecting team news for {team_name}")

        # Prepare search query - use news search for better results
        query = f"{team_name} FC latest news injury update"

        # Use news search for team news (more relevant results)
        search_results = await self.search_client.search_news(
            query,
            num_results=self.config["search"]["num_results"]
        )

        if not search_results:
            logger.warning(f"No search results found for {team_name} team news")
            return {
                "title": f"{team_name} Team News",
                "team": team_name,
                "team_side": team_side,
                "sources": [],
                "content": "No team news information found."
            }

        # Scrape each URL
        scraped_results = []

        for result in search_results:
            url = result["link"]

            # Skip if URL is empty or invalid
            if not url or not url.startswith(("http://", "https://")):
                continue

            scraped_result = await self.scrape_url(url)

            if scraped_result["success"]:
                scraped_results.append({
                    "url": url,
                    "title": result["title"],
                    "snippet": result.get("description", ""),
                    "content": scraped_result.get("fit_markdown", "") or scraped_result.get("raw_markdown", "")
                })

        # Generate combined content
        sources = [{"url": r["url"], "title": r["title"]} for r in scraped_results]

        content_parts = []
        for result in scraped_results:
            content_parts.append(f"## {result['title']}\n\n{result['content']}\n\n")

        combined_content = "\n".join(content_parts) if content_parts else "No team news information found."

        return {
            "title": f"{team_name} Team News",
            "team": team_name,
            "team_side": team_side,
            "sources": sources,
            "content": combined_content
        }

    async def _collect_head_to_head(self, home_team: str, away_team: str) -> Dict:
        """
        Collect head-to-head information between teams

        Args:
            home_team: Name of the home team
            away_team: Name of the away team

        Returns:
            Dictionary with head-to-head information
        """
        logger.info(f"Collecting head-to-head data for {home_team} vs {away_team}")

        # Prepare search query
        query_template = self.config["search"]["queries"]["head_to_head"]
        query = query_template.replace("{home_team}", home_team).replace("{away_team}", away_team)

        # Search for relevant pages
        search_results = await self.search_client.search(
            query,
            num_results=self.config["search"]["num_results"]
        )

        if not search_results:
            logger.warning(f"No search results found for head-to-head: {home_team} vs {away_team}")
            return {
                "title": f"{home_team} vs {away_team} Head-to-Head",
                "home_team": home_team,
                "away_team": away_team,
                "sources": [],
                "content": "No head-to-head information found."
            }

        # Scrape each URL
        scraped_results = []

        for result in search_results:
            url = result["link"]

            # Skip if URL is empty or invalid
            if not url or not url.startswith(("http://", "https://")):
                continue

            scraped_result = await self.scrape_url(url)

            if scraped_result["success"]:
                scraped_results.append({
                    "url": url,
                    "title": result["title"],
                    "snippet": result.get("description", ""),
                    "content": scraped_result.get("fit_markdown", "") or scraped_result.get("raw_markdown", "")
                })

        # Generate combined content
        sources = [{"url": r["url"], "title": r["title"]} for r in scraped_results]

        content_parts = []
        for result in scraped_results:
            content_parts.append(f"## {result['title']}\n\n{result['content']}\n\n")

        combined_content = "\n".join(content_parts) if content_parts else "No head-to-head information found."

        return {
            "title": f"{home_team} vs {away_team} Head-to-Head",
            "home_team": home_team,
            "away_team": away_team,
            "sources": sources,
            "content": combined_content
        }

    def _generate_markdown(self, data: Dict) -> str:
        """
        Generate consolidated markdown output from all collected data

        Args:
            data: Collected match data

        Returns:
            Consolidated markdown string
        """
        # Start with match header
        match_time = data.get("match_date", "Unknown date")
        venue = data.get("venue_name", "Unknown venue")

        # Add league and matchday information if available
        league_info = f"*League: {data.get('league', 'Unknown')}*\n\n" if "league" in data else ""
        matchday_info = f"*Matchday: {data.get('matchday', 'Unknown')}*\n\n" if "matchday" in data else ""
        time_info = f"*Time: {data.get('match_time', 'TBD')}*\n\n" if "match_time" in data else ""

        # Add title and header
        markdown = f"# {data['home_team']} vs {data['away_team']} Match Analysis\n\n"
        markdown += f"*Match ID: {data['match_id']}*\n\n"
        markdown += league_info
        markdown += matchday_info
        markdown += f"*Venue: {venue}*\n\n"
        markdown += f"*Date: {match_time}*\n\n"
        markdown += time_info
        markdown += f"*Analysis generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        markdown += "---\n\n"

        # Table of contents
        markdown += "## Table of Contents\n\n"
        markdown += "1. [Player Health Information](#player-health-information)\n"
        markdown += "   - [Home Team](#home-team-health)\n"
        markdown += "   - [Away Team](#away-team-health)\n"
        markdown += "2. [Weather Forecast](#weather-forecast)\n"
        markdown += "3. [Pitch Conditions](#pitch-conditions)\n"
        markdown += "4. [Team News](#team-news)\n"
        markdown += "   - [Home Team](#home-team-news)\n"
        markdown += "   - [Away Team](#away-team-news)\n"
        markdown += "5. [Head-to-Head Analysis](#head-to-head-analysis)\n"
        markdown += "6. [Sources](#sources)\n\n"
        markdown += "---\n\n"

        # Player health section
        markdown += "## Player Health Information\n\n"

        # Home team health
        markdown += "### Home Team Health\n\n"
        home_health = data["sections"]["player_health_home"]
        markdown += home_health["content"] + "\n\n"

        # Away team health
        markdown += "### Away Team Health\n\n"
        away_health = data["sections"]["player_health_away"]
        markdown += away_health["content"] + "\n\n"

        # Weather forecast section
        markdown += "## Weather Forecast\n\n"
        weather = data["sections"]["weather_forecast"]
        markdown += weather["content"] + "\n\n"

        # Pitch conditions section
        markdown += "## Pitch Conditions\n\n"
        pitch = data["sections"]["pitch_conditions"]
        markdown += pitch["content"] + "\n\n"

        # Team news section
        markdown += "## Team News\n\n"

        # Home team news
        markdown += "### Home Team News\n\n"
        home_news = data["sections"]["team_news_home"]
        markdown += home_news["content"] + "\n\n"

        # Away team news
        markdown += "### Away Team News\n\n"
        away_news = data["sections"]["team_news_away"]
        markdown += away_news["content"] + "\n\n"

        # Head-to-head section
        markdown += "## Head-to-Head Analysis\n\n"
        h2h = data["sections"]["head_to_head"]
        markdown += h2h["content"] + "\n\n"

        # Sources section
        markdown += "## Sources\n\n"

        # Collect all sources
        all_sources = []

        for section_name, section_data in data["sections"].items():
            if "sources" in section_data:
                for source in section_data["sources"]:
                    # Add section name to source
                    source_copy = source.copy()
                    source_copy["section"] = section_data.get("title", section_name)
                    all_sources.append(source_copy)

        # Add sources to markdown
        if all_sources:
            for i, source in enumerate(all_sources):
                markdown += f"{i + 1}. [{source['title']}]({source['url']}) - *{source['section']}*\n"
        else:
            markdown += "No sources available."

        return markdown

    async def save_output(self, data: Dict, output_path: Optional[str] = None) -> str:
        """
        Save match data to file

        Args:
            data: Match data
            output_path: Optional output path

        Returns:
            Path where the data was saved
        """
        match_id = data["match_id"]
        home_team = data["home_team"]
        away_team = data["away_team"]
        league = data.get("league", "unknown")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if not output_path:
            # Create default filename
            output_dir = Path(self.config["output_dir"])
            output_dir.mkdir(exist_ok=True)

            # Create filename
            filename = f"{match_id}_{league}_{home_team}_vs_{away_team}_{timestamp}.md"
            output_path = output_dir / filename

        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(data["markdown"])

        logger.info(f"Saved output to {output_path}")
        return str(output_path)

    async def close(self) -> None:
        """Close the crawler and clean up resources"""
        if self.crawler:
            await self.crawler.close()
            self.crawler = None

def generate_match_id(home_team: str, away_team: str, match_date: str = None) -> str:
    """
    Generate a unique match ID based on team names and date.

    Args:
        home_team: Name of the home team
        away_team: Name of the away team
        match_date: Date of the match (YYYY-MM-DD format), defaults to current date

    Returns:
        A unique match ID string
    """
    # Use current date if not provided
    if not match_date:
        match_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Clean team names (remove special characters, convert to lowercase)
    home_team_clean = re.sub(r'[^a-zA-Z0-9]', '', home_team.lower())
    away_team_clean = re.sub(r'[^a-zA-Z0-9]', '', away_team.lower())

    # Create a unique string by combining teams and date
    unique_string = f"{home_team_clean}_{away_team_clean}_{match_date}"

    # Create a hash
    hash_object = hashlib.md5(unique_string.encode())

    # Use the first 8 characters of the hash
    match_id = hash_object.hexdigest()[:8]

    return match_id

def parse_date(date_str: str) -> str:
    """
    Parse date string to YYYY-MM-DD format

    Args:
        date_str: Date string in various formats

    Returns:
        Date in YYYY-MM-DD format or None if invalid
    """
    if not date_str:
        return datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        # Try different date formats
        formats = [
            "%Y-%m-%d",  # 2023-01-31
            "%d/%m/%Y",  # 31/01/2023
            "%m/%d/%Y",  # 01/31/2023
            "%d-%m-%Y",  # 31-01-2023
            "%m-%d-%Y",  # 01-31-2023
            "%d.%m.%Y",  # 31.01.2023
            "%Y/%m/%d",  # 2023/01/31
            "%B %d, %Y",  # January 31, 2023
            "%d %B %Y",  # 31 January 2023
            "%d %b %Y",  # 31 Jan 2023
            "%b %d, %Y"  # Jan 31, 2023
        ]

        for fmt in formats:
            try:
                return datetime.datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        # If we get here, none of the formats matched
        raise ValueError(f"Could not parse date: {date_str}")

    except Exception as e:
        # Use current date as fallback
        logger.warning(f"Error parsing date '{date_str}': {e}. Using today's date.")
        return datetime.datetime.now().strftime("%Y-%m-%d")

async def main() -> None:
    """Command-line entry point with additional fixture-based functionality"""
    parser = argparse.ArgumentParser(description="Football Match Contextual Data Scraper")
    parser.add_argument("--config", help="Path to configuration file")

    # Add fixture-related arguments
    parser.add_argument("--fixtures", action="store_true", help="Process fixtures for a date")
    parser.add_argument("--date", help="Date to fetch fixtures for (YYYY-MM-DD, defaults to today)")
    parser.add_argument("--league", help="Filter fixtures by league")

    # Add match-specific arguments
    parser.add_argument("--match-id", help="Match identifier (optional, will be generated if not provided)")
    parser.add_argument("--home-team", help="Home team name")
    parser.add_argument("--away-team", help="Away team name")
    parser.add_argument("--venue-name", help="Stadium name")
    parser.add_argument("--venue-city", help="City where the match is played")
    parser.add_argument("--match-date", help="Date of the match (YYYY-MM-DD)")
    parser.add_argument("--output", help="Output file path")

    args = parser.parse_args()

    try:
        # Initialize scraper
        scraper = FootballDataScraper(args.config)

        # Process fixtures or a specific match
        if args.fixtures:
            # Parse date
            target_date = parse_date(args.date)

            # Process fixtures for the target date
            fixtures_results = await scraper.collect_fixture_data(
                target_date=target_date,
                league_name=args.league
            )

            if not fixtures_results:
                print(f"No fixtures found for {target_date}" + (f" in {args.league}" if args.league else ""))
            else:
                print(f"Processed {len(fixtures_results)} fixtures for {target_date}")
                for result in fixtures_results:
                    print(
                        f"- {result['home_team']} vs {result['away_team']} ({result['league']}): {result['output_path']}")

        # Process a specific match (legacy mode)
        elif args.home_team and args.away_team:
            # Generate match_id if not provided
            match_id = args.match_id
            if not match_id:
                match_id = generate_match_id(args.home_team, args.away_team, args.match_date)
                print(f"Generated Match ID: {match_id}")

            # Collect match data
            match_data = await scraper.collect_match_data(
                match_id=match_id,
                home_team=args.home_team,
                away_team=args.away_team,
                venue_name=args.venue_name,
                venue_city=args.venue_city,
                match_date=args.match_date
            )

            # Save output
            output_path = await scraper.save_output(match_data, args.output)

            # Print success message
            print(f"Match data saved to {output_path}")

        else:
            # No actions specified
            print("""
Football Match Contextual Data Scraper - Usage Examples:

1. Process all fixtures for today:
   python scraper.py --fixtures

2. Process fixtures for a specific date:
   python scraper.py --fixtures --date 2025-04-20

3. Process fixtures for a specific league:
   python scraper.py --fixtures --league "English Premier League 2024-2025"

4. Process a specific match:
   python scraper.py --home-team "Liverpool FC" --away-team "Chelsea FC" --venue-name "Anfield"
            """)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"Error: {e}")
    finally:
        # Clean up resources
        if 'scraper' in locals():
            await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())