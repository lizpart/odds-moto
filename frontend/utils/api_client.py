"""
API Client - Handles communication with the backend Football API
"""
import requests
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from frontend.utils.constants import (
    FIXTURES_ENDPOINT,
    ANALYZE_ENDPOINT,
    STATS_ENDPOINT,
    API_REQUEST_TIMEOUT
)

logger = logging.getLogger(__name__)


class FootballAPIClient:
    """Client for interacting with Football Analysis API"""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = API_REQUEST_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.fixtures_endpoint = f"{base_url}/msg/fixtures"
        self.analyze_endpoint = f"{base_url}/msg/analyze"
        self.stats_endpoint = f"{base_url}/msg/stats"

    def get_today_fixtures(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get today's fixtures"""
        try:
            payload = {
                "date": "today",
                "live": False
            }
            
            if league_id:
                payload["league_id"] = league_id

            response = requests.post(
                self.fixtures_endpoint,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched fixtures. Count: {data.get('count', 0)}")
            return data

        except requests.exceptions.Timeout:
            logger.error("Fixtures request timed out")
            return {"success": False, "error": "Request timed out. Please try again."}
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to API")
            return {"success": False, "error": "Unable to reach prediction service"}
        except Exception as e:
            logger.error(f"Error fetching fixtures: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_prediction(self, fixture_id: int, analysis_type: str = "enhanced") -> Dict[str, Any]:
        """Get prediction for a specific fixture"""
        try:
            payload = {
                "fixture_id": fixture_id,
                "analysis_type": analysis_type
            }

            response = requests.post(
                self.analyze_endpoint,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched prediction for fixture {fixture_id}")
            return data

        except requests.exceptions.Timeout:
            logger.error("Prediction request timed out")
            return {"success": False, "error": "Request timed out. Please try again."}
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to API")
            return {"success": False, "error": "Unable to reach prediction service"}
        except Exception as e:
            logger.error(f"Error fetching prediction: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_team_stats(self, fixture_id: int) -> Dict[str, Any]:
        """Get team statistics for a fixture"""
        try:
            payload = {
                "fixture_id": fixture_id
            }

            response = requests.post(
                self.stats_endpoint,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched stats for fixture {fixture_id}")
            return data

        except requests.exceptions.Timeout:
            logger.error("Stats request timed out")
            return {"success": False, "error": "Request timed out. Please try again."}
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to API")
            return {"success": False, "error": "Unable to reach prediction service"}
        except Exception as e:
            logger.error(f"Error fetching stats: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_all_today_predictions(self) -> Dict[str, Any]:
        """Get all today's predictions with analysis"""
        try:
            fixtures = self.get_today_fixtures()
            
            if not fixtures.get('success'):
                return fixtures

            predictions = []
            for fixture in fixtures.get('fixtures', [])[:10]:  # Limit to 10
                pred = self.get_prediction(fixture['id'])
                if pred.get('success'):
                    predictions.append(pred)

            return {
                "success": True,
                "count": len(predictions),
                "predictions": predictions
            }

        except Exception as e:
            logger.error(f"Error getting all predictions: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_league_predictions(self, league_id: int) -> Dict[str, Any]:
        """Get predictions for a specific league"""
        try:
            fixtures = self.get_today_fixtures(league_id=league_id)
            
            if not fixtures.get('success'):
                return fixtures

            predictions = []
            for fixture in fixtures.get('fixtures', []):
                pred = self.get_prediction(fixture['id'])
                if pred.get('success'):
                    predictions.append(pred)

            return {
                "success": True,
                "league_id": league_id,
                "count": len(predictions),
                "predictions": predictions
            }

        except Exception as e:
            logger.error(f"Error getting league predictions: {str(e)}")
            return {"success": False, "error": str(e)}
