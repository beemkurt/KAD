from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
import time
from typing import Any

from app.config import get_settings
from app.db import connect


class ConnectionUnavailable(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code


def _derive_token_secret(
    *,
    vpn_client_id: int,
    public_id: str,
    app_secret: str,
) -> str:
    message = (
        f"kad-subscription:"
        f"{vpn_client_id}:"
        f"{public_id}"
    ).encode("utf-8")

    digest = hmac.new(
        app_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()

    return (
        base64.urlsafe_b64encode(digest)
        .rstrip(b"=")
        .decode("ascii")
    )


def _build_token(
    *,
    vpn_client_id: int,
    public_id: str,
    app_secret: str,
) -> str:
    token_secret = _derive_token_secret(
        vpn_client_id=vpn_client_id,
        public_id=public_id,
        app_secret=app_secret,
    )

    return f"{public_id}.{token_secret}"


def _hash_token(
    token: str,
    *,
    app_secret: str,
) -> str:
    return hmac.new(
        app_secret.encode("utf-8"),
        b"public-token:" + token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _create_token_record(
    connection: sqlite3.Connection,
    *,
    vpn_client_id: int,
    app_secret: str,
) -> tuple[str, str]:
    for _ in range(5):
        public_id = secrets.token_urlsafe(12)

        token = _build_token(
            vpn_client_id=vpn_client_id,
            public_id=public_id,
            app_secret=app_secret,
        )

        token_hash = _hash_token(
            token,
            app_secret=app_secret,
        )

        try:
            connection.execute(
                """
                INSERT INTO public_subscription_tokens (
                    vpn_client_id,
                    public_id,
                    token_hash,
                    is_active
                )
                VALUES (?, ?, ?, 1)
                """,
                (
                    vpn_client_id,
                    public_id,
                    token_hash,
                ),
            )

            return public_id, token

        except sqlite3.IntegrityError:
            existing = connection.execute(
                """
                SELECT public_id
                FROM public_subscription_tokens
                WHERE vpn_client_id = ?
                LIMIT 1
                """,
                (vpn_client_id,),
            ).fetchone()

            if existing is not None:
                public_id = existing["public_id"]

                token = _build_token(
                    vpn_client_id=vpn_client_id,
                    public_id=public_id,
                    app_secret=app_secret,
                )

                return public_id, token

    raise RuntimeError(
        "Не удалось создать публичный токен"
    )


def get_or_create_connection(
    telegram_id: int,
) -> dict[str, Any]:
    settings = get_settings()

    app_secret = (
        settings.public_link_secret
        .get_secret_value()
    )

    now_ms = int(time.time() * 1000)

    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                u.id AS user_id,

                s.status AS subscription_status,
                s.expires_at,

                vc.id AS vpn_client_id,
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

            LEFT JOIN vpn_clients AS vc
                ON vc.user_id = u.id

            WHERE u.telegram_id = ?
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()

        if row is None:
            raise ConnectionUnavailable(
                "user_not_found",
                "Пользователь не зарегистрирован",
            )

        if row["subscription_status"] is None:
            raise ConnectionUnavailable(
                "subscription_missing",
                "Активная подписка отсутствует",
            )

        if row["subscription_status"] != "active":
            raise ConnectionUnavailable(
                "subscription_inactive",
                "Подписка не активна",
            )

        expires_at = row["expires_at"]

        if (
            expires_at is not None
            and int(expires_at) <= now_ms
        ):
            raise ConnectionUnavailable(
                "subscription_expired",
                "Срок подписки истёк",
            )

        vpn_client_id = row["vpn_client_id"]

        if vpn_client_id is None:
            raise ConnectionUnavailable(
                "vpn_not_configured",
                "VPN-подключение ещё не настроено",
            )

        if not bool(row["vpn_enabled"]):
            raise ConnectionUnavailable(
                "vpn_disabled",
                "VPN-подключение отключено",
            )

        token_row = connection.execute(
            """
            SELECT
                public_id,
                token_hash,
                is_active
            FROM public_subscription_tokens
            WHERE vpn_client_id = ?
            LIMIT 1
            """,
            (vpn_client_id,),
        ).fetchone()

        if token_row is None:
            public_id, token = _create_token_record(
                connection,
                vpn_client_id=vpn_client_id,
                app_secret=app_secret,
            )

        else:
            public_id = token_row["public_id"]

            token = _build_token(
                vpn_client_id=vpn_client_id,
                public_id=public_id,
                app_secret=app_secret,
            )

            expected_hash = _hash_token(
                token,
                app_secret=app_secret,
            )

            token_is_valid = (
                bool(token_row["is_active"])
                and hmac.compare_digest(
                    token_row["token_hash"],
                    expected_hash,
                )
            )

            if not token_is_valid:
                public_id = secrets.token_urlsafe(12)

                token = _build_token(
                    vpn_client_id=vpn_client_id,
                    public_id=public_id,
                    app_secret=app_secret,
                )

                token_hash = _hash_token(
                    token,
                    app_secret=app_secret,
                )

                connection.execute(
                    """
                    UPDATE public_subscription_tokens
                    SET
                        public_id = ?,
                        token_hash = ?,
                        is_active = 1,
                        updated_at = CURRENT_TIMESTAMP,
                        revoked_at = NULL
                    WHERE vpn_client_id = ?
                    """,
                    (
                        public_id,
                        token_hash,
                        vpn_client_id,
                    ),
                )

        connection.commit()

    base_url = (
        settings.public_subscription_url_base
        .rstrip("/")
    )

    return {
        "available": True,
        "subscription_url": (
            f"{base_url}/{token}"
        ),
        "traffic": {
            "unlimited": True,
            "display": "∞",
        },
    }
