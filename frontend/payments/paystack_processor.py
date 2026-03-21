"""
Paystack Payment Integration - Handles M-Pesa payments via Paystack
"""
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from enum import Enum

import requests

from database.sync_connection import get_sync_db

logger = logging.getLogger(__name__)
CATALOG_PATH = Path(__file__).with_name("payment_catalog.json")


def _load_payment_packages() -> Dict[str, Dict[str, Any]]:
    """Load shared payment package metadata from disk."""
    default_packages: Dict[str, Dict[str, Any]] = {
        "1": {"name": "Basic (EPL)", "amount_ksh": 10},
        "2": {"name": "Premium (All Leagues)", "amount_ksh": 30},
    }

    try:
        loaded = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        packages: Dict[str, Dict[str, Any]] = {}
        for key, value in loaded.items():
            amount = int(value["amount_ksh"])
            packages[str(key)] = {
                "name": str(value.get("name", f"Package {key}")),
                "amount_ksh": amount,
            }
        return packages or default_packages
    except Exception as exc:
        logger.warning(f"Falling back to default payment packages: {exc}")
        return default_packages


PAYMENT_PACKAGES = _load_payment_packages()


class PaymentStatus(Enum):
    """Payment status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaystackPaymentProcessor:
    """Handles payment processing via Paystack API"""

    def __init__(self, secret_key: str, public_key: Optional[str] = None):
        """
        Initialize Paystack processor

        Args:
            secret_key: Paystack secret key
            public_key: Paystack public key
        """
        if not secret_key:
            raise ValueError("Paystack secret key not configured")

        self.secret_key = secret_key
        self.public_key = public_key
        self.charge_url = "https://api.paystack.co/charge"
        self.verify_url = "https://api.paystack.co/transaction/verify"
        self.headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _normalize_phone_number(phone_number: str) -> Optional[str]:
        """Normalize a Kenyan phone number to +2547XXXXXXXX format."""
        digits_only = ''.join(filter(str.isdigit, str(phone_number)))

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
    def _build_customer_email(user_id: str, normalized_phone: str) -> str:
        """
        Build a Paystack-safe synthetic customer email.

        WhatsApp IDs can contain values like ``51634130432248@lid``, which are not
        valid email local parts if inserted directly. We keep the address stable per
        user while stripping unsupported characters.
        """
        raw_user_id = str(user_id or "").strip().lower()
        safe_user_id = re.sub(r"[^a-z0-9._+-]+", "_", raw_user_id)
        safe_user_id = re.sub(r"_+", "_", safe_user_id).strip("._+-")

        phone_digits = ''.join(filter(str.isdigit, normalized_phone))[-9:]
        digest = hashlib.sha1(raw_user_id.encode("utf-8")).hexdigest()[:10]

        local_base = safe_user_id[:24] if safe_user_id else f"customer_{phone_digits or 'unknown'}"
        return f"user_{local_base}_{digest}@footballpred.com"

    def initialize_payment(self, user_id: str, amount_ksh: int,
                           package: str, phone_number: str) -> Dict[str, Any]:
        """
        Initiate an M-Pesa STK push via Paystack Charge API

        Args:
            user_id: User identifier
            amount_ksh: Amount in KSH
            package: Package selected ("1" or "2")
            phone_number: Customer's phone number in format +2547XXXXXXXX

        Returns:
            Charge response with status and display text
        """
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            if not normalized_phone:
                return {
                    "success": False,
                    "error": "Invalid phone number. Use a valid Kenyan M-Pesa number."
                }

            customer_email = self._build_customer_email(user_id, normalized_phone)

            payload = {
                "email": customer_email,
                "amount": amount_ksh * 100,  # Paystack uses kobo/cents
                "currency": "KES",
                "mobile_money": {
                    "phone": normalized_phone,
                    "provider": "mpesa"
                },
                "metadata": {
                    "user_id": user_id,
                    "package": package,
                    "service": "football_predictions",
                    "phone_number": normalized_phone
                }
            }

            response = requests.post(
                self.charge_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if data.get('status'):
                charge_data = data['data']
                logger.info(
                    f"M-Pesa charge initiated for user {user_id}. "
                    f"Amount: {amount_ksh} KSH. Status: {charge_data.get('status')}. "
                    f"Customer email: {customer_email}"
                )
                return {
                    "success": True,
                    "reference": charge_data['reference'],
                    "status": charge_data.get('status'),
                    "gateway_response": charge_data.get('gateway_response'),
                    "display_text": charge_data.get(
                        'display_text',
                        'Check your phone for the M-Pesa prompt.'
                    ),
                    "phone_number": normalized_phone
                }
            else:
                logger.error(f"Charge initiation failed: {data.get('message')}")
                return {
                    "success": False,
                    "error": data.get('message', 'Payment initiation failed')
                }

        except requests.exceptions.RequestException as e:
            error_body = None
            detail = ""
            if getattr(e, "response", None) is not None:
                try:
                    error_body = e.response.json()
                except ValueError:
                    error_body = e.response.text
                detail = f" | status={e.response.status_code} | body={error_body}"
            logger.error(f"Paystack charge error: {str(e)}{detail}")
            return {
                "success": False,
                "error": (
                    error_body.get('message')
                    if isinstance(error_body, dict) and error_body.get('message')
                    else "Payment service error. Please try again."
                )
            }
        except Exception as e:
            logger.error(f"Unexpected error during payment initiation: {str(e)}")
            return {
                "success": False,
                "error": "An unexpected error occurred"
            }

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verify a payment with Paystack

        Args:
            reference: Payment reference from charge initiation

        Returns:
            Verification response with payment status
        """
        try:
            verify_endpoint = f"{self.verify_url}/{reference}"

            response = requests.get(
                verify_endpoint,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if data.get('status'):
                payment_data = data.get('data', {})
                payment_status = payment_data.get('status')
                is_approved = payment_status == 'success'

                logger.info(
                    f"Payment verification for {reference}. "
                    f"Status: {payment_status}"
                )

                return {
                    "success": True,
                    "verified": is_approved,
                    "status": payment_status,
                    "reference": reference,
                    "amount": payment_data.get('amount', 0) / 100,  # Convert to KSH
                    "paid_at": payment_data.get('paid_at'),
                    "customer": payment_data.get('customer', {}),
                    "gateway_response": payment_data.get('gateway_response'),
                    "metadata": payment_data.get('metadata', {})
                }
            else:
                logger.error(f"Payment verification failed: {data.get('message')}")
                return {
                    "success": False,
                    "verified": False,
                    "error": data.get('message', 'Verification failed')
                }

        except requests.exceptions.RequestException as e:
            error_body = None
            detail = ""
            if getattr(e, "response", None) is not None:
                try:
                    error_body = e.response.json()
                except ValueError:
                    error_body = e.response.text
                detail = f" | status={e.response.status_code} | body={error_body}"
            logger.error(f"Paystack verification error: {str(e)}{detail}")
            return {
                "success": False,
                "verified": False,
                "error": (
                    error_body.get('message')
                    if isinstance(error_body, dict) and error_body.get('message')
                    else "Payment verification service error"
                )
            }
        except Exception as e:
            logger.error(f"Unexpected error during payment verification: {str(e)}")
            return {
                "success": False,
                "verified": False,
                "error": "An unexpected error occurred"
            }

    def get_payment_status(self, reference: str) -> str:
        """Get payment status"""
        result = self.verify_payment(reference)

        if result.get('success'):
            if result.get('verified'):
                return PaymentStatus.COMPLETED.value
            return result.get('status', PaymentStatus.PENDING.value)
        return PaymentStatus.PENDING.value

    def check_mpesa_enabled(self) -> bool:
        """Check if M-Pesa is available for payments"""
        return True


class PaymentManager:
    """High-level payment management"""

    LOCKOUT_WINDOW_MINUTES = 15
    LOCKOUT_THRESHOLD = 5
    LOCKOUT_DURATION_MINUTES = 10

    def __init__(self, paystack_secret: str, paystack_public: Optional[str] = None):
        self.processor = PaystackPaymentProcessor(paystack_secret, paystack_public)
        self.payment_records: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _json_dump(payload: Dict[str, Any]) -> str:
        return json.dumps(payload or {}, ensure_ascii=False)

    @staticmethod
    def _normalize_iso(value: Optional[str]) -> str:
        if not value:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except Exception:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _resolve_subscription_window(paid_at: Optional[str]) -> Dict[str, str]:
        eat = timezone(timedelta(hours=3))
        if paid_at:
            try:
                starts = datetime.fromisoformat(paid_at.replace("Z", "+00:00")).astimezone(eat)
            except Exception:
                starts = datetime.now(eat)
        else:
            starts = datetime.now(eat)

        expires = starts.replace(hour=23, minute=59, second=59, microsecond=0)
        if expires <= starts:
            expires = expires + timedelta(days=1)

        return {
            "starts_at": starts.isoformat(),
            "expires_at": expires.isoformat(),
        }

    @staticmethod
    def _map_package_to_plan(package: Optional[str]) -> str:
        # Current packages are day access tiers.
        return "daily"

    @staticmethod
    def _package_from_amount(amount: Optional[float]) -> Optional[str]:
        if amount is None:
            return None
        try:
            amount_int = int(round(float(amount)))
        except Exception:
            return None

        for package_key, package_details in PAYMENT_PACKAGES.items():
            try:
                if int(package_details.get("amount_ksh", -1)) == amount_int:
                    return str(package_key)
            except Exception:
                continue
        return None

    @staticmethod
    def _normalize_phone_number(phone_number: Optional[str]) -> Optional[str]:
        if not phone_number:
            return None
        return PaystackPaymentProcessor._normalize_phone_number(str(phone_number))

    @staticmethod
    def _normalize_pin(pin: Optional[str]) -> Optional[str]:
        if pin is None:
            return None
        digits = "".join(filter(str.isdigit, str(pin)))
        if len(digits) != 6:
            return None
        return digits

    @staticmethod
    def _coerce_db_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        raw = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except Exception:
            return None

    @staticmethod
    def _pin_from_reference(reference: str, attempt: int = 0) -> str:
        digest = hashlib.sha1(f"{reference}:{attempt}".encode("utf-8")).hexdigest()
        return str((int(digest[:12], 16) % 900000) + 100000)

    @staticmethod
    def _record_activation_attempt(
        conn,
        *,
        platform: str,
        platform_user_id: str,
        phone_tried: str,
        pin_tried: str,
        success: bool,
        failure_reason: Optional[str] = None,
    ) -> None:
        # Backward-compatible bootstrap for environments where bots start
        # before full async DB initialization/migrations are run.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activation_attempts (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                platform          TEXT NOT NULL,
                platform_user_id  TEXT NOT NULL,
                phone_tried       TEXT NOT NULL,
                pin_tried         TEXT NOT NULL,
                success           INTEGER DEFAULT 0,
                attempted_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        try:
            conn.execute(
                """
                INSERT INTO activation_attempts (
                    platform, platform_user_id, phone_tried, pin_tried, success, failure_reason
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    platform,
                    platform_user_id,
                    phone_tried,
                    pin_tried,
                    1 if success else 0,
                    failure_reason,
                ),
            )
            return
        except Exception as exc:
            message = str(exc).lower()
            if "no column named failure_reason" in message:
                try:
                    conn.execute(
                        """
                        ALTER TABLE activation_attempts
                        ADD COLUMN failure_reason TEXT
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO activation_attempts (
                            platform, platform_user_id, phone_tried, pin_tried, success, failure_reason
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            platform,
                            platform_user_id,
                            phone_tried,
                            pin_tried,
                            1 if success else 0,
                            failure_reason,
                        ),
                    )
                    return
                except Exception:
                    pass

            # Last-resort fallback for very old schemas.
            conn.execute(
                """
                INSERT INTO activation_attempts (
                    platform, platform_user_id, phone_tried, pin_tried, success
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    platform,
                    platform_user_id,
                    phone_tried,
                    pin_tried,
                    1 if success else 0,
                ),
            )

    def _build_access_payload(self, row: Any) -> Dict[str, Any]:
        package = self._package_from_amount(row["amount"])
        return {
            "subscription_id": int(row["subscription_id"]),
            "plan": str(row["plan"]),
            "expires_at": str(row["expires_at"]),
            "payment_phone": str(row["payment_phone"]),
            "package": package,
            "amount_ksh": row["amount"],
        }

    def _save_payment_transaction(
        self,
        transaction_id: str,
        platform: Optional[str],
        user_id: Optional[str],
        amount: Optional[float],
        package: Optional[str],
        status: str,
        reference: Optional[str],
        phone_number: Optional[str],
        created_at: Optional[str],
        verified_at: Optional[str],
        metadata: Dict[str, Any],
    ) -> None:
        with get_sync_db() as conn:
            conn.execute(
                """
                INSERT INTO payment_transactions (
                    transaction_id, platform, user_id, amount, package, status,
                    reference, phone_number, created_at, verified_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    platform = excluded.platform,
                    user_id = excluded.user_id,
                    amount = excluded.amount,
                    package = excluded.package,
                    status = excluded.status,
                    reference = excluded.reference,
                    phone_number = excluded.phone_number,
                    created_at = excluded.created_at,
                    verified_at = excluded.verified_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    transaction_id,
                    platform,
                    user_id,
                    float(amount) if isinstance(amount, (int, float)) else None,
                    package,
                    status,
                    reference,
                    phone_number,
                    self._normalize_iso(created_at),
                    self._normalize_iso(verified_at) if verified_at else None,
                    self._json_dump(metadata),
                ),
            )

    def _upsert_subscription_and_session(
        self,
        *,
        reference: str,
        phone_number: Optional[str],
        package: Optional[str],
        amount_ksh: Optional[float],
        paid_at: Optional[str],
        platform: Optional[str],
        platform_user_id: Optional[str],
    ) -> Dict[str, Optional[Any]]:
        normalized_phone = self._normalize_phone_number(phone_number)
        if not normalized_phone:
            return {
                "expires_at": None,
                "pin": None,
                "payment_phone": None,
                "package": None,
            }

        plan = self._map_package_to_plan(package)
        window = self._resolve_subscription_window(paid_at)
        starts_at = window["starts_at"]
        expires_at = window["expires_at"]

        with get_sync_db() as conn:
            inserted = False
            for attempt in range(20):
                candidate_pin = self._pin_from_reference(reference, attempt=attempt)
                try:
                    conn.execute(
                        """
                        INSERT INTO subscriptions (
                            payment_phone, paystack_ref, amount, currency, plan, pin,
                            starts_at, expires_at, status, initiated_from
                        )
                        VALUES (?, ?, ?, 'KES', ?, ?, ?, ?, 'active', ?)
                        ON CONFLICT(paystack_ref) DO UPDATE SET
                            payment_phone = excluded.payment_phone,
                            amount = excluded.amount,
                            plan = excluded.plan,
                            starts_at = excluded.starts_at,
                            expires_at = excluded.expires_at,
                            status = 'active',
                            initiated_from = excluded.initiated_from
                        """,
                        (
                            normalized_phone,
                            reference,
                            float(amount_ksh) if isinstance(amount_ksh, (int, float)) else None,
                            plan,
                            candidate_pin,
                            starts_at,
                            expires_at,
                            platform,
                        ),
                    )
                    inserted = True
                    break
                except Exception:
                    continue

            if not inserted:
                logger.warning("Could not allocate unique PIN for reference %s", reference)

            sub = conn.execute(
                """
                SELECT id, plan, expires_at, pin, payment_phone, amount
                FROM subscriptions
                WHERE paystack_ref = ?
                LIMIT 1
                """,
                (reference,),
            ).fetchone()

            if sub and platform and platform_user_id:
                platform_user_str = str(platform_user_id)
                conn.execute(
                    """
                    DELETE FROM platform_sessions
                    WHERE (subscription_id = ? AND platform = ?)
                       OR (platform = ? AND platform_user_id = ?)
                    """,
                    (int(sub["id"]), platform, platform, platform_user_str),
                )
                conn.execute(
                    """
                    INSERT INTO platform_sessions (
                        subscription_id, platform, platform_user_id, plan, expires_at,
                        activated_at, last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        int(sub["id"]),
                        platform,
                        platform_user_str,
                        sub["plan"],
                        sub["expires_at"],
                    ),
                )

            if sub:
                return {
                    "expires_at": str(sub["expires_at"]),
                    "pin": str(sub["pin"]),
                    "payment_phone": str(sub["payment_phone"]),
                    "package": self._package_from_amount(sub["amount"]),
                }
            return {
                "expires_at": expires_at,
                "pin": None,
                "payment_phone": normalized_phone,
                "package": package,
            }

    def initiate_user_payment(self, user_id: str, package: str,
                              phone_number: str) -> Dict[str, Any]:
        """
        Initiate M-Pesa STK push for a user's selected package

        Args:
            user_id: User identifier
            package: Package choice ("1" for KSH 10, "2" for KSH 30)
            phone_number: User's phone number in format +2547XXXXXXXX

        Returns:
            Payment initiation result with display text for the user
        """
        package_details = PAYMENT_PACKAGES.get(package)
        if not package_details:
            return {"success": False, "error": "Invalid package selection"}

        amount = int(package_details["amount_ksh"])

        result = self.processor.initialize_payment(
            user_id=user_id,
            amount_ksh=amount,
            package=package,
            phone_number=phone_number
        )

        if result.get('success'):
            reference = result["reference"]
            record = {
                "user_id": user_id,
                "package": package,
                "amount_ksh": amount,
                "phone_number": result.get('phone_number'),
                "status": PaymentStatus.PENDING.value,
                "reference": reference,
                "initiated_at": datetime.now().isoformat()
            }
            self.payment_records[reference] = record
            self._save_payment_transaction(
                transaction_id=reference,
                platform=None,
                user_id=str(user_id),
                amount=float(amount),
                package=package,
                status=PaymentStatus.PENDING.value,
                reference=reference,
                phone_number=result.get("phone_number"),
                created_at=record["initiated_at"],
                verified_at=None,
                metadata=record,
            )

            return {
                "success": True,
                "reference": reference,
                "status": result.get('status'),
                "display_text": result.get(
                    'display_text',
                    'Check your phone for the M-Pesa prompt.'
                ),
                "amount_ksh": amount,
                "phone_number": result.get('phone_number'),
            }

        return result

    def activate_subscription(
        self,
        *,
        platform: str,
        platform_user_id: str,
        payment_phone: str,
        pin: str,
    ) -> Dict[str, Any]:
        platform_name = (platform or "").strip().lower()
        platform_user = str(platform_user_id or "").strip()
        normalized_phone = self._normalize_phone_number(payment_phone)
        normalized_pin = self._normalize_pin(pin)
        phone_tried = normalized_phone or str(payment_phone or "").strip()
        pin_tried = normalized_pin or str(pin or "").strip()

        if not platform_name or not platform_user:
            return {
                "success": False,
                "activated": False,
                "locked": False,
                "reason": "invalid_identity",
            }

        with get_sync_db() as conn:
            lock_row = conn.execute(
                """
                SELECT COUNT(*) AS fail_count, MAX(attempted_at) AS last_failed_at
                FROM activation_attempts
                WHERE platform = ?
                  AND platform_user_id = ?
                  AND success = 0
                  AND datetime(attempted_at) >= datetime('now', ?)
                """,
                (platform_name, platform_user, f"-{self.LOCKOUT_WINDOW_MINUTES} minutes"),
            ).fetchone()

            fail_count = int(lock_row["fail_count"] or 0)
            last_failed_at = self._coerce_db_datetime(lock_row["last_failed_at"])
            if fail_count >= self.LOCKOUT_THRESHOLD and last_failed_at is not None:
                lock_until = last_failed_at + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
                now_utc = datetime.utcnow()
                if now_utc < lock_until:
                    retry_after = max(1, int((lock_until - now_utc).total_seconds()))
                    self._record_activation_attempt(
                        conn,
                        platform=platform_name,
                        platform_user_id=platform_user,
                        phone_tried=phone_tried,
                        pin_tried=pin_tried,
                        success=False,
                        failure_reason="locked_out",
                    )
                    return {
                        "success": True,
                        "activated": False,
                        "locked": True,
                        "retry_after_seconds": retry_after,
                        "reason": "locked_out",
                    }

            if not normalized_phone or not normalized_pin:
                self._record_activation_attempt(
                    conn,
                    platform=platform_name,
                    platform_user_id=platform_user,
                    phone_tried=phone_tried,
                    pin_tried=pin_tried,
                    success=False,
                    failure_reason="invalid_credentials",
                )
                return {
                    "success": True,
                    "activated": False,
                    "locked": False,
                    "reason": "invalid_credentials",
                }

            sub = conn.execute(
                """
                SELECT id, plan, expires_at, amount, payment_phone
                FROM subscriptions
                WHERE payment_phone = ?
                  AND pin = ?
                  AND status = 'active'
                  AND datetime(expires_at) > datetime('now')
                ORDER BY datetime(expires_at) DESC
                LIMIT 1
                """,
                (normalized_phone, normalized_pin),
            ).fetchone()

            if not sub:
                self._record_activation_attempt(
                    conn,
                    platform=platform_name,
                    platform_user_id=platform_user,
                    phone_tried=normalized_phone,
                    pin_tried=normalized_pin,
                    success=False,
                    failure_reason="invalid_credentials",
                )
                return {
                    "success": True,
                    "activated": False,
                    "locked": False,
                    "reason": "invalid_credentials",
                }

            sub_id = int(sub["id"])
            conn.execute(
                """
                UPDATE subscriptions
                SET pin_used = 1
                WHERE id = ?
                """,
                (sub_id,),
            )
            conn.execute(
                """
                DELETE FROM platform_sessions
                WHERE (subscription_id = ? AND platform = ?)
                   OR (platform = ? AND platform_user_id = ?)
                """,
                (sub_id, platform_name, platform_name, platform_user),
            )
            conn.execute(
                """
                INSERT INTO platform_sessions (
                    subscription_id, platform, platform_user_id, plan, expires_at,
                    activated_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    sub_id,
                    platform_name,
                    platform_user,
                    str(sub["plan"]),
                    str(sub["expires_at"]),
                ),
            )

            self._record_activation_attempt(
                conn,
                platform=platform_name,
                platform_user_id=platform_user,
                phone_tried=normalized_phone,
                pin_tried=normalized_pin,
                success=True,
                failure_reason=None,
            )

            return {
                "success": True,
                "activated": True,
                "locked": False,
                "reason": "activated",
                "plan": str(sub["plan"]),
                "expires_at": str(sub["expires_at"]),
                "payment_phone": str(sub["payment_phone"]),
                "package": self._package_from_amount(sub["amount"]),
                "amount_ksh": sub["amount"],
            }

    def check_access(self, *, platform: str, platform_user_id: str) -> Dict[str, Any]:
        platform_name = (platform or "").strip().lower()
        platform_user = str(platform_user_id or "").strip()
        if not platform_name or not platform_user:
            return {
                "success": False,
                "active": False,
                "reason": "invalid_identity",
            }

        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT
                    s.id AS subscription_id,
                    s.plan,
                    s.expires_at,
                    s.payment_phone,
                    s.amount
                FROM platform_sessions ps
                JOIN subscriptions s ON s.id = ps.subscription_id
                WHERE ps.platform = ?
                  AND ps.platform_user_id = ?
                  AND s.status = 'active'
                  AND datetime(s.expires_at) > datetime('now')
                ORDER BY datetime(s.expires_at) DESC
                LIMIT 1
                """,
                (platform_name, platform_user),
            ).fetchone()

            if not row:
                return {
                    "success": True,
                    "active": False,
                    "reason": "no_active_subscription",
                }

            conn.execute(
                """
                UPDATE platform_sessions
                SET last_seen_at = datetime('now'),
                    plan = ?,
                    expires_at = ?
                WHERE platform = ? AND platform_user_id = ?
                """,
                (str(row["plan"]), str(row["expires_at"]), platform_name, platform_user),
            )

            payload = self._build_access_payload(row)
            return {
                "success": True,
                "active": True,
                "reason": "active",
                **payload,
            }

    def verify_user_payment(
        self,
        reference: str,
        platform: Optional[str] = None,
        platform_user_id: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a user's payment"""
        result = self.processor.verify_payment(reference)

        if not result.get('success'):
            self._save_payment_transaction(
                transaction_id=reference,
                platform=platform,
                user_id=str(platform_user_id) if platform_user_id is not None else None,
                amount=None,
                package=None,
                status=PaymentStatus.PENDING.value,
                reference=reference,
                phone_number=phone_number,
                created_at=datetime.now().isoformat(),
                verified_at=None,
                metadata={"error": result.get("error"), "reference": reference},
            )
            return {
                "success": False,
                "verified": False,
                "status": PaymentStatus.PENDING.value,
                "error": result.get('error', 'Payment verification failed')
            }

        payment_status = result.get('status', PaymentStatus.PENDING.value)
        if reference in self.payment_records:
            self.payment_records[reference]['status'] = payment_status
            self.payment_records[reference]['checked_at'] = datetime.now().isoformat()

            if result.get('verified'):
                self.payment_records[reference]['verified_at'] = datetime.now().isoformat()

        metadata = result.get('metadata', {})
        verified = result.get('verified', False)
        amount_ksh = result.get("amount")
        resolved_user_id = metadata.get("user_id") or (
            str(platform_user_id) if platform_user_id is not None else None
        )
        resolved_package = str(metadata.get("package")) if metadata.get("package") is not None else None
        resolved_phone = self._normalize_phone_number(
            phone_number
            or metadata.get("phone_number")
            or (self.payment_records.get(reference, {}) or {}).get("phone_number")
        )
        verified_at = datetime.now().isoformat() if verified else None

        payment_payload = {
            "reference": reference,
            "status": payment_status,
            "verified": verified,
            "amount_ksh": amount_ksh,
            "user_id": resolved_user_id,
            "package": resolved_package,
            "phone_number": resolved_phone,
            "gateway_response": result.get("gateway_response"),
            "metadata": metadata,
        }
        self._save_payment_transaction(
            transaction_id=reference,
            platform=platform,
            user_id=resolved_user_id,
            amount=float(amount_ksh) if isinstance(amount_ksh, (int, float)) else None,
            package=resolved_package,
            status=payment_status,
            reference=reference,
            phone_number=resolved_phone,
            created_at=self.payment_records.get(reference, {}).get("initiated_at"),
            verified_at=verified_at,
            metadata=payment_payload,
        )

        response = {
            "success": True,
            "verified": verified,
            "status": payment_status,
            "amount_ksh": amount_ksh,
            "reference": reference,
            "user_id": resolved_user_id,
            "package": resolved_package,
            "phone_number": resolved_phone,
            "message": "Payment verified successfully!" if verified else "Payment not completed yet.",
            "gateway_response": result.get('gateway_response')
        }

        if verified:
            subscription_payload = self._upsert_subscription_and_session(
                reference=reference,
                phone_number=resolved_phone,
                package=resolved_package,
                amount_ksh=amount_ksh,
                paid_at=result.get("paid_at"),
                platform=platform,
                platform_user_id=str(platform_user_id) if platform_user_id is not None else None,
            )
            if subscription_payload.get("expires_at"):
                response["subscription_expires_at"] = subscription_payload.get("expires_at")
            if subscription_payload.get("pin"):
                response["activation_pin"] = subscription_payload.get("pin")
            if subscription_payload.get("payment_phone"):
                response["payment_phone"] = subscription_payload.get("payment_phone")
            if not response.get("package") and subscription_payload.get("package"):
                response["package"] = subscription_payload.get("package")
            return response

        response["error"] = result.get('gateway_response') or f"Payment is currently {payment_status}."
        return response

    def get_payment_details(self, reference: str) -> Optional[Dict]:
        """Get stored payment details"""
        cached = self.payment_records.get(reference)
        if cached:
            return cached

        with get_sync_db() as conn:
            row = conn.execute(
                """
                SELECT metadata_json
                FROM payment_transactions
                WHERE transaction_id = ? OR reference = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (reference, reference),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["metadata_json"])
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
