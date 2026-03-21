"""
Telegram Bot for football predictions.

Database-backed session/payment state with API-backed prediction retrieval.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

from frontend.payments.paystack_processor import PAYMENT_PACKAGES, PaymentManager
from frontend.utils.api_client import FootballAPIClient
from frontend.utils.state_manager import UserStateManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BACKEND_API = os.getenv("BACKEND_API", "http://localhost:8000")
WHATSAPP_LINK = os.getenv("WHATSAPP_LINK", "https://wa.me/+254752573307")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC = os.getenv("PAYSTACK_PUBLIC_KEY")
PREDICTIONS_CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "predictions"

EAT = timezone(timedelta(hours=3))


class STATE:
    INITIAL = "initial"
    GREETING_SENT = "greeting_sent"
    AWAITING_CHOICE = "awaiting_choice"
    AWAITING_PHONE = "awaiting_phone"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_CONFIRMED = "payment_confirmed"
    AWAITING_ACTIVATION_PHONE = "awaiting_activation_phone"
    AWAITING_ACTIVATION_PIN = "awaiting_activation_pin"


def get_subscription_minutes_left(memory: Dict) -> int:
    if not memory.get("subscription_expires_at"):
        return 0
    try:
        expiry = datetime.fromisoformat(memory["subscription_expires_at"])
    except Exception:
        return 0
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=EAT)
    minutes = int((expiry.astimezone(EAT) - datetime.now(EAT)).total_seconds() / 60)
    return max(0, minutes)


class TelegramBot:
    """Telegram bot for football predictions."""

    def __init__(self):
        self.state_manager = UserStateManager()
        self.api_client = FootballAPIClient(base_url=BACKEND_API)
        self.payment_manager: Optional[PaymentManager] = None

        if PAYSTACK_SECRET:
            try:
                self.payment_manager = PaymentManager(PAYSTACK_SECRET, PAYSTACK_PUBLIC)
                logger.info("Telegram Paystack payment manager initialized.")
            except Exception as exc:
                logger.error("Failed to initialize payment manager: %s", exc)
        else:
            logger.warning("Paystack secret key not configured. Telegram payments are disabled.")

    def _read_memory(self, user_id: str) -> Dict:
        memory = self.state_manager.get_platform_state("telegram", user_id)
        if memory:
            memory.setdefault("user_id", user_id)
            memory.setdefault("state", STATE.INITIAL)
            return memory
        return {"user_id": user_id, "state": STATE.INITIAL}

    def _write_memory(self, user_id: str, data: Dict) -> None:
        payload = dict(data or {})
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.state_manager.set_platform_state("telegram", user_id, payload)

    @staticmethod
    def _normalize_phone_number(phone_number: Optional[str]) -> Optional[str]:
        if not phone_number:
            return None
        digits_only = "".join(filter(str.isdigit, str(phone_number)))
        if len(digits_only) == 9:
            digits_only = f"254{digits_only}"
        elif len(digits_only) == 10 and digits_only.startswith("0"):
            digits_only = f"254{digits_only[1:]}"
        elif len(digits_only) == 12 and digits_only.startswith("254"):
            pass
        else:
            return None
        return f"+{digits_only}"

    @staticmethod
    def _normalize_pin(pin_value: Optional[str]) -> Optional[str]:
        if pin_value is None:
            return None
        digits_only = "".join(filter(str.isdigit, str(pin_value)))
        if len(digits_only) != 6:
            return None
        return digits_only

    @staticmethod
    def _package_details(package: str) -> Dict:
        return PAYMENT_PACKAGES.get(package, {"name": f"Package {package}", "amount_ksh": 0})

    @staticmethod
    def _is_menu_command(msg: str) -> bool:
        return msg in {"hi", "hello", "hey", "start", "/start", "menu", "help", "/help"}

    @staticmethod
    def _is_start_over_command(msg: str) -> bool:
        normalized = " ".join(msg.split())
        return normalized in {"start over", "startover", "/startover"}

    @staticmethod
    def _build_plan_menu() -> str:
        return (
            "Welcome to Football Analysis Bot.\n\n"
            "Choose a plan:\n"
            "1. KSH 10 - *Basic* (EPL only)\n"
            "2. KSH 30 - *Premium* (All leagues)\n\n"
            "3. Activate existing subscription\n\n"
            "Reply with *1*, *2*, or *3*.\n\n"
            "You can send `start over` or `startover` anytime to return to this menu."
        )

    @staticmethod
    def _is_prediction_command(msg: str) -> bool:
        if msg in {"matches", "/matches", "status"} or msg.startswith("predict "):
            return True
        if not msg.isdigit():
            return False
        # Keep plan choices (1/2) in payment flow; numeric fixture IDs are longer.
        return len(msg) >= 4

    def _sync_subscription_memory(self, memory: Dict, payload: Dict) -> None:
        expires_at = payload.get("expires_at") or payload.get("subscription_expires_at")
        if expires_at:
            memory["subscription_expires_at"] = expires_at

        payment_phone = payload.get("payment_phone") or payload.get("phone_number")
        normalized_phone = self._normalize_phone_number(payment_phone) if payment_phone else None
        if normalized_phone:
            memory["phone_number"] = normalized_phone

        package = payload.get("package")
        if package is not None:
            package_str = str(package)
            if package_str in PAYMENT_PACKAGES:
                details = self._package_details(package_str)
                memory["package"] = package_str
                memory["tier"] = int(package_str)
                memory["amount"] = int(details["amount_ksh"])

    def _require_payment_manager(self, user_id: str, memory: Dict) -> Optional[str]:
        if self.payment_manager:
            return None
        memory["state"] = STATE.GREETING_SENT
        self._write_memory(user_id, memory)
        return "Payment service is not configured right now. Please check the Paystack keys."

    def _start_payment(self, user_id: str, memory: Dict, package: str, phone_number: str) -> str:
        normalized_phone = self._normalize_phone_number(phone_number)
        if not normalized_phone:
            memory["state"] = STATE.AWAITING_PHONE
            self._write_memory(user_id, memory)
            return "Please send a valid Safaricom M-Pesa number.\n\nUse `+254712345678`."

        payment_guard_message = self._require_payment_manager(user_id, memory)
        if payment_guard_message:
            return payment_guard_message

        result = self.payment_manager.initiate_user_payment(
            user_id=user_id,
            package=package,
            phone_number=normalized_phone,
        )

        package_details = self._package_details(package)
        memory["tier"] = int(package)
        memory["package"] = package
        memory["amount"] = int(package_details["amount_ksh"])
        memory["phone_number"] = normalized_phone

        if not result.get("success"):
            memory["state"] = STATE.GREETING_SENT
            memory["last_payment_error"] = result.get("error")
            memory.pop("payment_reference", None)
            memory.pop("payment_status", None)
            self._write_memory(user_id, memory)
            return (
                f"Payment initiation failed: {result.get('error', 'unknown error')}.\n\n"
                "Reply with `1` or `2` to try again."
            )

        memory["state"] = STATE.PAYMENT_PENDING
        memory["payment_reference"] = result.get("reference")
        memory["payment_status"] = result.get("status", "pending")
        memory["payment_message"] = result.get("display_text")
        memory.pop("last_payment_error", None)
        self._write_memory(user_id, memory)

        return (
            f"Payment request sent for KSH {memory['amount']} to `{normalized_phone}`.\n\n"
            f"{result.get('display_text', 'Check your phone for the M-Pesa prompt.')}\n"
            f"Reference: `{result.get('reference')}`\n\n"
            "Approve the charge on your phone, then send `verify`.\n"
            "You can also send `status` to re-check the payment."
        )

    def _verify_pending_payment(self, user_id: str, memory: Dict) -> str:
        payment_guard_message = self._require_payment_manager(user_id, memory)
        if payment_guard_message:
            return payment_guard_message

        reference = memory.get("payment_reference")
        if not reference:
            memory["state"] = STATE.GREETING_SENT
            self._write_memory(user_id, memory)
            return "No pending payment was found. Reply with `1` or `2` to start again."

        result = self.payment_manager.verify_user_payment(
            reference=reference,
            platform="telegram",
            platform_user_id=str(user_id),
            phone_number=memory.get("phone_number"),
        )

        if not result.get("success"):
            self._write_memory(user_id, memory)
            return (
                f"I could not verify that payment yet: {result.get('error', 'verification failed')}.\n\n"
                "If you already approved the M-Pesa prompt, wait a few seconds and send `verify` again."
            )

        payment_status = result.get("status", "pending")
        memory["payment_status"] = payment_status

        expected_amount = int(memory.get("amount", 0))
        paid_amount = int(round(float(result.get("amount_ksh", 0) or 0)))

        if result.get("verified"):
            if expected_amount and paid_amount and paid_amount != expected_amount:
                memory["state"] = STATE.GREETING_SENT
                memory["last_payment_error"] = (
                    f"Expected KSH {expected_amount}, but received KSH {paid_amount}."
                )
                self._write_memory(user_id, memory)
                return (
                    f"Payment amount mismatch. Expected KSH {expected_amount} but received KSH {paid_amount}.\n\n"
                    "Reply with `1` or `2` to start a fresh payment."
                )

            memory["state"] = STATE.PAYMENT_CONFIRMED
            self._sync_subscription_memory(memory, result)
            memory.pop("last_payment_error", None)
            self._write_memory(user_id, memory)

            payment_phone = result.get("payment_phone") or result.get("phone_number") or memory.get("phone_number")
            activation_pin = result.get("activation_pin")

            if activation_pin and payment_phone:
                return (
                    "Payment confirmed.\n\n"
                    f"Your PIN is `{activation_pin}`.\n"
                    f"Activation phone: `{payment_phone}`.\n\n"
                    "Use this phone + PIN to activate on Telegram or WhatsApp.\n"
                    "Send `matches` to see available predictions."
                )

            return (
                "Payment confirmed.\n\n"
                "Your subscription is now active.\n\n"
                "Send `matches` to see available predictions."
            )

        if payment_status in {"pending", "ongoing", "processing", "pay_offline"}:
            self._write_memory(user_id, memory)
            return (
                f"Your payment is still `{payment_status}`.\n\n"
                "Complete the M-Pesa prompt on your phone, then send `verify` again."
            )

        if payment_status in {"failed", "abandoned", "reversed"}:
            memory["state"] = STATE.GREETING_SENT
            memory["last_payment_error"] = result.get("error")
            self._write_memory(user_id, memory)
            return (
                f"Payment was not completed. Paystack status: `{payment_status}`.\n\n"
                "Reply with `1` or `2` to start a new payment."
            )

        self._write_memory(user_id, memory)
        return (
            f"Paystack returned status `{payment_status}`.\n\n"
            "Send `verify` again in a few seconds, or reply with `1` or `2` to restart."
        )

    def _begin_activation_flow(self, user_id: str, memory: Dict) -> str:
        payment_guard_message = self._require_payment_manager(user_id, memory)
        if payment_guard_message:
            return payment_guard_message

        access = self._check_access(str(user_id), memory)
        if access.get("success") and access.get("active"):
            self._write_memory(user_id, memory)
            minutes_left = get_subscription_minutes_left(memory)
            hours = minutes_left // 60
            minutes = minutes_left % 60
            return (
                "You already have an active subscription.\n\n"
                f"Expires in: {hours}h {minutes}m\n\n"
                "Commands: `matches`, `predict <id>`, `status`, or `start over`."
            )

        memory["state"] = STATE.AWAITING_ACTIVATION_PHONE
        memory.pop("activation_phone", None)
        self._write_memory(user_id, memory)
        return (
            "Activation started.\n\n"
            "Send the M-Pesa phone number used for payment in this format:\n"
            "`+254712345678`"
        )

    def _handle_activation_phone(self, user_id: str, memory: Dict, text: str) -> str:
        provided_phone = self._normalize_phone_number(text)
        if not provided_phone:
            return "Please send a valid payment phone number in the format `+254712345678`."

        memory["activation_phone"] = provided_phone
        memory["state"] = STATE.AWAITING_ACTIVATION_PIN
        self._write_memory(user_id, memory)
        return "Now send your 6-digit PIN."

    def _handle_activation_pin(self, user_id: str, memory: Dict, text: str) -> str:
        payment_guard_message = self._require_payment_manager(user_id, memory)
        if payment_guard_message:
            return payment_guard_message

        activation_phone = memory.get("activation_phone")
        if not activation_phone:
            memory["state"] = STATE.AWAITING_ACTIVATION_PHONE
            self._write_memory(user_id, memory)
            return "Activation phone not found. Please send the payment phone number again."

        pin_value = self._normalize_pin(text)
        if not pin_value:
            return "PIN must be 6 digits. Please send the PIN again."

        result = self.payment_manager.activate_subscription(
            platform="telegram",
            platform_user_id=str(user_id),
            payment_phone=activation_phone,
            pin=pin_value,
        )

        if not result.get("success"):
            memory["state"] = STATE.GREETING_SENT
            self._write_memory(user_id, memory)
            return f"Activation failed: {result.get('error', 'unexpected error')}."

        if result.get("locked"):
            retry_seconds = int(result.get("retry_after_seconds", 0) or 0)
            retry_minutes = max(1, (retry_seconds + 59) // 60)
            self._write_memory(user_id, memory)
            return (
                "Too many failed activation attempts.\n\n"
                f"Please wait about {retry_minutes} minute(s), then try again."
            )

        if not result.get("activated"):
            self._write_memory(user_id, memory)
            return (
                "Invalid phone or PIN. Send the correct details, send `activate` to restart activation, "
                "or send `start over` for the home menu."
            )

        memory["state"] = STATE.PAYMENT_CONFIRMED
        self._sync_subscription_memory(memory, result)
        memory.pop("activation_phone", None)
        memory.pop("last_payment_error", None)
        self._write_memory(user_id, memory)
        return (
            "Activation successful.\n\n"
            f"Plan active until `{memory.get('subscription_expires_at', result.get('expires_at', 'N/A'))}`.\n"
            "Send `matches` to see available predictions."
        )

    def _check_access(self, user_id: str, memory: Dict) -> Dict:
        if not self.payment_manager:
            return {"success": False, "active": False, "reason": "payment_service_unavailable"}
        result = self.payment_manager.check_access(platform="telegram", platform_user_id=user_id)
        if result.get("success") and result.get("active"):
            self._sync_subscription_memory(memory, result)
            memory["state"] = STATE.PAYMENT_CONFIRMED
        return result

    def _fetch_today_fixtures(self, tier: int) -> Dict:
        league_id = 39 if tier == 1 else None
        return self.api_client.get_today_fixtures(league_id=league_id)

    @staticmethod
    def _leagues_for_tier(tier: int):
        return ["EPL"] if tier == 1 else ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]

    def _load_local_predictions(self, tier: int):
        predictions = []
        for league in self._leagues_for_tier(tier):
            league_dir = PREDICTIONS_CACHE_DIR / league
            if not league_dir.exists():
                continue
            for json_file in league_dir.glob("*.json"):
                try:
                    payload = json.loads(json_file.read_text(encoding="utf-8"))
                    predictions.append(
                        {
                            "fixture_id": payload.get("fixture_id"),
                            "league": league,
                            "match": payload.get("data", {}).get("match", "Unknown"),
                            "probabilities": payload.get("data", {}).get("probabilities", {}),
                            "summary": payload.get("data", {}).get("summary", ""),
                            "top_bets": payload.get("data", {}).get("top_bets", []),
                        }
                    )
                except Exception:
                    continue
        return predictions

    def _load_local_prediction(self, match_id: str):
        for league in ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]:
            file_path = PREDICTIONS_CACHE_DIR / league / f"{match_id}_enhanced.json"
            if not file_path.exists():
                continue
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                data = payload.get("data", {})
                return {
                    "match": data.get("match", "Unknown Match"),
                    "probabilities": data.get("probabilities", {}),
                    "top_bets": data.get("top_bets", []),
                    "summary": data.get("summary", ""),
                }
            except Exception:
                continue
        return None

    def _format_matches_response(self, memory: Dict) -> str:
        tier = memory.get("tier", 1)
        minutes_left = get_subscription_minutes_left(memory)
        tier_name = "Basic (EPL)" if tier == 1 else "Premium (All Leagues)"

        fixtures_response = self._fetch_today_fixtures(tier)
        response = f"*{tier_name} Plan* - Matches Available\n\n"

        if not fixtures_response.get("success"):
            local_predictions = self._load_local_predictions(tier)
            if not local_predictions:
                response += f"Could not fetch fixtures: {fixtures_response.get('error', 'unknown error')}\n\n"
            else:
                grouped = {}
                for prediction in local_predictions:
                    grouped.setdefault(prediction["league"], []).append(prediction)
                for league, matches in grouped.items():
                    response += f"{league} ({len(matches)} matches)\n"
                    for index, match in enumerate(matches, 1):
                        probabilities = match.get("probabilities") or {}
                        response += f"{index}. {match.get('match', 'Unknown Match')}\n"
                        if probabilities:
                            response += (
                                f"   Home {probabilities.get('home', 0)}% | "
                                f"Draw {probabilities.get('draw', 0)}% | "
                                f"Away {probabilities.get('away', 0)}%\n"
                            )
                        response += f"   ID: {match.get('fixture_id')}\n\n"
        else:
            fixtures = fixtures_response.get("fixtures", [])
            if not fixtures:
                response += "No matches available right now.\n\n"
            else:
                for index, fixture in enumerate(fixtures[:20], 1):
                    response += f"{index}. {fixture.get('match', 'Unknown Match')}\n"
                    response += f"   ID: {fixture.get('id')}\n"
                    response += f"   League: {fixture.get('league', 'Unknown')}\n"
                    response += f"   Time: {fixture.get('time', '--:--')}\n\n"

        response += f"Subscription expires in {minutes_left} minutes.\n\n"
        response += "Reply with a match ID to get prediction."
        response += f"\n\nAlso on WhatsApp: {WHATSAPP_LINK}"
        return response

    def _format_prediction_response(self, match_id: str, memory: Dict) -> str:
        prediction = self.api_client.get_prediction(int(match_id))
        if not prediction.get("success"):
            local_prediction = self._load_local_prediction(match_id)
            if not local_prediction:
                return (
                    f"No prediction found for match ID: {match_id}\n\n"
                    f"Reason: {prediction.get('error', 'not available')}\n\n"
                    "Send `matches` to see available options."
                )
            prediction = {
                "success": True,
                "match": local_prediction["match"],
                "probabilities": local_prediction["probabilities"],
                "top_bets": local_prediction["top_bets"],
                "summary": local_prediction["summary"],
            }

        probabilities = prediction.get("probabilities", {})
        minutes_left = get_subscription_minutes_left(memory)

        response = f"*{prediction.get('match', 'Unknown Match')}*\n\n"
        response += "*Probabilities:*\n"
        response += (
            f"Home: {probabilities.get('home', 0)}% | "
            f"Draw: {probabilities.get('draw', 0)}% | "
            f"Away: {probabilities.get('away', 0)}%\n\n"
        )

        top_bets = prediction.get("top_bets", [])
        if top_bets:
            response += "*Top Bets:*\n"
            for index, bet in enumerate(top_bets[:3], 1):
                response += f"{index}. {bet.get('bet', 'Unknown')}\n"
                response += f"   Odds: {bet.get('odds', 'N/A')}\n\n"

        summary = prediction.get("summary")
        if summary:
            response += f"*Analysis:*\n{summary[:300]}...\n\n"

        response += f"{minutes_left} minutes left on your subscription.\n\n"
        response += f"Also on WhatsApp: {WHATSAPP_LINK}"
        return response

    async def process_message(
        self,
        user_id: str,
        username: str,
        text: str,
        phone_number: Optional[str] = None,
    ) -> str:
        """Process an incoming Telegram message."""
        try:
            del username  # username is currently unused
            user_id_str = str(user_id)
            memory = self._read_memory(user_id_str)
            current_state = memory.get("state", STATE.INITIAL)
            msg = (text or "").strip().lower()

            normalized_contact = self._normalize_phone_number(phone_number)
            if normalized_contact:
                memory["phone_number"] = normalized_contact
                self._write_memory(user_id_str, memory)

            if self._is_start_over_command(msg):
                memory["state"] = STATE.GREETING_SENT
                memory.pop("activation_phone", None)
                self._write_memory(user_id_str, memory)
                return self._build_plan_menu()

            if msg in {"activate", "/activate"}:
                return self._begin_activation_flow(user_id_str, memory)

            if current_state == STATE.AWAITING_ACTIVATION_PHONE:
                return self._handle_activation_phone(user_id_str, memory, text)

            if current_state == STATE.AWAITING_ACTIVATION_PIN:
                return self._handle_activation_pin(user_id_str, memory, text)

            if current_state == STATE.PAYMENT_PENDING:
                if msg in {"verify", "status"}:
                    return self._verify_pending_payment(user_id_str, memory)
                return (
                    "Awaiting payment confirmation.\n\n"
                    "Approve the M-Pesa prompt on your phone, then send `verify`.\n"
                    "Send `start over` to return to the home menu."
                )

            if self._is_prediction_command(msg):
                access = self._check_access(user_id_str, memory)
                if not (access.get("success") and access.get("active")):
                    memory["state"] = STATE.GREETING_SENT
                    self._write_memory(user_id_str, memory)
                    return (
                        "No active subscription was found.\n\n"
                        "Reply with *1* or *2* to pay, or send `activate` to link an existing subscription."
                    )

                self._write_memory(user_id_str, memory)
                if msg in {"matches", "/matches"}:
                    return self._format_matches_response(memory)
                if msg == "status":
                    minutes_left = get_subscription_minutes_left(memory)
                    hours = minutes_left // 60
                    minutes = minutes_left % 60
                    return (
                        "Subscription active.\n\n"
                        f"Expires in: {hours}h {minutes}m\n\n"
                        "Commands: `matches`, `predict <id>`, `activate`."
                    )

                match_id = msg.replace("predict ", "").strip()
                if match_id.isdigit():
                    return self._format_prediction_response(match_id, memory)
                return "Invalid match ID. Send `matches` to see available options."

            if current_state in {STATE.INITIAL, STATE.GREETING_SENT}:
                if self._is_menu_command(msg):
                    memory["state"] = STATE.GREETING_SENT
                    self._write_memory(user_id_str, memory)
                    return self._build_plan_menu()

                if msg in {"1", "2"}:
                    memory["tier"] = int(msg)
                    memory["package"] = msg
                    package_details = self._package_details(msg)
                    memory["amount"] = int(package_details["amount_ksh"])
                    stored_phone = normalized_contact or memory.get("phone_number")
                    if stored_phone:
                        return self._start_payment(user_id_str, memory, msg, stored_phone)

                    memory["state"] = STATE.AWAITING_PHONE
                    self._write_memory(user_id_str, memory)
                    return (
                        f"You selected *{package_details['name']}* (KSH {package_details['amount_ksh']}).\n\n"
                        "Send the M-Pesa number to charge in this format:\n"
                        "`+254712345678`"
                    )

                if msg == "3":
                    return self._begin_activation_flow(user_id_str, memory)

                if current_state == STATE.INITIAL:
                    memory["state"] = STATE.GREETING_SENT
                    self._write_memory(user_id_str, memory)
                    return self._build_plan_menu()

                return f"Invalid choice.\n\n{self._build_plan_menu()}"

            if current_state == STATE.AWAITING_PHONE:
                package = memory.get("package")
                provided_phone = normalized_contact or self._normalize_phone_number(text)
                if package not in PAYMENT_PACKAGES:
                    memory["state"] = STATE.GREETING_SENT
                    self._write_memory(user_id_str, memory)
                    return "Your package selection expired. Reply with *1* or *2* to begin again."

                if not provided_phone:
                    return (
                        "I still need the M-Pesa number to charge.\n\n"
                        "Send it as `+254712345678`."
                    )

                return self._start_payment(user_id_str, memory, package, provided_phone)

            if current_state == STATE.PAYMENT_CONFIRMED:
                return "Commands: `matches`, `predict <id>`, `status`, `activate`, or `start over`."

            return "Invalid state. Send /start to begin."

        except Exception as exc:
            logger.error("Error processing Telegram message: %s", exc)
            return f"Error: {str(exc)[:100]}"
