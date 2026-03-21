# Integration Checklist

Complete checklist to integrate the frontend with your Football Analysis API.

## 📋 Pre-Integration Requirements

- [ ] Football Analysis API running on `http://localhost:8000`
- [ ] Paystack account created (https://paystack.com)
- [ ] Telegram bot created via @BotFather
- [ ] Google Chrome or Chromium browser installed (for WhatsApp Web.js)
- [ ] Python 3.9+ installed
- [ ] Virtual environment ready

---

## 🔧 Step-by-Step Integration

### Phase 1: Environment Setup

- [ ] Navigate to `frontend/` directory
- [ ] Create `.env` file from `.env.example`
  ```bash
  cp .env.example .env
  ```
- [ ] Get Paystack API keys
  - [ ] Visit https://dashboard.paystack.com
  - [ ] Go to Settings → Developer
  - [ ] Copy Secret Key (sk_test_...)
  - [ ] Copy Public Key (pk_test_...)
- [ ] Get Telegram Bot Token
  - [ ] Message @BotFather on Telegram
  - [ ] Send `/newbot`
  - [ ] Follow instructions
  - [ ] Copy the token (format: 123456:ABC-DEF...)
- [ ] WhatsApp Setup (using whatsapp-web.js)
  - [ ] Ensure Chrome/Chromium installed
  - [ ] Create `data/whatsapp_sessions/` directory
  - [ ] No API keys needed - will authenticate via QR code
  - [ ] (Future) Twilio credentials for production migration

### Phase 2: Configuration

- [ ] Open `.env` file
- [ ] Add Paystack credentials
  ```
  PAYSTACK_SECRET_KEY=sk_test_your_key_here
  PAYSTACK_PUBLIC_KEY=pk_test_your_key_here
  ```
- [ ] Add Telegram token
  ```
  TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
  ```
- [ ] Configure WhatsApp (whatsapp-web.js)
  ```
  WHATSAPP_SESSION_DIR=./data/whatsapp_sessions
  WHATSAPP_WEBHOOK_TOKEN=football_predictions_token
  ```
- [ ] (Future) Add Twilio credentials when available
  ```
  TWILIO_ACCOUNT_SID=your_twilio_account_sid
  TWILIO_AUTH_TOKEN=your_twilio_auth_token
  TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
  ```
- [ ] Verify Football API URL
  ```
  FOOTBALL_API_BASE=http://localhost:8000
  ```
- [ ] Run configuration validator
  ```bash
  python -c "from frontend.config import validate_configuration; errors, warnings = validate_configuration(); print('Valid!' if not errors else 'Errors: ' + str(errors))"
  ```

### Phase 3: Installation

- [ ] Install Python dependencies
  ```bash
  pip install -r requirements.txt
  ```
- [ ] Verify installations
  ```bash
  python -c "import fastapi; import requests; import telegram; print('✅ All dependencies installed')"
  ```
- [ ] Create data directories
  ```bash
  mkdir -p data cache logs
  ```

### Phase 4: Local Testing

#### 4a: Start Services
- [ ] Ensure Football API is running
  ```bash
  curl http://localhost:8000/status
  ```
- [ ] Start frontend bots
  ```bash
  python run.py
  ```
- [ ] Verify services started
  - [ ] WhatsApp bot on http://localhost:5000/health
  - [ ] Telegram bot on http://localhost:5001/health

#### 4b: Test Endpoints
- [ ] Test WhatsApp health
  ```bash
  curl http://localhost:5000/health
  ```
- [ ] Test Telegram health
  ```bash
  curl http://localhost:5001/health
  ```
- [ ] Test message processing (WhatsApp)
  ```bash
  curl -X POST http://localhost:5000/webhook \
    -H "Content-Type: application/json" \
    -d '{"entry": [{"changes": [{"value": {"messages": [{"from": "254712345678", "body": "Hi"}]}}]}]}'
  ```
- [ ] Test message processing (Telegram)
  ```bash
  curl -X POST http://localhost:5001/webhook \
    -H "Content-Type: application/json" \
    -d '{"message": {"from": {"id": 123456, "username": "testuser"}, "text": "/start"}}'
  ```

#### 4c: Verify Phone Number Handling
- [ ] Test different phone formats
  - [ ] `712345678` (9 digits) → converts to `254712345678`
  - [ ] `0712345678` (10 digits with 0) → converts to `254712345678`
  - [ ] `254712345678` (12 digits) → stays `254712345678`
- [ ] Check logs for normalization
  ```bash
  tail -f logs/bot.log | grep "phone"
  ```

### Phase 5: Webhook Configuration

#### 5a: WhatsApp Webhook (if using)
- [ ] Start ngrok for testing
  ```bash
  ngrok http 5000
  ```
- [ ] Copy ngrok URL
- [ ] Go to WhatsApp dashboard
- [ ] Set Webhook URL: `https://your-ngrok-url/webhook`
- [ ] Set Verify Token: `football_predictions_token`
- [ ] Test webhook verification
  - [ ] Check that WhatsApp verifies webhook

#### 5b: Telegram Webhook (if using production)
- [ ] Get public domain/IP
- [ ] Set webhook via API
  ```bash
  curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
    -H 'Content-Type: application/json' \
    -d '{"url": "https://your-domain.com/webhook"}'
  ```
- [ ] Verify webhook info
  ```bash
  curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
  ```

### Phase 6: Payment Testing

- [ ] Create test Paystack transaction
  ```bash
  curl -X POST http://localhost:5000/send_message \
    -H "Content-Type: application/json" \
    -d '{"to": "254712345678", "message": "Test payment flow"}'
  ```
- [ ] Verify payment records created
  ```bash
  cat data/transactions.json
  ```
- [ ] Check user state tracking
  ```bash
  cat data/user_states.json
  ```

### Phase 7: User Flow Testing

- [ ] Test complete WhatsApp flow
  - [ ] Send "Hi"
  - [ ] Receive greeting
  - [ ] Send "1"
  - [ ] Receive package confirmation
  - [ ] Verify payment initiated
  - [ ] Check transaction record

- [ ] Test complete Telegram flow
  - [ ] Send `/start`
  - [ ] Receive welcome
  - [ ] Send `/fixtures`
  - [ ] Receive today's fixtures
  - [ ] Send `/predict 1379137`
  - [ ] Receive prediction

---

## 🌐 Production Deployment

### Phase 8: Prepare for Production

- [ ] Switch Paystack account to live mode
  ```
  PAYSTACK_SECRET_KEY=sk_live_...
  PAYSTACK_PUBLIC_KEY=pk_live_...
  ```
- [ ] Update all credentials to production values
- [ ] Configure HTTPS/SSL certificate
- [ ] Set up database (if needed)
  ```bash
  # PostgreSQL or MongoDB recommended
  ```
- [ ] Configure environment file for production
  ```bash
  cp .env .env.production
  # Edit with production credentials
  ```

### Phase 9: Deploy Services

- [ ] Option A: Using Gunicorn
  ```bash
  gunicorn -w 4 -b 0.0.0.0:5000 frontend.whatsapp.server:app
  gunicorn -w 4 -b 0.0.0.0:5001 frontend.telegram.server:app
  ```

- [ ] Option B: Using Docker
  ```bash
  docker build -t football-bot .
  docker run -p 5000:5000 -p 5001:5001 \
    -e PAYSTACK_SECRET_KEY=sk_live_xxx \
    -e TELEGRAM_BOT_TOKEN=xxx \
    football-bot
  ```

- [ ] Option C: Using Docker Compose
  ```bash
  docker-compose up -d
  ```

### Phase 10: Configure Webhooks for Production

- [ ] Update WhatsApp webhook URL (if using)
  ```
  https://your-production-domain.com/webhook
  ```
- [ ] Update Telegram webhook URL
  ```bash
  curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
    -H 'Content-Type: application/json' \
    -d '{"url": "https://your-production-domain.com/webhook"}'
  ```
- [ ] Verify webhooks are active
  ```bash
  curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
  ```

### Phase 11: Monitoring & Logging

- [ ] Set up log rotation
  ```bash
  # Use logrotate or similar
  ```
- [ ] Configure error tracking
  ```bash
  # Sentry, Rollbar, or similar
  ```
- [ ] Set up monitoring
  - [ ] CPU/Memory usage
  - [ ] Error rates
  - [ ] Payment success rate
  - [ ] API response times

### Phase 12: Backups & Recovery

- [ ] Backup user states
  ```bash
  cp -r data/ backups/data_$(date +%Y%m%d)
  ```
- [ ] Set up automated backups
- [ ] Test recovery procedure
- [ ] Document disaster recovery plan

---

## ✅ Post-Integration Verification

### User-Facing Tests

- [ ] Can users send "Hi" on WhatsApp
- [ ] Do users receive proper greeting
- [ ] Can users select package (1 or 2)
- [ ] Does M-Pesa prompt appear
- [ ] Does payment verification work
- [ ] Are predictions delivered correctly
- [ ] Is Telegram link in all messages

### Backend Tests

- [ ] User states saved correctly
- [ ] Transactions logged properly
- [ ] Phone numbers normalized
- [ ] API calls succeed
- [ ] Error handling works
- [ ] Timeouts handled gracefully
- [ ] Logs are readable

### Performance Tests

- [ ] Message processing < 2 seconds
- [ ] Payment verification < 5 seconds
- [ ] Prediction delivery < 3 seconds
- [ ] No memory leaks
- [ ] CPU usage normal

---

## 🆘 Troubleshooting During Integration

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Paystack connection fails | Check API keys in .env |
| Telegram bot doesn't respond | Verify token and webhook URL |
| WhatsApp messages not received | Check webhook verification |
| Phone number format error | Use 254XXXXXXXXX format |
| High latency | Check Football API performance |
| Sessions not persisting | Check data/ directory permissions |

---

## 📞 Support During Integration

1. **Check logs**
   ```bash
   tail -f logs/bot.log
   ```

2. **Read documentation**
   - IMPLEMENTATION_GUIDE.md
   - PHONE_NUMBER_HANDLING.md
   - README.md

3. **Test endpoints directly**
   ```bash
   curl -v http://localhost:5000/health
   ```

4. **Check external services**
   - Paystack dashboard
   - Telegram Bot API
   - WhatsApp Business dashboard

---

## ✨ Sign-Off Checklist

Once all items are complete, the frontend is fully integrated:

- [ ] All configuration items completed
- [ ] All services running
- [ ] All tests passing
- [ ] All webhooks configured
- [ ] Monitoring in place
- [ ] Backups configured
- [ ] Documentation complete
- [ ] Team trained
- [ ] Production ready
- [ ] Customer feedback positive

---

## 📊 Integration Summary

**Total Steps**: 120+
**Estimated Time**: 4-6 hours
**Difficulty**: Intermediate

**What you get**:
✅ WhatsApp + Telegram bot integration
✅ Payment processing with M-Pesa
✅ User session management
✅ Football predictions delivery
✅ Production-ready deployment
✅ Complete monitoring and logging

---

**Ready to start?** Begin with Phase 1 above!
