"""
WhatsApp Server - FastAPI server for WhatsApp webhook integration
Implements webhook for receiving and responding to WhatsApp messages
"""
import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import json
from datetime import datetime

from frontend.whatsapp.bot import WhatsAppBot

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="WhatsApp Football Predictions Bot",
    description="WhatsApp bot for football match predictions and betting analysis"
)

# Initialize WhatsApp Bot
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC = os.getenv("PAYSTACK_PUBLIC_KEY")
BACKEND_API = os.getenv("FOOTBALL_API_BASE", "http://localhost:8000")

if not PAYSTACK_SECRET or not PAYSTACK_PUBLIC:
    logger.warning("Paystack API keys not configured. Please set PAYSTACK_SECRET_KEY and PAYSTACK_PUBLIC_KEY")

whatsapp_bot = WhatsAppBot(
    paystack_secret=PAYSTACK_SECRET or "test_secret",
    paystack_public=PAYSTACK_PUBLIC or "test_public",
    api_base_url=BACKEND_API
)

# WhatsApp webhook configuration
WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_TOKEN", "football_predictions_token")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "whatsapp-bot",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    WhatsApp webhook verification
    
    WhatsApp sends GET request with:
    - hub.mode: "subscribe"
    - hub.challenge: verification token
    - hub.verify_token: token we set
    """
    try:
        hub_mode = request.query_params.get("hub.mode")
        hub_challenge = request.query_params.get("hub.challenge")
        hub_verify_token = request.query_params.get("hub.verify_token")

        if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
            logger.info("WhatsApp webhook verified successfully")
            return PlainTextResponse(hub_challenge)
        else:
            logger.error("Invalid webhook verification attempt")
            raise HTTPException(status_code=403, detail="Forbidden")

    except Exception as e:
        logger.error(f"Webhook verification error: {str(e)}")
        raise HTTPException(status_code=400, detail="Bad Request")


@app.post("/webhook")
async def receive_message(request: Request):
    """
    Handle incoming WhatsApp messages
    
    Expected payload from WhatsApp:
    {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "1234567890",
                        "body": "message content"
                    }]
                }
            }]
        }]
    }
    """
    try:
        data = await request.json()
        
        # Log incoming webhook
        logger.info(f"Received webhook: {json.dumps(data, indent=2)}")

        # Extract message data
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return JSONResponse({"status": "ok"})

        message = messages[0]
        user_id = message.get("from", "unknown")
        phone_number = user_id  # In WhatsApp, phone number is the user ID (from)
        message_text = message.get("body", "")

        logger.info(f"Message from {user_id} (Phone: {phone_number}): {message_text}")

        # Process message with WhatsApp phone number
        response_text = await whatsapp_bot.process_message(
            user_id=user_id,
            phone_number=phone_number,  # WhatsApp phone number for payment processing
            message_text=message_text
        )

        # Split long messages
        response_messages = whatsapp_bot.message_formatter.split_long_message(response_text)

        # Send responses
        for msg in response_messages:
            await send_whatsapp_message(user_id, msg)

        return JSONResponse({"status": "ok", "message_sent": True})

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def send_whatsapp_message(to_number: str, message_text: str):
    """
    Send WhatsApp message via WhatsApp Cloud API
    
    Note: This requires WhatsApp Business Account configuration
    You'll need to:
    1. Create a WhatsApp Business Account
    2. Get your Phone Number ID
    3. Get your Access Token
    4. Use the WhatsApp Cloud API to send messages
    
    Example implementation:
    """
    try:
        # TODO: Implement actual WhatsApp Cloud API integration
        # This is a placeholder - you'll need to use your WhatsApp Business Account credentials
        
        whatsapp_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        whatsapp_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

        if not whatsapp_phone_id or not whatsapp_token:
            logger.warning("WhatsApp credentials not configured. Message not sent.")
            return

        import requests
        
        url = f"https://graph.instagram.com/v18.0/{whatsapp_phone_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {whatsapp_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {
                "body": message_text
            }
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Message sent to {to_number}")
        else:
            logger.error(f"Failed to send message: {response.text}")

    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")


@app.post("/send_message")
async def send_message_endpoint(request: Request):
    """
    Manual endpoint to send test messages
    
    Useful for testing without actual WhatsApp
    
    Request body:
    {
        "to": "1234567890",
        "message": "Your message"
    }
    """
    try:
        data = await request.json()
        to_number = data.get("to")
        message = data.get("message")

        if not to_number or not message:
            raise HTTPException(status_code=400, detail="Missing 'to' or 'message'")

        await send_whatsapp_message(to_number, message)

        return JSONResponse({
            "status": "ok",
            "message": "Message sent",
            "to": to_number
        })

    except Exception as e:
        logger.error(f"Error in send_message endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "WhatsApp Football Predictions Bot",
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
    uvicorn.run(app, host="0.0.0.0", port=5000)
