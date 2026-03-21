"""
Pytest configuration and fixtures for API tests
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from services.data_collection_service import DataCollectionService
from services.prediction_service import PredictionService
from app_config import settings
import os
import tempfile
import shutil
import asyncio


@pytest.fixture(scope="function", autouse=True)
def initialize_services():
    """Initialize services before each test"""
    import main
    # Initialize services for testing
    if main.data_service is None:
        main.data_service = DataCollectionService(config_path=settings.config_file)
    if main.prediction_service is None:
        main.prediction_service = PredictionService(output_dir=settings.output_dir)
    yield
    # Cleanup after test
    # Services will be cleaned up by lifespan in production


@pytest.fixture
def client():
    """Create a test client for the API"""
    return TestClient(app)


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_fixture_id():
    """Sample fixture ID for testing"""
    return 1379137


@pytest.fixture
def sample_date():
    """Sample date for testing"""
    return "2025-12-24"


@pytest.fixture
def sample_league_id():
    """Sample league ID for testing"""
    return 39  # Premier League

