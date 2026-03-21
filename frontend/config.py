"""
Frontend Configuration and Setup
Local configuration for WhatsApp and Telegram bot integration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paystack Configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY")

# WhatsApp Configuration (whatsapp-web.js)
WHATSAPP_SESSION_DIR = os.getenv("WHATSAPP_SESSION_DIR", "./data/whatsapp_sessions")
WHATSAPP_WEBHOOK_TOKEN = os.getenv("WHATSAPP_WEBHOOK_TOKEN", "football_predictions_token")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")

# Football API Configuration
FOOTBALL_API_BASE = os.getenv("FOOTBALL_API_BASE", "http://localhost:8000")

# Server Configuration
WHATSAPP_SERVER_HOST = os.getenv("WHATSAPP_SERVER_HOST", "0.0.0.0")
WHATSAPP_SERVER_PORT = int(os.getenv("WHATSAPP_SERVER_PORT", 5000))

TELEGRAM_SERVER_HOST = os.getenv("TELEGRAM_SERVER_HOST", "0.0.0.0")
TELEGRAM_SERVER_PORT = int(os.getenv("TELEGRAM_SERVER_PORT", 5001))

# Data Storage
DATA_DIR = os.getenv("DATA_DIR", "data")
CACHE_DIR = os.getenv("CACHE_DIR", "cache")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configuration Validation
def validate_configuration():
    """Validate that all required configurations are set"""
    warnings = []
    errors = []

    # Paystack is required
    if not PAYSTACK_SECRET_KEY:
        errors.append("PAYSTACK_SECRET_KEY not configured")
    if not PAYSTACK_PUBLIC_KEY:
        errors.append("PAYSTACK_PUBLIC_KEY not configured")

    # Telegram is optional but recommended
    if not TELEGRAM_BOT_TOKEN:
        warnings.append("TELEGRAM_BOT_TOKEN not configured - Telegram bot won't work")

    # WhatsApp session dir is created automatically on first run
    if not os.path.exists(WHATSAPP_SESSION_DIR):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"WhatsApp session directory will be created at: {WHATSAPP_SESSION_DIR}")

    return errors, warnings


if __name__ == "__main__":
    errors, warnings = validate_configuration()
    
    if errors:
        print("❌ Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("⚠️ Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("✅ All configurations are valid!")
