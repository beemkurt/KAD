from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException
from pydantic import BaseModel, ValidationError

from app.config import get_settings


class TelegramMiniAppUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    allows_write_to_pm: bool | None = None
    photo_url: str | None = None


class TelegramAuthError(ValueError):
    pass


def validate_telegram_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int,
) -> TelegramMiniAppUser:
    if not init_data:
        raise TelegramAuthError(
            "Telegram initData отсутствует"
        )

    try:
        values = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
                strict_parsing=True,
            )
        )
    except ValueError as exc:
        raise TelegramAuthError(
            "Некорректный формат Telegram initData"
        ) from exc

    received_hash = values.pop("hash", None)

    if not received_hash:
        raise TelegramAuthError(
            "Подпись Telegram отсутствует"
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(values.items())
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        received_hash,
        expected_hash,
    ):
        raise TelegramAuthError(
            "Подпись Telegram недействительна"
        )

    try:
        auth_date = int(values["auth_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramAuthError(
            "Telegram auth_date отсутствует"
        ) from exc

    now = int(time.time())

    if auth_date > now + 60:
        raise TelegramAuthError(
            "Telegram auth_date находится в будущем"
        )

    if now - auth_date > max_age_seconds:
        raise TelegramAuthError(
            "Telegram initData устарела"
        )

    raw_user = values.get("user")

    if not raw_user:
        raise TelegramAuthError(
            "Данные пользователя отсутствуют"
        )

    try:
        user = TelegramMiniAppUser.model_validate(
            json.loads(raw_user)
        )
    except (
        json.JSONDecodeError,
        ValidationError,
        TypeError,
    ) as exc:
        raise TelegramAuthError(
            "Некорректные данные пользователя"
        ) from exc

    if user.is_bot:
        raise TelegramAuthError(
            "Бот не может войти в Mini App"
        )

    return user


def require_telegram_user(
    x_telegram_init_data: str | None = Header(
        default=None,
        alias="X-Telegram-Init-Data",
    ),
) -> TelegramMiniAppUser:
    settings = get_settings()

    try:
        return validate_telegram_init_data(
            x_telegram_init_data or "",
            bot_token=(
                settings.telegram_bot_token
                .get_secret_value()
            ),
            max_age_seconds=(
                settings
                .telegram_init_data_max_age_seconds
            ),
        )
    except TelegramAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc
