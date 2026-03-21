# ⚡ Quick Start Reference

## 🚀 Start Both Bots (ONE COMMAND)

```bash
node frontend/run_all_bots.js
```

**Expected Output:**
```
✓ WhatsApp Bot: Shows QR code → Scan with phone
✓ Telegram Bot: Shows "Polling..." message
```

## 🔧 Configuration (.env)

Required fields to fill in:

```env
TELEGRAM_BOT_TOKEN=XXX           # From @BotFather
TELEGRAM_LINK=https://t.me/YourBot
WHATSAPP_LINK=https://wa.me/254712345678
OPENAI_API_KEY=sk-xxx...         # Already set
```

## 📱 Test Messages

### WhatsApp
```
Message          Response
─────────────────────────────
hi               Greeting + Telegram link
1                Select Basic (EPL only)
2                Select Premium (All 5 leagues)  
verify           Confirm payment
matches          Show predictions
1379139          Match details
```

### Telegram
```
Message          Response
─────────────────────────────
/start           Greeting + WhatsApp link
1                Select Basic (EPL only)
2                Select Premium (All 5 leagues)
verify           Confirm payment
matches          Show predictions
1379139          Match details
```

## 💾 Setup Timeline

| Step | Command | Time |
|------|---------|------|
| 1. Config | Edit `.env` file | 2 min |
| 2. Install Node | `cd frontend/whatsapp && npm install` *(auto-installs Puppeteer Chrome binary)* | 1-2 min |
| 3. Install Python | `pip install -r requirements.txt` | 2 min |
| 4. Run Both | `node frontend/run_all_bots.js` | 10 sec |
| 5. QR Code | Scan QR on phone | 30 sec |
| 6. Test | Send "hi" on WhatsApp/Telegram | 1 min |

**Total: ~6-7 minutes**

## 🐛 Quick Fixes

| Issue | Fix |
|-------|-----|
| "TELEGRAM_BOT_TOKEN not configured" | Add token to `.env`, restart |
| WhatsApp QR not showing | Already have session? Delete `.wwebjs_auth/` |
| WhatsApp Chrome missing on server | Run `cd frontend/whatsapp && npm run install:browser` |
| Puppeteer cache EPERM/permission | Set `PUPPETEER_CACHE_DIR=frontend/whatsapp/.cache/puppeteer` and rerun install |
| Telegram not responding | Check token is correct, restart |
| Predictions not found | Check `cache/predictions/{league}/` has JSON files |
| Cross-links wrong | Fix TELEGRAM_LINK and WHATSAPP_LINK in `.env` |

## 📊 File Structure

```
Your Project/
├── .env                          ← EDIT THIS (add Telegram info)
├── requirements.txt              ← pip install this
├── frontend/
│   ├── run_all_bots.js          ← RUN THIS
│   ├── whatsapp/
│   │   ├── bot.js               (WhatsApp logic)
│   │   ├── package.json
│   │   ├── node_modules/
│   │   └── memory/              (user sessions)
│   └── telegram/
│       ├── __main__.py          (Telegram launcher)
│       ├── bot.py               (Telegram logic)
│       └── memory/              (user sessions)
└── cache/predictions/
    ├── EPL/                     (your predictions)
    ├── LaLiga/
    ├── SerieA/
    ├── Bundesliga/
    └── Ligue1/
```

## 🎯 What Happens When Both Run

```
┌─────────────────────────────────────┐
│  User sends WhatsApp message        │
└──────────────┬──────────────────────┘
               │
        ┌──────▼──────┐
        │ WhatsApp Bot │
        │  (Node.js)   │
        └──────┬───────┘
               │
    ┌──────────┴────────────┐
    │                       │
    ▼                       ▼
[Check State]         [Get Predictions]
[Check Tier]          [From cache]
[Check Expiry]        [Filter by tier]
    │                       │
    └──────────┬────────────┘
               │
        ┌──────▼──────┐
        │   Response  │
        │ (+ Telegram │
        │   link)     │
        └─────────────┘

Same flow for Telegram → WhatsApp link
```

## 🔐 Subscription System

```
BASIC (Tier 1)
├─ Price: KSH 10
├─ Leagues: EPL only
└─ Expires: Midnight EAT (UTC+3)

PREMIUM (Tier 2)
├─ Price: KSH 30
├─ Leagues: EPL + LaLiga + SerieA + Bundesliga + Ligue1
└─ Expires: Midnight EAT (UTC+3)
```

## 📍 Key Directories

| Dir | Purpose |
|-----|---------|
| `frontend/whatsapp/memory/` | Stores WhatsApp user data |
| `frontend/telegram/memory/` | Stores Telegram user data |
| `cache/predictions/EPL/` | EPL match predictions |
| `cache/predictions/LaLiga/` | LaLiga predictions |
| etc. | Same for other leagues |

## ✓ Success Indicators

- [ ] Both bots running (console shows both messages)
- [ ] WhatsApp shows QR code
- [ ] Telegram shows "Polling..." 
- [ ] You can scan WhatsApp QR
- [ ] Telegram responds to /start
- [ ] Both show cross-platform links
- [ ] Messages include correct Telegram link
- [ ] Messages include correct WhatsApp link

## 🚨 Emergency Shutdown

```bash
Ctrl+C    # Gracefully stops both bots
```

Both bots will:
1. Stop receiving messages
2. Clean up connections
3. Exit within 3 seconds

Then you can:
- Fix `.env` and restart
- Debug issues
- Check logs

---

**Ready to start?** → `node frontend/run_all_bots.js`
