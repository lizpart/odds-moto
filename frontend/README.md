# Football Predictions Frontend

WhatsApp and Telegram bot integration for the Football Analysis API with Paystack payment processing.

## 🎯 Overview

This frontend enables users to:
- Receive football match predictions via WhatsApp (primary) or Telegram
- Choose between 2 subscription tiers:
  - **Tier 1**: Specific league predictions (KSH 10)
  - **Tier 2**: All leagues predictions (KSH 30)
- Pay via M-Pesa through Paystack gateway using their **WhatsApp or Telegram phone number**
- Get instant predictions after payment verification

## 📚 Documentation

Start with these guides:
1. **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Complete setup and deployment
2. **[PHONE_NUMBER_HANDLING.md](PHONE_NUMBER_HANDLING.md)** - How phone numbers work in payments
3. **[.env.example](.env.example)** - Configuration template

## 📁 Project Structure

```
frontend/
├── __init__.py
├── config.py                 # Configuration management
├── .env.example             # Environment template
│
├── utils/
│   ├── __init__.py
│   ├── constants.py         # Message templates & constants
│   ├── message_formatter.py # Format responses
│   ├── state_manager.py     # User session management
│   └── api_client.py        # Football API client
│
├── whatsapp/
│   ├── __init__.py
│   ├── bot.py              # WhatsApp bot logic
│   └── server.py           # WhatsApp webhook server
│
├── telegram/
│   ├── __init__.py
│   ├── bot.py              # Telegram bot logic
│   └── server.py           # Telegram webhook server
│
└── payments/
    ├── __init__.py
    └── paystack_processor.py  # Paystack payment integration
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- Paystack account (for payments)
- WhatsApp account (using whatsapp-web.js library - no business account needed initially)
- Telegram account (for Telegram bot)
- Google Chrome/Chromium browser

### 2. Installation

```bash
# Clone and navigate to frontend directory
cd frontend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r ../requirements.txt
pip install python-telegram-bot python-dotenv
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 4. Run Servers

**WhatsApp Bot (Port 5000):**
```bash
python -m uvicorn whatsapp.server:app --reload --host 0.0.0.0 --port 5000
```

**Telegram Bot (Port 5001):**
```bash
python -m uvicorn telegram.server:app --reload --host 0.0.0.0 --port 5001
```

## 🔑 Configuration Guide

### Paystack Setup

1. **Create Account**: Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. **Get Keys**: Settings → Developer → API Keys
3. **Add to .env**:
   ```
   PAYSTACK_SECRET_KEY=sk_test_xxxx
   PAYSTACK_PUBLIC_KEY=pk_test_xxxx
   ```

### WhatsApp Setup

**Current Implementation (whatsapp-web.js):**

The bot uses the whatsapp-web.js library which works via browser automation:
- No official WhatsApp Business Account needed
- No API keys required
- Authenticates using QR code on first run

**Setup Instructions:**

```bash
# Create session directory for WhatsApp authentication
mkdir -p data/whatsapp_sessions

# Run bot with WhatsApp service
python run.py --service whatsapp

# On first run:
# 1. A QR code will be displayed
# 2. Scan with your WhatsApp phone
# 3. Bot will be authenticated and ready
```

**Configuration:**

```env
WHATSAPP_SESSION_DIR=./data/whatsapp_sessions
WHATSAPP_WEBHOOK_TOKEN=football_predictions_token
```

**Future: Twilio Integration**

Once your WhatsApp number is verified with Twilio, you can migrate to:
```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### Telegram Setup

1. **Create Bot**: Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send: `/newbot`
   - Follow instructions to create bot
   - Copy token

2. **Add to .env**:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABCDEFxxx
   TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
   ```

3. **Set Webhook** (after deploying):
   ```bash
   curl -X POST https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook \
     -H 'Content-Type: application/json' \
     -d '{"url": "https://your-domain.com/telegram/webhook"}'
   ```

## 💬 Communication Flow

### WhatsApp (Primary Channel)

```
User sends "Hi" 
    ↓
Bot sends greeting + help menu
    ↓
User replies "1" or "2"
    ↓
Bot confirms selection + M-Pesa amount
    ↓
M-Pesa prompt appears
    ↓
User completes payment
    ↓
Bot verifies payment
    ↓
Bot sends predictions
    ↓
Message includes Telegram link
```

### Telegram (Secondary)

- Provides free access to `/fixtures` and `/predict` commands
- Directs users to WhatsApp for paid predictions
- Shows Telegram link in all WhatsApp messages

## 📋 User States

The bot tracks user conversation state:

- `INITIAL` - First interaction
- `GREETING_SENT` - Greeting message shown
- `AWAITING_CHOICE` - Waiting for package selection (1 or 2)
- `CHOICE_RECEIVED` - User selected a package
- `PAYMENT_INITIATED` - Payment process started
- `PAYMENT_PENDING` - Awaiting payment confirmation
- `PAYMENT_CONFIRMED` - Payment verified
- `PAYMENT_FAILED` - Payment failed
- `PREDICTIONS_SENT` - Predictions delivered
- `SESSION_EXPIRED` - Session timeout

## 💳 Pricing

| Tier | Price | Content |
|------|-------|---------|
| 1 | KSH 10 | Specific league/tournament predictions |
| 2 | KSH 30 | All leagues and tournaments predictions |

## 📊 Payment Flow

1. **Initialize**: `POST /payments/initialize` → Get Paystack reference
2. **M-Pesa**: User completes M-Pesa payment
3. **Verify**: `POST /payments/verify/{reference}` → Check status
4. **Deliver**: Send predictions upon confirmation

## 🔄 API Endpoints

### WhatsApp Bot

- `GET /` - Bot info
- `GET /health` - Health check
- `GET /webhook` - Webhook verification (WhatsApp)
- `POST /webhook` - Receive WhatsApp messages
- `POST /send_message` - Send test message

### Telegram Bot

- `GET /` - Bot info
- `GET /health` - Health check
- `POST /webhook` - Receive Telegram updates
- `POST /send_message` - Send test message

## 🧪 Testing

### Test WhatsApp Webhook

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "1234567890",
            "body": "Hi"
          }]
        }
      }]
    }]
  }'
```

### Test Telegram Webhook

```bash
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "from": {
        "id": 123456,
        "username": "testuser"
      },
      "text": "/start"
    }
  }'
```

### Send Test Message via WhatsApp

```bash
curl -X POST http://localhost:5000/send_message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "1234567890",
    "message": "Test message"
  }'
```

### Send Test Message via Telegram

```bash
curl -X POST http://localhost:5001/send_message \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "123456",
    "text": "Test message"
  }'
```

## 🔐 Security

- Store API keys in `.env` file (never commit)
- Validate webhook tokens
- Verify Paystack payment references
- Use HTTPS in production
- Implement rate limiting
- Validate user input

## 📱 Telegram Commands

- `/start` - Start bot
- `/help` - Show help
- `/fixtures` - Today's fixtures
- `/predict <fixture_id>` - Get prediction
- `/stats <fixture_id>` - Get team stats

## 📝 Data Storage

User sessions and transactions stored in:
- `data/user_states.json` - User conversation states
- `data/transactions.json` - Payment records

## 🚀 Deployment

### Production with Ngrok (Testing)

```bash
# Install ngrok
# Create account: https://ngrok.com

# Start ngrok tunnel
ngrok http 5000
```

### Production Deployment

1. **Use HTTPS** - Paystack requires HTTPS
2. **Configure DNS** - Point domain to server
3. **Set Webhooks** - Update WhatsApp/Telegram webhook URLs
4. **Environment** - Set production credentials
5. **Monitoring** - Log all transactions

## 🐛 Troubleshooting

### Paystack Payment Fails

- Check API keys in .env
- Verify M-Pesa is enabled for your Paystack account
- Check user's phone number format (should be valid Kenyan number)

### WhatsApp Messages Not Sent

- Ensure Chrome/Chromium is installed and accessible
- Check that `data/whatsapp_sessions/` directory exists and is writable
- If QR code doesn't appear, delete session files and restart: `rm -rf data/whatsapp_sessions/*`
- Ensure WhatsApp is not already logged in on another browser/device
- Monitor browser automation process in logs
- Note: whatsapp-web.js may require re-authentication if WhatsApp updates

### Telegram Messages Not Sent

- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check webhook URL is publicly accessible
- Verify webhook is registered with Telegram

### Session Expires Too Quickly

- Adjust `PAYMENT_TIMEOUT_SECONDS` in `frontend/utils/constants.py`
- Default is 300 seconds (5 minutes)

## 📞 Support

For issues with:
- **WhatsApp Web.js**: [GitHub Repository](https://github.com/pedrosans/whatsapp-web.js)
- **Selenium**: [Selenium Documentation](https://www.selenium.dev/documentation/)
- **Twilio** (future): [Twilio WhatsApp API](https://www.twilio.com/whatsapp)
- **Paystack**: [Paystack Support](https://paystack.com/contact)
- **Telegram**: [Telegram Bot API Docs](https://core.telegram.org/bots/api)

## 🔗 Integration with Main API

The frontend communicates with the main Football Analysis API:

```
Frontend (WhatsApp/Telegram)
    ↓
Paystack (Payment)
    ↓
Football API (http://localhost:8000)
    ├── /msg/fixtures
    ├── /msg/analyze
    └── /msg/stats
```

## 📄 License

Same as parent project.
