"""
Telegram Server - FastAPI server for Telegram bot webhook
"""
import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json
from datetime import datetime

from frontend.telegram.bot import TelegramBot

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Telegram Football Predictions Bot",
    description="Telegram bot for football predictions"
)

# Initialize Telegram Bot
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC = os.getenv("PAYSTACK_PUBLIC_KEY")
BACKEND_API = os.getenv("FOOTBALL_API_BASE", "http://localhost:8000")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN not configured")

telegram_bot = TelegramBot()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "telegram-bot",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/webhook")
async def receive_update(request: Request):
    """
    Handle incoming Telegram updates
    
    Expected payload from Telegram:
    {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "date": 1234567890,
            "chat": {
                "id": 123456,
                "type": "private",
                "username": "username"
            },
            "from": {
                "id": 123456,
                "is_bot": false,
                "username": "username"
            },
            "text": "message content"
        }
    }
    """
    try:
        data = await request.json()
        
        logger.info(f"Received Telegram update: {json.dumps(data, indent=2)}")

        # Extract message
        message = data.get("message")
        if not message:
            return JSONResponse({"status": "ok"})

        user_id = str(message.get("from", {}).get("id", "unknown"))
        username = message.get("from", {}).get("username", "unknown")
        message_text = message.get("text", "")
        contact = message.get("contact") or {}
        phone_number = contact.get("phone_number")

        if phone_number:
            logger.info(f"Contact shared by {username} ({user_id}): {phone_number}")
        else:
            logger.info(f"Message from {username} ({user_id}): {message_text}")

        effective_text = message_text or phone_number or ""

        # Process message
        response_text = await telegram_bot.process_message(
            user_id=user_id,
            username=username,
            text=effective_text,
            phone_number=phone_number
        )

        # Send response via Telegram API
        await send_telegram_message(user_id, response_text)

        return JSONResponse({"status": "ok"})

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        return JSONResponse({"status": "error"}, status_code=400)
    except Exception as e:
        logger.error(f"Error processing Telegram update: {str(e)}")
        return JSONResponse({"status": "error"}, status_code=500)


async def send_telegram_message(chat_id: str, text: str):
    """
    Send message via Telegram Bot API
    
    Requires TELEGRAM_BOT_TOKEN environment variable
    """
    try:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token not configured")
            return

        import requests

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info(f"Message sent to Telegram user {chat_id}")
        else:
            logger.error(f"Failed to send Telegram message: {response.text}")

    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")


@app.post("/send_message")
async def send_message_endpoint(request: Request):
    """
    Manual endpoint to send test messages
    
    Request body:
    {
        "chat_id": "123456",
        "text": "Your message"
    }
    """
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        text = data.get("text")

        if not chat_id or not text:
            raise HTTPException(status_code=400, detail="Missing 'chat_id' or 'text'")

        await send_telegram_message(str(chat_id), text)

        return JSONResponse({
            "status": "ok",
            "message": "Message sent",
            "chat_id": chat_id
        })

    except Exception as e:
        logger.error(f"Error in send_message endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Telegram Football Predictions Bot",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "webhook": "/webhook",
            "send_message": "/send_message"
        },
        "documentation": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
