# Frontend Architecture & Flow Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER COMMUNICATION LAYER                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐   │
│  │     WHATSAPP INTEGRATION     │    │   TELEGRAM INTEGRATION       │   │
│  ├──────────────────────────────┤    ├──────────────────────────────┤   │
│  │                              │    │                              │   │
│  │  ┌──────────────────────┐    │    │  ┌──────────────────────┐    │   │
│  │  │   WhatsApp Bot      │    │    │  │   Telegram Bot      │    │   │
│  │  │  (bot.py)           │    │    │  │  (bot.py)           │    │   │
│  │  │                      │    │    │  │                      │    │   │
│  │  │ • State Management   │    │    │  │ • Commands          │    │   │
│  │  │ • Choice Handler     │    │    │  │ • Help              │    │   │
│  │  │ • Payment Init       │    │    │  │ • Fixtures          │    │   │
│  │  │ • Verification      │    │    │  │ • Predict           │    │   │
│  │  │ • Prediction Send    │    │    │  │ • Stats             │    │   │
│  │  └──────────────────────┘    │    │  └──────────────────────┘    │   │
│  │           │                   │    │           │                  │   │
│  │           ↓                   │    │           ↓                  │   │
│  │  ┌──────────────────────┐    │    │  ┌──────────────────────┐    │   │
│  │  │  WhatsApp Server    │    │    │  │   Telegram Server    │    │   │
│  │  │  (server.py)        │    │    │  │   (server.py)        │    │   │
│  │  │  FastAPI            │    │    │  │   FastAPI            │    │   │
│  │  │  Port: 5000         │    │    │  │   Port: 5001         │    │   │
│  │  └──────────────────────┘    │    │  └──────────────────────┘    │   │
│  │           │                   │    │           │                  │   │
│  └───────────┼───────────────────┘    └───────────┼──────────────────┘   │
│              │                                    │                       │
└──────────────┼────────────────────────────────────┼──────────────────────┘
               │                                    │
       ┌───────▼────────────────────────────────────▼────────┐
       │     SHARED SERVICES & UTILITIES LAYER              │
       ├────────────────────────────────────────────────────┤
       │                                                    │
       │  ┌──────────────────┐  ┌────────────────────────┐ │
       │  │ State Manager    │  │ Message Formatter      │ │
       │  │ (state_mgr.py)   │  │ (msg_formatter.py)     │ │
       │  │                  │  │                        │ │
       │  │ • User Sessions  │  │ • Rich Formatting      │ │
       │  │ • Transactions   │  │ • Message Splitting    │ │
       │  │ • State Machine  │  │ • Platform Optimization│ │
       │  │ • Timeouts       │  │ • Emoji Support        │ │
       │  │ • History        │  │ • Telegram Links       │ │
       │  └──────────────────┘  └────────────────────────┘ │
       │                                                    │
       │  ┌──────────────────┐  ┌────────────────────────┐ │
       │  │ Payment Manager  │  │ API Client             │ │
       │  │ (paystack)       │  │ (api_client.py)        │ │
       │  │                  │  │                        │ │
       │  │ • Initialize     │  │ • Fixtures             │ │
       │  │ • Verify         │  │ • Predictions          │ │
       │  │ • M-Pesa        │  │ • Statistics           │ │
       │  │ • Records        │  │ • Error Handling       │ │
       │  │ • Transactions   │  │ • Timeouts             │ │
       │  └──────────────────┘  └────────────────────────┘ │
       │                                                    │
       └────────────────────────────────────────────────────┘
               │                          │
       ┌───────▼──────────────┬──────────▼──────────┐
       │   PAYSTACK GATEWAY   │   FOOTBALL API      │
       │   (paystack.co)      │   (localhost:8000)  │
       │                      │                     │
       │ • Initialize Payment │ • /msg/fixtures    │
       │ • Verify Payment     │ • /msg/analyze     │
       │ • M-Pesa            │ • /msg/stats       │
       └───────┬──────────────┴──────────┬──────────┘
               │                        │
               ↓                        ↓
        ┌─────────────┐         ┌──────────────┐
        │  M-Pesa    │         │ Football DB  │
        │  Network   │         │ Real-time    │
        └─────────────┘         │ Data         │
                                └──────────────┘
```

---

## Communication Flow Diagram

### WhatsApp Complete Flow

```
┌─────────┐
│  User   │
└────┬────┘
     │ Sends "Hi" on WhatsApp
     ↓
┌──────────────────────────────────┐
│  WhatsApp Webhook Received        │
│  Extract: from=254712345678       │
│  Extract: text="Hi"               │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  Normalize Phone Number           │
│  254712345678 → 254712345678      │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  Check User State                 │
│  State = INITIAL                  │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  handle_start()                   │
│  ✓ Store phone number             │
│  ✓ Set state = GREETING_SENT      │
└────┬─────────────────────────────┘
     │
     ↓
     │ Send Greeting Message
     │ "Choose: 1) KSH 10  2) KSH 30"
     ↓
┌─────────┐
│  User   │
└────┬────┘
     │ Sends "1"
     ↓
┌──────────────────────────────────┐
│  Check State = AWAITING_CHOICE    │
│  validate: 1 ∈ ["1", "2"] ✓      │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  handle_choice()                  │
│  Choice: "1" (KSH 10)             │
│  Phone: 254712345678              │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  payment_manager.initiate()       │
│                                   │
│  POST to Paystack:                │
│  {                                │
│    "amount": 1000,  (KSH 10)      │
│    "phone": "254712345678",       │
│    "metadata": {                  │
│      "user_id": "254712345678",   │
│      "package": "1"               │
│    }                              │
│  }                                │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  Paystack Response:               │
│  {                                │
│    "reference": "pay_xxx",        │
│    "authorization_url": "..."     │
│  }                                │
└────┬─────────────────────────────┘
     │
     ↓
│ Store transaction record
│ Update user state = PAYMENT_INITIATED
└────┬─────────────────────────────┘
     │
     ↓
     │ Send: "M-Pesa prompt coming..."
     │       "Reference: pay_xxx"
     ↓
┌─────────┐
│  User   │ ← M-Pesa prompt sent to 254712345678
└────┬────┘
     │ Completes M-Pesa payment
     ↓
┌──────────────────────────────────┐
│  User replies "verify" (or auto)  │
└────┬─────────────────────────────┘
     │
     ↓
┌──────────────────────────────────┐
│  payment_manager.verify()         │
│  Reference: pay_xxx               │
│  Check Paystack: payment_status   │
└────┬─────────────────────────────┘
     │
     ├─→ Payment Success
     │   ↓
     │   Set state = PAYMENT_CONFIRMED
     │   ↓
     │   fetch_predictions()
     │   ↓
     │   format_predictions()
     │   ↓
     │   Send predictions to user
     │
     └─→ Payment Failed
         ↓
         Set state = PAYMENT_FAILED
         ↓
         Send error message
```

### Telegram Command Flow

```
/start  → handle_start() → Show welcome
  ↓
/help   → handle_help()  → Show help menu
  ↓
/fixtures → handle_fixtures() → Fetch & format today's matches
  ↓
/predict <id> → handle_prediction(id) → Fetch & format prediction
  ↓
/stats <id> → handle_stats(id) → Fetch & format statistics
```

---

## State Machine Diagram

```
                    ┌─────────────┐
                    │   INITIAL   │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
      /start            User sends         Message
       or Hi            "Hi" first          timeout
         │                 │                 │
         ↓                 ↓                 │
    ┌──────────────────────────────┐        │
    │   GREETING_SENT (5 min)      │        │
    │   [State: Greeting shown]    │        │
    └────────────────┬─────────────┘        │
                     │                      │
         ┌───────────┴─────────────┐        │
         │                         │        │
       Valid (1|2)          Invalid choice  │
         │                         │        │
         ↓                         ↓        │
    ┌──────────────────────────────┐        │
    │   CHOICE_RECEIVED            │        │
    │   [Choice: 1 or 2]           │        │
    └────────────────┬─────────────┘        │
                     │                      │
                  Initiate                  │
                  Payment                   │
                     │                      │
                     ↓                      │
    ┌──────────────────────────────┐        │
    │   PAYMENT_INITIATED          │        │
    │   [M-Pesa prompt sent]       │        │
    └────────────────┬─────────────┘        │
                     │                      │
    ┌────────────────▼─────────────┐        │
    │   PAYMENT_PENDING (5 min)    │        │
    │   [Awaiting verification]    │        │
    └────────┬───────────┬─────────┘        │
             │           │                  │
       Verified      Failed or             │
         (✓)         Timeout               │
             │           │                  │
             ↓           ↓                  │
    ┌─────────────┐  ┌──────────────┐      │
    │  PAYMENT    │  │  PAYMENT     │      │
    │  CONFIRMED  │  │  FAILED      │      │
    └──────┬──────┘  └──────┬───────┘      │
           │                │              │
        Fetch            Show Error     (←─┘
        Predictions      Msg
           │                │
           ↓                ↓
    ┌─────────────┐  ┌──────────────┐
    │ PREDICTIONS │  │   AWAITING   │
    │    SENT     │  │   RETRY      │
    │   (Done)    │  │              │
    └─────────────┘  └──────────────┘
         │                  │
         └──────┬───────────┘
                │
           After 5 min
            (timeout)
                │
                ↓
           ┌──────────────────┐
           │ SESSION_EXPIRED  │
           │ (Reset session)  │
           └──────────────────┘
```

---

## Data Flow Diagram

```
User Input
    ↓
┌─────────────────────────────────────────┐
│  Webhook Server                         │
│  (receive_message / handle_update)      │
│  ✓ Extract user_id                      │
│  ✓ Extract phone_number                 │
│  ✓ Extract message_text                 │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  Phone Number Normalizer                │
│  Input: 0712345678                      │
│  Output: 254712345678                   │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  State Manager                          │
│  • Check current state                  │
│  • Check session expiration             │
│  • Load user metadata                   │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  Message Router                         │
│  • Route by state                       │
│  • Route by command                     │
│  • Call appropriate handler             │
└────────────┬────────────────────────────┘
             │
             ├─→ Start Handler
             │   ├─→ Set initial state
             │   └─→ Return greeting
             │
             ├─→ Choice Handler
             │   ├─→ Validate choice (1|2)
             │   ├─→ Call Payment Manager
             │   ├─→ Store state
             │   └─→ Return confirmation
             │
             ├─→ Verify Handler
             │   ├─→ Check Paystack
             │   ├─→ Update state
             │   ├─→ Fetch predictions
             │   └─→ Return predictions
             │
             └─→ Help Handler
                 └─→ Return help text
                 
             ↓
┌─────────────────────────────────────────┐
│  Message Formatter                      │
│  • Format response                      │
│  • Add emojis & styling                 │
│  • Split long messages                  │
│  • Add Telegram link                    │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  Send Response                          │
│  • Send via WhatsApp Cloud API or       │
│  • Send via Telegram Bot API            │
└────────────┬────────────────────────────┘
             │
             ↓
        User Receives Message
```

---

## File Interaction Diagram

```
┌──────────────────────────────────────────────────────────┐
│                   run.py (Main Entry)                    │
│                  Launches both bots                      │
└────────┬─────────────────────────────┬────────┬──────────┘
         │                             │        │
         ↓                             ↓        ↓
    ┌────────────┐          ┌────────────┐  ┌─────────┐
    │ whatsapp/  │          │ telegram/  │  │ config  │
    │ server.py  │          │ server.py  │  │ .py     │
    │ (FastAPI)  │          │ (FastAPI)  │  └─────────┘
    └────┬───────┘          └────┬───────┘
         │                        │
         ↓                        ↓
    ┌────────────┐          ┌────────────┐
    │ whatsapp/  │          │ telegram/  │
    │ bot.py     │          │ bot.py     │
    │            │          │            │
    │ • process  │          │ • process  │
    │ • handlers │          │ • commands │
    └────┬───────┘          └────┬───────┘
         │                        │
         └────────────┬───────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ↓            ↓            ↓
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ utils/   │ │payments/ │ │ data/    │
   │constants │ │paystack  │ │user_st.. │
   │messages  │ │_processor│ │trans...  │
   │formatting│ │          │ │          │
   │state_mgr │ │Initialize│ │Save/Load │
   │api_client│ │Verify    │ │Records   │
   └──────────┘ └──────────┘ └──────────┘
        │            │             │
        └────────────┼─────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         ↓           ↓           ↓
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │Football │ │Paystack │ │ User    │
    │ API     │ │ API     │ │ Storage │
    │ local   │ │ Online  │ │ Local   │
    │ 8000    │ │ paystack│ │ JSON    │
    └─────────┘ └─────────┘ └─────────┘
```

---

## Phone Number Flow

```
WhatsApp/Telegram Input
    │
    ├─→ "254712345678"  → 254712345678  ✓
    ├─→ "0712345678"    → 254712345678  ✓
    ├─→ "712345678"     → 254712345678  ✓
    └─→ "+254712345678" → 254712345678  ✓
    
         │
         ↓
   Validation
    │
    ├─→ 12 digits? ✓
    ├─→ Starts with 254? ✓
    └─→ All digits? ✓
    
         │
         ↓
   Paystack
    │
    └─→ {"phone": "254712345678"}
         │
         ↓
    M-Pesa Prompt sent to user's phone
```

---

## Summary

This architecture provides:
- ✅ Modular, maintainable code
- ✅ Clear separation of concerns
- ✅ Scalable design
- ✅ Flexible payment integration
- ✅ Robust error handling
- ✅ Complete state management

Perfect for production deployment!
