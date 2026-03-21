"""
WhatsApp Bot Integration using WhatsApp-JS Library
Handles user communication via WhatsApp
"""
import logging
import json
from typing import Dict, Optional, Callable, Any
from datetime import datetime

from frontend.utils.constants import (
    GREETING_MESSAGE, HELP_MESSAGE, INVALID_CHOICE_MESSAGE,
    PACKAGE_SELECTED_MESSAGE_TEMPLATE, SUBSCRIPTION_TIERS,
    PAYMENT_PENDING_MESSAGE, PAYMENT_CONFIRMED_MESSAGE,
    PAYMENT_FAILED_MESSAGE, TELEGRAM_LINK
)
from frontend.utils.message_formatter import MessageFormatter, LeagueFormatter
from frontend.utils.state_manager import UserStateManager, UserState
from frontend.utils.api_client import FootballAPIClient
from frontend.payments.paystack_processor import PaymentManager

logger = logging.getLogger(__name__)


class WhatsAppBot:
    """WhatsApp bot for football predictions"""

    def __init__(self, paystack_secret: str, paystack_public: str, 
                 api_base_url: str = "http://localhost:8000"):
        """
        Initialize WhatsApp bot
        
        Args:
            paystack_secret: Paystack secret API key
            paystack_public: Paystack public API key
            api_base_url: Football API base URL
        """
        self.state_manager = UserStateManager()
        self.payment_manager = PaymentManager(paystack_secret, paystack_public)
        self.api_client = FootballAPIClient(base_url=api_base_url)
        self.message_formatter = MessageFormatter()
        
        # Message handlers
        self.handlers: Dict[str, Callable] = {
            "start": self.handle_start,
            "help": self.handle_help,
            "choice": self.handle_choice,
            "verify": self.handle_verify_payment,
            "fixtures": self.handle_fixtures,
            "predict": self.handle_predictions,
            "stats": self.handle_stats,
        }

    async def process_message(self, user_id: str, phone_number: str, 
                             message_text: str) -> str:
        """
        Process incoming WhatsApp message
        
        Args:
            user_id: User identifier
            phone_number: User's WhatsApp phone number (for payment processing)
            message_text: Incoming message content
            
        Returns:
            Response message to send back
        """
        try:
            message_lower = message_text.strip().lower()
            
            # Normalize phone number (remove special characters)
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Check for session expiration
            if self.state_manager.is_session_expired(user_id):
                self.state_manager.reset_user_session(user_id)
                return GREETING_MESSAGE

            # Check current user state
            user_state_data = self.state_manager.get_user_state(user_id)
            current_state = UserState(user_state_data['state']) if user_state_data else UserState.INITIAL

            # Route message based on current state
            if current_state == UserState.INITIAL or current_state is None:
                return await self.handle_start(user_id, normalized_phone, message_text)
            
            elif current_state == UserState.GREETING_SENT or current_state == UserState.AWAITING_CHOICE:
                # User should send 1 or 2
                if message_lower in ["1", "2"]:
                    return await self.handle_choice(user_id, normalized_phone, message_lower)
                else:
                    self.state_manager.set_user_state(user_id, UserState.AWAITING_CHOICE, phone_number=normalized_phone)
                    return INVALID_CHOICE_MESSAGE

            elif current_state == UserState.PAYMENT_PENDING:
                # Check if they're verifying payment
                if message_lower.startswith("verify"):
                    return await self.handle_verify_payment(user_id)
                else:
                    return PAYMENT_PENDING_MESSAGE

            elif current_state == UserState.PAYMENT_CONFIRMED:
                # Get and send predictions
                return await self.send_user_predictions(user_id)

            # Default: send help
            if message_lower == "help":
                return HELP_MESSAGE
            
            return GREETING_MESSAGE

        except Exception as e:
            logger.error(f"Error processing message from user {user_id}: {str(e)}")
            return "An error occurred. Please try again later. 📱 Support: " + TELEGRAM_LINK
    
    @staticmethod
    def _normalize_phone_number(phone_number: str) -> str:
        """
        Normalize phone number for Paystack payment
        Remove special characters and ensure proper format
        Supports:
        - Local format: 712345678 (9 digits)
        - Local format: 0712345678 (10 digits with 0)
        - International: 254712345678 (12 digits with country code)
        - With +: +254712345678
        """
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Kenyan numbers: ensure starts with 254 (country code)
        if len(digits_only) == 9:  # Local format: 712345678
            digits_only = '254' + digits_only
        elif len(digits_only) == 10:  # Format: 0712345678
            if digits_only.startswith('0'):
                digits_only = '254' + digits_only[1:]
        elif len(digits_only) == 12:  # Format: 254712345678
            pass  # Already in correct format
        
        return digits_only

    async def handle_start(self, user_id: str, phone_number: str, 
                          message_text: str = "") -> str:
        """Handle initial start message"""
        self.state_manager.set_user_state(user_id, UserState.GREETING_SENT, phone_number=phone_number)
        return GREETING_MESSAGE

    async def handle_help(self, user_id: str) -> str:
        """Handle help request"""
        return HELP_MESSAGE

    async def handle_choice(self, user_id: str, phone_number: str, choice: str) -> str:
        """
        Handle package selection (1 or 2)
        
        Args:
            user_id: User identifier
            phone_number: User's WhatsApp phone number (normalized for Paystack)
            choice: Selected package ("1" or "2")
        """
        try:
            if choice not in ["1", "2"]:
                return INVALID_CHOICE_MESSAGE

            # Store choice
            self.state_manager.set_user_choice(user_id, choice)
            
            # Get package info
            package_info = SUBSCRIPTION_TIERS[choice]
            amount_ksh = package_info['price_ksh']
            package_name = package_info['name']

            # Create response message
            response = PACKAGE_SELECTED_MESSAGE_TEMPLATE.format(
                package_name=package_name,
                price=amount_ksh
            )

            # Initiate payment with WhatsApp phone number
            payment_result = self.payment_manager.initiate_user_payment(
                user_id=user_id,
                package=choice,
                phone_number=phone_number  # Using WhatsApp phone number (normalized)
            )

            if payment_result.get('success'):
                self.state_manager.save_transaction(
                    user_id=user_id,
                    transaction_id=payment_result["reference"],
                    amount=amount_ksh,
                    package=choice,
                    status="pending",
                )
                # Update user state to payment pending
                self.state_manager.set_user_state(
                    user_id,
                    UserState.PAYMENT_INITIATED,
                    choice=choice,
                    phone_number=phone_number,
                    reference=payment_result['reference']
                )

                response += f"\n\n📲 {payment_result['display_text']}\n"
                response += f"Reference: {payment_result['reference']}\n\n"
                response += "After payment, reply with: *verify*"

                # Update to payment pending after short delay
                self.state_manager.set_user_state(
                    user_id,
                    UserState.PAYMENT_PENDING,
                    choice=choice,
                    reference=payment_result['reference'],
                    phone_number=phone_number
                )
            else:
                response = f"❌ Payment initiation failed: {payment_result.get('error')}\n"
                response += "Please try again or contact support."

            return response

        except Exception as e:
            logger.error(f"Error handling choice for user {user_id}: {str(e)}")
            logger.error(f"Phone number used: {phone_number}")
            return "Error processing your choice. Please try again."

    async def handle_verify_payment(self, user_id: str) -> str:
        """Handle payment verification"""
        try:
            user_state = self.state_manager.get_user_state(user_id)
            if not user_state:
                return "Session expired. Please start over."

            reference = user_state.get('metadata', {}).get('reference')
            if not reference:
                return "No payment reference found. Please try again."

            # Verify payment with Paystack
            result = self.payment_manager.verify_user_payment(
                reference=reference,
                platform="whatsapp",
                platform_user_id=str(user_id),
                phone_number=user_state.get("metadata", {}).get("phone_number"),
            )

            if result.get('success') and result.get('verified'):
                self.state_manager.update_transaction(reference, "completed")
                # Update user state to payment confirmed
                self.state_manager.set_user_state(
                    user_id,
                    UserState.PAYMENT_CONFIRMED,
                    reference=reference,
                    choice=result.get('package')
                )

                # Get and return predictions
                return await self.send_user_predictions(user_id)
            else:
                self.state_manager.update_transaction(
                    reference,
                    "failed",
                    error=result.get("error"),
                    gateway_response=result.get("gateway_response"),
                )
                self.state_manager.set_user_state(
                    user_id,
                    UserState.PAYMENT_FAILED,
                    reference=reference
                )
                return PAYMENT_FAILED_MESSAGE

        except Exception as e:
            logger.error(f"Error verifying payment for user {user_id}: {str(e)}")
            return "Error verifying payment. Please try again."

    async def send_user_predictions(self, user_id: str) -> str:
        """Send predictions based on user's package selection"""
        try:
            user_state = self.state_manager.get_user_state(user_id)
            choice = user_state.get('metadata', {}).get('choice', '2')

            if choice == "1":
                # Get league-specific predictions
                # For now, default to Premier League (39)
                predictions = self.api_client.get_league_predictions(league_id=39)
            else:
                # Get all predictions
                predictions = self.api_client.get_all_today_predictions()

            if not predictions.get('success'):
                return f"❌ Error fetching predictions: {predictions.get('error')}"

            # Format predictions into messages
            response = PAYMENT_CONFIRMED_MESSAGE + "\n\n"

            prediction_list = predictions.get('predictions', [])
            if not prediction_list:
                response += "No matches available today."
            else:
                for pred in prediction_list[:5]:  # Limit to 5
                    response += self.message_formatter.format_prediction(pred) + "\n\n"

            response += f"📱 Join Telegram: {TELEGRAM_LINK}"

            # Update user state
            self.state_manager.set_user_state(user_id, UserState.PREDICTIONS_SENT)

            return response

        except Exception as e:
            logger.error(f"Error sending predictions to user {user_id}: {str(e)}")
            return "Error fetching predictions. Please try again."

    async def handle_fixtures(self, user_id: str) -> str:
        """Handle fixtures request"""
        try:
            fixtures = self.api_client.get_today_fixtures()
            return self.message_formatter.format_fixtures(fixtures)
        except Exception as e:
            logger.error(f"Error fetching fixtures: {str(e)}")
            return "Error fetching fixtures. Please try again."

    async def handle_predictions(self, user_id: str, fixture_id: int) -> str:
        """Handle prediction request for specific fixture"""
        try:
            prediction = self.api_client.get_prediction(fixture_id)
            return self.message_formatter.format_prediction(prediction)
        except Exception as e:
            logger.error(f"Error fetching prediction: {str(e)}")
            return "Error fetching prediction. Please try again."

    async def handle_stats(self, user_id: str, fixture_id: int) -> str:
        """Handle stats request"""
        try:
            stats = self.api_client.get_team_stats(fixture_id)
            return self.message_formatter.format_stats(stats)
        except Exception as e:
            logger.error(f"Error fetching stats: {str(e)}")
            return "Error fetching stats. Please try again."

    def cleanup_expired_sessions(self, timeout_seconds: int = 300):
        """Periodically cleanup expired sessions"""
        self.state_manager.cleanup_expired_sessions(timeout_seconds)
