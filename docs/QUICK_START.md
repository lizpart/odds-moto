# Quick Start Guide

Get the Football Analysis API up and running in 5 minutes.

## Prerequisites

- Python 3.10+
- API-Football account (free plan works)
- OpenAI API key (optional, for predictions)
- Serper API key (optional, for news/weather)

## Installation

### 1. Activate Virtual Environment

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

Edit `config.json` or set environment variables:

```json
{
  "openai_api_key": "your-openai-key",
  "api_football": {
    "api_key": "your-api-football-key"
  },
  "serper": {
    "api_key": "your-serper-key"
  }
}
```

Or use environment variables:
```bash
export OPENAI_API_KEY="your-key"
export API_FOOTBALL_KEY="your-key"
export SERPER_API_KEY="your-key"
```

### 4. Start the Server

```bash
python run_api.py
```

Server runs on `http://localhost:8000`

## Test the API

### Check Status

**Windows PowerShell:**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/status
```

**Linux/Mac (curl):**
```bash
curl http://localhost:8000/status
```

### Get Today's Fixtures (Messaging Endpoint)

**Windows PowerShell (Recommended):**
```powershell
$body = '{"date": "today"}'
Invoke-RestMethod -Uri http://localhost:8000/msg/fixtures -Method POST -ContentType "application/json" -Body $body
```

**Or one-liner:**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/msg/fixtures -Method POST -ContentType "application/json" -Body '{"date":"today"}'
```

**Linux/Mac (curl):**
```bash
curl -X POST http://localhost:8000/msg/fixtures \
  -H "Content-Type: application/json" \
  -d '{"date": "today"}'
```

### Get Fixture MD File

**Windows PowerShell:**
```powershell
$body = '{"fixture_id": 1379137}'
Invoke-WebRequest -Uri http://localhost:8000/fixtures -Method POST -ContentType "application/json" -Body $body -OutFile match_report.md
```

**Linux/Mac (curl):**
```bash
curl -X POST http://localhost:8000/fixtures \
  -H "Content-Type: application/json" \
  -d '{"fixture_id": 1379137}' \
  --output match_report.md
```

### Get Analysis (Messaging Endpoint)

**By Fixture ID:**
```powershell
$body = '{"fixture_id": 1379137, "analysis_type": "enhanced"}'
Invoke-RestMethod -Uri http://localhost:8000/msg/analyze -Method POST -ContentType "application/json" -Body $body
```

**From Saved MD File:**
```powershell
$body = '{"md_file_path": "output/match_1379137_20251224_154843.md", "analysis_type": "enhanced"}'
Invoke-RestMethod -Uri http://localhost:8000/msg/analyze -Method POST -ContentType "application/json" -Body $body
```

**Linux/Mac (curl):**
```bash
# By fixture ID
curl -X POST http://localhost:8000/msg/analyze \
  -H "Content-Type: application/json" \
  -d '{"fixture_id": 1379137, "analysis_type": "enhanced"}'

# From saved MD file
curl -X POST http://localhost:8000/msg/analyze \
  -H "Content-Type: application/json" \
  -d '{"md_file_path": "output/match_1379137_20251224_154843.md", "analysis_type": "enhanced"}'
```

### Get Team Stats

**Windows PowerShell:**
```powershell
$body = '{"fixture_id": 1379137}'
Invoke-RestMethod -Uri http://localhost:8000/msg/stats -Method POST -ContentType "application/json" -Body $body
```

## Caching System

The API uses intelligent caching to optimize performance:

- **Automatic Caching**: Predictions are cached after first generation
- **Fast Retrieval**: Cached responses return in <10ms (vs 30-60s for new generation)
- **Frontend-Ready**: Cached data is stored in frontend-ready JSON format
- **Cost Reduction**: OpenAI API calls only happen once per fixture per day

### Force Refresh Cache

To bypass cache and regenerate analysis:

**Windows PowerShell:**
```powershell
$body = '{"fixture_id": 1379137, "analysis_type": "enhanced"}'
Invoke-RestMethod -Uri "http://localhost:8000/msg/analyze?force_refresh=true" -Method POST -ContentType "application/json" -Body $body
```

## Morning Batch Predictions

Pre-generate predictions for today's games in the morning. Perfect for scheduled jobs (cron, Task Scheduler).

### Process Today's Premier League Games

**Windows PowerShell:**
```powershell
$body = '{"dates": ["today"], "league_ids": [39], "analysis_type": "enhanced", "skip_cached": true}'
$response = Invoke-RestMethod -Uri http://localhost:8000/batch/predict -Method POST -ContentType "application/json" -Body $body
Write-Host "Generated: $($response.generated) | Cached: $($response.cached) | Total: $($response.total_fixtures)"
```

### Process Multiple Leagues

**Windows PowerShell:**
```powershell
$body = '{"dates": ["today"], "league_ids": [39, 140, 135], "analysis_type": "enhanced"}'
$response = Invoke-RestMethod -Uri http://localhost:8000/batch/predict -Method POST -ContentType "application/json" -Body $body
```

### Cache Refresh Examples

Refresh single fixture:
```powershell
$body = '{"fixture_ids": [1379137], "analysis_type": "enhanced"}'
Invoke-RestMethod -Uri http://localhost:8000/cache/refresh -Method POST -ContentType "application/json" -Body $body
```

Refresh today's Premier League games:
```powershell
$body = '{"date": "today", "league_ids": [39], "analysis_type": "enhanced"}'
Invoke-RestMethod -Uri http://localhost:8000/cache/refresh -Method POST -ContentType "application/json" -Body $body
```

## Next Steps

- **[API Reference](API_REFERENCE.md)** - Complete endpoint documentation
- **[Bot Integration](BOT_INTEGRATION.md)** - Build WhatsApp/Telegram bots
- **[Response Formats](RESPONSE_FORMATS.md)** - Understand response structures

## Common Issues

### API Not Responding
- Check server is running: `curl http://localhost:8000/status`
- Verify port 8000 is not in use
- Check firewall settings

### Missing API Keys
- Ensure keys are set in `config.json` or environment variables
- Check key validity with API providers

### Analysis Fails
- Verify OpenAI API key is valid
- Check OpenAI account has credits
- See [Error Handling](ERROR_HANDLING.md) for details

