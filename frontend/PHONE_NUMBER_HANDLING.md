# Phone Number Handling Guide

## Overview

The bots automatically use the phone number from WhatsApp or Telegram to process payments via Paystack.

## WhatsApp Phone Numbers

### Automatic Extraction
- WhatsApp phone numbers are automatically extracted from incoming messages
- The `from` field in WhatsApp webhook contains the user's phone number
- Format: International phone number (e.g., `254712345678`)

### Normalization
The system automatically normalizes phone numbers to support multiple formats:

| Format | Example | Result |
|--------|---------|--------|
| Local (9 digits) | `712345678` | `254712345678` |
| Local with 0 | `0712345678` | `254712345678` |
| International | `254712345678` | `254712345678` |
| With + prefix | `+254712345678` | `254712345678` |

### Implementation
Located in `frontend/whatsapp/bot.py`:

```python
@staticmethod
def _normalize_phone_number(phone_number: str) -> str:
    """Normalize phone number for Paystack payment"""
    # Removes special characters
    # Ensures format starts with country code (254 for Kenya)
    # Handles multiple input formats
```

## Telegram Phone Numbers

### Collection Flow

Telegram doesn't include phone numbers in messages by default. Two options:

#### Option 1: User Provides Phone Number
User can message their phone number:
```
User: 0712345678
Bot: Payment will be sent to: 0712345678
```

#### Option 2: Contact Sharing (Recommended)
Telegram supports contact sharing button:
```python
# Request contact: 
# "Send your phone number"
# → User clicks "Share Contact"
# → Bot receives phone number
```

### Implementation
In `frontend/telegram/bot.py`, phone numbers can be:
1. **Extracted from message text** - User types their number
2. **Received from contact share** - User shares contact
3. **Retrieved from Telegram contact** - If user has shared previously

## Payment Processing Flow

### WhatsApp
```
1. User sends message on WhatsApp
   ↓
2. Phone number extracted from "from" field
   ↓
3. Phone number normalized (e.g., 0712345678 → 254712345678)
   ↓
4. Stored in user state for payment processing
   ↓
5. Passed to Paystack when initializing payment
   ↓
6. M-Pesa prompt sent to that number
```

### Telegram
```
1. User sends message on Telegram
   ↓
2. Bot asks: "Please provide your phone number"
   ↓
3. User responds with phone number or shares contact
   ↓
4. Phone number normalized
   ↓
5. Stored for payment processing
   ↓
6. Passed to Paystack when initializing payment
   ↓
7. M-Pesa prompt sent to that number
```

## Error Handling

### Invalid Phone Numbers
- System validates phone number format
- Must be valid Kenyan number (254XXXXXXXXX)
- Error message: "Invalid phone number format"

### Phone Number Mismatch
- If user provides number that can't be normalized, bot:
  1. Logs the issue
  2. Asks user to verify number
  3. Provides format examples

## Testing

### Test with WhatsApp Phone Numbers

```bash
# Local format
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "712345678",
            "body": "Hi"
          }]
        }
      }]
    }]
  }'

# International format
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "254712345678",
            "body": "Hi"
          }]
        }
      }]
    }]
  }'
```

### Test with Telegram Phone Numbers

```bash
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "from": {
        "id": 123456,
        "username": "testuser"
      },
      "text": "0712345678"
    }
  }'
```

## Paystack Integration

### Phone Number Requirements
- Paystack requires valid Kenyan phone number
- Format must be: `254XXXXXXXXX` (12 digits with country code)
- System automatically normalizes before sending to Paystack

### Example Payment Initialization
```python
# Bot sends to Paystack:
{
    "email": "user_12345@footballpred.com",
    "amount": 1000,  # KSH 10 (in cents)
    "phone": "254712345678",  # Normalized phone number
    "metadata": {
        "user_id": "254712345678",
        "package": "1"
    }
}
```

## Phone Number Storage

### User State
Phone number stored in user state with transaction reference:
```json
{
    "state": "payment_pending",
    "timestamp": "2025-12-29T10:30:00",
    "metadata": {
        "phone_number": "254712345678",
        "choice": "1",
        "reference": "pay_xxx"
    }
}
```

### Transaction Record
Phone number also stored in transaction history:
```json
{
    "user_id": "254712345678",
    "transaction_id": "pay_xxx",
    "amount": 10,
    "phone": "254712345678",
    "status": "pending",
    "timestamp": "2025-12-29T10:30:00"
}
```

## Security Considerations

1. **Phone numbers are validated** - Only valid Kenyan numbers accepted
2. **Stored securely** - In local JSON files with restricted access
3. **Used only for payments** - Not shared or sold
4. **Logged carefully** - Full numbers only in system logs for debugging
5. **HTTPS required** - In production for data in transit protection

## Troubleshooting

### Phone Number Not Working for M-Pesa
- ✅ Check format is valid Kenyan number
- ✅ Verify M-Pesa is enabled on that number
- ✅ Check Paystack account has M-Pesa enabled
- ✅ Verify Paystack API keys are correct

### Different Numbers in Payment vs WhatsApp
- Check if user changed phone number between sessions
- Verify phone number normalization is working correctly
- Check transaction logs for what number was used

### Contact Sharing in Telegram Not Working
- Telegram contact sharing is optional
- Fall back to manual phone number entry
- Ensure bot has permission to receive contacts
