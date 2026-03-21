# Response Formats

Detailed documentation of all API response structures.

## Frontend-Ready JSON

All messaging endpoints (`/msg/*`) return **frontend-ready JSON** responses:
- ✅ Clean, minimal structure (1-5 KB)
- ✅ No nested complexity
- ✅ Directly consumable by frontend frameworks (React, Vue, Angular)
- ✅ Perfect for WhatsApp/Telegram bots
- ✅ Ready for mobile apps
- ✅ No parsing or transformation needed

## Messaging Endpoints

### `/msg/fixtures` Response

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

**Field Descriptions:**
- `success` (boolean): Request success status
- `date` (string): Date of fixtures (YYYY-MM-DD)
- `count` (integer): Number of fixtures returned
- `fixtures` (array): List of fixture objects
  - `id` (integer): Fixture ID
  - `match` (string): Match description
  - `home_team` (string): Home team name
  - `away_team` (string): Away team name
  - `time` (string): Match time (HH:MM)
  - `date` (string): Match date (YYYY-MM-DD)
  - `league` (string): League name
  - `status` (string): Match status (NS, LIVE, FT, HT, etc.)

**Status Codes:**
- `NS` - Not Started
- `LIVE` - Live
- `FT` - Full Time
- `HT` - Half Time
- `CANC` - Cancelled
- `POST` - Postponed

---

### `/msg/analyze` Response

**Note:** This response format is also used for cached predictions. Cached responses are stored in this exact format for instant frontend consumption.

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
    },
    {
      "bet": "Both Teams to Score - Yes",
      "odds": 1.85
    }
  ],
  "summary": "Arsenal has strong home form...",
  "reasoning": "Detailed analysis with team insights..."
}
```

**Field Descriptions:**
- `success` (boolean): Request success status
- `fixture_id` (integer): Fixture ID
- `match` (string): Match description
- `probabilities` (object): Win probabilities
  - `home` (integer): Home win probability (0-100)
  - `draw` (integer): Draw probability (0-100)
  - `away` (integer): Away win probability (0-100)
  - Note: Probabilities sum to 100
- `top_bets` (array): Top betting recommendations
  - `bet` (string): Bet description
  - `odds` (float): Betting odds
- `summary` (string): Brief analysis summary (200 chars)
- `reasoning` (string): Detailed reasoning (500 chars)

**Caching:** Responses are automatically cached. Subsequent requests return the same format instantly (<10ms).

---

### `/msg/stats` Response

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

**Field Descriptions:**
- `success` (boolean): Request success status
- `home_team` (object): Home team statistics
- `away_team` (object): Away team statistics

**Team Stats Fields:**
- `team` (string): Team name
- `position` (integer|null): League position
- `form` (string): Recent form (W=Win, D=Draw, L=Loss)
- `goals_scored` (integer): Total goals scored
- `goals_conceded` (integer): Total goals conceded
- `wins` (integer): Number of wins
- `draws` (integer): Number of draws
- `losses` (integer): Number of losses

---

## MD File Endpoints

### `/fixtures` Response

**Content-Type:** `text/markdown`

Returns MD file content directly. File contains:
- Match details
- Team information
- Statistics
- Weather data
- News updates

### `/predict` Response

**Content-Type:** `text/markdown`

Returns analysis MD file content with:
- Win probabilities
- Betting recommendations
- Detailed reasoning
- Match insights

### `/analyze` Response

**Content-Type:** `text/markdown`

Returns complete analysis MD file (same as `/predict` but includes data fetching).

### `/batch` Response

```json
{
  "success": true,
  "message": "Processed 10 fixtures for 2025-12-24",
  "date": "2025-12-24",
  "total_fixtures": 10,
  "processed_fixtures": 10,
  "md_files": [
    "output/match_1379137_20251224_154843.md",
    "output/match_1379143_20251224_154827.md"
  ],
  "analysis_files": [
    "output/match_1379137_20251224_154843_analysis.txt"
  ],
  "errors": []
}
```

---

### `/batch/predict` Response

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
    39: {
      "fixtures": 10,
      "generated": 3,
      "cached": 7
    },
    140: {
      "fixtures": 10,
      "generated": 2,
      "cached": 8
    }
  },
  "processing_time_seconds": 125.5
}
```

**Field Descriptions:**
- `success` (boolean): Request success status
- `total_fixtures` (integer): Total fixtures found
- `processed` (integer): Fixtures processed (generated or skipped)
- `generated` (integer): New analyses generated
- `cached` (integer): Fixtures that were already cached
- `errors` (array): List of error messages
- `by_date` (object): Breakdown by date
  - Key: Date string (YYYY-MM-DD)
  - Value: Object with `fixtures`, `generated`, `cached`, `errors`
- `by_league` (object): Breakdown by league ID
  - Key: League ID (integer)
  - Value: Object with `fixtures`, `generated`, `cached`
- `processing_time_seconds` (float): Total processing time

---

### `/cache/refresh` Response

```json
{
  "success": true,
  "refreshed_count": 5,
  "errors": [],
  "by_fixture": {
    1379137: "refreshed",
    1379145: "refreshed",
    1379150: "error: No MD file found"
  },
  "processing_time_seconds": 45.2
}
```

**Field Descriptions:**
- `success` (boolean): Request success status
- `refreshed_count` (integer): Number of fixtures refreshed
- `errors` (array): List of errors encountered
- `by_fixture` (object): Status per fixture
  - Key: Fixture ID (integer)
  - Value: Status string ("refreshed" or "error: ...")
- `processing_time_seconds` (float): Total processing time

---

### `/cache/invalidate` Response

```json
{
  "success": true,
  "invalidated_count": 10,
  "errors": []
}
```

**Field Descriptions:**
- `success` (boolean): Request success status
- `invalidated_count` (integer): Number of cache entries deleted
- `errors` (array): List of errors encountered

---

## Cached Response Format

Cached predictions are stored in the exact same format as `/msg/analyze` responses (MessagingAnalysisResponse). This ensures:

- ✅ **Frontend-Ready**: Cached data is immediately consumable
- ✅ **No Transformation**: Direct return from cache, no parsing needed
- ✅ **Consistent Format**: Same structure whether cached or fresh
- ✅ **Fast Retrieval**: <10ms response time

**Cache File Structure:**
```json
{
  "fixture_id": 1379137,
  "analysis_type": "enhanced",
  "cached_at": "2025-12-24T08:00:00Z",
  "match_date": "2025-12-24",
  "data": {
    "success": true,
    "fixture_id": 1379137,
    "match": "Arsenal vs Chelsea",
    "probabilities": {"home": 45, "draw": 28, "away": 27},
    "top_bets": [...],
    "summary": "...",
    "reasoning": "..."
  }
}
```

The `data` field contains the frontend-ready JSON that matches `/msg/analyze` response format.

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

**Common Errors:**
- `"Fixture not found"` - Invalid fixture ID
- `"MD file not generated"` - File generation failed
- `"OpenAI API key not configured"` - Missing API key
- `"Failed to fetch fixtures"` - API-Football error

---

## Response Sizes

**Messaging Endpoints:**
- `/msg/fixtures`: 1-5 KB (depends on fixture count)
- `/msg/analyze`: 1-2 KB
- `/msg/stats`: < 1 KB

**MD File Endpoints:**
- `/fixtures`: 10-50 KB (MD file size)
- `/predict`: 5-20 KB (analysis file size)
- `/analyze`: 5-20 KB (analysis file size)

---

## Data Types

- **Strings**: All text fields
- **Integers**: IDs, counts, probabilities, positions
- **Floats**: Odds, statistics
- **Booleans**: Success flags
- **Arrays**: Lists of objects
- **Objects**: Nested data structures
- **null**: Optional fields that may be null

---

## Next Steps

- **[API Reference](API_REFERENCE.md)** - Complete endpoint docs
- **[Bot Integration](BOT_INTEGRATION.md)** - Integration examples
- **[Error Handling](ERROR_HANDLING.md)** - Error codes

