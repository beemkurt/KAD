from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db import connect, upsert_user
from app.telegram_auth import TelegramMiniAppUser


def _milliseconds_to_iso(
    value: object,
) -> str | None:
    try:
        milliseconds = int(value or 0)
    except (TypeError, ValueError):
        return None

    if milliseconds <= 0:
        return None

    moment = datetime.fromtimestamp(
        milliseconds / 1000,
        tz=timezone.utc,
    )

    return (
        moment
        .isoformat()
        .replace("+00:00", "Z")
    )


def get_or_create_profile(
    telegram_user: TelegramMiniAppUser,
    *,
    admin_id: int,
) -> dict[str, Any]:
    user_id = upsert_user(
        telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        language_code=telegram_user.language_code,
    )

    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                u.id AS user_id,
                u.telegram_id,
                u.username,
                u.first_name,
                u.last_name,
                u.language_code,
                u.created_at,

                s.plan_code,
                s.status AS subscription_status,
                s.starts_at,
                s.expires_at,

                p.title AS plan_title,
                p.duration_unit,
                p.duration_value,
                p.price_minor,
                p.currency,

                vc.inbound_id,
                vc.enabled AS vpn_enabled

            FROM users AS u

            LEFT JOIN subscriptions AS s
                ON s.id = (
                    SELECT id
                    FROM subscriptions
                    WHERE user_id = u.id
                    ORDER BY id DESC
                    LIMIT 1
                )

            LEFT JOIN plans AS p
                ON p.code = s.plan_code

            LEFT JOIN vpn_clients AS vc
                ON vc.user_id = u.id

            WHERE u.id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "Пользователь не найден после регистрации"
        )

    now_ms = int(
        datetime.now(timezone.utc).timestamp()
        * 1000
    )

    subscription: dict[str, Any] | None = None

    if row["plan_code"] is not None:
        stored_status = (
            row["subscription_status"]
            or "pending"
        )

        effective_status = stored_status

        expires_at = row["expires_at"]

        if (
            stored_status == "active"
            and expires_at
            and int(expires_at) <= now_ms
        ):
            effective_status = "expired"

        subscription = {
            "status": effective_status,
            "plan": {
                "code": row["plan_code"],
                "title": row["plan_title"],
                "duration": {
                    "unit": row["duration_unit"],
                    "value": row["duration_value"],
                },
                "price": {
                    "amount_minor": row["price_minor"],
                    "currency": row["currency"],
                },
            },
            "starts_at": _milliseconds_to_iso(
                row["starts_at"]
            ),
            "expires_at": _milliseconds_to_iso(
                row["expires_at"]
            ),
        }

    vpn_configured = (
        row["inbound_id"] is not None
    )

    return {
        "user": {
            "telegram_id": row["telegram_id"],
            "username": row["username"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "language_code": row["language_code"],
            "is_admin": (
                row["telegram_id"] == admin_id
            ),
            "created_at": row["created_at"],
        },
        "subscription": subscription,
        "vpn": {
            "configured": vpn_configured,
            "enabled": (
                bool(row["vpn_enabled"])
                if vpn_configured
                else False
            ),
            "inbound_id": row["inbound_id"],
            "traffic": {
                "unlimited": True,
                "display": "∞",
            },
        },
    }
