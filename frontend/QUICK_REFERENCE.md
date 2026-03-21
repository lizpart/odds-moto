# Frontend Quick Reference

## 🚀 Start Here

### 1️⃣ Setup (5 minutes)
```bash
cd frontend
cp .env.example .env
# Edit .env with your keys
python run.py
```

### 2️⃣ Test It
- WhatsApp: http://localhost:5000/health
- Telegram: http://localhost:5001/health

### 3️⃣ Deploy
See IMPLEMENTATION_GUIDE.md for production setup

---

## 📱 How It Works

### WhatsApp
```
User: Hi
Bot: Choose package (1=KSH 10, 2=KSH 30)
User: 1
Bot: Sends M-Pesa to your WhatsApp number
User: Pays via M-Pesa
Bot: Delivers predictions
```

### Telegram
```
User: /start
Bot: Shows menu
User: /fixtures
Bot: Lists today's matches
User: /predict 1234
Bot: Shows prediction for fixture 1234
```

---

## 🔑 Required Configuration

```env
# Payment (REQUIRED)
PAYSTACK_SECRET_KEY=sk_test_xxx
PAYSTACK_PUBLIC_KEY=pk_test_xxx

# Telegram (REQUIRED)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# WhatsApp (Optional)
WHATSAPP_PHONE_NUMBER_ID=119...
WHATSAPP_ACCESS_TOKEN=EAABxxx...

# Backend
FOOTBALL_API_BASE=http://localhost:8000
```

---

## 💾 File Locations

| File | Purpose |
|------|---------|
| `.env` | Your configuration (create from .env.example) |
| `data/user_states.json` | User sessions |
| `data/transactions.json` | Payment history |
| `logs/bot.log` | Application logs |

---

## 🎯 Key Features

| Feature | Status | Details |
|---------|--------|---------|
| WhatsApp Integration | ✅ | Primary messaging channel |
| Telegram Integration | ✅ | Secondary with free commands |
| M-Pesa Payments | ✅ | Via Paystack |
| Phone Normalization | ✅ | Auto-converts formats |
| State Management | ✅ | 5-min session timeout |
| Message Formatting | ✅ | Optimized for both platforms |

---

## 🔗 API Endpoints

### WhatsApp Bot
```
GET  /                    # Bot info
GET  /health              # Health check
GET  /webhook             # Webhook verification
POST /webhook             # Receive messages
POST /send_message        # Send test message
```

### Telegram Bot
```
GET  /                    # Bot info
GET  /health              # Health check
POST /webhook             # Receive updates
POST /send_message        # Send test message
```

---

## 💰 Pricing

| Tier | Price | Package |
|------|-------|---------|
| 1 | KSH 10 | League-specific predictions |
| 2 | KSH 30 | All leagues predictions |

---

## 📚 Documentation Files

1. **PROJECT_SUMMARY.md** - What was built and overview
2. **IMPLEMENTATION_GUIDE.md** - Complete setup guide
3. **PHONE_NUMBER_HANDLING.md** - How phone numbers work
4. **README.md** - Quick start
5. **This file** - Quick reference

---

## 🧪 Test Commands

### WhatsApp Test
```bash
curl -X POST http://localhost:5000/send_message \
  -H "Content-Type: application/json" \
  -d '{"to":"254712345678","message":"Test"}'
```

### Telegram Test
```bash
curl -X POST http://localhost:5001/send_message \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"123456","text":"Test"}'
```

### Health Check
```bash
curl http://localhost:5000/health
curl http://localhost:5001/health
```

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Messages not sending | Check API keys in .env |
| Paystack error | Verify account in test mode |
| Phone format error | Must be 254XXXXXXXXX (12 digits) |
| Webhook not working | Check WHATSAPP_WEBHOOK_TOKEN |
| Telegram not responding | Verify TELEGRAM_BOT_TOKEN |

---

## 📊 Directory Structure

```
frontend/
├── whatsapp/              # WhatsApp bot
│   ├── bot.py
│   └── server.py
├── telegram/              # Telegram bot
│   ├── bot.py
│   └── server.py
├── payments/              # Payment processing
│   └── paystack_processor.py
├── utils/                 # Shared utilities
│   ├── constants.py
│   ├── message_formatter.py
│   ├── state_manager.py
│   └── api_client.py
├── data/                  # User data (auto-created)
│   ├── user_states.json
│   └── transactions.json
├── config.py
├── run.py
├── requirements.txt
├── .env.example
├── README.md
├── IMPLEMENTATION_GUIDE.md
├── PHONE_NUMBER_HANDLING.md
└── PROJECT_SUMMARY.md
```

---

## 🔐 Security Checklist

- [ ] .env file created with actual keys
- [ ] .env added to .gitignore
- [ ] Webhook token is strong
- [ ] HTTPS enabled in production
- [ ] API keys rotated regularly
- [ ] Database backups configured
- [ ] Rate limiting enabled
- [ ] Error logging configured

---

## 📈 Production Checklist

- [ ] Paystack account in production mode
- [ ] All credentials moved to environment
- [ ] HTTPS/SSL configured
- [ ] Database set up (optional)
- [ ] Monitoring configured
- [ ] Backups automated
- [ ] Load balancer configured
- [ ] Rate limiting enabled
- [ ] Error tracking set up
- [ ] Documentation complete

---

## 🎓 Learning Path

1. **Understand**: Read PROJECT_SUMMARY.md
2. **Setup**: Follow IMPLEMENTATION_GUIDE.md
3. **Integrate**: Review PHONE_NUMBER_HANDLING.md
4. **Deploy**: Use docker-compose (see IMPLEMENTATION_GUIDE.md)
5. **Monitor**: Check logs and metrics

---

## 🔗 Related Projects

- **Main API**: `../main.py` - Football Analysis API
- **Tests**: `../tests/` - API tests
- **Docs**: `../docs/` - API documentation

---

## 📞 Quick Links

- Paystack Docs: https://paystack.com/docs
- Telegram Bot API: https://core.telegram.org/bots
- WhatsApp API: https://developers.facebook.com/docs/whatsapp
- Football API Docs: ../docs/API_REFERENCE.md

---

## ✅ Checklist to Start

- [ ] Clone repository
- [ ] Navigate to frontend/
- [ ] Copy .env.example to .env
- [ ] Get Paystack keys (https://paystack.com)
- [ ] Get Telegram bot token (@BotFather)
- [ ] Add keys to .env
- [ ] Run `pip install -r requirements.txt`
- [ ] Run `python run.py`
- [ ] Test with curl commands
- [ ] Read full IMPLEMENTATION_GUIDE.md
- [ ] Deploy to production

---

**Done? Start here:** `python run.py`

**Need setup help?** See `IMPLEMENTATION_GUIDE.md`

**How do payments work?** See `PHONE_NUMBER_HANDLING.md`
