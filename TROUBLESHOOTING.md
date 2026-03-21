# Dual Bot System - Troubleshooting Guide

## 🔍 Diagnosing Issues

### Console Error Messages

#### Error: "TELEGRAM_BOT_TOKEN not configured in .env"
**Cause**: Missing or empty TELEGRAM_BOT_TOKEN
**Fix**:
1. Open `.env` file
2. Add: `TELEGRAM_BOT_TOKEN=<your_token>`
3. Get token from @BotFather on Telegram: `/newbot`
4. Restart: `Ctrl+C` then `node frontend/run_all_bots.js`

#### Error: "Cannot find module 'whatsapp-web.js'"
**Cause**: Node packages not installed
**Fix**:
```bash
cd frontend/whatsapp
npm install
cd ../..
node frontend/run_all_bots.js
```

#### Error: "ModuleNotFoundError: No module named 'telegram'"
**Cause**: Python telegram-bot not installed
**Fix**:
```bash
pip install python-telegram-bot>=20.0.0
node frontend/run_all_bots.js
```

#### Error: "ENOENT: no such file or directory..."
**Cause**: Missing directory structure
**Fix**:
```bash
# Create missing directories
mkdir -p frontend/whatsapp/memory
mkdir -p frontend/telegram/memory
mkdir -p cache/predictions/{EPL,LaLiga,SerieA,Bundesliga,Ligue1}
# Restart
node frontend/run_all_bots.js
```

---

## 🔌 WhatsApp Bot Issues

### WhatsApp: No QR Code Displaying

**Symptoms**: 
- No QR code appears in terminal
- Bot seems to hang or show "Waiting for QR..."

**Possible Causes**:
1. Browser automation not available
2. Port 3000 already in use
3. Session already exists

**Solutions**:

**Option 1: Already logged in (Best)**
- If you've used this bot before, the session is cached
- The bot should start without QR code
- This is normal! Just send a message

**Option 2: Reset session**
```bash
# Delete cached session
rm -rf frontend/whatsapp/.wwebjs_auth
rm -rf frontend/whatsapp/.wwebjs_cache

# Restart to get new QR
node frontend/run_all_bots.js
```

**Option 3: Install Chrome**
```bash
# Windows (if Chrome not installed)
# Download from: https://google.com/chrome

# Or use system Chrome:
# The bot should auto-detect it
```

### WhatsApp: Bot Connected But Not Receiving Messages

**Symptoms**:
- QR scanned successfully
- Bot shows "Ready"
- But doesn't respond to messages

**Solutions**:

1. **Verify WhatsApp linked device is active**:
   - Phone WhatsApp → Settings → Linked Devices
   - Check device is showing as connected
   - Close and reopen WhatsApp to refresh

2. **Check bot number setup**:
   - WhatsApp must be linked (not logged in as secondary device)
   - You can only link 4 devices max

3. **Test connectivity**:
   - Send message: "hi"
   - Check console for message event
   - If no event appears, device connection dropped

4. **Force reconnect**:
   ```bash
   # Stop bot
   Ctrl+C
   
   # Delete session
   rm -rf frontend/whatsapp/.wwebjs_auth
   
   # Restart
   node frontend/run_all_bots.js
   
   # Scan QR again
   ```

### WhatsApp: Memory Files Not Creating

**Symptoms**:
- Bot responds but doesn't remember user
- Always asks for plan selection
- `frontend/whatsapp/memory/` directory empty

**Cause**: Permission issue or directory deleted

**Fix**:
```bash
# Ensure memory directory exists
mkdir -p frontend/whatsapp/memory

# Check permissions
ls -la frontend/whatsapp/memory/

# Restart bot
node frontend/run_all_bots.js
```

---

## 🤖 Telegram Bot Issues

### Telegram: Bot Not Responding to /start

**Symptoms**:
- Bot exists (@BotFather created it)
- But doesn't respond to /start command
- No "Polling..." message in console

**Causes**:
1. TELEGRAM_BOT_TOKEN is wrong/incomplete
2. python-telegram-bot not installed
3. Network connectivity issue

**Solutions**:

1. **Verify token**:
   ```bash
   # Check .env has correct token
   grep TELEGRAM_BOT_TOKEN .env
   
   # Token should look like: 1234567890:ABCdef-ghijklmnop_qrstuv
   # If it's different, get correct one from @BotFather
   ```

2. **Reinstall package**:
   ```bash
   pip uninstall python-telegram-bot
   pip install python-telegram-bot>=20.0.0
   
   # Verify installation
   python -c "import telegram; print(telegram.__version__)"
   ```

3. **Check network**:
   ```bash
   # Try to ping Telegram servers
   ping api.telegram.org
   
   # Should respond (not timeout)
   ```

4. **View Telegram logs**:
   - Look at console output for errors
   - Should show: "TelegramBot: Polling..."
   - If shows error, paste it in logs

### Telegram: "Polling..." But No Response

**Symptoms**:
- Console shows "Polling..."
- Telegram bot exists
- But /start command doesn't work

**Cause**: Webhook or polling conflict

**Fix**:
```bash
# Reset Telegram bot webhook
curl https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook

# Then restart bot
Ctrl+C
node frontend/run_all_bots.js

# Should now respond
```

### Telegram: Memory Files Not Creating

**Symptoms**:
- Bot responds but forgets user state
- Always returns to INITIAL state
- `frontend/telegram/memory/` stays empty

**Fix**:
```bash
# Create memory directory
mkdir -p frontend/telegram/memory

# Check permissions
ls -la frontend/telegram/memory/

# Restart bot
node frontend/run_all_bots.js

# Send /start to create first memory file
```

---

## 📊 Predictions Not Loading

### Issue: "No predictions available right now"

**When Happens**: User sends "matches" but gets empty response

**Causes**:
1. Prediction files missing from cache
2. Wrong directory structure
3. JSON files have errors

**Debug Steps**:

1. **Check if directories exist**:
   ```bash
   ls -la cache/predictions/
   # Should show: EPL/ LaLiga/ SerieA/ Bundesliga/ Ligue1/
   ```

2. **Check if files exist**:
   ```bash
   ls cache/predictions/EPL/
   # Should show: 1379139.json, 1379139_enhanced.json, etc.
   ```

3. **Validate JSON files**:
   ```bash
   # Check JSON syntax
   python -m json.tool cache/predictions/EPL/1379139.json
   
   # Should output without errors
   # If error, JSON is corrupted
   ```

4. **Check file format**:
   ```bash
   # Should have this structure:
   cat cache/predictions/EPL/1379139.json | head
   
   # Should show:
   # {
   #   "fixture_id": 1379139,
   #   "data": {
   #     "match": "...",
   #     "probabilities": { "home": X, "draw": X, "away": X },
   #     ...
   ```

**Fix Steps**:

1. **Create missing directories**:
   ```bash
   mkdir -p cache/predictions/{EPL,LaLiga,SerieA,Bundesliga,Ligue1}
   ```

2. **Add sample prediction files**:
   ```bash
   # Create sample EPL prediction
   cat > cache/predictions/EPL/1379139.json << 'EOF'
   {
     "fixture_id": 1379139,
     "data": {
       "match": "Liverpool vs Chelsea",
       "probabilities": {"home": 65, "draw": 20, "away": 15},
       "summary": "Liverpool at home with strong form...",
       "top_bets": [
         {"bet": "Home Win", "odds": 1.55}
       ]
     }
   }
   EOF
   ```

3. **Create enhanced version**:
   ```bash
   cat > cache/predictions/EPL/1379139_enhanced.json << 'EOF'
   {
     "fixture_id": 1379139,
     "data": {
       "match": "Liverpool vs Chelsea",
       "probabilities": {"home": 65, "draw": 20, "away": 15},
       "summary": "Detailed analysis... Liverpool's recent form shows 3 wins in last 4...",
       "top_bets": [
         {"bet": "Home Win", "odds": 1.55},
         {"bet": "Over 2.5 Goals", "odds": 1.60},
         {"bet": "Both Teams to Score", "odds": 1.70}
       ]
     }
   }
   EOF
   ```

4. **Restart bots**:
   ```bash
   node frontend/run_all_bots.js
   ```

5. **Test predictions**:
   - Send "matches" to see if they load
   - Send "1379139" to see detailed analysis

---

## 🔗 Cross-Platform Links Not Working

### Issue: Links in Messages Are Wrong

**Symptoms**:
- WhatsApp shows wrong Telegram link
- Telegram shows wrong WhatsApp link
- Links don't open correct platform

**Cause**: TELEGRAM_LINK or WHATSAPP_LINK incorrectly configured

**Solutions**:

1. **Check .env values**:
   ```bash
   grep "TELEGRAM_LINK\|WHATSAPP_LINK" .env
   
   # Should show:
   # TELEGRAM_LINK=https://t.me/YourActualBotUsername
   # WHATSAPP_LINK=https://wa.me/254712345678
   ```

2. **Fix TELEGRAM_LINK**:
   - Find your actual bot username from @BotFather
   - Edit .env: `TELEGRAM_LINK=https://t.me/YourBotUsername`
   - Make sure it's exact (case-sensitive)

3. **Fix WHATSAPP_LINK**:
   - Get your WhatsApp number with country code
   - Edit .env: `WHATSAPP_LINK=https://wa.me/254712345678`
   - No spaces, no dashes in number

4. **Restart bots**:
   ```bash
   Ctrl+C
   node frontend/run_all_bots.js
   ```

5. **Test new links**:
   - Send "matches" to check new links
   - Links should now be correct

---

## ⏰ Subscription Expiry Issues

### Issue: Subscription Expires Immediately

**Symptoms**:
- User pays, subscription works for 1 minute
- Then expires and goes back to INITIAL state

**Cause**: Midnight EAT calculation is wrong

**Check System Time**:
```bash
# Check current time
date

# Should match your actual time zone
# System should be set to GMT/UTC for correct EAT calculation
```

**If Time is Wrong**:

On Windows:
```cmd
# Set to UTC
timedatectl set-timezone UTC
```

On Linux:
```bash
# Set to UTC
timedatectl set-timezone UTC
```

On Mac:
```bash
# Set timezone in System Preferences
# Or: sudo systemsetup -settimezone UTC
```

**If Still Wrong After Time Fix**:

Check the `get_midnight_eat()` function in both bots:

WhatsApp (`frontend/whatsapp/bot.js`):
```javascript
function getMidnightEAT() {
    const now = new Date();
    const eatTime = new Date(now.toLocaleString('en-US', { timeZone: 'Africa/Nairobi' }));
    const midnight = new Date(eatTime);
    midnight.setHours(23, 59, 59, 999);
    return midnight;
}
```

Telegram (`frontend/telegram/bot.py`):
```python
def get_midnight_eat():
    now = datetime.now()
    eat_now = now + timedelta(hours=3)
    midnight = eat_now.replace(hour=23, minute=59, second=59, microsecond=0)
    return midnight
```

---

## 🔐 State/Memory Issues

### Issue: User State Keeps Resetting

**Symptoms**:
- User was in PAYMENT_CONFIRMED state
- Next message: back to INITIAL
- Memory file not saving

**Causes**:
1. Memory directory not writable
2. JSON file corrupted
3. Permission issues

**Debug**:
```bash
# Check memory file exists
ls -la frontend/whatsapp/memory/254712345678.json

# Check file contents
cat frontend/whatsapp/memory/254712345678.json

# Should show: {"state": "payment_confirmed", ...}
```

**Fix**:

1. **Ensure directory exists and is writable**:
   ```bash
   mkdir -p frontend/whatsapp/memory
   chmod 755 frontend/whatsapp/memory
   ```

2. **Delete corrupted memory file**:
   ```bash
   rm frontend/whatsapp/memory/254712345678.json
   
   # User will restart from INITIAL
   # Send /start or "hi" to reinitialize
   ```

3. **Check file permissions**:
   ```bash
   # Should be readable/writable
   chmod 644 frontend/whatsapp/memory/*.json
   ```

---

## 💥 Both Bots Crash Together

### Symptoms**:
- Both bots start
- Both crash after few seconds
- Same error for both

**Most Common Causes**:
1. .env file missing or corrupted
2. Node/Python versions incompatible
3. Port conflicts

**Solutions**:

1. **Verify .env exists and is valid**:
   ```bash
   cat .env
   # Should show all variables (OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, etc.)
   ```

2. **Check Node.js version**:
   ```bash
   node -v
   # Should be v16 or higher
   # If lower: Update Node.js
   ```

3. **Check Python version**:
   ```bash
   python -v
   # Should be 3.9 or higher
   # If lower: Update Python
   ```

4. **Check for port conflicts**:
   ```bash
   # Find what's using ports
   lsof -i :3000  # WhatsApp
   lsof -i :5000  # Telegram (if configured)
   
   # Kill conflicting process
   kill <PID>
   ```

5. **View full error output**:
   ```bash
   # Run with verbose output
   DEBUG=* node frontend/run_all_bots.js
   ```

---

## 📋 Quick Diagnostic Checklist

Run these to troubleshoot:

```bash
# 1. Verify .env
echo "=== .env CONFIG ==="
grep -E "TELEGRAM|WHATSAPP|OPENAI" .env

# 2. Check Node.js
echo "=== NODE VERSION ==="
node -v
npm -v

# 3. Check Python
echo "=== PYTHON VERSION ==="
python -v
pip list | grep telegram

# 4. Check dependencies
echo "=== NODE PACKAGES ==="
npm list --depth=0 -g

# 5. Check directories
echo "=== DIRECTORIES ==="
ls -la frontend/whatsapp/
ls -la frontend/telegram/
ls -la cache/predictions/
ls -la frontend/whatsapp/memory/
ls -la frontend/telegram/memory/

# 6. Check main files
echo "=== MAIN FILES ==="
ls -la frontend/whatsapp/bot.js
ls -la frontend/telegram/bot.py
ls -la frontend/telegram/__main__.py
ls -la frontend/run_all_bots.js

# 7. Test imports
echo "=== IMPORTS ==="
python -c "import telegram; print('✓ python-telegram-bot')"
node -e "require('whatsapp-web.js'); console.log('✓ whatsapp-web.js')"
```

---

## 🆘 Still Having Issues?

**Steps to get help**:

1. **Collect debug info**:
   ```bash
   # Save full output
   node frontend/run_all_bots.js > bot_output.log 2>&1
   
   # Include last 50 lines
   tail -50 bot_output.log
   ```

2. **Share relevant files**:
   - `.env` (with tokens hidden)
   - Error message (full output)
   - Which bot fails (WhatsApp, Telegram, or both)

3. **Check these first**:
   - [ ] .env has all required variables
   - [ ] Node.js version is 16+
   - [ ] Python version is 3.9+
   - [ ] python-telegram-bot is installed
   - [ ] Memory directories exist
   - [ ] Prediction cache has files
   - [ ] No other bots using same ports

---

**Most issues are fixed by:**
1. Restarting: `Ctrl+C` then `node frontend/run_all_bots.js`
2. Clearing cache: `rm -rf frontend/*/.wwebjs_* && rm -rf frontend/*/memory/*`
3. Reinstalling: `npm install && pip install -r requirements.txt`
4. Checking .env: All variables filled in correctly

**Try these in order!** 🚀
