# Football Analysis API Documentation

Welcome to the Football Analysis API documentation. This API provides football match data, predictions, and analysis optimized for both file-based workflows and messaging applications.

## Quick Navigation

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes
- **[API Reference](API_REFERENCE.md)** - Complete endpoint documentation
- **[Bot Integration Guide](BOT_INTEGRATION.md)** - WhatsApp/Telegram integration examples
- **[Response Formats](RESPONSE_FORMATS.md)** - Response structure documentation
- **[Error Handling](ERROR_HANDLING.md)** - Error codes and troubleshooting
- **[Endpoint Comparison](ENDPOINT_COMPARISON.md)** - When to use MD vs messaging endpoints

## API Overview

This API provides two types of endpoints:

### 1. MD File Endpoints
These endpoints generate and return Markdown files containing match data and analysis:
- `/fixtures` - Generate match report MD files
- `/predict` - Generate analysis MD files
- `/analyze` - Complete workflow (fetch + analyze) returning MD file
- `/batch` - Batch process multiple fixtures, returns MD file paths

**Use these when:**
- You need to store match data as files
- You want full detailed reports
- You're building a file-based workflow

### 2. Messaging Endpoints
These endpoints return clean, minimal JSON optimized for bots:
- `/msg/fixtures` - Get fixtures in clean JSON (1-5 KB)
- `/msg/analyze` - Get predictions in clean JSON (1-2 KB)
- `/msg/stats` - Get team stats in clean JSON (< 1 KB)

**Use these when:**
- Building WhatsApp/Telegram bots
- Need fast, lightweight responses
- Want structured data without parsing

## Features

- ✅ Real-time match data from API-Football
- ✅ AI-powered predictions using OpenAI GPT-4
- ✅ Weather and news data via Serper
- ✅ Optimized responses for messaging apps
- ✅ Comprehensive error handling
- ✅ Type-safe responses with Pydantic models

## Getting Started

1. **Read the [Quick Start Guide](QUICK_START.md)** for setup instructions
2. **Check the [API Reference](API_REFERENCE.md)** for endpoint details
3. **See [Bot Integration](BOT_INTEGRATION.md)** for WhatsApp/Telegram examples

## Support

For issues or questions:
- Check [Error Handling](ERROR_HANDLING.md) for common problems
- Review [API Reference](API_REFERENCE.md) for endpoint details
- See [Endpoint Comparison](ENDPOINT_COMPARISON.md) to choose the right endpoint


