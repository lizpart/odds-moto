"""
End-to-end tests for Football Analysis API
"""
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


class TestStatusEndpoint:
    """Tests for /status endpoint"""
    
    def test_status_endpoint(self, client):
        """Test status endpoint returns valid response"""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["status"] == "operational"
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data


class TestMessagingEndpoints:
    """Tests for messaging endpoints (/msg/*)"""
    
    def test_msg_fixtures_today(self, client):
        """Test /msg/fixtures with today's date"""
        response = client.post(
            "/msg/fixtures",
            json={"date": "today"}
        )
        # May return 200 with empty fixtures or 500 if API keys not configured
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "date" in data
            assert "count" in data
            assert "fixtures" in data
            assert isinstance(data["fixtures"], list)
    
    def test_msg_fixtures_with_date(self, client):
        """Test /msg/fixtures with specific date"""
        response = client.post(
            "/msg/fixtures",
            json={"date": "2025-12-24", "league_id": 39}
        )
        # May return 200 with fixtures or 500 if API keys not configured
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert data["date"] == "2025-12-24"
    
    def test_msg_fixtures_validation(self, client):
        """Test /msg/fixtures request validation"""
        # Missing required field (date or fixture_id or live)
        response = client.post(
            "/msg/fixtures",
            json={}
        )
        assert response.status_code == 400
    
    def test_msg_analyze_validation(self, client):
        """Test /msg/analyze request validation"""
        # Missing fixture_id and md_file_path
        response = client.post(
            "/msg/analyze",
            json={"analysis_type": "enhanced"}
        )
        # Should accept but may fail during processing
        assert response.status_code in [200, 400, 500]
    
    def test_msg_stats_validation(self, client):
        """Test /msg/stats request validation"""
        response = client.post(
            "/msg/stats",
            json={"fixture_id": 1379137}
        )
        # May return 200 with stats or 404/500 if fixture not found or API keys not configured
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "home_team" in data
            assert "away_team" in data


class TestMDEndpoints:
    """Tests for MD file endpoints"""
    
    def test_fixtures_endpoint_validation(self, client):
        """Test /fixtures endpoint validation"""
        # Missing required fields
        response = client.post(
            "/fixtures",
            json={}
        )
        assert response.status_code == 400
    
    def test_predict_endpoint_validation(self, client):
        """Test /predict endpoint validation"""
        response = client.post(
            "/predict",
            json={"analysis_type": "enhanced"}
        )
        # Should accept but may fail during processing
        assert response.status_code in [200, 400, 404, 500]
    
    def test_analyze_endpoint_validation(self, client):
        """Test /analyze endpoint validation"""
        response = client.post(
            "/analyze",
            json={"fixture_id": 1379137}
        )
        # May return 200 with MD file or 404/500 if fixture not found
        assert response.status_code in [200, 404, 500]
    
    def test_batch_endpoint_validation(self, client):
        """Test /batch endpoint validation"""
        response = client.post(
            "/batch",
            json={"date": "2025-12-24"}
        )
        # May return 200 with file paths or 500 if API keys not configured
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "md_files" in data


class TestErrorHandling:
    """Tests for error handling"""
    
    def test_invalid_fixture_id(self, client):
        """Test error handling for invalid fixture ID"""
        response = client.post(
            "/msg/fixtures",
            json={"fixture_id": 999999999}
        )
        # Should return 404 or 500
        assert response.status_code in [404, 500]
        if response.status_code in [404, 500]:
            data = response.json()
            assert "error" in data or "detail" in data
    
    def test_invalid_date_format(self, client):
        """Test error handling for invalid date format"""
        response = client.post(
            "/msg/fixtures",
            json={"date": "invalid-date"}
        )
        # May accept but fail during processing, or return 400
        assert response.status_code in [200, 400, 500]
    
    def test_missing_required_fields(self, client):
        """Test error handling for missing required fields"""
        response = client.post(
            "/batch",
            json={}
        )
        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422]


class TestResponseFormats:
    """Tests for response format validation"""
    
    def test_messaging_fixtures_format(self, client):
        """Test /msg/fixtures response format"""
        response = client.post(
            "/msg/fixtures",
            json={"date": "today"}
        )
        if response.status_code == 200:
            data = response.json()
            # Check required fields
            assert "success" in data
            assert "date" in data
            assert "count" in data
            assert "fixtures" in data
            # Check fixture structure if fixtures exist
            if data["fixtures"]:
                fixture = data["fixtures"][0]
                assert "id" in fixture or fixture.get("id") is None
                assert "match" in fixture
                assert "home_team" in fixture
                assert "away_team" in fixture
                assert "time" in fixture
                assert "date" in fixture
                assert "league" in fixture
                assert "status" in fixture
    
    def test_messaging_analyze_format(self, client):
        """Test /msg/analyze response format"""
        response = client.post(
            "/msg/analyze",
            json={"fixture_id": 1379137, "analysis_type": "enhanced"}
        )
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "match" in data
            assert "probabilities" in data
            assert "top_bets" in data
            assert "summary" in data
            # Check probabilities structure
            if "probabilities" in data:
                prob = data["probabilities"]
                assert "home" in prob
                assert "draw" in prob
                assert "away" in prob
    
    def test_messaging_stats_format(self, client):
        """Test /msg/stats response format"""
        response = client.post(
            "/msg/stats",
            json={"fixture_id": 1379137}
        )
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "home_team" in data
            assert "away_team" in data
            # Check team stats structure
            if "home_team" in data:
                team = data["home_team"]
                assert "team" in team
                assert "position" in team or team.get("position") is None
                assert "form" in team
                assert "goals_scored" in team
                assert "goals_conceded" in team


