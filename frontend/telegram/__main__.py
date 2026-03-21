"""
Telegram Bot Launcher.

Run with: python -m frontend.telegram
"""
import logging
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_LINK = os.getenv('TELEGRAM_LINK', 'https://t.me/ProSokaAIbot')
WHATSAPP_LINK = os.getenv('WHATSAPP_LINK', 'https://wa.me/+254752573307')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not configured in .env")

tg_bot = TelegramBot()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    del context
    user_id = update.effective_user.id
    username = update.effective_user.username or 'User'

    response = await tg_bot.process_message(user_id, username, '/start')
    await update.message.reply_text(response, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    del context
    help_text = (
        "*Help and Commands*\n\n"
        "/start - Start the bot\n"
        "/help - Show this help\n\n"
        "*Plan Selection:*\n"
        "Reply with *1* for Basic (KSH 10, EPL only)\n"
        "Reply with *2* for Premium (KSH 30, all leagues)\n\n"
        "*Payment:*\n"
        "After choosing a plan, send your M-Pesa number in `+2547XXXXXXXX` format if the bot asks for it.\n"
        "Approve the STK prompt, then send *verify*.\n\n"
        "*Commands after payment:*\n"
        "Type *matches* - See available predictions\n"
        "Type *predict <id>* - Get detailed prediction\n\n"
        "*Also available:*\n"
        f"WhatsApp: {WHATSAPP_LINK}"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    del context
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or 'User'
    text = update.message.text or ''

    logger.info(f"Message from {username} ({user_id}): {text}")

    try:
        response = await tg_bot.process_message(user_id, username, text)
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as exc:
        logger.error(f"Error processing message: {exc}")
        await update.message.reply_text("Error processing your message. Please try again.", parse_mode='Markdown')


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a shared Telegram contact for payment processing."""
    del context
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or 'User'
    contact = update.message.contact
    phone_number = contact.phone_number if contact else ''

    logger.info(f"Contact shared by {username} ({user_id}): {phone_number}")

    try:
        response = await tg_bot.process_message(
            user_id,
            username,
            phone_number,
            phone_number=phone_number
        )
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as exc:
        logger.error(f"Error processing contact: {exc}")
        await update.message.reply_text("Error processing your contact. Please try again.", parse_mode='Markdown')


def main():
    """Start the Telegram bot."""
    print('\n' + '=' * 60)
    print('TELEGRAM BOT STARTING')
    print('=' * 60 + '\n')

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram bot initialized")
    logger.info(f"Bot link: {TELEGRAM_LINK}")
    logger.info("Starting polling...")

    application.run_polling()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\nTelegram bot stopped')
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Fatal error: {exc}")
        sys.exit(1)
