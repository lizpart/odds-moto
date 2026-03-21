# WhatsApp Web.js Bot Setup Guide

## Overview

The football predictions bot uses **whatsapp-web.js** (Selenium-based) instead of Meta's WhatsApp Business API. This approach:
- ✅ Requires NO API approval from Meta
- ✅ Authenticates via QR code (like your phone)
- ✅ Uses real WhatsApp session
- ✅ Can be deployed immediately

## Current Status

### ✅ Completed
1. Chrome automation setup with Selenium
2. QR code authentication flow
3. Session persistence (persistent Chrome profile)
4. WhatsApp Web connection
5. Message handler skeleton

### 🔄 In Progress
1. Message listening implementation
2. Integration with existing payment system

### ⏳ Planned
1. Full message receiving/sending via Selenium
2. Production-grade message listener (using whatsapp-web.js NPM library)
3. Webhook integration for auto-responses

## Requirements

### System Requirements
- **OS**: Windows, macOS, or Linux
- **Chrome/Chromium**: Must be installed ([Download Chrome](https://www.google.com/chrome))
- **Python**: 3.9+ with pip

### Python Dependencies
```bash
pip install selenium>=4.0.0 webdriver-manager>=3.8.6 qrcode>=7.4.0 pillow>=10.0.0
```

All dependencies are in `frontend/requirements.txt`:
```bash
cd frontend
pip install -r requirements.txt
```

## Running the Bot

### Option 1: WhatsApp Only
```bash
cd frontend
python run.py --service whatsapp
```

Expected output:
```
2025-12-30 00:12:16,300 - __main__ - INFO - Starting WhatsApp bot with whatsapp-web.js...
2025-12-30 00:12:23,716 - frontend.whatsapp.webjs_bot - INFO - Chrome browser initialized successfully
2025-12-30 00:12:24,997 - frontend.whatsapp.webjs_bot - INFO - 📱 Please open WhatsApp on your phone and scan the QR code shown in the browser
```

A Chrome window will open with WhatsApp Web. **Scan the QR code with your phone.**

### Option 2: Both Bots (WhatsApp + Telegram)
```bash
cd frontend
python run.py --service both
```

### Option 3: Telegram Only
```bash
cd frontend
python run.py --service telegram
```

## Authentication Flow

### Step 1: Launch Bot
```bash
python run.py --service whatsapp
```

### Step 2: See QR Code
Chrome browser opens automatically with WhatsApp Web:
- If you see the QR code → Scan it with your phone (Step 3)
- If you see chats list → Already authenticated, bot starts listening (Step 4)

### Step 3: Scan QR Code
1. Open **WhatsApp** on your phone
2. Go to **Settings > Linked Devices** (or **Settings > WhatsApp Web/Desktop**)
3. Tap **Link a device**
4. **Scan the QR code** shown in the Chrome window
5. Wait for "✅ Successfully authenticated!" message

### Step 4: Bot Ready
Once authenticated:
```
============================================================
✅ WhatsApp Web Bot is running!
============================================================
Ready to receive messages...
Messages will appear in the WhatsApp Web interface
Type 'quit' to stop the bot
============================================================
```

Bot is now listening for messages from WhatsApp Web!

## File Structure

```
frontend/
├── whatsapp/
│   ├── webjs_bot.py          # Main bot (Selenium + QR auth)
│   ├── bot.py                # Message handlers (handle_start, handle_choice, etc)
│   ├── server.py             # Legacy webhook server (not used)
│   └── __init__.py
├── run.py                    # Entry point (--service whatsapp)
├── config.py                 # Configuration validation
└── requirements.txt          # Dependencies
```

### Key Files

**`frontend/whatsapp/webjs_bot.py`** (Main bot)
- `WhatsAppWebBot` class: Handles Chrome automation
- `setup_browser()`: Initializes Chrome with persistent profile
- `connect()`: Opens WhatsApp Web and waits for QR code
- `listen()`: Keeps browser alive and ready for messages
- `main()`: Entry point

**`frontend/whatsapp/bot.py`** (Message handlers)
- `WhatsAppBot` class: Processes incoming messages
- `process_message()`: Routes messages based on user state
- `handle_start()`: Greeting and initial state
- `handle_choice()`: Process user selection (1 or 2)
- `handle_verify_payment()`: Payment verification

**`frontend/run.py`** (Launcher)
- `start_whatsapp_bot()`: Launches webjs_bot
- `start_telegram_bot()`: Launches Telegram bot
- `start_both()`: Runs both in separate processes

## Environment Configuration

### `.env` File
```bash
# WhatsApp Configuration
WHATSAPP_SESSION_DIR=./data/whatsapp_sessions

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_token_here

# Payment Configuration
PAYSTACK_SECRET_KEY=your_paystack_secret
PAYSTACK_PUBLIC_KEY=your_paystack_public

# Football API
FOOTBALL_API_BASE_URL=http://localhost:8000
```

### Session Directory
- **Location**: `frontend/data/whatsapp_sessions/`
- **Contains**: Chrome profile with WhatsApp session
- **Auto-created** when bot runs first time
- **Persisted** across bot restarts (no need to scan QR code again)

## Troubleshooting

### Chrome Crashes on Startup
**Error**: "Chrome failed to start: crashed"

**Solutions**:
1. **Kill existing Chrome processes**:
   ```bash
   # Windows PowerShell
   Get-Process chrome, chromedriver -ErrorAction SilentlyContinue | Stop-Process -Force
   ```

2. **Delete corrupted profile**:
   ```bash
   rm -r frontend/data/whatsapp_sessions/chrome_profile
   ```

3. **Reinstall ChromeDriver**:
   ```bash
   pip install --upgrade webdriver-manager
   ```

4. **Check Chrome installation**:
   ```
   Should be at: C:\Program Files\Google\Chrome\Application\chrome.exe
   ```

### QR Code Not Appearing
**Problem**: Chrome opens but no QR code

**Solutions**:
1. **Wait longer** (up to 30 seconds)
2. **Check internet connection** (WhatsApp Web needs internet)
3. **Clear Chrome profile**: `rm -r frontend/data/whatsapp_sessions/chrome_profile`
4. **Check Chrome version**: Run `python -c "from selenium import webdriver; print(webdriver.__version__)"`

### Bot Not Receiving Messages
**Current limitation**: Full message listening requires the actual `whatsapp-web.js` NPM library

**Current state**: Bot authenticates and keeps connection alive, but doesn't yet receive/send messages automatically

**Next steps**: 
- Use Puppeteer + whatsapp-web.js NPM package (better than Selenium)
- Or integrate with WhatsApp Cloud API for webhooks (requires Meta approval)

### Bot Hangs on "Waiting for QR code"
**Problem**: Stuck at "📱 Please open WhatsApp on your phone and scan the QR code shown in the browser"

**Solutions**:
1. **Check Chrome window is actually open** (may be behind other windows)
2. **Ensure phone has WhatsApp installed** with valid SIM/account
3. **Try manual QR scan**: Phone camera → Settings > Linked Devices → Scan
4. **Restart bot**: Kill process and run again

### Module Not Found Errors
```
ModuleNotFoundError: No module named 'selenium'
```

**Fix**:
```bash
# Activate venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\Activate.ps1  # Windows

# Install requirements
pip install -r frontend/requirements.txt
```

## Message Flow

### Current (Authentication Only)
```
Bot Launch
  ↓
Chrome Opens
  ↓
WhatsApp Web Loads
  ↓
QR Code Appears
  ↓
User Scans (phone)
  ↓
Session Authenticated
  ↓
Bot Running (waiting for messages)
```

### Planned (Full Integration)
```
Bot Launch
  ↓
Authentication (as above)
  ↓
Listen for Messages
  ↓
Route to Handler (handle_start, handle_choice, handle_verify)
  ↓
Get Response (predictions, payment links, etc)
  ↓
Send Message Back to User
  ↓
Update User State
  ↓
Ready for Next Message
```

## Architecture Notes

### Why whatsapp-web.js?
1. **No API keys needed** - Uses actual WhatsApp session
2. **Immediate deployment** - No Meta approval waiting
3. **Cost effective** - No Twilio/paid API charges
4. **Full control** - Access to all chat features

### Why Selenium?
1. **Cross-platform** - Works on Windows, macOS, Linux
2. **Simple setup** - No complex build process
3. **Debugging** - Can see what bot is doing
4. **Fallback** - Works if NPM package isn't available

### Limitations of Current Approach
1. **Message polling** - Not real-time (delays possible)
2. **Browser required** - Can't run headless (no `--headless` mode)
3. **Single session** - One Chrome window per bot instance
4. **Maintenance** - WhatsApp Web updates may break it

### Future: Production Approach
Consider upgrading to full whatsapp-web.js:
```javascript
// package.json (Node.js)
{
  "dependencies": {
    "whatsapp-web.js": "^1.23.0",
    "qrcode-terminal": "^0.12.0"
  }
}
```

This provides:
- ✅ Real message events
- ✅ Better reliability
- ✅ Headless support
- ✅ Production-ready stability

## Security Notes

⚠️ **Important**:
1. **Phone stays online** - Chrome window must stay open (or use headless after stability improvements)
2. **Session cookie stored** - In `data/whatsapp_sessions/` (keep secure)
3. **Consider VPS** - Run bot on always-on server for 24/7 availability
4. **Don't share session** - Each instance needs separate WhatsApp account

## Next Steps

1. **Verify bot authenticates** ✓ (Done - you see QR code)
2. **Implement message receiving** (Next - requires whatsapp-web.js NPM or webhook)
3. **Test message handlers** (After step 2)
4. **Deploy to production** (VPS or cloud)

## Support & Debugging

### Enable Debug Logging
Edit `run.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
```

### Check Logs
```bash
# WhatsApp bot logs
tail -f /path/to/bot.log

# Chrome/Selenium logs
# Available in browser console (F12 in Chrome)
```

### Test Setup Script
```bash
python -c "
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
print('✓ Selenium installed')
print('✓ Webdriver-manager installed')
print('✓ Chrome found at:', ChromeDriverManager().install())
"
```

## References

- [Whatsapp-web.js Documentation](https://docs.wwebjs.dev)
- [Selenium Documentation](https://selenium-python.readthedocs.io)
- [WebDriver Manager](https://github.com/SergeyPirogov/webdriver_manager)
- [WhatsApp Web Architecture](https://github.com/pedroslopez/whatsapp-web.js)

