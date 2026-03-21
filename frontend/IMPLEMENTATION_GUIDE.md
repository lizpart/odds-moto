# Frontend Implementation Guide

Complete guide to implement and deploy the WhatsApp and Telegram bot frontend.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Setup Steps](#setup-steps)
4. [Configuration](#configuration)
5. [Communication Flows](#communication-flows)
6. [Deployment](#deployment)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Development (Local)

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
cp .env.example .env
# Edit .env with your API keys

# 4. Run both bots
python run.py

# Or run individually:
python run.py --service whatsapp  # Port 5000
python run.py --service telegram  # Port 5001
```

### Testing Locally

Use ngrok to expose your local server:

```bash
# In another terminal
ngrok http 5000  # For WhatsApp

# Copy the ngrok URL and set it as webhook URL in WhatsApp dashboard
```

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    User Communication Layer                 │
├──────────────────────────────┬──────────────────────────────┤
│   WhatsApp                   │   Telegram                   │
│   ├─ Bot (bot.py)            │   ├─ Bot (bot.py)            │
│   ├─ Server (server.py)      │   ├─ Server (server.py)      │
│   └─ Webhook Handler         │   └─ Webhook Handler        │
├──────────────────────────────┴──────────────────────────────┤
│                    Shared Services Layer                    │
├──────────────────────────────┬──────────────────────────────┤
│   State Management           │   Payment Processing        │
│   ├─ User Sessions           │   ├─ Paystack               │
│   ├─ Transaction History     │   ├─ M-Pesa                 │
│   └─ Message Formatting      │   └─ Payment Verification  │
├──────────────────────────────┴──────────────────────────────┤
│                    Backend Integration                      │
├──────────────────────────────────────────────────────────────┤
│   Football Analysis API                                     │
│   ├─ /msg/fixtures (Today's matches)                       │
│   ├─ /msg/analyze  (Predictions & odds)                    │
│   └─ /msg/stats    (Team statistics)                       │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Message (WhatsApp/Telegram)
    ↓
Webhook Server (receive_message, handle_update)
    ↓
Bot Processor (process_message)
    ↓
State Manager (check user state, manage session)
    ↓
Decision Tree (route to handler)
    ↓
Handler Functions (start, choice, verify, predict)
    ↓
Paystack / API Client (initialize payment / fetch data)
    ↓
Message Formatter (format response)
    ↓
Response Send (send_whatsapp_message / send_telegram_message)
    ↓
User Receives Message
```

---

## Setup Steps

### Step 1: Prerequisites

- Python 3.9+ installed
- Paystack account (free) at https://paystack.com
- Telegram bot token (from @BotFather)
- Google Chrome or Chromium browser (for WhatsApp Web)
- Football API running on http://localhost:8000

### Step 2: Clone and Install

```bash
# Navigate to project
cd scraper-final-serper-latest
cd frontend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Get API Keys

#### Paystack

1. Go to https://dashboard.paystack.com
2. Sign up (free account is fine for testing)
3. Navigate to Settings → Developer
4. Copy your:
   - Secret Key (starts with `sk_test_` or `sk_live_`)
   - Public Key (starts with `pk_test_` or `pk_live_`)

#### Telegram

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Choose a name for your bot
4. Copy the token (format: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

#### WhatsApp (Using whatsapp-web.js)

The bot uses whatsapp-web.js library which connects to WhatsApp Web via browser automation:

1. **No API keys needed** - authenticates via QR code
2. **No waiting for Meta approval** - works immediately
3. **Works with personal WhatsApp accounts** - no business account required
4. **Browser requirement**: Google Chrome or Chromium

Setup is automatic - when you first run the bot:
1. QR code will be displayed in terminal
2. Scan with your WhatsApp phone
3. Bot will be authenticated and ready to use

**Future Migration to Twilio:**
Once your WhatsApp number is verified with Twilio, you can migrate by updating credentials.

### Step 4: Configure Environment

```bash
# Create .env file from template
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your editor
```

Example .env:
```
PAYSTACK_SECRET_KEY=sk_test_your_key_here
PAYSTACK_PUBLIC_KEY=pk_test_your_key_here
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
WHATSAPP_SESSION_DIR=./data/whatsapp_sessions
WHATSAPP_WEBHOOK_TOKEN=football_predictions_token
```

**For future Twilio setup**, add:
```
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```
FOOTBALL_API_BASE=http://localhost:8000
```

### Step 5: Create Data Directories

```bash
# These are created automatically, but you can pre-create them
mkdir data
mkdir cache
```

### Step 6: Test Locally

```bash
# Start the bots
python run.py

# In another terminal, test WhatsApp webhook
curl -X POST http://localhost:5000/health

# Test Telegram webhook
curl -X POST http://localhost:5001/health

# Test message processing
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"entry": [{"changes": [{"value": {"messages": [{"from": "254712345678", "body": "Hi"}]}}]}]}'
```

---

## Configuration

### Environment Variables

#### Payment Gateway
```
PAYSTACK_SECRET_KEY      # Required for payments
PAYSTACK_PUBLIC_KEY      # Required for payments
```

#### Messaging Platforms
```
WHATSAPP_PHONE_NUMBER_ID # Required to send WhatsApp messages
WHATSAPP_ACCESS_TOKEN    # Required to send WhatsApp messages
WHATSAPP_WEBHOOK_TOKEN   # For webhook verification

TELEGRAM_BOT_TOKEN       # Required to send Telegram messages
TELEGRAM_WEBHOOK_URL     # For production deployment
```

#### Backend
```
FOOTBALL_API_BASE=http://localhost:8000  # Main API URL
```

#### Server
```
WHATSAPP_SERVER_HOST=0.0.0.0  # Listen on all interfaces
WHATSAPP_SERVER_PORT=5000

TELEGRAM_SERVER_HOST=0.0.0.0
TELEGRAM_SERVER_PORT=5001
```

#### Storage
```
DATA_DIR=data              # User sessions and transactions
CACHE_DIR=cache            # Temporary data
LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR
```

### Configuration Validation

Check if all required configurations are set:

```bash
# Run configuration validator
python -c "from frontend.config import validate_configuration; errors, warnings = validate_configuration(); print('Errors:', errors); print('Warnings:', warnings)"
```

---

## Communication Flows

### WhatsApp Flow (Primary)

```
1. User sends "Hi" on WhatsApp
   ↓
   Bot: "Welcome! Choose package: 1) League Specific (KSH 10) 2) All Leagues (KSH 30)"

2. User replies "1"
   ↓
   Bot: "Selected League Specific. Price: KSH 10. M-Pesa prompt coming..."

3. M-Pesa prompt appears on user's phone
   ↓
   User: Completes M-Pesa payment

4. User replies "verify" (optional - auto-checks after 30s)
   ↓
   Bot verifies payment with Paystack

5. Payment confirmed
   ↓
   Bot: Sends today's predictions
```

### Telegram Flow (Secondary)

```
1. User sends /start
   ↓
   Bot: "Welcome! Send /fixtures for free, or /help for paid predictions"

2. User sends /fixtures
   ↓
   Bot: "Today's fixtures: [List]"

3. User sends /predict 1379137
   ↓
   Bot: "Prediction for fixture: [Analysis]"

4. For paid predictions:
   - User chooses package (1 or 2)
   - Bot directs: "Send payment on WhatsApp: [Link]"
   - After payment, bot delivers predictions
```

### State Machine

```
┌─────────────┐
│   INITIAL   │
└──────┬──────┘
       │ /start or "hi"
       ↓
┌──────────────────┐
│  GREETING_SENT   │
└──────┬───────────┘
       │ user sends 1 or 2
       ↓
┌──────────────────┐
│ CHOICE_RECEIVED  │
└──────┬───────────┘
       │ initiate_payment()
       ↓
┌──────────────────┐
│PAYMENT_INITIATED │
└──────┬───────────┘
       │ M-Pesa prompt sent
       ↓
┌──────────────────┐
│ PAYMENT_PENDING  │
└──────┬───────────┘
       │ verify_payment()
       ├─→ Success
       │   ↓
       │ ┌──────────────────┐
       │ │PAYMENT_CONFIRMED │
       │ └──────┬───────────┘
       │        │ send_predictions()
       │        ↓
       │ ┌──────────────────┐
       │ │PREDICTIONS_SENT  │
       │ └──────────────────┘
       │
       └─→ Failed
           ↓
       ┌──────────────────┐
       │  PAYMENT_FAILED  │
       └──────┬───────────┘
             │ retry or timeout
             ↓
       ┌──────────────────┐
       │SESSION_EXPIRED   │
       └──────────────────┘
```

---

## Deployment

### Production Checklist

- [ ] Paystack account in production mode
- [ ] All API keys set to production values
- [ ] HTTPS configured (required for Telegram webhooks)
- [ ] WhatsApp Web.js properly authenticated (QR code scanned)
- [ ] Telegram webhook URL configured
- [ ] Chrome/Chromium installed on server
- [ ] Session directory writable (`data/whatsapp_sessions/`)
- [ ] Database backups configured
- [ ] Monitoring and alerts set up
- [ ] Rate limiting enabled
- [ ] Error tracking configured
- [ ] Phone number validation implemented

### Using Gunicorn (Production)

```bash
# Install gunicorn
pip install gunicorn

# Run WhatsApp bot
gunicorn -w 4 -b 0.0.0.0:5000 frontend.whatsapp.server:app

# Run Telegram bot
gunicorn -w 4 -b 0.0.0.0:5001 frontend.telegram.server:app
```

### Using Docker (Recommended)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "run.py"]
```

```bash
# Build
docker build -t football-bot .

# Run
docker run -p 5000:5000 -p 5001:5001 \
  -e PAYSTACK_SECRET_KEY=your_key \
  -e PAYSTACK_PUBLIC_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  football-bot
```

### Using Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  football-api:
    image: football-api:latest
    ports:
      - "8000:8000"

  frontend-bot:
    image: football-bot:latest
    ports:
      - "5000:5000"
      - "5001:5001"
    environment:
      - PAYSTACK_SECRET_KEY=${PAYSTACK_SECRET_KEY}
      - PAYSTACK_PUBLIC_KEY=${PAYSTACK_PUBLIC_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - FOOTBALL_API_BASE=http://football-api:8000
    depends_on:
      - football-api
```

---

## Monitoring

### Health Checks

```bash
# WhatsApp bot health
curl http://localhost:5000/health

# Telegram bot health
curl http://localhost:5001/health

# Check if Football API is running
curl http://localhost:8000/status
```

### Logging

Logs are printed to console. For production, redirect to file:

```bash
python run.py > logs/bot.log 2>&1 &
```

### Metrics to Monitor

- Message processing time
- Payment success rate
- API response times
- Error rates
- User session count
- Transaction volume

---

## Troubleshooting

### WhatsApp Messages Not Sending

**Problem**: Messages processed but not sent to user

**Solutions**:
1. Check webhook configuration in WhatsApp dashboard
2. Verify access token is valid
3. Ensure phone number ID is correct
4. Check webhook logs: `curl http://localhost:5000/webhook`

### Telegram Messages Not Sending

**Problem**: Telegram messages not received by users

**Solutions**:
1. Verify bot token is correct: `curl https://api.telegram.org/botYOUR_TOKEN/getMe`
2. Check webhook URL is publicly accessible: `curl https://your-domain.com/telegram/webhook`
3. Verify webhook is registered: `curl https://api.telegram.org/botYOUR_TOKEN/getWebhookInfo`

### Payment Fails

**Problem**: Users can't pay via Paystack

**Solutions**:
1. Check Paystack API keys (test vs production)
2. Verify M-Pesa is enabled for your Paystack account
3. Test phone number format: Must be 254XXXXXXXXX (12 digits)
4. Check Paystack dashboard for transaction logs

### High API Response Time

**Problem**: Predictions take too long to load

**Solutions**:
1. Check Football API status: `curl http://localhost:8000/status`
2. Verify network connectivity
3. Check if API is overloaded
4. Implement caching for frequently requested predictions

---

## Next Steps

1. **Set up monitoring** - Implement error tracking (Sentry, etc.)
2. **Add analytics** - Track user engagement and conversions
3. **Implement advanced features**:
   - League-specific predictions
   - Betting strategy suggestions
   - Historical data and trends
   - User feedback and ratings
4. **Scale infrastructure** - Add load balancing if needed
5. **Compliance** - Ensure GDPR/local regulations

---

## Support Resources

- **Paystack Docs**: https://paystack.com/docs
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **WhatsApp Business API**: https://developers.facebook.com/docs/whatsapp
- **Football API Docs**: See ../docs/API_REFERENCE.md
