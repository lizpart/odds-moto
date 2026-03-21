"""
Frontend Launcher - Start WhatsApp and Telegram bots
"""
import os
import sys
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
FRONTEND_DIR = Path(__file__).parent
PROJECT_DIR = FRONTEND_DIR.parent

# Add project root to Python path so we can import frontend package
sys.path.insert(0, str(PROJECT_DIR))

# Load environment variables
load_dotenv(FRONTEND_DIR / ".env")

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG to see more details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_config():
    """Validate required configuration"""
    from frontend.config import validate_configuration
    
    errors, warnings = validate_configuration()
    
    if errors:
        print("\n❌ Configuration Errors:")
        for error in errors:
            print(f"   {error}")
        print("\n⚠️ Please set up your .env file first!")
        print("   Copy .env.example to .env and fill in your credentials.\n")
        return False
    
    if warnings:
        print("\n⚠️ Configuration Warnings:")
        for warning in warnings:
            print(f"   {warning}")
        print()
    
    return True


def start_whatsapp_bot():
    """Start WhatsApp bot using whatsapp-web.js (Selenium)"""
    logger.info("Starting WhatsApp bot with whatsapp-web.js...")
    logger.info("Make sure Chrome/Chromium is installed on your system")
    
    from frontend.whatsapp.webjs_bot import WhatsAppWebBot
    
    try:
        session_dir = FRONTEND_DIR / "data" / "whatsapp_sessions"
        bot = WhatsAppWebBot(session_dir=str(session_dir))
        logger.info(f"Session directory: {session_dir}")
        
        # Connect to WhatsApp Web
        if bot.connect():
            logger.info("✅ Connected successfully! Starting message listener...")
            # Keep the bot running and listening for messages
            bot.listen()
        else:
            logger.error("Failed to connect to WhatsApp Web")
            
    except KeyboardInterrupt:
        logger.info("\nWhatsApp bot stopped by user")
    except Exception as e:
        logger.error(f"Error running WhatsApp bot: {e}")
        raise


def start_telegram_bot():
    """Start Telegram bot"""
    logger.info("Starting Telegram bot...")
    
    from frontend.telegram.server import app
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5001,
        log_level="info"
    )


def start_both():
    """Start both bots using subprocesses"""
    import time
    
    # Create data directory if it doesn't exist
    data_dir = FRONTEND_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    
    logger.info("Starting Frontend Services...")
    logger.info("Note: WhatsApp uses whatsapp-web.js (QR code auth, not webhook server)")
    logger.info(f"Telegram Bot: http://localhost:5001")
    logger.info(f"Data Directory: {data_dir}")
    
    # Start WhatsApp bot as a separate process
    whatsapp_process = subprocess.Popen(
        [
            sys.executable, "-c",
            "import sys; sys.path.insert(0, r'" + str(PROJECT_DIR) + "'); from frontend.run import start_whatsapp_bot; start_whatsapp_bot()"
        ],
        cwd=PROJECT_DIR
    )
    
    time.sleep(2)
    
    # Start Telegram bot
    telegram_process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "frontend.telegram.server:app",
            "--host", "0.0.0.0",
            "--port", "5001",
            "--reload"
        ],
        cwd=PROJECT_DIR
    )
    
    logger.info("\n✅ Both bots started successfully!")
    logger.info("\nServices running:")
    logger.info("  WhatsApp: Direct connection with QR code (check console)")
    logger.info("  Telegram: http://localhost:5001")
    logger.info("  Football API: http://localhost:8000")
    
    logger.info("\nCtrl+C to stop services")
    
    try:
        whatsapp_process.wait()
        telegram_process.wait()
    except KeyboardInterrupt:
        logger.info("\nStopping services...")
        whatsapp_process.terminate()
        telegram_process.terminate()
        whatsapp_process.wait()
        telegram_process.wait()
        logger.info("Services stopped.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Frontend Bot Launcher")
    parser.add_argument(
        "--service",
        choices=["whatsapp", "telegram", "both"],
        default="both",
        help="Which service to start"
    )
    
    args = parser.parse_args()
    
    # Validate configuration first
    if not validate_config():
        sys.exit(1)
    
    try:
        if args.service == "whatsapp":
            start_whatsapp_bot()
        elif args.service == "telegram":
            start_telegram_bot()
        else:
            start_both()
    except KeyboardInterrupt:
        logger.info("\nServices stopped.")
    except Exception as e:
        logger.error(f"Error starting services: {str(e)}")
        sys.exit(1)
