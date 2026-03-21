# Testing Guide

## Quick Local Testing

### 1. Setup Testing Environment

```bash
# Navigate to project
cd c:\Users\jacob\Desktop\scraper-final-serper-latest\frontend

# Install dependencies
pip install -r requirements.txt

# Copy env template
copy .env.example .env

# Edit .env with test values
notepad .env
```

### 2. Minimal .env for Testing

```
# Football API
FOOTBALL_API_BASE_URL=http://localhost:8000

# WhatsApp
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_VERIFY_TOKEN=your_verify_token

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# Paystack
PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx

# Optional
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## Testing Scenarios

### Scenario 1: WhatsApp Flow Test

**Setup:**
1. Start Football API: `python main.py` (in main project folder)
2. Start WhatsApp bot: `python run.py --service whatsapp`
3. Use WhatsApp Web/Desktop connected to your business account

**Test Steps:**

```
Step 1: User sends "hi"
Expected: Greeting message with 2 package options

Step 2: User sends "1"
Expected: Confirmation + M-Pesa prompt

Step 3: User sends "verify"
Expected: Predictions fetched and delivered

Test Phone Number: Use your actual WhatsApp number
```

### Scenario 2: Telegram Flow Test

**Setup:**
1. Start Football API: `python main.py`
2. Start Telegram bot: `python run.py --service telegram`
3. Message your Telegram bot

**Test Steps:**

```
Step 1: Send /start
Expected: Welcome message

Step 2: Send /help
Expected: Help menu

Step 3: Send /fixtures
Expected: Today's matches (no payment required)

Step 4: Send /predict 1234
Expected: Prediction for fixture 1234 (no payment required)

Step 5: Send /stats 1234
Expected: Statistics for fixture 1234 (no payment required)
```

### Scenario 3: Payment Flow Test

**Setup:**
1. Ensure Paystack is in TEST mode
2. Use test phone number

**Test Steps:**

```
Step 1: Initiate payment (WhatsApp "1" or Telegram premium)
Expected: Payment reference generated, M-Pesa prompt

Step 2: Use Paystack test credentials:
  Phone: 254712345678 (any format accepted)
  Amount: KSH 10 or KSH 30
  
Step 3: Verify payment
Expected: Payment confirmed, predictions delivered
```

### Scenario 4: State Machine Test

**Test each state transition:**

```
INITIAL → GREETING_SENT (auto on first message)
GREETING_SENT → CHOICE_RECEIVED (user sends "1" or "2")
CHOICE_RECEIVED → PAYMENT_INITIATED (system processes)
PAYMENT_INITIATED → PAYMENT_PENDING (waiting for user verification)
PAYMENT_PENDING → PAYMENT_CONFIRMED (payment verified)
PAYMENT_CONFIRMED → PREDICTIONS_SENT (predictions delivered)

Timeout Test:
- Wait 5+ minutes without responding
- Expected: Session expires, restart conversation
```

### Scenario 5: Error Handling Test

**Test error scenarios:**

```
Invalid Choice:
  Send "3" when options are 1-2
  Expected: Error message, retry prompt

Network Error:
  Stop Football API, try to get predictions
  Expected: Graceful error message

Invalid Phone Number:
  Send non-numeric characters
  Expected: Normalized or error message

Missing Configuration:
  Stop bot, remove .env key
  Expected: Clear error message on startup
```

---

## Unit Test Examples

### Test State Manager

```python
# File: tests/test_state_manager.py

from frontend.utils.state_manager import StateManager, UserState

def test_user_state_creation():
    sm = StateManager()
    user_id = "254712345678"
    
    # Set initial state
    sm.set_user_state(user_id, UserState.GREETING_SENT)
    
    # Retrieve state
    state = sm.get_user_state(user_id)
    assert state == UserState.GREETING_SENT

def test_session_timeout():
    sm = StateManager()
    user_id = "254712345678"
    
    # Set state
    sm.set_user_state(user_id, UserState.AWAITING_CHOICE)
    
    # Check session (should be valid initially)
    assert not sm.is_session_expired(user_id)
    
    # Manually set old timestamp for testing
    # (In real test, would mock time)
    import time
    old_state = sm.get_user_state(user_id)
    old_state['timestamp'] = time.time() - 400  # 6+ minutes ago
    
    # Check again (should be expired)
    assert sm.is_session_expired(user_id)

def test_transaction_saving():
    sm = StateManager()
    
    transaction = {
        "user_id": "254712345678",
        "amount": 1000,
        "reference": "pay_xxx",
        "status": "pending"
    }
    
    sm.save_transaction(transaction)
    
    # Verify it was saved
    transactions = sm.load_transactions()
    assert any(t['reference'] == 'pay_xxx' for t in transactions)
```

### Test Phone Number Normalization

```python
# File: tests/test_phone_normalization.py

from frontend.whatsapp.bot import WhatsAppBot

def test_phone_normalization():
    test_cases = [
        ("254712345678", "254712345678"),  # Already normalized
        ("0712345678", "254712345678"),    # Local format
        ("712345678", "254712345678"),     # Without leading 0
        ("+254712345678", "254712345678"), # With +
        ("0712345678", "254712345678"),    # Variations
    ]
    
    for input_phone, expected in test_cases:
        result = WhatsAppBot._normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}"

def test_invalid_phone():
    invalid_cases = [
        "abc",
        "",
        "123",  # Too short
    ]
    
    for invalid_phone in invalid_cases:
        result = WhatsAppBot._normalize_phone_number(invalid_phone)
        # Should handle gracefully
        assert len(result) > 0
```

### Test Message Formatting

```python
# File: tests/test_message_formatting.py

from frontend.utils.message_formatter import MessageFormatter

def test_greeting_message():
    msg = MessageFormatter.format_greeting()
    assert "Welcome" in msg or "welcome" in msg.lower()
    assert "1" in msg  # Should have option 1
    assert "2" in msg  # Should have option 2

def test_choice_confirmation():
    msg = MessageFormatter.format_choice_confirmation("1")
    assert "KSH 10" in msg or "10" in msg
    assert "M-Pesa" in msg or "Mpesa" in msg

def test_message_splitting():
    # Create very long message
    long_msg = "x" * 5000
    
    split = MessageFormatter.split_long_message(long_msg)
    assert len(split) > 1  # Should be split
    assert all(len(m) <= 4096 for m in split)  # All under limit

def test_fixture_formatting():
    fixtures = [
        {
            "fixture_id": 1,
            "home": "Arsenal",
            "away": "Chelsea",
            "time": "15:00"
        }
    ]
    
    msg = MessageFormatter.format_fixtures(fixtures)
    assert "Arsenal" in msg
    assert "Chelsea" in msg
    assert "15:00" in msg
```

### Test API Client

```python
# File: tests/test_api_client.py

from frontend.utils.api_client import APIClient

def test_api_connection():
    client = APIClient()
    
    try:
        fixtures = client.get_today_fixtures()
        # Should return list or have error handling
        assert isinstance(fixtures, (list, dict))
    except Exception as e:
        # Connection error is expected if API not running
        print(f"API not available: {e}")

def test_prediction_caching():
    client = APIClient()
    
    # First call
    pred1 = client.get_prediction(1234)
    
    # Second call (should be cached)
    pred2 = client.get_prediction(1234)
    
    assert pred1 == pred2  # Should be identical
```

---

## Manual Testing Checklist

- [ ] **WhatsApp Setup**
  - [ ] Webhook URL configured in Meta
  - [ ] Access token valid
  - [ ] Phone number ID correct

- [ ] **Telegram Setup**
  - [ ] Bot token valid
  - [ ] Webhook URL configured
  - [ ] Bot privacy set correctly

- [ ] **Football API**
  - [ ] Running on localhost:8000
  - [ ] Endpoints responding
  - [ ] Sample data available

- [ ] **WhatsApp Flow**
  - [ ] Greeting message sends
  - [ ] Choice validation works
  - [ ] Payment reference generates
  - [ ] Phone number normalizes correctly

- [ ] **Telegram Flow**
  - [ ] /start command works
  - [ ] /help command works
  - [ ] /fixtures command works
  - [ ] /predict command works

- [ ] **Payment Integration**
  - [ ] Paystack test keys configured
  - [ ] Payment initializes
  - [ ] Verification works
  - [ ] Phone number used correctly

- [ ] **State Management**
  - [ ] States transition correctly
  - [ ] Sessions expire after 5 minutes
  - [ ] User data persists
  - [ ] Transactions logged

- [ ] **Error Handling**
  - [ ] Invalid input handled gracefully
  - [ ] Network errors caught
  - [ ] Timeouts handled
  - [ ] Clear error messages

- [ ] **Message Formatting**
  - [ ] Messages readable
  - [ ] Emojis display
  - [ ] Links work
  - [ ] Long messages split correctly

---

## Debugging Tips

### Enable Debug Logging

```python
# In run.py, before starting bot:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Log Files

```bash
# Watch logs in real-time
tail -f logs/app.log

# Or in PowerShell
Get-Content logs/app.log -Wait
```

### Test API Directly

```bash
# Test fixtures endpoint
curl http://localhost:8000/msg/fixtures

# Test analyze endpoint
curl http://localhost:8000/msg/analyze -d '{"fixture_id": 1234}'

# Test stats endpoint
curl http://localhost:8000/msg/stats -d '{"fixture_id": 1234}'
```

### Test Webhook Locally

```bash
# Start webhook server
python -m frontend.whatsapp.server

# In another terminal, test webhook
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "254712345678",
            "text": {"body": "test"}
          }]
        }
      }]
    }]
  }'
```

### View State Data

```bash
# Check user states
type data/user_states.json | python -m json.tool

# Check transactions
type data/transactions.json | python -m json.tool
```

---

## Expected Output Examples

### Successful WhatsApp Flow

```
User: "Hi"
Bot: "🎯 Welcome to Football Predictions!
Choose your package:
1️⃣ KSH 10 - Daily predictions
2️⃣ KSH 30 - Premium analysis"

User: "1"
Bot: "✅ You selected KSH 10
📱 M-Pesa prompt coming to 254712345678
Reference: pay_xyz123
Reply with 'verify' after payment"

User: "verify"
Bot: "🎉 Payment verified!
Here are your predictions:
⚽ Arsenal vs Chelsea (15:00)
Prediction: Arsenal Win
Odds: 1.85..."
```

### Successful Telegram Flow

```
User: /start
Bot: "Welcome! Use /help for commands"

User: /fixtures
Bot: "⚽ Today's Matches:
1. Arsenal vs Chelsea (15:00)
2. Man City vs Liverpool (17:30)"

User: /predict 1234
Bot: "🎯 Prediction for Match 1234
Home Team: 60% chance
Away Team: 25% chance
Draw: 15% chance"
```

---

## Performance Testing

### Load Test Script

```python
# File: tests/load_test.py

import concurrent.futures
import requests
import time

def test_concurrent_users(num_users=10):
    """Simulate multiple users"""
    
    def user_flow(user_id):
        session = requests.Session()
        
        # Send message
        response = session.post(
            "http://localhost:5000/webhook",
            json={
                "entry": [{
                    "changes": [{
                        "value": {
                            "messages": [{
                                "from": f"25471234567{user_id}",
                                "text": {"body": "hi"}
                            }]
                        }
                    }]
                }]
            }
        )
        
        return response.status_code == 200
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(user_flow, range(num_users)))
    
    duration = time.time() - start_time
    success_rate = sum(results) / len(results) * 100
    
    print(f"Users: {num_users}")
    print(f"Success Rate: {success_rate}%")
    print(f"Duration: {duration:.2f}s")
    print(f"Requests/second: {num_users/duration:.2f}")

if __name__ == "__main__":
    test_concurrent_users(50)
```

---

## Next Steps After Testing

1. ✅ Local testing complete
2. Deploy to production server
3. Configure real Paystack keys
4. Configure real WhatsApp business account
5. Configure real Telegram bot token
6. Monitor logs and metrics
7. Collect user feedback
8. Iterate based on feedback

Happy testing! 🚀
