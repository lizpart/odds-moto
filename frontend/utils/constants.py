"""
Communication Constants and Configuration
"""

# Subscription Tiers
SUBSCRIPTION_TIERS = {
    "1": {
        "name": "League Specific",
        "price_ksh": 10,
        "description": "Get predictions for specific leagues or tournaments",
        "features": [
            "Specific league predictions",
            "Match analysis",
            "Betting odds"
        ]
    },
    "2": {
        "name": "All Leagues",
        "price_ksh": 30,
        "description": "Get predictions for all leagues and tournaments",
        "features": [
            "All league predictions",
            "Comprehensive analysis",
            "Complete betting odds",
            "Team statistics",
            "Head-to-head records"
        ]
    }
}

# Message Templates
GREETING_MESSAGE = """
⚽ *Welcome to Football Prediction Bot!*

Get AI-powered predictions and analysis for football matches.

Choose your package:

*1️⃣ League Specific (KSH 10)*
Get predictions for specific leagues or tournaments you choose.

*2️⃣ All Leagues (KSH 30)*
Get comprehensive predictions for ALL leagues and tournaments.

Reply with *1* or *2* to choose your package.

📱 Available on Telegram too: https://t.me/football_predictions_bot
"""

HELP_MESSAGE = """
*How to Use:*

1️⃣ Reply with your choice (1 or 2)
2️⃣ Complete payment via M-Pesa
3️⃣ Receive predictions immediately

For support, type *help*
"""

PACKAGE_SELECTED_MESSAGE_TEMPLATE = """
Great! You selected: *{package_name}*
Price: *KSH {price}*

Complete payment via M-Pesa to receive your predictions.

📱 Check out our Telegram channel for updates: https://t.me/football_predictions_bot
"""

PAYMENT_PENDING_MESSAGE = """
⏳ Processing your payment...

This may take a few seconds. Once verified, you'll receive your predictions.
"""

PAYMENT_CONFIRMED_MESSAGE = """
✅ Payment confirmed!

Here are your predictions:
"""

PAYMENT_FAILED_MESSAGE = """
❌ Payment verification failed.

Please try again or contact support.

📱 Join us on Telegram: https://t.me/football_predictions_bot
"""

INVALID_CHOICE_MESSAGE = """
Invalid choice. Please reply with *1* or *2*:

*1* - League Specific (KSH 10)
*2* - All Leagues (KSH 30)

📱 Also available on Telegram: https://t.me/football_predictions_bot
"""

TELEGRAM_LINK = "https://t.me/football_predictions_bot"

# API Endpoints
BACKEND_API_BASE = "http://localhost:8000"
FIXTURES_ENDPOINT = f"{BACKEND_API_BASE}/msg/fixtures"
ANALYZE_ENDPOINT = f"{BACKEND_API_BASE}/msg/analyze"
STATS_ENDPOINT = f"{BACKEND_API_BASE}/msg/stats"

# Paystack Configuration
PAYSTACK_SECRET_KEY = None  # Will be loaded from env
PAYSTACK_PUBLIC_KEY = None  # Will be loaded from env
PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"

# M-Pesa Prefix for Paystack
MPESA_PAYMENT_METHOD = "mpesa"

# Session/User State Management
# Legacy file constants retained for backward compatibility with docs/scripts.
USER_STATE_FILE = "data/user_states.json"
TRANSACTIONS_FILE = "data/transactions.json"

# Message Size Limits
MAX_MESSAGE_LENGTH = 4096  # WhatsApp message limit
TELEGRAM_MESSAGE_LIMIT = 4096

# Timeout Settings
PAYMENT_TIMEOUT_SECONDS = 300  # 5 minutes to complete payment
API_REQUEST_TIMEOUT = 30  # seconds
