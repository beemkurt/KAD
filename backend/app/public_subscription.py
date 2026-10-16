from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.db import connect


TOKEN_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{8,64}\.[A-Za-z0-9_-]{32,96}$"
)


class PublicSubscriptionNotFound(RuntimeError):
    pass


class PublicSubscriptionUpstreamError(RuntimeError):
    pass


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


def resolve_public_token(
    token: str,
) -> dict[str, Any]:
    if not TOKEN_PATTERN.fullmatch(token):
        raise PublicSubscriptionNotFound()

    public_id, _ = token.split(".", 1)

    settings = get_settings()

    app_secret = (
        settings.public_link_secret
        .get_secret_value()
    )

    calculated_hash = _hash_token(
        token,
        app_secret=app_secret,
    )

    now_ms = int(time.time() * 1000)

    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                pst.id AS token_id,
                pst.token_hash,
                pst.is_active AS token_active,

                vc.sub_id,
                vc.enabled AS vpn_enabled,

                s.status AS subscription_status,
                s.expires_at

            FROM public_subscription_tokens AS pst

            JOIN vpn_clients AS vc
                ON vc.id = pst.vpn_client_id

            JOIN users AS u
                ON u.id = vc.user_id

            LEFT JOIN subscriptions AS s
                ON s.id = (
                    SELECT id
                    FROM subscriptions
                    WHERE user_id = u.id
                    ORDER BY id DESC
                    LIMIT 1
                )

            WHERE pst.public_id = ?
            LIMIT 1
            """,
            (public_id,),
        ).fetchone()

        if row is None:
            raise PublicSubscriptionNotFound()

        hash_is_valid = hmac.compare_digest(
            row["token_hash"],
            calculated_hash,
        )

        subscription_is_valid = (
            row["subscription_status"] == "active"
            and (
                row["expires_at"] is None
                or int(row["expires_at"]) > now_ms
            )
        )

        if not all(
            (
                hash_is_valid,
                bool(row["token_active"]),
                bool(row["vpn_enabled"]),
                subscription_is_valid,
                bool(row["sub_id"]),
            )
        ):
            raise PublicSubscriptionNotFound()

        connection.execute(
            """
            UPDATE public_subscription_tokens
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["token_id"],),
        )

        connection.commit()

        return {
            "sub_id": row["sub_id"],
        }


async def fetch_public_subscription(
    token: str,
) -> tuple[bytes, dict[str, str]]:
    resolved = resolve_public_token(token)

    settings = get_settings()

    upstream_base = str(
        settings.public_sub_base_url
    ).rstrip("/")

    if not upstream_base:
        raise PublicSubscriptionUpstreamError(
            "Внутренний адрес подписок не настроен"
        )

    encoded_sub_id = quote(
        str(resolved["sub_id"]),
        safe="",
    )

    upstream_url = (
        f"{upstream_base}/{encoded_sub_id}"
    )

    try:
        async with httpx.AsyncClient(
            verify=settings.xui_verify_tls,
            timeout=10,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                upstream_url
            )

    except httpx.HTTPError as exc:
        raise PublicSubscriptionUpstreamError(
            "Сервис подписок недоступен"
        ) from exc

    if response.status_code != 200:
        raise PublicSubscriptionUpstreamError(
            "Сервис подписок вернул ошибку"
        )

    response_headers: dict[str, str] = {
        "Cache-Control": (
            "private, no-store, no-cache, "
            "must-revalidate, max-age=0"
        ),
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }

    allowed_headers = (
        "content-type",
        "subscription-userinfo",
        "profile-title",
        "profile-update-interval",
    )

    for header_name in allowed_headers:
        value = response.headers.get(
            header_name
        )

        if value:
            response_headers[header_name] = value

    if "content-type" not in response_headers:
        response_headers["content-type"] = (
            "text/plain; charset=utf-8"
        )

    return (
        response.content,
        response_headers,
    )
