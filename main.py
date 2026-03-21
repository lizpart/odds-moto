"""
FastAPI Application for Football Match Analysis and Prediction
Provides REST API endpoints for data collection and AI-powered predictions
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
import logging
import os
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime
import time

from pydantic import BaseModel, Field
from api_models import (
    FixtureRequest, FixtureResponse,
    PredictionRequest, PredictionResponse,
    FullAnalysisRequest, FullAnalysisResponse,
    BatchFixtureRequest, BatchFixtureResponse,
    StatusResponse, ErrorResponse,
    MessagingFixtureResponse, MessagingAnalysisResponse, QuickStatsResponse,
    MessagingErrorResponse,
    BatchPredictRequest, BatchPredictResponse,
    CacheRefreshRequest, CacheRefreshResponse,
    CacheInvalidateRequest, CacheInvalidateResponse
)
from services.response_transformer import (
    transform_fixture_data, transform_analysis, transform_team_stats
)
from services.data_collection_service import DataCollectionService
from services.prediction_service import PredictionService
from services.cache_service import CacheService
from app_config import settings, config, get_openai_key
from database import init_db, cleanup_old_data

# Configure structured logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
data_service: DataCollectionService = None
prediction_service: PredictionService = None
cache_service: CacheService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global data_service, prediction_service, cache_service
    
    # Startup
    logger.info("Starting Football Analysis API...")
    await init_db()
    await cleanup_old_data()
    data_service = DataCollectionService(config_path=settings.config_file)
    
    # Initialize cache service if enabled
    if settings.cache_enabled:
        cache_service = CacheService(cache_dir=settings.cache_dir)
        logger.info(f"Cache service initialized (cache_dir: {settings.cache_dir})")
    else:
        logger.info("Cache service disabled")
        cache_service = None
    
    # Initialize prediction service with cache
    prediction_service = PredictionService(
        output_dir=settings.output_dir,
        cache_service=cache_service
    )
    logger.info("Services initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Football Analysis API...")
    if data_service:
        await data_service.close()
    logger.info("Cleanup completed")


# Initialize FastAPI app
app = FastAPI(
    title="Football Match Analysis API",
    description="""
    AI-powered football match analysis and prediction system.
    
    ## Two Types of Endpoints:
    
    ### MD File Endpoints
    - `/fixtures` - Generate and return match report MD files
    - `/predict` - Generate and return analysis MD files
    - `/analyze` - Complete workflow: fetch data + analyze (returns MD file)
    - `/batch` - Batch process multiple fixtures (returns MD file paths)
    
    ### Messaging Endpoints (Optimized for WhatsApp/Telegram)
    - `/msg/fixtures` - Get fixtures in clean JSON (1-5 KB)
    - `/msg/analyze` - Get predictions in clean JSON (1-2 KB)
    - `/msg/stats` - Get team stats in clean JSON (< 1 KB)
    
    ## Features:
    - Real-time match data from API-Football
    - AI-powered predictions using OpenAI
    - Weather and news data via Serper
    - Optimized responses for messaging apps
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
# In production, replace "*" with specific allowed origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",") if os.getenv("ALLOWED_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root():
    """
    Root endpoint - API information
    
    This API provides two types of endpoints:
    - **MD File Endpoints**: Return markdown files for data collection and analysis
    - **Messaging Endpoints**: Return clean JSON optimized for WhatsApp/Telegram bots
    """
    return {
        "name": "Football Match Analysis API",
        "version": "1.0.0",
        "description": "AI-powered football match analysis and prediction",
        "endpoints": {
            "status": "/status",
            "md_file_endpoints": {
                "fixtures": "/fixtures - Returns MD files",
                "prediction": "/predict - Returns analysis MD file",
                "full_analysis": "/analyze - Returns analysis MD file",
                "batch": "/batch - Returns MD file paths"
            },
            "messaging_endpoints": {
                "fixtures": "/msg/fixtures - Clean JSON for bots",
                "analyze": "/msg/analyze - Clean JSON predictions",
                "stats": "/msg/stats - Clean JSON team stats"
            }
        },
        "documentation": "/docs"
    }


@app.get("/status", response_model=StatusResponse, tags=["General"])
async def get_status():
    """Get API status and configuration"""
    try:
        # Check API-Football status
        api_status = None
        if data_service:
            collector = await data_service._get_collector()
            status_response = await collector.api_client.get_status()
            raw_status = status_response.get("response", {})
            if isinstance(raw_status, dict):
                api_status = raw_status
            elif isinstance(raw_status, list):
                api_status = raw_status[0] if raw_status and isinstance(raw_status[0], dict) else {}
            else:
                api_status = {}
        
        # Check LLM configuration (Groq/OpenAI-compatible)
        # Keep response field name `openai_configured` for backward compatibility.
        openai_configured = bool(settings.groq_api_key)
        
        return StatusResponse(
            status="operational",
            version="1.0.0",
            api_football_status=api_status,
            openai_configured=openai_configured
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/fixtures",
    tags=["Data Collection"],
    summary="Get fixture data and generate match reports (MD files)",
    response_description="MD file content or file paths"
)
async def get_fixtures(
    request: FixtureRequest = Body(
        ...,
        examples={
            "single_fixture": {
                "summary": "Get single fixture by ID",
                "value": {
                    "fixture_id": 1379137
                }
            },
            "by_date": {
                "summary": "Get fixtures for a date",
                "value": {
                    "date": "2025-12-24",
                    "league_id": 39
                }
            },
            "today": {
                "summary": "Get today's fixtures",
                "value": {
                    "date": "today"
                }
            },
            "live": {
                "summary": "Get live fixtures",
                "value": {
                    "live": True
                }
            }
        }
    )
):
    """
    Get fixture data and generate match reports (MD files)
    
    Returns MD file content or file paths.
    
    - **fixture_id**: Get specific fixture by ID
    - **date**: Get fixtures for a date (YYYY-MM-DD or 'today')
    - **league_id**: Filter by league ID
    - **live**: Get live fixtures
    """
    try:
        # Single fixture
        if request.fixture_id:
            result = await data_service.get_fixture_data(request.fixture_id)
            if result.get("success"):
                md_file = result.get("md_file")
                if md_file and os.path.exists(md_file):
                    return FileResponse(
                        md_file,
                        media_type="text/markdown",
                        filename=os.path.basename(md_file)
                    )
                else:
                    raise HTTPException(status_code=404, detail="MD file not generated")
            else:
                raise HTTPException(status_code=404, detail=result.get("error", "Fixture not found"))
        
        # Live fixtures
        elif request.live:
            result = await data_service.get_live_fixtures(process=True)
            if result.get("success"):
                md_files = result.get("md_files", [])
                if md_files:
                    # Return first MD file or list of paths as JSON
                    if len(md_files) == 1 and os.path.exists(md_files[0]):
                        return FileResponse(
                            md_files[0],
                            media_type="text/markdown",
                            filename=os.path.basename(md_files[0])
                        )
                    else:
                        return JSONResponse(content={"md_files": md_files})
                else:
                    raise HTTPException(status_code=404, detail="No MD files generated")
            else:
                raise HTTPException(status_code=500, detail=result.get("error"))
        
        # Fixtures by date
        elif request.date:
            league_ids = request.league_ids or ([request.league_id] if request.league_id else None)
            result = await data_service.get_fixtures_by_date(
                date=request.date,
                league_ids=league_ids,
                process=True
            )
            if result.get("success"):
                md_files = result.get("md_files", [])
                if md_files:
                    # Return first MD file or list of paths as JSON
                    if len(md_files) == 1 and os.path.exists(md_files[0]):
                        return FileResponse(
                            md_files[0],
                            media_type="text/markdown",
                            filename=os.path.basename(md_files[0])
                        )
                    else:
                        return JSONResponse(content={"md_files": md_files})
                else:
                    raise HTTPException(status_code=404, detail="No MD files generated")
            else:
                raise HTTPException(status_code=500, detail=result.get("error"))

        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide fixture_id, date, or set live=true"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/predict",
    tags=["Prediction"],
    summary="Analyze a match and generate predictions (returns MD file)",
    response_description="Analysis MD file content"
)
async def predict_match(
    request: PredictionRequest = Body(
        ...,
        examples={
            "by_fixture_id": {
                "summary": "Analyze by fixture ID",
                "value": {
                    "fixture_id": 1379137,
                    "analysis_type": "enhanced"
                }
            },
            "by_md_file": {
                "summary": "Analyze from MD file path",
                "value": {
                    "md_file_path": "output/match_1379137.md",
                    "analysis_type": "basic"
                }
            }
        }
    ),
    force_refresh: bool = Query(False, description="Force refresh cache and regenerate analysis")
):
    """
    Analyze a match and generate predictions (returns MD file)
    
    Returns the analysis MD file content.
    Checks cache first (unless force_refresh=true), then generates if needed.

    **Supports two ways to specify the match:**
    - **fixture_id**: Fixture ID (will auto-find the MD file)
    - **md_file_path**: Direct path to saved MD file (fixture_id will be extracted from file)
    
    - **analysis_type**: 'basic' or 'enhanced' (default: enhanced)
    - **force_refresh**: If true, bypass cache and regenerate analysis
    
    **Note:** When using `md_file_path`, the fixture_id is automatically extracted from the file
    for caching purposes. This allows you to analyze saved MD files while still benefiting from caching.
    """
    try:
        result = await prediction_service.analyze_match(
            md_file_path=request.md_file_path,
            fixture_id=request.fixture_id,
            analysis_type=request.analysis_type.value,
            force_refresh=force_refresh
        )

        if result.get("success"):
            analysis_file = result.get("analysis_file")
            if analysis_file and os.path.exists(analysis_file):
                return FileResponse(
                    analysis_file,
                    media_type="text/markdown",
                    filename=os.path.basename(analysis_file)
                )
            else:
                raise HTTPException(status_code=404, detail="Analysis file not found")
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in predict_match: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/analyze",
    tags=["Full Analysis"],
    summary="Complete workflow: Fetch fixture data + Generate analysis (returns MD file)",
    response_description="Analysis MD file content"
)
async def full_analysis(
    request: FullAnalysisRequest = Body(
        ...,
        examples={
            "default": {
                "summary": "Complete analysis workflow",
                "value": {
                    "fixture_id": 1379137,
                    "analysis_type": "enhanced"
                }
            },
            "basic": {
                "summary": "Basic analysis",
                "value": {
                    "fixture_id": 1379137,
                    "analysis_type": "basic"
                }
            }
        }
    ),
    force_refresh: bool = Query(False, description="Force refresh cache and regenerate analysis")
):
    """
    Complete workflow: Fetch fixture data + Generate analysis (returns MD file)
    
    Returns the analysis MD file content.
    Checks cache first (unless force_refresh=true), then generates if needed.

    - **fixture_id**: Fixture ID to analyze
    - **analysis_type**: 'basic' or 'enhanced' (default: enhanced)
    - **force_refresh**: If true, bypass cache and regenerate analysis
    """
    try:
        # Step 1: Fetch fixture data
        logger.info(f"Fetching data for fixture {request.fixture_id}")
        data_result = await data_service.get_fixture_data(request.fixture_id)

        if not data_result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=f"Failed to fetch fixture data: {data_result.get('error')}"
            )

        md_file = data_result.get("md_file")
        if not md_file:
            raise HTTPException(
                status_code=500,
                detail="Fixture data fetched but no MD file generated"
            )

        # Step 2: Analyze the match
        logger.info(f"Analyzing fixture {request.fixture_id} using {request.analysis_type.value} analysis")
        analysis_result = await prediction_service.analyze_match(
            md_file_path=md_file,
            fixture_id=request.fixture_id,
            analysis_type=request.analysis_type.value,
            force_refresh=force_refresh
        )

        if not analysis_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {analysis_result.get('error')}"
            )

        analysis_file = analysis_result.get("analysis_file")
        if analysis_file and os.path.exists(analysis_file):
            return FileResponse(
                analysis_file,
                media_type="text/markdown",
                filename=os.path.basename(analysis_file)
            )
        else:
            raise HTTPException(status_code=404, detail="Analysis file not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in full_analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/batch",
    tags=["Batch Processing"],
    summary="Batch process fixtures for a date (returns MD file paths)",
    response_description="JSON with list of MD file paths"
)
async def batch_process(
    request: BatchFixtureRequest = Body(
        ...,
        examples={
            "simple": {
                "summary": "Process fixtures for a date",
                "value": {
                    "date": "2025-12-24"
                }
            },
            "with_leagues": {
                "summary": "Process specific leagues",
                "value": {
                    "date": "2025-12-24",
                    "league_ids": [39, 135, 140]
                }
            },
            "with_analysis": {
                "summary": "Process and analyze all fixtures",
                "value": {
                    "date": "2025-12-24",
                    "league_ids": [39],
                    "analyze": True,
                    "analysis_type": "enhanced"
                }
            }
        }
    ),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Batch process fixtures for a date (returns MD file paths)
    
    Returns JSON with list of MD file paths.

    - **date**: Date to process (YYYY-MM-DD)
    - **league_ids**: Optional list of league IDs to filter
    - **analyze**: Whether to also run analysis on all fixtures
    - **analysis_type**: Type of analysis if analyze=True
    """
    try:
        # Fetch fixtures
        logger.info(f"Batch processing fixtures for {request.date}")
        data_result = await data_service.get_fixtures_by_date(
            date=request.date,
            league_ids=request.league_ids,
            process=True
        )

        if not data_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch fixtures: {data_result.get('error')}"
            )

        md_files = data_result.get("md_files", [])
        fixture_count = data_result.get("fixture_count", 0)

        analysis_files = []
        errors = []

        # Optionally analyze all fixtures
        if request.analyze and md_files:
            logger.info(f"Analyzing {len(md_files)} fixtures...")

            for md_file in md_files:
                try:
                    analysis_result = await prediction_service.analyze_match(
                        md_file_path=md_file,
                        analysis_type=request.analysis_type.value
                    )

                    if analysis_result.get("success"):
                        analysis_files.append(analysis_result.get("analysis_file"))
                    else:
                        errors.append(f"{md_file}: {analysis_result.get('error')}")

                    # Prevent hitting Free Tier request/minute limits during batch runs
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error analyzing {md_file}: {e}")
                    errors.append(f"{md_file}: {str(e)}")

        # Return MD file paths as JSON
        return JSONResponse(content={
            "success": True,
            "message": f"Processed {fixture_count} fixtures for {request.date}",
            "date": request.date,
            "total_fixtures": fixture_count,
            "processed_fixtures": len(md_files),
            "md_files": md_files,
            "analysis_files": analysis_files,
            "errors": errors
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch_process: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Messaging Endpoints (JSON) ====================

@app.post(
    "/msg/fixtures",
    response_model=MessagingFixtureResponse,
    tags=["Messaging"],
    summary="Get fixtures in clean JSON format (1-5 KB)",
    response_description="Clean JSON with minimal fixture data"
)
async def get_messaging_fixtures(
    request: FixtureRequest = Body(
        ...,
        examples={
            "today": {
                "summary": "Get today's fixtures",
                "value": {
                    "date": "today"
                }
            },
            "by_date": {
                "summary": "Get fixtures for specific date",
                "value": {
                    "date": "2025-12-24",
                    "league_id": 39
                }
            },
            "multiple_leagues": {
                "summary": "Get fixtures for multiple leagues",
                "value": {
                    "date": "2025-12-24",
                    "league_ids": [39, 135, 140]
                }
            },
            "live": {
                "summary": "Get live fixtures",
                "value": {
                    "live": True
                }
            }
        }
    )
):
    """
    Get fixtures in clean JSON format optimized for WhatsApp/Telegram bots.
    
    Returns minimal fixture data (1-5 KB) instead of verbose API responses.
    
    - **date**: Date in YYYY-MM-DD format or 'today'
    - **league_id**: Filter by league ID
    - **league_ids**: Multiple league IDs
    - **live**: Get live fixtures
    """
    try:
        fixtures_list = []
        
        # Single fixture
        if request.fixture_id:
            result = await data_service.get_fixture_data(request.fixture_id)
            if result.get("success"):
                fixture_data = result.get("fixture_data", {})
                transformed = transform_fixture_data(fixture_data)
                fixtures_list = [transformed]
            else:
                raise HTTPException(status_code=404, detail=result.get("error", "Fixture not found"))
        
        # Live fixtures
        elif request.live:
            result = await data_service.get_live_fixtures(process=False)  # Don't process, just get data
            if result.get("success"):
                fixtures_data = result.get("fixtures", [])
                for fixture in fixtures_data:
                    transformed = transform_fixture_data(fixture)
                    fixtures_list.append(transformed)
            else:
                raise HTTPException(status_code=500, detail=result.get("error"))
        
        # Fixtures by date
        elif request.date:
            league_ids = request.league_ids or ([request.league_id] if request.league_id else None)
            result = await data_service.get_fixtures_by_date(
            date=request.date,
                league_ids=league_ids,
                process=False  # Don't process, just get data
            )
            if result.get("success"):
                fixtures_data = result.get("fixtures", [])
                for fixture in fixtures_data:
                    transformed = transform_fixture_data(fixture)
                    fixtures_list.append(transformed)
            else:
                raise HTTPException(status_code=500, detail=result.get("error"))
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide fixture_id, date, or set live=true"
            )
        
        date_str = request.date if request.date else "today"
        if date_str.lower() == "today":
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        return MessagingFixtureResponse(
            success=True,
            date=date_str,
            count=len(fixtures_list),
            fixtures=fixtures_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_messaging_fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/msg/analyze",
    response_model=MessagingAnalysisResponse,
    tags=["Messaging"],
    summary="Get match predictions in clean JSON format (1-2 KB)",
    response_description="Clean JSON with probabilities and top bets"
)
async def get_messaging_analysis(
    request: PredictionRequest = Body(
        ...,
        examples={
            "by_fixture_id": {
                "summary": "Get analysis by fixture ID",
                "value": {
                    "fixture_id": 1379137,
                    "analysis_type": "enhanced"
                }
            },
            "by_md_file": {
                "summary": "Analyze from saved MD file",
                "value": {
                    "md_file_path": "output/match_1379137_20251224_154843.md",
                    "analysis_type": "enhanced"
                }
            },
            "basic": {
                "summary": "Basic analysis",
                "value": {
                    "fixture_id": 1379137,
                    "analysis_type": "basic"
                }
            }
        }
    ),
    force_refresh: bool = Query(False, description="Force refresh cache and regenerate analysis")
):
    """
    Get match analysis in clean JSON format optimized for WhatsApp/Telegram bots.
    
    Returns concise predictions with probabilities and top bets (1-2 KB).
    Checks cache first (unless force_refresh=true), then generates if needed.
    
    **Supports two ways to specify the match:**
    - **fixture_id**: Fixture ID to analyze (will auto-find MD file)
    - **md_file_path**: Direct path to saved MD file (fixture_id will be extracted from file)
    
    - **analysis_type**: 'basic' or 'enhanced' (default: enhanced)
    - **force_refresh**: If true, bypass cache and regenerate analysis
    
    **Note:** When using `md_file_path`, the fixture_id is automatically extracted from the file
    for caching purposes. This allows you to analyze saved MD files while still benefiting from caching.
    """
    try:
        result = await prediction_service.analyze_match(
            md_file_path=request.md_file_path,
            fixture_id=request.fixture_id,
            analysis_type=request.analysis_type.value,
            force_refresh=force_refresh
        )

        if result.get("success"):
            # Check if result is from cache (frontend-ready JSON)
            if result.get("cached") and result.get("cached_data"):
                logger.info(f"Returning cached analysis for fixture {request.fixture_id}")
                # Return cached data directly (already in MessagingAnalysisResponse format)
                cached_data = result.get("cached_data")
                return MessagingAnalysisResponse(**cached_data)
            
            # Transform analysis text into clean structure (newly generated)
            analysis_text = result.get("analysis", "")
            analysis_file = result.get("analysis_file")
            transformed = transform_analysis(analysis_text, analysis_file)
            
            # Get match info
            home_team = result.get("home_team", "Unknown")
            away_team = result.get("away_team", "Unknown")
            match_str = f"{home_team} vs {away_team}"
            
            return MessagingAnalysisResponse(
                success=True,
                fixture_id=result.get("fixture_id"),
                match=match_str,
                probabilities=transformed["probabilities"],
                top_bets=transformed["top_bets"],
                summary=transformed["summary"],
                reasoning=transformed.get("reasoning")
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_messaging_analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class StatsRequest(BaseModel):
    """Request model for stats endpoint"""
    fixture_id: int = Field(..., description="Fixture ID to get stats for")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fixture_id": 1379137
            }
        }

@app.post(
    "/msg/stats",
    response_model=QuickStatsResponse,
    tags=["Messaging"],
    summary="Get team statistics in clean JSON format (< 1 KB)",
    response_description="Clean JSON with team stats for both teams"
)
async def get_messaging_stats(
    request: StatsRequest = Body(
        ...,
        examples={
            "default": {
                "summary": "Get team stats for a fixture",
                "value": {
                    "fixture_id": 1379137
                }
            }
        }
    )
):
    """
    Get team statistics in clean JSON format optimized for WhatsApp/Telegram bots.
    
    Returns team stats summary (form, position, goals) for both teams (< 1 KB).
    
    - **fixture_id**: Fixture ID to get stats for
    """
    try:
        # Get fixture data
        result = await data_service.get_fixture_data(request.fixture_id)
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Fixture not found"))
        
        fixture_data = result.get("fixture_data", {})
        
        # Extract team names
        api_data = fixture_data.get("api_data", {})
        fixture = api_data.get("fixture", {})
        teams = fixture.get("teams", {})
        home_team_name = teams.get("home", {}).get("name", "Unknown")
        away_team_name = teams.get("away", {}).get("name", "Unknown")
        
        # Transform team stats
        home_stats = transform_team_stats(fixture_data, home_team_name)
        away_stats = transform_team_stats(fixture_data, away_team_name)
        
        return QuickStatsResponse(
            success=True,
            home_team=home_stats,
            away_team=away_stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_messaging_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Batch Processing Endpoints ====================

@app.post(
    "/batch/predict",
    response_model=BatchPredictResponse,
    tags=["Batch Processing"],
    summary="Batch process predictions for multiple dates and leagues",
    response_description="Summary of batch processing results"
)
async def batch_predict(
    request: BatchPredictRequest = Body(
        ...,
        examples={
            "today_single_league": {
                "summary": "Process today's Premier League games",
                "value": {
                    "dates": ["today"],
                    "league_ids": [39],
                    "analysis_type": "enhanced",
                    "skip_cached": True
                }
            },
            "multiple_leagues": {
                "summary": "Process multiple leagues for today",
                "value": {
                    "dates": ["today"],
                    "league_ids": [39, 140, 135],
                    "analysis_type": "enhanced"
                }
            },
            "multiple_dates": {
                "summary": "Process weekend fixtures",
                "value": {
                    "dates": ["2025-12-24", "2025-12-25", "2025-12-26"],
                    "league_ids": [39, 140, 135],
                    "analysis_type": "enhanced"
                }
            }
        }
    )
):
    """
    Batch process predictions for multiple dates and leagues.
    
    Generates predictions for all fixtures matching the criteria, skipping cached ones
    unless force_refresh=true. Returns detailed summary with breakdowns by date and league.
    
    - **dates**: List of dates (YYYY-MM-DD) or ["today"]
    - **league_ids**: Optional filter by specific league IDs
    - **analysis_type**: Type of analysis to generate
    - **force_refresh**: Force re-analysis even if cached
    - **skip_cached**: Skip fixtures that already have cache (unless force_refresh=true)
    """
    start_time = time.time()
    
    try:
        total_fixtures = 0
        processed = 0
        generated = 0
        cached_count = 0
        errors = []
        by_date = {}
        by_league = {}
        
        # Normalize dates
        from datetime import datetime
        normalized_dates = []
        for date_str in request.dates:
            if date_str.lower() == "today":
                normalized_dates.append(datetime.now().strftime("%Y-%m-%d"))
            else:
                normalized_dates.append(date_str)
        
        # Process each date
        for date_str in normalized_dates:
            date_fixtures = 0
            date_generated = 0
            date_cached = 0
            date_errors = []
            
            logger.info(f"Processing fixtures for {date_str} (leagues: {request.league_ids})")
            
            # Get fixtures for this date
            fixtures_result = await data_service.get_fixtures_by_date(
                date=date_str,
                league_ids=request.league_ids,
                process=False  # Don't process MD files, just get fixture data
            )
            
            if not fixtures_result.get("success"):
                date_errors.append(f"Failed to fetch fixtures: {fixtures_result.get('error')}")
                by_date[date_str] = {
                    "fixtures": 0,
                    "generated": 0,
                    "cached": 0,
                    "errors": date_errors
                }
                continue
            
            fixtures_data = fixtures_result.get("fixtures", [])
            date_fixtures = len(fixtures_data)
            total_fixtures += date_fixtures
            
            # Process each fixture
            for fixture_data in fixtures_data:
                fixture_id = None
                try:
                    # Extract fixture ID
                    if isinstance(fixture_data, dict):
                        if "fixture" in fixture_data:
                            fixture_id = fixture_data["fixture"].get("id")
                        elif "id" in fixture_data:
                            fixture_id = fixture_data["id"]
                        else:
                            # Try to get from api_data structure
                            api_data = fixture_data.get("api_data", {})
                            if "fixture" in api_data:
                                fixture_id = api_data["fixture"].get("id")
                    
                    if not fixture_id:
                        date_errors.append(f"Could not extract fixture ID from fixture data")
                        continue
                    
                    # Check cache
                    should_skip = False
                    if not request.force_refresh and request.skip_cached and cache_service:
                        if cache_service.cache_exists(fixture_id, request.analysis_type.value):
                            cached_count += 1
                            date_cached += 1
                            processed += 1
                            should_skip = True
                    
                    if should_skip:
                        continue
                    
                    # Get or find MD file for this fixture
                    md_file_result = await data_service.get_fixture_data(fixture_id)
                    if not md_file_result.get("success"):
                        date_errors.append(f"Fixture {fixture_id}: {md_file_result.get('error')}")
                        continue
                    
                    md_file = md_file_result.get("md_file")
                    if not md_file:
                        date_errors.append(f"Fixture {fixture_id}: No MD file generated")
                        continue
                    
                    # Generate analysis
                    analysis_result = await prediction_service.analyze_match(
                        md_file_path=md_file,
                        fixture_id=fixture_id,
                        analysis_type=request.analysis_type.value,
                        force_refresh=request.force_refresh
                    )
                    
                    if analysis_result.get("success"):
                        generated += 1
                        date_generated += 1
                        processed += 1
                    else:
                        date_errors.append(f"Fixture {fixture_id}: {analysis_result.get('error')}")

                    # Prevent hitting Free Tier request/minute limits during batch runs
                    await asyncio.sleep(2)
                    
                    # Track by league
                    if request.league_ids:
                        # Extract league ID from fixture data
                        league_id = None
                        if isinstance(fixture_data, dict):
                            if "league" in fixture_data:
                                league_id = fixture_data["league"].get("id")
                            elif "api_data" in fixture_data:
                                league = fixture_data["api_data"].get("league", {})
                                league_id = league.get("id")
                        
                        if league_id and league_id in request.league_ids:
                            if league_id not in by_league:
                                by_league[league_id] = {"fixtures": 0, "generated": 0, "cached": 0}
                            by_league[league_id]["fixtures"] += 1
                            if analysis_result.get("success"):
                                by_league[league_id]["generated"] += 1
                            elif should_skip:
                                by_league[league_id]["cached"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing fixture {fixture_id}: {e}", exc_info=True)
                    error_msg = f"Fixture {fixture_id}: {str(e)}"
                    date_errors.append(error_msg)
                    errors.append(error_msg)
            
            by_date[date_str] = {
                "fixtures": date_fixtures,
                "generated": date_generated,
                "cached": date_cached,
                "errors": date_errors
            }
            errors.extend(date_errors)
        
        processing_time = time.time() - start_time
        
        return BatchPredictResponse(
            success=True,
            total_fixtures=total_fixtures,
            processed=processed,
            generated=generated,
            cached=cached_count,
            errors=errors,
            by_date=by_date,
            by_league=by_league if by_league else None,
            processing_time_seconds=round(processing_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Error in batch_predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Cache Management Endpoints ====================

@app.post(
    "/cache/refresh",
    response_model=CacheRefreshResponse,
    tags=["Cache Management"],
    summary="Refresh cache for fixtures (regenerate predictions)",
    response_description="Summary of cache refresh results"
)
async def refresh_cache(
    request: CacheRefreshRequest = Body(
        ...,
        examples={
            "single_fixture": {
                "summary": "Refresh single fixture",
                "value": {
                    "fixture_ids": [1379137],
                    "analysis_type": "enhanced"
                }
            },
            "multiple_fixtures": {
                "summary": "Refresh multiple fixtures",
                "value": {
                    "fixture_ids": [1379137, 1379145],
                    "analysis_type": "enhanced"
                }
            },
            "by_date_league": {
                "summary": "Refresh by date and league",
                "value": {
                    "date": "today",
                    "league_ids": [39],
                    "analysis_type": "enhanced"
                }
            }
        }
    )
):
    """
    Refresh cache for fixtures by regenerating predictions.
    
    Supports flexible filtering: by fixture IDs, date, league IDs, or combinations.
    Invalidates existing cache and generates new analysis.
    
    - **fixture_ids**: Refresh specific fixtures (single or multiple)
    - **date**: Refresh all fixtures for a date (YYYY-MM-DD or "today")
    - **league_ids**: Refresh fixtures for specific leagues
    - **analysis_type**: Filter by analysis type (if None, refresh all types)
    - **force_regenerate**: Force new analysis generation (default: true)
    """
    if not cache_service:
        raise HTTPException(status_code=503, detail="Cache service not available")
    
    start_time = time.time()
    
    try:
        refreshed_count = 0
        errors = []
        by_fixture = {}
        
        # Determine which fixtures to refresh
        fixture_ids_to_refresh = []
        
        if request.fixture_ids:
            # Refresh specific fixtures
            fixture_ids_to_refresh = request.fixture_ids
        elif request.date or request.league_ids:
            # Get fixtures by date/league
            date_str = request.date or "today"
            if date_str.lower() == "today":
                from datetime import datetime
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            fixtures_result = await data_service.get_fixtures_by_date(
                date=date_str,
                league_ids=request.league_ids,
                process=False
            )
            
            if not fixtures_result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch fixtures: {fixtures_result.get('error')}"
                )
            
            fixtures_data = fixtures_result.get("fixtures", [])
            for fixture_data in fixtures_data:
                fixture_id = None
                if isinstance(fixture_data, dict):
                    if "fixture" in fixture_data:
                        fixture_id = fixture_data["fixture"].get("id")
                    elif "id" in fixture_data:
                        fixture_id = fixture_data["id"]
                    elif "api_data" in fixture_data:
                        fixture_id = fixture_data["api_data"].get("fixture", {}).get("id")
                
                if fixture_id:
                    fixture_ids_to_refresh.append(fixture_id)
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide fixture_ids, date, or league_ids"
            )
        
        # Refresh each fixture
        analysis_types = [request.analysis_type] if request.analysis_type else ["basic", "enhanced"]
        
        for fixture_id in fixture_ids_to_refresh:
            for analysis_type in analysis_types:
                try:
                    # Invalidate cache
                    cache_service.invalidate_cache(fixture_id, analysis_type)
                    
                    # Get MD file
                    md_file_result = await data_service.get_fixture_data(fixture_id)
                    if not md_file_result.get("success"):
                        error_msg = f"Fixture {fixture_id}: {md_file_result.get('error')}"
                        errors.append(error_msg)
                        by_fixture[fixture_id] = f"error: {error_msg}"
                        continue
                    
                    md_file = md_file_result.get("md_file")
                    if not md_file:
                        error_msg = f"Fixture {fixture_id}: No MD file"
                        errors.append(error_msg)
                        by_fixture[fixture_id] = f"error: {error_msg}"
                        continue
                    
                    # Generate new analysis
                    analysis_result = await prediction_service.analyze_match(
                        md_file_path=md_file,
                        fixture_id=fixture_id,
                        analysis_type=analysis_type,
                        force_refresh=True
                    )
                    
                    if analysis_result.get("success"):
                        refreshed_count += 1
                        by_fixture[fixture_id] = "refreshed"
                    else:
                        error_msg = f"Fixture {fixture_id}: {analysis_result.get('error')}"
                        errors.append(error_msg)
                        by_fixture[fixture_id] = f"error: {error_msg}"
                        
                except Exception as e:
                    logger.error(f"Error refreshing fixture {fixture_id}: {e}", exc_info=True)
                    error_msg = f"Fixture {fixture_id}: {str(e)}"
                    errors.append(error_msg)
                    by_fixture[fixture_id] = f"error: {error_msg}"
        
        processing_time = time.time() - start_time
        
        return CacheRefreshResponse(
            success=True,
            refreshed_count=refreshed_count,
            errors=errors,
            by_fixture=by_fixture if by_fixture else None,
            processing_time_seconds=round(processing_time, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in refresh_cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/cache/invalidate",
    response_model=CacheInvalidateResponse,
    tags=["Cache Management"],
    summary="Invalidate cache entries (delete without regenerating)",
    response_description="Summary of cache invalidation results"
)
async def invalidate_cache(
    request: CacheInvalidateRequest = Body(
        ...,
        examples={
            "single_fixture": {
                "summary": "Invalidate single fixture",
                "value": {
                    "fixture_ids": [1379137]
                }
            },
            "by_date": {
                "summary": "Invalidate by date",
                "value": {
                    "date": "2025-12-24",
                    "analysis_type": "enhanced"
                }
            },
            "by_league": {
                "summary": "Invalidate by league",
                "value": {
                    "league_ids": [39],
                    "analysis_type": "enhanced"
                }
            }
        }
    )
):
    """
    Invalidate cache entries without regenerating predictions.
    
    Supports flexible filtering: by fixture IDs, date, league IDs, or combinations.
    Only deletes cache files, does not generate new analysis.
    
    - **fixture_ids**: Invalidate specific fixtures
    - **date**: Invalidate all fixtures for a date (YYYY-MM-DD)
    - **league_ids**: Invalidate fixtures for specific leagues
    - **analysis_type**: Filter by analysis type (if None, invalidate all types)
    """
    if not cache_service:
        raise HTTPException(status_code=503, detail="Cache service not available")
    
    try:
        invalidated_count = 0
        errors = []
        
        if request.fixture_ids:
            # Invalidate specific fixtures
            result = cache_service.invalidate_cache_batch(
                fixture_ids=request.fixture_ids,
                analysis_type=request.analysis_type
            )
            invalidated_count = result["invalidated"]
            if result["errors"] > 0:
                errors.append(f"Errors invalidating {result['errors']} fixtures")
        elif request.date:
            # Invalidate by date
            date_str = request.date
            if date_str.lower() == "today":
                from datetime import datetime
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            result = cache_service.invalidate_cache_by_date(
                date=date_str,
                analysis_type=request.analysis_type
            )
            invalidated_count = result["invalidated"]
            if result["errors"] > 0:
                errors.append(f"Errors invalidating {result['errors']} cache entries")
        elif request.league_ids:
            # Invalidate by league (need to get fixtures first)
            date_str = "today"
            fixtures_result = await data_service.get_fixtures_by_date(
                date=date_str,
                league_ids=request.league_ids,
                process=False
            )
            
            if fixtures_result.get("success"):
                fixtures_data = fixtures_result.get("fixtures", [])
                fixture_ids = []
                for fixture_data in fixtures_data:
                    fixture_id = None
                    if isinstance(fixture_data, dict):
                        if "fixture" in fixture_data:
                            fixture_id = fixture_data["fixture"].get("id")
                        elif "id" in fixture_data:
                            fixture_id = fixture_data["id"]
                        elif "api_data" in fixture_data:
                            fixture_id = fixture_data["api_data"].get("fixture", {}).get("id")
                    
                    if fixture_id:
                        fixture_ids.append(fixture_id)
                
                result = cache_service.invalidate_cache_batch(
                    fixture_ids=fixture_ids,
                    analysis_type=request.analysis_type
                )
                invalidated_count = result["invalidated"]
                if result["errors"] > 0:
                    errors.append(f"Errors invalidating {result['errors']} fixtures")
            else:
                errors.append(f"Failed to fetch fixtures: {fixtures_result.get('error')}")
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide fixture_ids, date, or league_ids"
            )
        
        return CacheInvalidateResponse(
            success=True,
            invalidated_count=invalidated_count,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in invalidate_cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
