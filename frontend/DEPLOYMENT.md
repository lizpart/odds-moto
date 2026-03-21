# Production Deployment Checklist

## Pre-Deployment (Development Phase)

### Code Quality
- [ ] All Python files follow PEP 8 style guide
- [ ] No hardcoded secrets or credentials
- [ ] Error handling in all critical paths
- [ ] Logging configured for debugging
- [ ] Type hints in function signatures
- [ ] Docstrings for all public functions
- [ ] No unused imports or variables
- [ ] Requirements.txt updated and tested

### Testing
- [ ] All unit tests passing
- [ ] Manual testing completed (see TESTING.md)
- [ ] Edge cases tested (invalid input, timeouts)
- [ ] Error scenarios tested
- [ ] Phone number normalization verified
- [ ] State machine transitions verified
- [ ] Payment flow tested with test keys

### Documentation
- [ ] README.md complete and accurate
- [ ] IMPLEMENTATION_GUIDE.md reviewed
- [ ] API documentation up to date
- [ ] Deployment instructions clear
- [ ] Environment variables documented
- [ ] Troubleshooting guide available

### Code Review
- [ ] Code reviewed by team member
- [ ] Architecture reviewed
- [ ] Security reviewed
- [ ] Performance reviewed
- [ ] Comments added where needed

---

## Credentials & Configuration

### WhatsApp Setup (whatsapp-web.js)

**No API keys needed!** The bot uses whatsapp-web.js which authenticates via QR code.

- [ ] Ensure Google Chrome or Chromium is installed on server
- [ ] Create `data/whatsapp_sessions/` directory
- [ ] Make directory writable by bot process
- [ ] Run bot once to generate QR code
- [ ] Scan QR code with your WhatsApp phone
- [ ] Bot will be authenticated for future runs

**Credentials Needed:**
```env
WHATSAPP_SESSION_DIR=./data/whatsapp_sessions
WHATSAPP_WEBHOOK_TOKEN=football_predictions_token
```

**Future: Twilio Migration**

Once WhatsApp number is verified with Twilio:
- [ ] Create Twilio account
- [ ] Get Account SID and Auth Token
- [ ] Update credentials below:

```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### Telegram Setup
- [ ] Create Telegram Bot via @BotFather
- [ ] Get bot token
- [ ] Set webhook URL
- [ ] Enable privacy mode

**Credentials Needed:**
- `TELEGRAM_BOT_TOKEN` - From @BotFather

**Webhook Configuration:**
```bash
# Set Telegram webhook (run once after deployment)
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://yourdomain.com/telegram/webhook"
```

### Paystack Setup
- [ ] Create Paystack account
- [ ] Go to Settings > API Keys & Webhooks
- [ ] Copy Secret Key (for API calls)
- [ ] Copy Public Key (for frontend - if needed)
- [ ] Add webhook URL: `https://yourdomain.com/paystack/webhook`
- [ ] Subscribe to `charge.success` events

**Credentials Needed:**
- `PAYSTACK_SECRET_KEY` - Secret API key
- `PAYSTACK_PUBLIC_KEY` - Public API key (optional for backend)

**In Production:** Use LIVE keys, not TEST keys

### Football API Setup
- [ ] API running on production server
- [ ] Database configured
- [ ] Caching enabled
- [ ] Rate limiting set
- [ ] CORS configured if needed

**Configuration:**
- `FOOTBALL_API_BASE_URL` - Should point to production API

---

## Server Requirements

### Minimum Server Specs
- **OS:** Ubuntu 20.04 LTS or CentOS 8+
- **RAM:** 2 GB minimum (4 GB recommended)
- **CPU:** 2 cores minimum
- **Disk:** 20 GB (for logs and cache)
- **Network:** Stable internet, static IP recommended

### Required Software
- [ ] Python 3.9+ installed
- [ ] pip package manager
- [ ] Virtual environment created
- [ ] Git installed (for deployment)
- [ ] SSL/TLS certificate (self-signed or Let's Encrypt)
- [ ] Reverse proxy (nginx) configured
- [ ] Process manager (systemd or supervisor)

### Python Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

---

## Environment Configuration

### Create Production .env File

```bash
# File: /path/to/frontend/.env

# Football API (Production)
FOOTBALL_API_BASE_URL=https://api.yourdomain.com
FOOTBALL_API_TIMEOUT=10
API_CACHE_ENABLED=true

# WhatsApp
WHATSAPP_PHONE_NUMBER_ID=your_production_phone_id
WHATSAPP_ACCESS_TOKEN=your_production_access_token
WHATSAPP_VERIFY_TOKEN=your_secure_token_string
WHATSAPP_API_VERSION=v18.0

# Telegram
TELEGRAM_BOT_TOKEN=your_production_bot_token

# Paystack (LIVE KEYS!)
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxxxxxxxxx
PAYSTACK_TIMEOUT=15

# Server Configuration
DEBUG=false
LOG_LEVEL=INFO
LOG_FILE=/var/log/football-predictions/app.log
HOST=0.0.0.0
WHATSAPP_PORT=5000
TELEGRAM_PORT=5001

# Session Configuration
SESSION_TIMEOUT=300
MAX_RETRIES=3

# Other
ENVIRONMENT=production
VERSION=1.0.0
```

### Secure .env File
```bash
# Set restrictive permissions
chmod 600 .env

# Only readable by owner
ls -la .env  # Should show: -rw------- 
```

---

## Deployment Steps

### Step 1: Prepare Server

```bash
# SSH into server
ssh user@server.com

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.9 python3-pip python3-venv nginx certbot

# Create application directory
sudo mkdir -p /opt/football-predictions
sudo chown $USER:$USER /opt/football-predictions

cd /opt/football-predictions
```

### Step 2: Clone & Setup Code

```bash
# Clone repository
git clone https://github.com/yourusername/scraper-final-serper-latest.git
cd scraper-final-serper-latest

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r frontend/requirements.txt

# Create .env from template
cp frontend/.env.example frontend/.env

# Edit .env with production credentials
nano frontend/.env
```

### Step 3: Configure SSL Certificate

```bash
# Using Let's Encrypt
sudo certbot certonly --standalone -d yourdomain.com

# Cert files will be in: /etc/letsencrypt/live/yourdomain.com/

# Create symlinks (optional)
sudo ln -s /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/football-predictions/cert.pem
sudo ln -s /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/football-predictions/key.pem

# Set permissions
sudo chown $USER:$USER cert.pem key.pem
chmod 600 key.pem
```

### Step 4: Configure Nginx (Reverse Proxy)

```nginx
# File: /etc/nginx/sites-available/football-predictions

upstream whatsapp_backend {
    server 127.0.0.1:5000;
}

upstream telegram_backend {
    server 127.0.0.1:5001;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # WhatsApp webhook
    location /whatsapp/webhook {
        proxy_pass http://whatsapp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Allow large payloads
        client_max_body_size 10M;
    }

    # Telegram webhook
    location /telegram/webhook {
        proxy_pass http://telegram_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Paystack webhook (if needed)
    location /paystack/webhook {
        proxy_pass http://whatsapp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "OK";
        add_header Content-Type text/plain;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

```bash
# Enable nginx config
sudo ln -s /etc/nginx/sites-available/football-predictions /etc/nginx/sites-enabled/
sudo nginx -t  # Test config
sudo systemctl restart nginx
```

### Step 5: Configure Systemd Service

```bash
# File: /etc/systemd/system/football-predictions-whatsapp.service

[Unit]
Description=Football Predictions - WhatsApp Bot
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/opt/football-predictions
Environment="PATH=/opt/football-predictions/venv/bin"
ExecStart=/opt/football-predictions/venv/bin/python -m frontend.whatsapp.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# File: /etc/systemd/system/football-predictions-telegram.service

[Unit]
Description=Football Predictions - Telegram Bot
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/opt/football-predictions
Environment="PATH=/opt/football-predictions/venv/bin"
ExecStart=/opt/football-predictions/venv/bin/python -m frontend.telegram.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable football-predictions-whatsapp
sudo systemctl enable football-predictions-telegram
sudo systemctl start football-predictions-whatsapp
sudo systemctl start football-predictions-telegram

# Check status
sudo systemctl status football-predictions-whatsapp
sudo systemctl status football-predictions-telegram

# View logs
sudo journalctl -u football-predictions-whatsapp -f
sudo journalctl -u football-predictions-telegram -f
```

### Step 6: Configure Logging

```bash
# Create log directory
sudo mkdir -p /var/log/football-predictions
sudo chown yourusername:yourusername /var/log/football-predictions

# Create rotation config
# File: /etc/logrotate.d/football-predictions

/var/log/football-predictions/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Step 7: Verify Deployment

```bash
# Check services running
ps aux | grep football-predictions

# Test WhatsApp webhook
curl -X GET https://yourdomain.com/whatsapp/webhook \
  -H "hub.verify_token: your_verify_token" \
  -H "hub.challenge: test_challenge"

# Test Telegram webhook
curl https://yourdomain.com/telegram/webhook

# Check logs
sudo tail -f /var/log/football-predictions/app.log
```

---

## Post-Deployment

### Verify Connections

**WhatsApp (whatsapp-web.js):**
```bash
# Check if bot is running
ps aux | grep whatsapp

# Check logs for authentication status
tail -f logs/app.log | grep -i "whatsapp"

# If authentication failed, re-scan QR code:
# 1. Delete session files: rm -rf data/whatsapp_sessions/*
# 2. Restart bot
# 3. Scan new QR code

# Verify Chrome/ChromeDriver process
ps aux | grep chromedriver
```

**Telegram:**
```bash
# Verify webhook set
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"

# Should show your webhook URL and "ok": true
```

**Paystack:**
```bash
# In Paystack Dashboard:
# 1. Go to Settings > Webhooks
# 2. Verify webhook URL is registered
# 3. Check "Webhook Logs" for successful deliveries
```

### Set Up Monitoring

```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Monitor resource usage
htop

# Set up alerts (using cron)
# File: /opt/football-predictions/check_health.sh

#!/bin/bash

WHATSAPP_PID=$(pgrep -f "football-predictions.*whatsapp")
TELEGRAM_PID=$(pgrep -f "football-predictions.*telegram")

if [ -z "$WHATSAPP_PID" ]; then
    echo "WhatsApp bot crashed!" | mail -s "Alert: WhatsApp Bot Down" admin@yourdomain.com
    sudo systemctl restart football-predictions-whatsapp
fi

if [ -z "$TELEGRAM_PID" ]; then
    echo "Telegram bot crashed!" | mail -s "Alert: Telegram Bot Down" admin@yourdomain.com
    sudo systemctl restart football-predictions-telegram
fi
```

```bash
# Add to crontab to check every 5 minutes
chmod +x /opt/football-predictions/check_health.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/football-predictions/check_health.sh") | crontab -
```

### Backup Strategy

```bash
# Daily backup of user data and transactions
# File: /opt/football-predictions/backup.sh

#!/bin/bash

BACKUP_DIR="/backups/football-predictions"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup data files
tar -czf "$BACKUP_DIR/data_$TIMESTAMP.tar.gz" \
    /opt/football-predictions/data/

# Keep only last 30 days
find $BACKUP_DIR -name "data_*.tar.gz" -mtime +30 -delete
```

```bash
# Add daily backup to cron
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/football-predictions/backup.sh") | crontab -
```

---

## Security Checklist

- [ ] SSL certificate installed and valid
- [ ] .env file has restricted permissions (600)
- [ ] Database credentials not in code
- [ ] API tokens not logged
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (if applicable)
- [ ] CSRF protection enabled
- [ ] Security headers configured
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
- [ ] Regular security updates applied
- [ ] Firewall configured (ufw)
- [ ] SSH key-based auth only (no passwords)
- [ ] Regular security audits scheduled

---

## Firewall Configuration

```bash
# Enable UFW
sudo ufw enable

# Allow SSH (CRITICAL!)
sudo ufw allow 22/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (redirect to HTTPS)
sudo ufw allow 80/tcp

# Deny all other incoming
sudo ufw default deny incoming

# Verify
sudo ufw status
```

---

## Troubleshooting

### WhatsApp Bot Not Responding

```bash
# Check if service running
sudo systemctl status football-predictions-whatsapp

# Check logs
sudo journalctl -u football-predictions-whatsapp -n 50

# Check Chrome/WebDriver process
ps aux | grep chrome

# If QR code didn't authenticate:
# 1. Delete sessions: rm -rf data/whatsapp_sessions/*
# 2. Restart bot
# 3. Scan new QR code

# Monitor WebDriver logs
tail -f logs/selenium.log
```

### Telegram Bot Not Responding

```bash
# Check service
sudo systemctl status football-predictions-telegram

# Check logs
sudo journalctl -u football-predictions-telegram -n 50

# Verify webhook
curl https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo

# Reset webhook if needed
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url="
```

### Payment Processing Failing

```bash
# Check Paystack credentials in .env
grep PAYSTACK /opt/football-predictions/frontend/.env

# Verify in Paystack test mode (development)
# Verify using LIVE keys (production)

# Check webhook in Paystack dashboard
# Verify log entries
```

### High Memory/CPU Usage

```bash
# Identify process
ps aux | grep football-predictions

# Check for memory leaks
# Restart bot if necessary
sudo systemctl restart football-predictions-whatsapp
sudo systemctl restart football-predictions-telegram

# Review logs for errors
```

---

## Rollback Procedure

If deployment fails:

```bash
# Stop services
sudo systemctl stop football-predictions-whatsapp
sudo systemctl stop football-predictions-telegram

# Revert code to last working version
cd /opt/football-predictions
git checkout last-working-commit

# Reinstall dependencies
source venv/bin/activate
pip install -r frontend/requirements.txt

# Restart services
sudo systemctl start football-predictions-whatsapp
sudo systemctl start football-predictions-telegram

# Verify
sudo systemctl status football-predictions-whatsapp
sudo systemctl status football-predictions-telegram
```

---

## Success Criteria

✅ Deployment is successful when:

1. **Services Running**
   - WhatsApp bot service active and running
   - Telegram bot service active and running
   - No errors in systemd logs

2. **Webhooks Connected**
   - WhatsApp webhook shows "connected" in Meta dashboard
   - Telegram bot receives updates
   - Paystack webhook operational

3. **Functionality Working**
   - User can send message on WhatsApp
   - Bot responds with greeting
   - User can select package
   - Payment flow initiates
   - Predictions delivered after payment

4. **Monitoring Active**
   - Logs being written
   - Health checks passing
   - Backups running
   - Alerts configured

5. **Security Verified**
   - HTTPS working
   - SSL certificate valid
   - Credentials secured
   - Firewall active

---

## Post-Deployment Maintenance

**Daily:**
- [ ] Monitor logs for errors
- [ ] Check service health
- [ ] Verify payment processing

**Weekly:**
- [ ] Review performance metrics
- [ ] Check backup integrity
- [ ] Update dependencies (security patches)

**Monthly:**
- [ ] Full system backup
- [ ] Security audit
- [ ] Performance optimization
- [ ] Update documentation

**Quarterly:**
- [ ] Major dependency updates
- [ ] Database optimization
- [ ] Capacity planning
- [ ] User feedback review

---

**Deployment Date:** _______________  
**Deployed By:** _______________  
**Production URL:** _______________  

**Go Live Confirmation:** ✓ All checks passed!
