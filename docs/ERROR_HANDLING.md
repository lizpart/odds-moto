# Error Handling Guide

Complete guide to handling errors in the Football Analysis API.

## Error Response Format

All endpoints return errors in this consistent format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

## HTTP Status Codes

### 400 Bad Request
Invalid request parameters or missing required fields.

**Examples:**
- Missing required parameter
- Invalid date format
- Invalid fixture ID

**Solution:**
- Check request body format
- Verify all required fields are present
- Validate parameter types

### 404 Not Found
Requested resource not found.

**Examples:**
- Fixture ID doesn't exist
- MD file not generated
- Team not found

**Solution:**
- Verify fixture ID is valid
- Check if data exists in API-Football
- Ensure MD file was generated successfully

### 500 Internal Server Error
Server-side error occurred.

**Examples:**
- API-Football connection failed
- OpenAI API error
- File system error

**Solution:**
- Check server logs
- Verify API keys are valid
- Check disk space for file operations

## Common Errors

### "Fixture not found"
**Cause:** Invalid or non-existent fixture ID.

**Solution:**
```python
# Verify fixture exists first
response = requests.get(f"{API_BASE}/fixtures", params={"id": fixture_id})
if response.status_code == 404:
    print("Fixture not found")
```

### "MD file not generated"
**Cause:** File generation failed during processing.

**Solution:**
- Check output directory permissions
- Verify disk space
- Check API-Football data availability

### "OpenAI API key not configured"
**Cause:** OpenAI API key missing or invalid.

**Solution:**
```bash
# Set in config.json
{
  "openai_api_key": "sk-..."
}

# Or environment variable
export OPENAI_API_KEY="sk-..."
```

### "Failed to fetch fixtures"
**Cause:** API-Football connection or rate limit issue.

**Solution:**
- Check API-Football status
- Verify API key is valid
- Check rate limits (30/min for free plan)
- Wait and retry

### "Analysis processing failed"
**Cause:** Analysis generation error.

**Solution:**
- Check OpenAI API key
- Verify OpenAI account has credits
- Check analysis file permissions

## Error Handling Examples

### Python

```python
import requests

def safe_api_call(endpoint, data):
    """Safe API call with error handling"""
    try:
        response = requests.post(
            f"{API_BASE}{endpoint}",
            json=data,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return result
        
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timeout"
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Connection error"
        }
    except requests.exceptions.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP error: {e.response.status_code}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

# Usage
result = safe_api_call("/msg/fixtures", {"date": "today"})
if not result["success"]:
    print(f"Error: {result['error']}")
else:
    print(f"Found {result['count']} fixtures")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

async function safeApiCall(endpoint, data) {
  try {
    const response = await axios.post(
      `${API_BASE}${endpoint}`,
      data,
      { timeout: 10000 }
    );
    
    if (!response.data.success) {
      return {
        success: false,
        error: response.data.error || 'Unknown error'
      };
    }
    
    return response.data;
  } catch (error) {
    if (error.response) {
      return {
        success: false,
        error: `HTTP ${error.response.status}: ${error.response.data.error}`
      };
    } else if (error.request) {
      return {
        success: false,
        error: 'No response from server'
      };
    } else {
      return {
        success: false,
        error: error.message
      };
    }
  }
}

// Usage
const result = await safeApiCall('/msg/fixtures', { date: 'today' });
if (!result.success) {
  console.error(`Error: ${result.error}`);
} else {
  console.log(`Found ${result.count} fixtures`);
}
```

## Retry Logic

For transient errors, implement retry logic:

```python
import time
from functools import wraps

def retry(max_attempts=3, delay=2):
    """Retry decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

@retry(max_attempts=3, delay=2)
def get_fixtures(date):
    response = requests.post(
        f"{API_BASE}/msg/fixtures",
        json={"date": date}
    )
    response.raise_for_status()
    return response.json()
```

## Validation

Always validate responses:

```python
def validate_fixtures_response(data):
    """Validate fixtures response"""
    if not isinstance(data, dict):
        return False
    if "success" not in data:
        return False
    if not data["success"]:
        return False
    if "fixtures" not in data:
        return False
    if not isinstance(data["fixtures"], list):
        return False
    return True

result = safe_api_call("/msg/fixtures", {"date": "today"})
if validate_fixtures_response(result):
    # Process fixtures
    pass
```

## Logging

Log errors for debugging:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_error(endpoint, error, context=None):
    """Log API errors"""
    logger.error(f"API Error - Endpoint: {endpoint}, Error: {error}")
    if context:
        logger.error(f"Context: {context}")

# Usage
result = safe_api_call("/msg/fixtures", {"date": "today"})
if not result["success"]:
    log_error("/msg/fixtures", result["error"], {"date": "today"})
```

## Best Practices

1. **Always Check Success**: Verify `success` field before processing
2. **Handle Timeouts**: Set appropriate timeout values
3. **Retry Transient Errors**: Implement retry for network errors
4. **Validate Responses**: Check response structure
5. **Log Errors**: Log for debugging and monitoring
6. **User-Friendly Messages**: Translate technical errors for users

## Troubleshooting

### API Not Responding
1. Check server is running: `curl http://localhost:8000/status`
2. Verify port 8000 is accessible
3. Check firewall settings

### Invalid Responses
1. Verify request format matches documentation
2. Check Content-Type header is `application/json`
3. Validate JSON structure

### Rate Limiting
1. Check API-Football rate limits (30/min free)
2. Implement request queuing
3. Cache responses when possible

---

## Next Steps

- **[API Reference](API_REFERENCE.md)** - Complete endpoint docs
- **[Response Formats](RESPONSE_FORMATS.md)** - Response structures
- **[Bot Integration](BOT_INTEGRATION.md)** - Integration examples


