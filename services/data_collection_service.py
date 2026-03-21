"""
Service layer for football data collection
Wraps football_data_collector.py functionality
"""
import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from football_data_collector import FootballDataCollector
from app_config import settings, config
from database.football_store import upsert_match_context_payload

logger = logging.getLogger(__name__)


class DataCollectionService:
    """Service for collecting football match data"""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the data collection service"""
        self.config_path = config_path
        self.collector: Optional[FootballDataCollector] = None
        
    async def _get_collector(self) -> FootballDataCollector:
        """Get or create collector instance"""
        if self.collector is None:
            self.collector = FootballDataCollector(config_path=self.config_path)
        return self.collector
    
    async def get_fixture_data(
        self,
        fixture_id: int,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get data for a specific fixture and generate MD report

        Args:
            fixture_id: Fixture ID to fetch
            output_path: Optional custom output path

        Returns:
            Dictionary with fixture data and file path
        """
        collector = await self._get_collector()

        try:
            # Get match context data
            match_data = await collector.get_match_context(
                fixture_id=fixture_id,
                include_scraper_data=True
            )

            if "error" in match_data:
                return {
                    "success": False,
                    "error": match_data.get("error", "Unknown error")
                }

            # Save the report
            md_file = await collector.save_match_report(match_data, output_path)
            await upsert_match_context_payload(match_data, md_report_path=md_file)

            return {
                "success": True,
                "fixture_id": fixture_id,
                "md_file": md_file,
                "fixture_data": match_data
            }

        except Exception as e:
            logger.error(f"Error fetching fixture {fixture_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_fixtures_by_date(
        self,
        date: str,
        league_ids: Optional[List[int]] = None,
        process: bool = True
    ) -> Dict[str, Any]:
        """
        Get fixtures for a specific date

        Args:
            date: Date string (YYYY-MM-DD) or 'today'
            league_ids: Optional list of league IDs to filter
            process: Whether to generate MD reports

        Returns:
            Dictionary with fixtures and generated files
        """
        collector = await self._get_collector()

        # Handle 'today' shorthand
        if date.lower() == "today":
            date = datetime.now().strftime("%Y-%m-%d")

        try:
            md_files = []
            fixtures_data = []

            if process:
                # Process and generate reports using the correct method
                results = await collector.process_date(
                    date=date,
                    league_ids=league_ids,
                    include_scraper_data=True,
                    save_reports=True
                )

                if results:
                    fixtures_data = results
                    # Extract MD file paths from results
                    # The save_match_report returns the path, but we need to track them
                    # For now, we'll search for generated files
                    import glob
                    pattern = f"{collector.output_dir}/match_*_{date.replace('-', '')}*.md"
                    md_files = glob.glob(pattern)
            else:
                # Just list fixtures without processing
                if league_ids:
                    fixtures = await collector.get_fixtures_for_leagues(date, league_ids)
                else:
                    fixtures = await collector.get_fixtures_by_date(date)
                fixtures_data = fixtures

                # Persist lightweight fixture rows for cache/date invalidation and lookups.
                for fixture_payload in fixtures_data:
                    await upsert_match_context_payload(
                        {
                            "fixture_id": (fixture_payload.get("fixture", {}) or {}).get("id")
                            if isinstance(fixture_payload, dict)
                            else None,
                            "api_data": {"fixture": fixture_payload},
                            "scraped_data": {},
                        }
                    )

            return {
                "success": True,
                "date": date,
                "fixture_count": len(fixtures_data),
                "fixtures": fixtures_data,
                "md_files": md_files
            }

        except Exception as e:
            logger.error(f"Error fetching fixtures for {date}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_live_fixtures(self, process: bool = False) -> Dict[str, Any]:
        """
        Get currently live fixtures

        Args:
            process: Whether to generate MD reports

        Returns:
            Dictionary with live fixtures
        """
        collector = await self._get_collector()

        try:
            md_files = []
            fixtures_data = []

            if process:
                # Use the process_live_fixtures method
                results = await collector.process_live_fixtures(
                    include_scraper_data=True,
                    save_reports=True
                )
                fixtures_data = results

                # Find generated MD files
                import glob
                pattern = f"{collector.output_dir}/match_*.md"
                all_files = glob.glob(pattern)
                # Get the most recent files (assuming they were just created)
                if all_files:
                    all_files.sort(key=os.path.getctime, reverse=True)
                    md_files = all_files[:len(results)]
            else:
                # Just get live fixtures without processing
                fixtures = await collector.get_live_fixtures()
                fixtures_data = fixtures

            return {
                "success": True,
                "fixture_count": len(fixtures_data),
                "fixtures": fixtures_data,
                "md_files": md_files
            }

        except Exception as e:
            logger.error(f"Error fetching live fixtures: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def close(self):
        """Close the collector and cleanup resources"""
        if self.collector:
            await self.collector.close()
