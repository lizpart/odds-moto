# API Reference

Complete reference for all Football Analysis API endpoints.

## Base URL

```
http://localhost:8000
```

## Authentication

No authentication required for local development. For production, configure API keys in `config.json`.

## Endpoints

### General

#### GET `/`
Get API information and available endpoints.

**Response:**
```json
{
  "name": "Football Match Analysis API",
  "version": "1.0.0",
  "description": "AI-powered football match analysis and prediction",
  "endpoints": { ... },
  "documentation": "/docs"
}
```

#### GET `/status`
Get API status and configuration.

**Response:**
```json
{
  "status": "operational",
  "version": "1.0.0",
  "api_football_status": { ... },
  "openai_configured": true
}
```

---

## MD File Endpoints

These endpoints return Markdown files or file paths.

### POST `/fixtures`
Generate match report MD files.

**Request:**
```json
{
  "fixture_id": 1379137,
  "date": "2025-12-24",
  "league_id": 39,
  "live": false
}
```

**Response:** MD file content (Content-Type: text/markdown)

**Use Cases:**
- Generate match reports for storage
- Create detailed fixture documentation

---

### POST `/predict`
Generate analysis MD file from existing fixture data.

**Request Options:**
You can specify the match in two ways:

**Option 1: By Fixture ID**
```json
{
  "fixture_id": 1379137,
  "analysis_type": "enhanced"
}
```

**Option 2: By MD File Path** (Analyze a saved MD file)
```json
{
  "md_file_path": "output/match_1379137_20251224_154843.md",
  "analysis_type": "enhanced"
}
```

**Query Parameters:**
- `force_refresh` (bool, optional): If `true`, bypass cache and regenerate analysis. Default: `false`

**Response:** Analysis MD file content (Content-Type: text/markdown)

**Analysis Types:**
- `basic` - Basic betting analysis
- `enhanced` - Enhanced analysis with psychological factors

**Note:** When using `md_file_path`, the fixture_id is automatically extracted from the file for caching. This allows you to analyze saved MD files while still benefiting from caching.

---

### POST `/analyze`
Complete workflow: fetch fixture data + generate analysis.

**Request:**
```json
{
  "fixture_id": 1379137,
  "analysis_type": "enhanced"
}
```

**Response:** Analysis MD file content (Content-Type: text/markdown)

**Use Cases:**
- One-step process to get complete analysis
- Generate analysis for a specific fixture

---

### POST `/batch`
Batch process multiple fixtures for a date.

**Request:**
```json
{
  "date": "2025-12-24",
  "league_ids": [39, 135, 140],
  "analyze": true,
  "analysis_type": "enhanced"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Processed 10 fixtures for 2025-12-24",
  "date": "2025-12-24",
  "total_fixtures": 10,
  "processed_fixtures": 10,
  "md_files": ["output/match_1.md", ...],
  "analysis_files": ["output/analysis_1.txt", ...],
  "errors": []
}
```

---

## Messaging Endpoints

These endpoints return clean JSON optimized for WhatsApp/Telegram bots.

### POST `/msg/fixtures`
Get fixtures in clean JSON format (1-5 KB). **Frontend-ready JSON** - optimized for direct consumption.

**Request:**
```json
{
  "date": "today",
  "league_id": 39,
  "live": false
}
```

**Response (Frontend-Ready):**
```json
{
  "success": true,
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
```

**PowerShell Example:**
```powershell
$body = '{"date": "today"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/msg/fixtures -Method POST -ContentType "application/json" -Body $body
$response.fixtures | Format-Table id, match, time, status
```

**Use Cases:**
- WhatsApp/Telegram bots
- Mobile apps
- Quick fixture listings
- Frontend applications (React, Vue, Angular)

---

### POST `/msg/analyze`
Get match predictions in clean JSON format (1-2 KB). **Frontend-ready JSON** - ready for direct display.

**Caching:** This endpoint uses intelligent caching. Responses are cached after first generation, and subsequent requests return cached data instantly (<10ms). Use `force_refresh=true` query parameter to bypass cache.

**Request Options:**
You can specify the match in two ways:

**Option 1: By Fixture ID**
```json
{
  "fixture_id": 1379137,
  "analysis_type": "enhanced"
}
```

**Option 2: By MD File Path** (Analyze a saved MD file)
```json
{
  "md_file_path": "output/match_1379137_20251224_154843.md",
  "analysis_type": "enhanced"
}
```

**Note:** When using `md_file_path`, the fixture_id is automatically extracted from the file for caching. This allows you to analyze saved MD files while still benefiting from caching.

**Query Parameters:**
- `force_refresh` (bool, optional): If `true`, bypass cache and regenerate analysis. Default: `false`

**Response (Frontend-Ready):**
```json
{
  "success": true,
  "fixture_id": 1379137,
  "match": "Arsenal vs Chelsea",
  "probabilities": {
    "home": 45,
    "draw": 28,
    "away": 27
  },
  "top_bets": [
    {
      "bet": "Arsenal to Win",
      "odds": 2.10
    },
    {
      "bet": "Over 2.5 Goals",
      "odds": 1.75
    }
  ],
  "summary": "Arsenal has strong home form...",
  "reasoning": "Detailed analysis..."
}
```

**PowerShell Examples:**

Get analysis by fixture ID:
```powershell
$body = '{"fixture_id": 1379137, "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/msg/analyze -Method POST -ContentType "application/json" -Body $body
Write-Host "Match: $($response.match)"
Write-Host "Home: $($response.probabilities.home)% | Draw: $($response.probabilities.draw)% | Away: $($response.probabilities.away)%"
```

Analyze from saved MD file:
```powershell
$body = '{"md_file_path": "output/match_1379137_20251224_154843.md", "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/msg/analyze -Method POST -ContentType "application/json" -Body $body
```

Force refresh (bypass cache):
```powershell
$body = '{"fixture_id": 1379137, "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri "http://localhost:8000/msg/analyze?force_refresh=true" -Method POST -ContentType "application/json" -Body $body
```

**Use Cases:**
- Quick predictions for bots
- Betting recommendations
- Match analysis summaries
- Frontend dashboards

---

### POST `/msg/stats`
Get team statistics in clean JSON format (< 1 KB). **Frontend-ready JSON** - perfect for comparison displays.

**Request:**
```json
{
  "fixture_id": 1379137
}
```

**Response (Frontend-Ready):**
```json
{
  "success": true,
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
```

**PowerShell Example:**
```powershell
$body = '{"fixture_id": 1379137}'
$response = Invoke-RestMethod -Uri http://localhost:8000/msg/stats -Method POST -ContentType "application/json" -Body $body
Write-Host "$($response.home_team.team) (Pos: $($response.home_team.position), Form: $($response.home_team.form))"
Write-Host "vs"
Write-Host "$($response.away_team.team) (Pos: $($response.away_team.position), Form: $($response.away_team.form))"
```

**Use Cases:**
- Team comparison
- Quick stats for bots
- Form analysis
- Frontend stat displays

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "success": false,
  "error": "Error message"
}
```

**Common Status Codes:**
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (fixture/data not found)
- `500` - Internal Server Error

See [Error Handling](ERROR_HANDLING.md) for details.

---

## Rate Limits

- API-Football: 30 requests/minute (free plan)
- OpenAI: Based on your plan
- Serper: Based on your plan

---

## Examples

### PowerShell (Windows - Recommended)

```powershell
# Get today's fixtures
$body = '{"date": "today"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/msg/fixtures -Method POST -ContentType "application/json" -Body $body
$response.fixtures | Format-Table

# Get fixtures for specific date
$body = '{"date": "2025-12-24", "league_id": 39}'
Invoke-RestMethod -Uri http://localhost:8000/msg/fixtures -Method POST -ContentType "application/json" -Body $body

# Get analysis
$body = '{"fixture_id": 1379137, "analysis_type": "enhanced"}'
Invoke-RestMethod -Uri http://localhost:8000/msg/analyze -Method POST -ContentType "application/json" -Body $body

# Get team stats
$body = '{"fixture_id": 1379137}'
Invoke-RestMethod -Uri http://localhost:8000/msg/stats -Method POST -ContentType "application/json" -Body $body

# One-liner for quick testing
Invoke-RestMethod -Uri http://localhost:8000/msg/fixtures -Method POST -ContentType "application/json" -Body '{"date":"today"}' | Select-Object success, date, count
```

### Python

```python
import requests

# Get today's fixtures
response = requests.post(
    "http://localhost:8000/msg/fixtures",
    json={"date": "today"}
)
fixtures = response.json()
print(f"Found {fixtures['count']} fixtures")

# Get analysis
response = requests.post(
    "http://localhost:8000/msg/analyze",
    json={"fixture_id": 1379137}
)
analysis = response.json()
print(f"Match: {analysis['match']}")
print(f"Home Win: {analysis['probabilities']['home']}%")
```

### cURL (Linux/Mac)

```bash
# Get fixtures
curl -X POST http://localhost:8000/msg/fixtures \
  -H "Content-Type: application/json" \
  -d '{"date": "today"}'

# Get analysis
curl -X POST http://localhost:8000/msg/analyze \
  -H "Content-Type: application/json" \
  -d '{"fixture_id": 1379137}'
```

### JavaScript/Node.js

```javascript
// Get today's fixtures
const response = await fetch('http://localhost:8000/msg/fixtures', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ date: 'today' })
});
const data = await response.json();
console.log(`Found ${data.count} fixtures`);
```

---

## Batch Processing Endpoints

### POST `/batch/predict`
Batch process predictions for multiple dates and leagues. Perfect for morning batch jobs to pre-generate predictions for the day's games.

**Request:**
```json
{
  "dates": ["today"],
  "league_ids": [39, 140, 135],
  "analysis_type": "enhanced",
  "force_refresh": false,
  "skip_cached": true
}
```

**Parameters:**
- `dates` (List[str]): List of dates (YYYY-MM-DD) or ["today"]. Default: ["today"]
- `league_ids` (List[int], optional): Filter by specific league IDs (e.g., [39] for Premier League)
- `analysis_type` (str): "basic" or "enhanced". Default: "enhanced"
- `force_refresh` (bool): Force re-analysis even if cached. Default: false
- `skip_cached` (bool): Skip fixtures that already have cache. Default: true

**Response:**
```json
{
  "success": true,
  "total_fixtures": 20,
  "processed": 20,
  "generated": 5,
  "cached": 15,
  "errors": [],
  "by_date": {
    "2025-12-24": {
      "fixtures": 20,
      "generated": 5,
      "cached": 15,
      "errors": []
    }
  },
  "by_league": {
    39: {"fixtures": 10, "generated": 3, "cached": 7},
    140: {"fixtures": 10, "generated": 2, "cached": 8}
  },
  "processing_time_seconds": 125.5
}
```

**PowerShell Examples:**

Process today's Premier League games:
```powershell
$body = '{"dates": ["today"], "league_ids": [39], "analysis_type": "enhanced", "skip_cached": true}'
$response = Invoke-RestMethod -Uri http://localhost:8000/batch/predict -Method POST -ContentType "application/json" -Body $body
Write-Host "Generated: $($response.generated) | Cached: $($response.cached) | Total: $($response.total_fixtures)"
```

Process multiple leagues:
```powershell
$body = '{"dates": ["today"], "league_ids": [39, 140, 135], "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/batch/predict -Method POST -ContentType "application/json" -Body $body
```

Process weekend fixtures (multiple dates):
```powershell
$body = '{"dates": ["2025-12-24", "2025-12-25", "2025-12-26"], "league_ids": [39, 140, 135]}'
$response = Invoke-RestMethod -Uri http://localhost:8000/batch/predict -Method POST -ContentType "application/json" -Body $body
```

**Use Cases:**
- Morning batch jobs (cron/scheduled tasks)
- Pre-generating predictions for the day
- Processing multiple leagues efficiently
- Weekend batch processing

---

## Cache Management Endpoints

### POST `/cache/refresh`
Refresh cache for fixtures by regenerating predictions. Supports flexible filtering by fixture IDs, date, league IDs, or combinations.

**Request:**
```json
{
  "fixture_ids": [1379137],
  "analysis_type": "enhanced",
  "force_regenerate": true
}
```

**Parameters:**
- `fixture_ids` (List[int], optional): Refresh specific fixtures (single or multiple)
- `date` (str, optional): Refresh all fixtures for a date (YYYY-MM-DD or "today")
- `league_ids` (List[int], optional): Refresh fixtures for specific leagues
- `analysis_type` (str, optional): Filter by analysis type. If None, refresh all types
- `force_regenerate` (bool): Force new analysis generation. Default: true

**Response:**
```json
{
  "success": true,
  "refreshed_count": 5,
  "errors": [],
  "by_fixture": {
    1379137: "refreshed",
    1379145: "refreshed"
  },
  "processing_time_seconds": 45.2
}
```

**PowerShell Examples:**

Refresh single fixture:
```powershell
$body = '{"fixture_ids": [1379137], "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/cache/refresh -Method POST -ContentType "application/json" -Body $body
Write-Host "Refreshed: $($response.refreshed_count) fixtures"
```

Refresh today's Premier League games:
```powershell
$body = '{"date": "today", "league_ids": [39], "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/cache/refresh -Method POST -ContentType "application/json" -Body $body
```

Refresh multiple fixtures:
```powershell
$body = '{"fixture_ids": [1379137, 1379145, 1379150], "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/cache/refresh -Method POST -ContentType "application/json" -Body $body
```

---

### POST `/cache/invalidate`
Invalidate cache entries without regenerating predictions. Only deletes cache files.

**Request:**
```json
{
  "date": "2025-12-24",
  "league_ids": [39],
  "analysis_type": "enhanced"
}
```

**Parameters:**
- `fixture_ids` (List[int], optional): Invalidate specific fixtures
- `date` (str, optional): Invalidate all fixtures for a date
- `league_ids` (List[int], optional): Invalidate fixtures for specific leagues
- `analysis_type` (str, optional): Filter by analysis type. If None, invalidate all types

**Response:**
```json
{
  "success": true,
  "invalidated_count": 10,
  "errors": []
}
```

**PowerShell Examples:**

Invalidate specific fixtures:
```powershell
$body = '{"fixture_ids": [1379137, 1379145]}'
$response = Invoke-RestMethod -Uri http://localhost:8000/cache/invalidate -Method POST -ContentType "application/json" -Body $body
Write-Host "Invalidated: $($response.invalidated_count) cache entries"
```

Invalidate by date:
```powershell
$body = '{"date": "2025-12-24", "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/cache/invalidate -Method POST -ContentType "application/json" -Body $body
```

---

## Caching System

The API uses an intelligent caching system to optimize performance and reduce costs:

- **Automatic Caching**: All predictions are automatically cached after first generation
- **Fast Retrieval**: Cached responses return in <10ms vs 30-60s for new generation
- **Frontend-Ready**: Cached data is stored in frontend-ready JSON format (MessagingAnalysisResponse)
- **Cost Reduction**: OpenAI API calls only happen once per fixture per day
- **Flexible Refresh**: Use `/cache/refresh` or `force_refresh=true` to regenerate when needed

**Cache Location:** `cache/predictions/{fixture_id}_{analysis_type}.json`

**Cache Format:** Frontend-ready JSON matching `MessagingAnalysisResponse` structure

---

## Next Steps

- **[Bot Integration](BOT_INTEGRATION.md)** - Build WhatsApp/Telegram bots
- **[Response Formats](RESPONSE_FORMATS.md)** - Detailed response structures
- **[Error Handling](ERROR_HANDLING.md)** - Troubleshooting guide

