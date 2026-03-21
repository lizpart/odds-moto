"""
Pydantic models for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date, datetime
from enum import Enum


class AnalysisType(str, Enum):
    """Type of analysis to perform"""
    BASIC = "basic"  # v1.py - basic analysis
    ENHANCED = "enhanced"  # prediction.py - enhanced with psychological analysis


class FixtureRequest(BaseModel):
    """Request model for fetching fixture data"""
    fixture_id: Optional[int] = Field(None, description="Specific fixture ID")
    date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format or 'today'")
    league_id: Optional[int] = Field(None, description="League ID to filter by")
    league_ids: Optional[List[int]] = Field(None, description="Multiple league IDs")
    team_id: Optional[int] = Field(None, description="Team ID for fixtures")
    next_n: Optional[int] = Field(None, description="Get next N fixtures for team")
    last_n: Optional[int] = Field(None, description="Get last N fixtures for team")
    live: bool = Field(False, description="Get live fixtures")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-12-24",
                "league_id": 39,
                "live": False
            }
        }


class PredictionRequest(BaseModel):
    """Request model for match prediction"""
    fixture_id: Optional[int] = Field(None, description="Fixture ID to analyze")
    md_file_path: Optional[str] = Field(None, description="Path to existing MD file")
    analysis_type: AnalysisType = Field(
        AnalysisType.ENHANCED, 
        description="Type of analysis: basic or enhanced"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "fixture_id": 1379137,
                "analysis_type": "enhanced"
            }
        }


class FixtureResponse(BaseModel):
    """Response model for fixture data"""
    success: bool
    message: str
    fixture_count: int = 0
    fixtures: List[dict] = []
    md_files: List[str] = []


class PredictionResponse(BaseModel):
    """Response model for prediction analysis"""
    success: bool
    message: str
    fixture_id: Optional[int] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    league: Optional[str] = None
    analysis: Optional[str] = None  # Full analysis text content
    analysis_file: Optional[str] = None  # File path (optional)
    analysis_type: str = "enhanced"


class FullAnalysisRequest(BaseModel):
    """Request for complete workflow: fetch data + analyze"""
    fixture_id: int = Field(..., description="Fixture ID to fetch and analyze")
    analysis_type: AnalysisType = Field(
        AnalysisType.ENHANCED,
        description="Type of analysis to perform"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "fixture_id": 1379137,
                "analysis_type": "enhanced"
            }
        }


class MatchData(BaseModel):
    """Structured match data from MD file"""
    fixture_id: Optional[int] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    league: Optional[str] = None
    date: Optional[str] = None
    venue: Optional[str] = None
    home_form: Optional[str] = None
    away_form: Optional[str] = None
    head_to_head: Optional[List[dict]] = None
    odds: Optional[dict] = None
    injuries: Optional[dict] = None
    standings: Optional[dict] = None


class FullAnalysisResponse(BaseModel):
    """Response for complete workflow - returns all data as JSON"""
    success: bool
    message: str
    fixture_id: int
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    league: Optional[str] = None
    match_data: Optional[MatchData] = None  # Structured match data
    analysis: Optional[str] = None  # Full analysis text
    analysis_summary: Optional[str] = None  # Short summary for bots
    analysis_file: Optional[str] = None  # File path (optional)
    analysis_type: str


class StatusResponse(BaseModel):
    """API status response"""
    status: str
    version: str = "1.0.0"
    api_football_status: Optional[dict] = None
    openai_configured: bool = False


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None


class BatchFixtureRequest(BaseModel):
    """Request for batch processing fixtures"""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    league_ids: Optional[List[int]] = Field(None, description="Filter by league IDs")
    analyze: bool = Field(False, description="Also run analysis on all fixtures")
    analysis_type: AnalysisType = Field(AnalysisType.ENHANCED, description="Analysis type if analyze=True")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-12-24",
                "league_ids": [39, 135, 140],
                "analyze": True,
                "analysis_type": "enhanced"
            }
        }


class BatchFixtureResponse(BaseModel):
    """Response for batch fixture processing"""
    success: bool
    message: str
    date: str
    total_fixtures: int
    processed_fixtures: int
    md_files: List[str] = []
    analysis_files: List[str] = []
    errors: List[str] = []


# ==================== Messaging Endpoint Models ====================

class MessagingFixtureItem(BaseModel):
    """Minimal fixture data for messaging apps"""
    id: Optional[int] = Field(None, description="Fixture ID")
    match: str = Field(..., description="Match description (e.g., 'Arsenal vs Chelsea')")
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    time: str = Field(..., description="Match time (HH:MM)")
    date: str = Field(..., description="Match date (YYYY-MM-DD)")
    league: str = Field(..., description="League name")
    status: str = Field(..., description="Match status (NS, LIVE, FT, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 12345,
                "match": "Arsenal vs Chelsea",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "time": "15:00",
                "date": "2025-12-24",
                "league": "Premier League",
                "status": "NS"
            }
        }


class MessagingFixtureResponse(BaseModel):
    """Response model for messaging fixtures endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    date: str = Field(..., description="Date of fixtures")
    count: int = Field(..., description="Number of fixtures returned")
    fixtures: List[MessagingFixtureItem] = Field(default_factory=list, description="List of fixtures")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "date": "2025-12-24",
                "count": 5,
                "fixtures": [
                    {
                        "id": 12345,
                        "match": "Arsenal vs Chelsea",
                        "home_team": "Arsenal",
                        "away_team": "Chelsea",
                        "time": "15:00",
                        "date": "2025-12-24",
                        "league": "Premier League",
                        "status": "NS"
                    }
                ]
            }
        }


class BettingOdds(BaseModel):
    """Betting odds for a specific bet"""
    bet: str = Field(..., description="Bet description")
    odds: float = Field(..., description="Betting odds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "bet": "Arsenal to Win",
                "odds": 2.10
            }
        }


class MatchPrediction(BaseModel):
    """Match prediction probabilities"""
    home: int = Field(..., description="Home win probability (%)")
    draw: int = Field(..., description="Draw probability (%)")
    away: int = Field(..., description="Away win probability (%)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "home": 45,
                "draw": 28,
                "away": 27
            }
        }


class MessagingAnalysisResponse(BaseModel):
    """Response model for messaging analysis endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    fixture_id: Optional[int] = Field(None, description="Fixture ID")
    match: str = Field(..., description="Match description")
    probabilities: MatchPrediction = Field(..., description="Win probabilities")
    top_bets: List[BettingOdds] = Field(default_factory=list, description="Top betting recommendations")
    summary: str = Field(..., description="Brief analysis summary")
    reasoning: Optional[str] = Field(None, description="Detailed reasoning (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "fixture_id": 12345,
                "match": "Arsenal vs Chelsea",
                "probabilities": {
                    "home": 45,
                    "draw": 28,
                    "away": 27
                },
                "top_bets": [
                    {"bet": "Arsenal to Win", "odds": 2.10},
                    {"bet": "Over 2.5 Goals", "odds": 1.75}
                ],
                "summary": "Arsenal has strong home form...",
                "reasoning": "Detailed analysis..."
            }
        }


class TeamStats(BaseModel):
    """Team statistics summary"""
    team: str = Field(..., description="Team name")
    position: Optional[int] = Field(None, description="League position")
    form: str = Field(default="", description="Recent form (e.g., 'WWDLW')")
    goals_scored: int = Field(default=0, description="Goals scored")
    goals_conceded: int = Field(default=0, description="Goals conceded")
    wins: int = Field(default=0, description="Number of wins")
    draws: int = Field(default=0, description="Number of draws")
    losses: int = Field(default=0, description="Number of losses")
    
    class Config:
        json_schema_extra = {
            "example": {
                "team": "Arsenal",
                "position": 3,
                "form": "WWDLW",
                "goals_scored": 45,
                "goals_conceded": 20,
                "wins": 12,
                "draws": 3,
                "losses": 2
            }
        }


class QuickStatsResponse(BaseModel):
    """Response model for messaging stats endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    home_team: TeamStats = Field(..., description="Home team statistics")
    away_team: TeamStats = Field(..., description="Away team statistics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "home_team": {
                    "team": "Arsenal",
                    "position": 3,
                    "form": "WWDLW",
                    "goals_scored": 45,
                    "goals_conceded": 20,
                    "wins": 12,
                    "draws": 3,
                    "losses": 2
                },
                "away_team": {
                    "team": "Chelsea",
                    "position": 5,
                    "form": "DLWWL",
                    "goals_scored": 38,
                    "goals_conceded": 25,
                    "wins": 10,
                    "draws": 4,
                    "losses": 3
                }
            }
        }


class MessagingErrorResponse(BaseModel):
    """Error response for messaging endpoints"""
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Fixture not found"
            }
        }


# ==================== Batch Prediction Models ====================

class BatchPredictRequest(BaseModel):
    """Request for batch prediction processing"""
    dates: List[str] = Field(default=["today"], description="List of dates (YYYY-MM-DD) or ['today']")
    league_ids: Optional[List[int]] = Field(None, description="Filter by specific league IDs")
    analysis_type: AnalysisType = Field(AnalysisType.ENHANCED, description="Type of analysis to generate")
    force_refresh: bool = Field(False, description="Force re-analysis even if cached")
    skip_cached: bool = Field(True, description="Skip fixtures that already have cache (unless force_refresh=true)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "dates": ["today"],
                "league_ids": [39, 140, 135],
                "analysis_type": "enhanced",
                "force_refresh": False,
                "skip_cached": True
            }
        }


class BatchPredictResponse(BaseModel):
    """Response for batch prediction processing"""
    success: bool = Field(..., description="Whether the batch processing was successful")
    total_fixtures: int = Field(..., description="Total fixtures found")
    processed: int = Field(..., description="Fixtures processed (generated or skipped)")
    generated: int = Field(..., description="New analyses generated")
    cached: int = Field(..., description="Fixtures that were already cached")
    errors: List[str] = Field(default_factory=list, description="List of error messages")
    by_date: Optional[Dict[str, Dict]] = Field(None, description="Breakdown by date")
    by_league: Optional[Dict[int, Dict]] = Field(None, description="Breakdown by league ID")
    processing_time_seconds: float = Field(..., description="Total processing time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_fixtures": 20,
                "processed": 20,
                "generated": 5,
                "cached": 15,
                "errors": [],
                "by_date": {
                    "2025-12-24": {"fixtures": 20, "generated": 5, "cached": 15}
                },
                "by_league": {
                    39: {"fixtures": 10, "generated": 3, "cached": 7}
                },
                "processing_time_seconds": 125.5
            }
        }


# ==================== Cache Management Models ====================

class CacheRefreshRequest(BaseModel):
    """Request for cache refresh"""
    fixture_ids: Optional[List[int]] = Field(None, description="Refresh specific fixtures (single or multiple)")
    date: Optional[str] = Field(None, description="Refresh all fixtures for a date (YYYY-MM-DD or 'today')")
    league_ids: Optional[List[int]] = Field(None, description="Refresh fixtures for specific leagues")
    analysis_type: Optional[str] = Field(None, description="Filter by analysis type (if None, refresh all types)")
    force_regenerate: bool = Field(True, description="Force new analysis generation (default: true)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fixture_ids": [1379137],
                "analysis_type": "enhanced",
                "force_regenerate": True
            }
        }


class CacheRefreshResponse(BaseModel):
    """Response for cache refresh"""
    success: bool = Field(..., description="Whether the refresh was successful")
    refreshed_count: int = Field(..., description="Number of fixtures refreshed")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    by_fixture: Optional[Dict[int, str]] = Field(None, description="Status per fixture ('refreshed' or 'error: ...')")
    processing_time_seconds: float = Field(..., description="Total processing time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "refreshed_count": 5,
                "errors": [],
                "by_fixture": {
                    1379137: "refreshed",
                    1379145: "refreshed"
                },
                "processing_time_seconds": 45.2
            }
        }


class CacheInvalidateRequest(BaseModel):
    """Request for cache invalidation"""
    fixture_ids: Optional[List[int]] = Field(None, description="Invalidate specific fixtures")
    date: Optional[str] = Field(None, description="Invalidate all fixtures for a date")
    league_ids: Optional[List[int]] = Field(None, description="Invalidate fixtures for specific leagues")
    analysis_type: Optional[str] = Field(None, description="Filter by analysis type (if None, invalidate all types)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-12-24",
                "league_ids": [39],
                "analysis_type": "enhanced"
            }
        }


class CacheInvalidateResponse(BaseModel):
    """Response for cache invalidation"""
    success: bool = Field(..., description="Whether the invalidation was successful")
    invalidated_count: int = Field(..., description="Number of cache entries deleted")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "invalidated_count": 10,
                "errors": []
            }
        }

