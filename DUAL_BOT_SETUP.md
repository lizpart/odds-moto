# Dual Bot Setup Guide (WhatsApp + Telegram)

This guide walks you through setting up and running both WhatsApp and Telegram bots simultaneously with shared subscription logic and league-based predictions.

## 📋 Prerequisites

- Node.js 16+ (for WhatsApp bot)
- Python 3.9+ (for Telegram bot)
- Telegram bot token (get from @BotFather)
- WhatsApp account (for QR code auth)

## 🚀 Quick Start (5 minutes)

### 1. **Configure Environment Variables**

Edit `.env` file with your credentials:

```env
# Required: OpenAI API Key (should already be set)
OPENAI_API_KEY=sk-proj-xxx...

# Required: Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_token_from_botfather

# Required: Cross-platform Links
TELEGRAM_LINK=https://t.me/YourBotUsername
WHATSAPP_LINK=https://wa.me/254712345678

# Optional: Backend API
BACKEND_API=http://localhost:8000
```

### 2. **Install Dependencies**

```bash
# Install Node.js dependencies for WhatsApp bot
cd frontend/whatsapp
npm install

# Back to root
cd ../..

# Install Python dependencies
pip install -r requirements.txt
# Or if using venv:
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. **Start Both Bots**

```bash
# From project root
node frontend/run_all_bots.js
```

This will:
- Launch WhatsApp bot (will show QR code in terminal)
- Launch Telegram bot (will show "polling..." message)
- Auto-restart on crash
- Gracefully shutdown on Ctrl+C

## 📱 WhatsApp Bot Setup

### First Time: QR Code Authentication

1. Run: `node frontend/run_all_bots.js`
2. WhatsApp bot will display a QR code in the terminal
3. Open WhatsApp on your phone
4. Go to **Settings → Linked Devices → Link a Device**
5. Scan the QR code with your phone camera
6. WhatsApp bot will confirm connection

**Note:** Session is cached in `.wwebjs_auth/` - you only need to scan QR once.

### Testing WhatsApp Bot

Send these messages in WhatsApp to your bot number:

| Message | Response |
|---------|----------|
| `hi` | Greeting with Telegram link |
| `1` | Select Basic plan (KSH 10, EPL only) |
| `2` | Select Premium plan (KSH 30, All 5 leagues) |
| `verify` | Confirm payment |
| `matches` | List available predictions |
| `1379139` | Get detailed match analysis |

## 🤖 Telegram Bot Setup

### Get Bot Token from @BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/start`
3. Send `/newbot`
4. Follow prompts:
   - Bot name: e.g., "Football Predictions Bot"
   - Bot username: e.g., "FootballPredictionBot"
5. Copy the token and paste into `.env` as `TELEGRAM_BOT_TOKEN`

### Testing Telegram Bot

1. Find your bot: `https://t.me/YourBotUsername`
2. Send `/start`
3. Send these messages:

| Message | Response |
|---------|----------|
| `/start` | Greeting with WhatsApp link |
| `1` | Select Basic plan (KSH 10, EPL only) |
| `2` | Select Premium plan (KSH 30, All 5 leagues) |
| `verify` | Confirm payment |
| `matches` | List available predictions |
| `1379139` | Get detailed match analysis |

## 🔗 Cross-Platform Integration

### WhatsApp → Telegram
All WhatsApp prediction messages include:
```
📱 *Also on Telegram:* https://t.me/YourBotUsername
```
Users can tap to switch to Telegram bot.

### Telegram → WhatsApp
All Telegram prediction messages include:
```
📱 *Also on WhatsApp:* https://wa.me/254712345678
```
Users can tap to switch to WhatsApp bot.

## 💾 Subscription System

### Tier System (Shared across platforms)

| Tier | Name | Price | Leagues |
|------|------|-------|---------|
| 1 | Basic | KSH 10 | EPL |
| 2 | Premium | KSH 30 | EPL, LaLiga, SerieA, Bundesliga, Ligue1 |

### Subscription Expiry

- **Expires**: Daily at **midnight EAT (UTC+3)**
- **Reset**: User must purchase new subscription next day
- **State**: Stored separately per platform (WhatsApp user and Telegram user are different)

### User Memory Files

```
frontend/
├── whatsapp/memory/
│   ├── 254712345678.json    # WhatsApp user memory
│   └── 254798765432.json
└── telegram/memory/
    ├── 123456789.json       # Telegram user memory (numeric ID)
    └── 987654321.json
```

Each file contains:
```json
{
  "state": "payment_confirmed",
  "tier": 2,
  "amount": 30,
  "subscription_expires_at": "2025-01-15T23:59:59",
  "created_at": "2025-01-14T15:30:00",
  "updated_at": "2025-01-14T15:30:00"
}
```

## 📊 Predictions Cache Structure

```
cache/predictions/
├── EPL/
│   ├── 1379139.json           # Standard prediction
│   ├── 1379139_enhanced.json  # Detailed analysis
│   └── ...
├── LaLiga/
│   └── sample_fixtures.json
├── SerieA/
├── Bundesliga/
└── Ligue1/
```

Each prediction file contains:
```json
{
  "fixture_id": 1379139,
  "data": {
    "match": "Liverpool vs Chelsea",
    "probabilities": {
      "home": 65,
      "draw": 20,
      "away": 15
    },
    "summary": "Analysis text...",
    "top_bets": [
      { "bet": "Home Win", "odds": 1.55 }
    ]
  }
}
```

## 🐛 Troubleshooting

### WhatsApp Bot Issues

**Problem**: QR code not displaying
- **Solution**: Check Chrome/Chromium is installed (`google-chrome --version`)
- **Fallback**: Run with `PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true`

**Problem**: Bot not receiving messages
- **Solution**: 
  1. Verify WhatsApp is logged in on phone
  2. Check bot number has received test message
  3. Restart: `Ctrl+C` then `node frontend/run_all_bots.js`

**Problem**: Session expired
- **Solution**: 
  1. Delete `.wwebjs_auth/` folder
  2. Restart bot to get new QR code
  3. Scan QR again from phone

### Telegram Bot Issues

**Problem**: Telegram bot not responding
- **Solution**:
  1. Verify `TELEGRAM_BOT_TOKEN` in `.env` is correct
  2. Check bot polling status in console (should say "Polling...")
  3. Restart: `Ctrl+C` then `node frontend/run_all_bots.js`

**Problem**: ImportError for python-telegram-bot
- **Solution**:
  ```bash
  pip install python-telegram-bot>=20.0.0
  ```

**Problem**: "TELEGRAM_BOT_TOKEN not configured"
- **Solution**: 
  1. Add `TELEGRAM_BOT_TOKEN=` to `.env`
  2. Restart bots
  3. Check console for error

### Shared Issues

**Problem**: Predictions not showing
- **Cause**: Cache directory empty
- **Solution**: 
  1. Verify `cache/predictions/{league}/` directories exist
  2. Add sample JSON files to test directories
  3. Check file permissions

**Problem**: Cross-platform links not working
- **Cause**: Wrong TELEGRAM_LINK or WHATSAPP_LINK in `.env`
- **Solution**:
  ```env
  TELEGRAM_LINK=https://t.me/YourActualBotUsername
  WHATSAPP_LINK=https://wa.me/254712345678  # include country code
  ```

**Problem**: Both bots crash together
- **Cause**: Usually missing environment variable or crashed dependency
- **Solution**:
  1. Check `.env` file is complete
  2. Look at error message in console
  3. Run `npm list` in frontend/whatsapp to verify Node packages
  4. Run `pip list | grep telegram` to verify Python package

## 📈 Monitoring

### Console Output Format

```
============================================================
🚀 FOOTBALL BOT MULTI-LAUNCHER
============================================================

🤖 WhatsApp Bot
   Status: Initializing...
   📱 Scan this QR code with your phone:

   [QR CODE DISPLAY]

   ✓ Ready for incoming messages

🤖 Telegram Bot
   Status: Polling...
   🔄 Listening for messages from @YourBotUsername
   
🎯 Both bots running (PID: 1234, 5678)
Press Ctrl+C to shutdown gracefully
```

### Checking Bot Health

Run in separate terminal:

```bash
# Check WhatsApp session
ls -la frontend/whatsapp/.wwebjs_auth/

# Check memory files
ls -la frontend/whatsapp/memory/
ls -la frontend/telegram/memory/

# Check if processes running
ps aux | grep "node\|python" | grep "bot"
```

## 🔄 Daily Operations

### Morning (after midnight EAT)

Subscriptions automatically reset at midnight. Users need to:
1. Send plan selection again (1 or 2)
2. Send `verify` to confirm payment
3. Send `matches` to see predictions

### Monitoring

Check console for:
- ✓ "Listening for incoming messages" (WhatsApp)
- ✓ "Polling..." (Telegram)
- ✓ Message processing logs

### Graceful Shutdown

```bash
# Press Ctrl+C in terminal running bots
# Bots will cleanup and exit within 3 seconds
```

## 📝 File Reference

| File | Purpose |
|------|---------|
| `frontend/run_all_bots.js` | Multi-bot orchestrator |
| `frontend/whatsapp/bot.js` | WhatsApp bot logic |
| `frontend/telegram/__main__.py` | Telegram bot launcher |
| `frontend/telegram/bot.py` | Telegram bot logic |
| `.env` | Configuration (credentials) |
| `cache/predictions/` | Prediction data cache |
| `frontend/whatsapp/memory/` | WhatsApp user sessions |
| `frontend/telegram/memory/` | Telegram user sessions |

## ✅ Verification Checklist

- [ ] `.env` has TELEGRAM_BOT_TOKEN
- [ ] `.env` has TELEGRAM_LINK (correct bot username)
- [ ] `.env` has WHATSAPP_LINK (correct phone)
- [ ] `npm install` completed in frontend/whatsapp
- [ ] `pip install -r requirements.txt` completed
- [ ] WhatsApp QR code scanned from phone
- [ ] WhatsApp bot receives test message
- [ ] Telegram bot responds to /start
- [ ] Both bots show cross-platform links
- [ ] Predictions load from cache directories

## 🎯 Next Steps

1. Complete `.env` configuration
2. Run `node frontend/run_all_bots.js`
3. Test WhatsApp bot (scan QR, send "hi")
4. Test Telegram bot (send /start)
5. Verify both show cross-platform links
6. Test subscription tiers (1 for Basic, 2 for Premium)
7. Monitor console for errors

## 📞 Support

For issues:
1. Check console output for error messages
2. Verify `.env` variables are correct
3. Ensure both `/wwebjs_auth/` and memory directories exist
4. Check that `cache/predictions/` has data

Happy predicting! 🎉
