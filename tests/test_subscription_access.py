import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture(scope="function", autouse=True)
def initialize_services():
    # Override global autouse fixture from tests/conftest.py for this test module.
    yield


@pytest.fixture(scope="function")
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "subscription_test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("AUTO_MIGRATE_LEGACY", "false")

    import database.connection as db_connection
    import database.init_db as db_init
    import database.sync_connection as sync_connection

    monkeypatch.setattr(db_connection, "DB_PATH", str(db_path), raising=False)
    monkeypatch.setattr(sync_connection, "DB_PATH", str(db_path), raising=False)
    monkeypatch.setattr(db_init, "DB_PATH", str(db_path), raising=False)

    asyncio.run(db_init.init_db())
    return db_path


def _seed_subscription(
    *,
    paystack_ref: str,
    phone: str,
    pin: str,
    amount: float = 30.0,
    plan: str = "daily",
    expires_in_hours: int = 6,
):
    from database.sync_connection import get_sync_db

    now = datetime.now(timezone.utc)
    starts_at = now.isoformat()
    expires_at = (now + timedelta(hours=expires_in_hours)).isoformat()

    with get_sync_db() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (
                payment_phone, paystack_ref, amount, currency, plan, pin,
                starts_at, expires_at, status, initiated_from
            )
            VALUES (?, ?, ?, 'KES', ?, ?, ?, ?, 'active', 'whatsapp')
            """,
            (phone, paystack_ref, amount, plan, pin, starts_at, expires_at),
        )


def test_activate_subscription_success_and_access(isolated_db):
    from frontend.payments.paystack_processor import PaymentManager

    _seed_subscription(
        paystack_ref="ref-success-001",
        phone="+254712345678",
        pin="123456",
        amount=30.0,
    )

    manager = PaymentManager("dummy-secret")
    activation = manager.activate_subscription(
        platform="telegram",
        platform_user_id="tg_user_1",
        payment_phone="+254712345678",
        pin="123456",
    )

    assert activation["success"] is True
    assert activation["activated"] is True
    assert activation["locked"] is False
    assert activation["reason"] == "activated"
    assert activation["package"] == "2"

    access = manager.check_access(platform="telegram", platform_user_id="tg_user_1")
    assert access["success"] is True
    assert access["active"] is True
    assert access["reason"] == "active"
    assert access["package"] == "2"


def test_activation_lockout_after_repeated_failures(isolated_db):
    from frontend.payments.paystack_processor import PaymentManager

    _seed_subscription(
        paystack_ref="ref-lockout-001",
        phone="+254700000001",
        pin="654321",
        amount=10.0,
    )

    manager = PaymentManager("dummy-secret")

    for _ in range(5):
        failed = manager.activate_subscription(
            platform="telegram",
            platform_user_id="tg_lock_user",
            payment_phone="+254700000001",
            pin="111111",
        )
        assert failed["success"] is True
        assert failed["activated"] is False
        assert failed["locked"] is False
        assert failed["reason"] == "invalid_credentials"

    locked = manager.activate_subscription(
        platform="telegram",
        platform_user_id="tg_lock_user",
        payment_phone="+254700000001",
        pin="111111",
    )
    assert locked["success"] is True
    assert locked["activated"] is False
    assert locked["locked"] is True
    assert locked["reason"] == "locked_out"
    assert int(locked.get("retry_after_seconds", 0)) > 0


def test_session_scope_one_account_per_platform(isolated_db):
    from database.sync_connection import get_sync_db
    from frontend.payments.paystack_processor import PaymentManager

    _seed_subscription(
        paystack_ref="ref-rebind-001",
        phone="+254711111111",
        pin="222222",
        amount=30.0,
    )

    manager = PaymentManager("dummy-secret")
    first = manager.activate_subscription(
        platform="telegram",
        platform_user_id="tg_user_old",
        payment_phone="+254711111111",
        pin="222222",
    )
    assert first["activated"] is True

    second = manager.activate_subscription(
        platform="telegram",
        platform_user_id="tg_user_new",
        payment_phone="+254711111111",
        pin="222222",
    )
    assert second["activated"] is True

    with get_sync_db() as conn:
        rows = conn.execute(
            """
            SELECT platform_user_id
            FROM platform_sessions
            WHERE platform = 'telegram'
            """
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["platform_user_id"] == "tg_user_new"

    old_access = manager.check_access(platform="telegram", platform_user_id="tg_user_old")
    new_access = manager.check_access(platform="telegram", platform_user_id="tg_user_new")
    assert old_access["active"] is False
    assert new_access["active"] is True


def test_payment_cli_activate_and_access(isolated_db):
    _seed_subscription(
        paystack_ref="ref-cli-001",
        phone="+254733333333",
        pin="333333",
        amount=10.0,
    )

    root_dir = Path(__file__).resolve().parents[1]
    cli_path = root_dir / "frontend" / "payments" / "payment_cli.py"
    env = os.environ.copy()
    env["DB_PATH"] = str(isolated_db)
    env["AUTO_MIGRATE_LEGACY"] = "false"
    env["PAYSTACK_SECRET_KEY"] = "dummy-secret"

    activate_cmd = [
        sys.executable,
        str(cli_path),
        "activate",
        "--platform",
        "whatsapp",
        "--platform-user-id",
        "wa_user_1",
        "--payment-phone",
        "+254733333333",
        "--pin",
        "333333",
    ]
    activate_proc = subprocess.run(
        activate_cmd,
        cwd=str(root_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    activate_payload = json.loads(activate_proc.stdout.strip())
    assert activate_proc.returncode == 0
    assert activate_payload["success"] is True
    assert activate_payload["activated"] is True

    access_cmd = [
        sys.executable,
        str(cli_path),
        "access",
        "--platform",
        "whatsapp",
        "--platform-user-id",
        "wa_user_1",
    ]
    access_proc = subprocess.run(
        access_cmd,
        cwd=str(root_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    access_payload = json.loads(access_proc.stdout.strip())
    assert access_proc.returncode == 0
    assert access_payload["success"] is True
    assert access_payload["active"] is True
