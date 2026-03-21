"""
Command-line bridge for shared payment operations.

This lets non-Python runtimes use the same PaymentManager logic as the Python bots.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from paystack_processor import PAYMENT_PACKAGES, PaymentManager


def _build_manager() -> PaymentManager:
    """Create a PaymentManager from environment variables."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    secret = os.getenv("PAYSTACK_SECRET_KEY")
    public = os.getenv("PAYSTACK_PUBLIC_KEY")
    if not secret:
        raise ValueError("PAYSTACK_SECRET_KEY is not configured")

    return PaymentManager(secret, public)


def _print_result(result: Dict[str, Any], exit_code: int = 0) -> None:
    """Write a JSON result to stdout."""
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    raise SystemExit(exit_code)


def main() -> None:
    """Run the CLI."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Shared payment helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    initiate = subparsers.add_parser("initiate", help="Initiate an M-Pesa payment")
    initiate.add_argument("--user-id", required=True)
    initiate.add_argument("--package", required=True)
    initiate.add_argument("--phone-number", required=True)

    verify = subparsers.add_parser("verify", help="Verify an M-Pesa payment")
    verify.add_argument("--reference", required=True)
    verify.add_argument("--platform", required=False)
    verify.add_argument("--platform-user-id", required=False)
    verify.add_argument("--phone-number", required=False)

    activate = subparsers.add_parser("activate", help="Activate subscription using payment phone + PIN")
    activate.add_argument("--platform", required=True)
    activate.add_argument("--platform-user-id", required=True)
    activate.add_argument("--payment-phone", required=True)
    activate.add_argument("--pin", required=True)

    access = subparsers.add_parser("access", help="Check active subscription access for a platform user")
    access.add_argument("--platform", required=True)
    access.add_argument("--platform-user-id", required=True)

    subparsers.add_parser("catalog", help="Return the shared payment package catalog")

    args = parser.parse_args()

    try:
        if args.command == "catalog":
            _print_result({"success": True, "packages": PAYMENT_PACKAGES})

        manager = _build_manager()

        if args.command == "initiate":
            result = manager.initiate_user_payment(
                user_id=args.user_id,
                package=args.package,
                phone_number=args.phone_number,
            )
            _print_result(result, 0 if result.get("success") else 1)

        if args.command == "verify":
            result = manager.verify_user_payment(
                reference=args.reference,
                platform=args.platform,
                platform_user_id=args.platform_user_id,
                phone_number=args.phone_number,
            )
            _print_result(result, 0 if result.get("success") else 1)

        if args.command == "activate":
            result = manager.activate_subscription(
                platform=args.platform,
                platform_user_id=args.platform_user_id,
                payment_phone=args.payment_phone,
                pin=args.pin,
            )
            _print_result(result, 0 if result.get("success") else 1)

        if args.command == "access":
            result = manager.check_access(
                platform=args.platform,
                platform_user_id=args.platform_user_id,
            )
            _print_result(result, 0 if result.get("success") else 1)

        _print_result({"success": False, "error": f"Unsupported command: {args.command}"}, 1)

    except Exception as exc:
        _print_result({"success": False, "error": str(exc)}, 1)


if __name__ == "__main__":
    main()
