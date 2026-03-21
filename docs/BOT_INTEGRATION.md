# Bot Integration Guide

Examples for integrating the Football Analysis API with WhatsApp and Telegram bots.

## Overview

The messaging endpoints (`/msg/*`) are optimized for bots:
- Small response sizes (1-5 KB)
- Clean JSON structure
- No parsing needed
- Fast response times

## WhatsApp Integration

### Example: Python with Flask

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
API_BASE = "http://localhost:8000"

def send_whatsapp_message(phone, message):
    """Send message via WhatsApp API"""
    # Your WhatsApp API integration here
    pass

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data.get('message', '').lower()
    phone = data.get('from')
    
    if message.startswith('fixtures'):
        # Get today's fixtures
        response = requests.post(
            f"{API_BASE}/msg/fixtures",
            json={"date": "today"}
        )
        fixtures_data = response.json()
        
        # Format message
        msg = "⚽ Today's Fixtures:\n\n"
        for f in fixtures_data['fixtures'][:10]:  # First 10
            msg += f"• {f['match']} @ {f['time']}\n"
            msg += f"  {f['league']} - {f['status']}\n\n"
        
        send_whatsapp_message(phone, msg)
        
    elif message.startswith('analyze'):
        # Extract fixture ID
        fixture_id = int(message.split()[1])
        
        # Get analysis
        response = requests.post(
            f"{API_BASE}/msg/analyze",
            json={"fixture_id": fixture_id}
        )
        analysis = response.json()
        
        # Format message
        msg = f"📊 {analysis['match']}\n\n"
        msg += f"Win Probability:\n"
        msg += f"Home: {analysis['probabilities']['home']}%\n"
        msg += f"Draw: {analysis['probabilities']['draw']}%\n"
        msg += f"Away: {analysis['probabilities']['away']}%\n\n"
        msg += "Top Bets:\n"
        for bet in analysis['top_bets'][:3]:
            msg += f"• {bet['bet']} @ {bet['odds']}\n"
        msg += f"\n{analysis['summary']}"
        
        send_whatsapp_message(phone, msg)
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=5000)
```

### Example: Node.js with Express

```javascript
const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

const API_BASE = 'http://localhost:8000';

app.post('/webhook', async (req, res) => {
  const message = req.body.message.toLowerCase();
  const phone = req.body.from;
  
  if (message.startsWith('fixtures')) {
    const response = await axios.post(`${API_BASE}/msg/fixtures`, {
      date: 'today'
    });
    
    const fixtures = response.data.fixtures;
    let msg = '⚽ Today\'s Fixtures:\n\n';
    
    fixtures.slice(0, 10).forEach(f => {
      msg += `• ${f.match} @ ${f.time}\n`;
      msg += `  ${f.league} - ${f.status}\n\n`;
    });
    
    sendWhatsAppMessage(phone, msg);
  }
  
  res.json({ status: 'ok' });
});

app.listen(5000);
```

---

## Telegram Integration

### Example: Python with python-telegram-bot

```python
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests

API_BASE = "http://localhost:8000"

async def fixtures(update: Update, context):
    """Get today's fixtures"""
    response = requests.post(
        f"{API_BASE}/msg/fixtures",
        json={"date": "today"}
    )
    fixtures_data = response.json()
    
    msg = "⚽ Today's Fixtures:\n\n"
    for f in fixtures_data['fixtures'][:10]:
        msg += f"• {f['match']} @ {f['time']}\n"
        msg += f"  {f['league']} - {f['status']}\n\n"
    
    await update.message.reply_text(msg)

async def analyze(update: Update, context):
    """Analyze a match"""
    if not context.args:
        await update.message.reply_text("Usage: /analyze <fixture_id>")
        return
    
    fixture_id = int(context.args[0])
    
    response = requests.post(
        f"{API_BASE}/msg/analyze",
        json={"fixture_id": fixture_id}
    )
    analysis = response.json()
    
    msg = f"📊 {analysis['match']}\n\n"
    msg += f"Win Probability:\n"
    msg += f"Home: {analysis['probabilities']['home']}%\n"
    msg += f"Draw: {analysis['probabilities']['draw']}%\n"
    msg += f"Away: {analysis['probabilities']['away']}%\n\n"
    msg += "Top Bets:\n"
    for bet in analysis['top_bets'][:3]:
        msg += f"• {bet['bet']} @ {bet['odds']}\n"
    msg += f"\n{analysis['summary']}"
    
    await update.message.reply_text(msg)

async def stats(update: Update, context):
    """Get team stats"""
    if not context.args:
        await update.message.reply_text("Usage: /stats <fixture_id>")
        return
    
    fixture_id = int(context.args[0])
    
    response = requests.post(
        f"{API_BASE}/msg/stats",
        json={"fixture_id": fixture_id}
    )
    stats_data = response.json()
    
    home = stats_data['home_team']
    away = stats_data['away_team']
    
    msg = f"📈 Team Stats\n\n"
    msg += f"{home['team']} (Position: {home['position']})\n"
    msg += f"Form: {home['form']}\n"
    msg += f"Goals: {home['goals_scored']}-{home['goals_conceded']}\n"
    msg += f"Record: {home['wins']}W {home['draws']}D {home['losses']}L\n\n"
    msg += f"{away['team']} (Position: {away['position']})\n"
    msg += f"Form: {away['form']}\n"
    msg += f"Goals: {away['goals_scored']}-{away['goals_conceded']}\n"
    msg += f"Record: {away['wins']}W {away['draws']}D {away['losses']}L"
    
    await update.message.reply_text(msg)

def main():
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    application.add_handler(CommandHandler("fixtures", fixtures))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("stats", stats))
    
    application.run_polling()

if __name__ == '__main__':
    main()
```

---

## Response Formatting Tips

### For WhatsApp
- Keep messages under 4096 characters
- Use emojis for visual appeal
- Format with simple text (no markdown)

### For Telegram
- Supports Markdown formatting
- Can send longer messages
- Use `*bold*`, `_italic_`, `[links](url)`

### Example Formatter

```python
def format_fixture_message(fixture):
    """Format fixture for messaging"""
    status_emoji = {
        "NS": "⏰",
        "LIVE": "🔴",
        "FT": "✅",
        "HT": "⏸️"
    }
    
    emoji = status_emoji.get(fixture['status'], "⚽")
    return f"{emoji} {fixture['match']}\n{fixture['time']} | {fixture['league']}"
```

---

## Error Handling

```python
def safe_api_call(endpoint, data):
    """Safe API call with error handling"""
    try:
        response = requests.post(
            f"{API_BASE}{endpoint}",
            json=data,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }
```

---

## Best Practices

1. **Cache Responses**: Cache fixture data for 5-10 minutes
2. **Handle Errors**: Always check `success` field
3. **Rate Limiting**: Respect API rate limits
4. **Timeout**: Set request timeouts (10-30 seconds)
5. **User Feedback**: Show loading messages for long operations

---

## Next Steps

- **[API Reference](API_REFERENCE.md)** - Complete endpoint docs
- **[Response Formats](RESPONSE_FORMATS.md)** - Response structures
- **[Error Handling](ERROR_HANDLING.md)** - Error codes


