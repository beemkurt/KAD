from __future__ import annotations

import asyncio
import calendar
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import connect
from app.xui import XUIClient, XUIError


_PAYMENT_LOCK = asyncio.Lock()


class PaymentError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code


def _add_duration(
    base_ms: int,
    unit: str,
    value: int,
) -> int:
    base = datetime.fromtimestamp(
        base_ms / 1000,
        tz=timezone.utc,
    )

    if unit == "day":
        result = base + timedelta(days=value)

    elif unit == "month":
        month_index = (
            base.year * 12
            + base.month
            - 1
            + value
        )

        year = month_index // 12
        month = month_index % 12 + 1

        last_day = calendar.monthrange(
            year,
            month,
        )[1]

        result = base.replace(
            year=year,
            month=month,
            day=min(base.day, last_day),
        )

    else:
        raise PaymentError(
            "unsupported_duration",
            "Неизвестная единица срока тарифа",
        )

    return int(result.timestamp() * 1000)


def _load_order(
    public_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                o.id AS order_id,
                o.public_id,
                o.status AS order_status,

                o.plan_code,
                o.plan_title,
                o.duration_unit,
                o.duration_value,
                o.amount_minor,
                o.currency,

                u.id AS user_id,
                u.telegram_id,
                u.username,
                u.first_name,

                vc.id AS vpn_client_id,
                vc.xui_email,
                vc.sub_id,
                vc.inbound_id,
                vc.enabled AS vpn_enabled,
                vc.expiry_time AS vpn_expiry_time,
                vc.total_bytes,

                s.expires_at AS subscription_expires_at

            FROM orders AS o

            INNER JOIN users AS u
                ON u.id = o.user_id

            LEFT JOIN vpn_clients AS vc
                ON vc.user_id = u.id

            LEFT JOIN subscriptions AS s
                ON s.id = (
                    SELECT id
                    FROM subscriptions
                    WHERE user_id = u.id
                    ORDER BY id DESC
                    LIMIT 1
                )

            WHERE o.public_id = ?
            LIMIT 1
            """,
            (public_id,),
        ).fetchone()

    return dict(row) if row else None


def get_latest_pending_order() -> (
    dict[str, Any] | None
):
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                o.public_id,
                o.status,
                o.plan_code,
                o.plan_title,
                o.duration_unit,
                o.duration_value,
                o.amount_minor,
                o.currency,
                o.created_at,

                u.telegram_id,
                u.username,
                u.first_name

            FROM orders AS o

            INNER JOIN users AS u
                ON u.id = o.user_id

            WHERE o.status = 'pending'

            ORDER BY o.id DESC
            LIMIT 1
            """
        ).fetchone()

    return dict(row) if row else None


def _paid_result(
    order: dict[str, Any],
    *,
    expires_at: int,
    already_paid: bool,
    vpn_created: bool,
) -> dict[str, Any]:
    return {
        "order_id": order["public_id"],
        "telegram_id": order["telegram_id"],
        "plan_code": order["plan_code"],
        "plan_title": order["plan_title"],
        "amount_minor": order["amount_minor"],
        "currency": order["currency"],
        "expires_at": expires_at,
        "already_paid": already_paid,
        "vpn_created": vpn_created,
    }


async def confirm_test_payment(
    public_id: str,
    *,
    xui: XUIClient,
    default_inbound_id: int,
) -> dict[str, Any]:
    async with _PAYMENT_LOCK:
        order = _load_order(public_id)

        if order is None:
            raise PaymentError(
                "order_not_found",
                "Заказ не найден",
            )

        if order["order_status"] == "paid":
            current_expiry = max(
                int(
                    order.get(
                        "subscription_expires_at"
                    )
                    or 0
                ),
                int(
                    order.get("vpn_expiry_time")
                    or 0
                ),
            )

            return _paid_result(
                order,
                expires_at=current_expiry,
                already_paid=True,
                vpn_created=False,
            )

        if order["order_status"] != "pending":
            raise PaymentError(
                "order_not_pending",
                "Этот заказ уже не ожидает оплаты",
            )

        now_ms = int(time.time() * 1000)

        base_ms = max(
            now_ms,
            int(
                order.get(
                    "subscription_expires_at"
                )
                or 0
            ),
            int(
                order.get("vpn_expiry_time")
                or 0
            ),
        )

        expires_at = _add_duration(
            base_ms,
            str(order["duration_unit"]),
            int(order["duration_value"]),
        )

        existing_email = order.get("xui_email")

        original_client: (
            dict[str, Any] | None
        ) = None

        original_inbound_ids: list[int] = []

        vpn_created = False
        xui_email: str
        sub_id: str
        inbound_id: int

        try:
            if existing_email:
                xui_email = str(existing_email)

                state = await xui.get_client(
                    xui_email
                )

                original_client = dict(
                    state["client"]
                )

                original_inbound_ids = [
                    int(value)
                    for value in (
                        state.get("inbound_ids")
                        or [
                            order.get("inbound_id")
                            or default_inbound_id
                        ]
                    )
                ]

                updated_client = dict(
                    original_client
                )

                updated_client["expiryTime"] = (
                    expires_at
                )
                updated_client["enable"] = True
                updated_client["totalGB"] = 0

                await xui.update_client(
                    email=xui_email,
                    client=updated_client,
                    inbound_ids=(
                        original_inbound_ids
                    ),
                )

                verified = await xui.get_client(
                    xui_email
                )

                verified_client = verified["client"]

                if (
                    int(
                        verified_client.get(
                            "expiryTime"
                        )
                        or 0
                    )
                    != expires_at
                ):
                    raise PaymentError(
                        "xui_update_mismatch",
                        (
                            "3x-ui не сохранил "
                            "новый срок действия"
                        ),
                    )

                if not bool(
                    verified_client.get("enable")
                ):
                    raise PaymentError(
                        "xui_client_disabled",
                        (
                            "3x-ui оставил "
                            "клиента отключённым"
                        ),
                    )

                sub_id = str(
                    order.get("sub_id") or ""
                )

                inbound_id = int(
                    order.get("inbound_id")
                    or default_inbound_id
                )

            else:
                xui_email = (
                    f"kad_{secrets.token_hex(12)}"
                )

                inbound_id = int(
                    default_inbound_id
                )

                await xui.create_client(
                    email=xui_email,
                    inbound_id=inbound_id,
                    expiry_time=expires_at,
                    total_bytes=0,
                )

                vpn_created = True

                state = await xui.get_client(
                    xui_email
                )

                client = state["client"]

                sub_id = str(
                    client.get("subId")
                    or client.get("sub_id")
                    or ""
                )

                if not sub_id:
                    raise PaymentError(
                        "xui_sub_id_missing",
                        "3x-ui не вернул subId",
                    )

        except (XUIError, PaymentError):
            if vpn_created:
                try:
                    await xui.delete_client(
                        xui_email
                    )
                except Exception:
                    pass

            raise

        try:
            with connect() as connection:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                current = connection.execute(
                    """
                    SELECT status
                    FROM orders
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (order["order_id"],),
                ).fetchone()

                if current is None:
                    raise PaymentError(
                        "order_disappeared",
                        "Заказ исчез из базы",
                    )

                if current["status"] == "paid":
                    connection.rollback()

                    return _paid_result(
                        order,
                        expires_at=expires_at,
                        already_paid=True,
                        vpn_created=False,
                    )

                if current["status"] != "pending":
                    raise PaymentError(
                        "order_status_changed",
                        (
                            "Статус заказа "
                            "уже изменился"
                        ),
                    )

                connection.execute(
                    """
                    UPDATE subscriptions
                    SET
                        status = 'expired',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                      AND status = 'active'
                    """,
                    (order["user_id"],),
                )

                connection.execute(
                    """
                    INSERT INTO subscriptions (
                        user_id,
                        plan_code,
                        status,
                        starts_at,
                        expires_at
                    )
                    VALUES (
                        ?,
                        ?,
                        'active',
                        ?,
                        ?
                    )
                    """,
                    (
                        order["user_id"],
                        order["plan_code"],
                        now_ms,
                        expires_at,
                    ),
                )

                if existing_email:
                    connection.execute(
                        """
                        UPDATE vpn_clients
                        SET
                            enabled = 1,
                            expiry_time = ?,
                            total_bytes = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                        """,
                        (
                            expires_at,
                            order["user_id"],
                        ),
                    )

                else:
                    connection.execute(
                        """
                        INSERT INTO vpn_clients (
                            user_id,
                            xui_email,
                            sub_id,
                            inbound_id,
                            enabled,
                            expiry_time,
                            total_bytes
                        )
                        VALUES (
                            ?,
                            ?,
                            ?,
                            ?,
                            1,
                            ?,
                            0
                        )
                        """,
                        (
                            order["user_id"],
                            xui_email,
                            sub_id,
                            inbound_id,
                            expires_at,
                        ),
                    )

                cursor = connection.execute(
                    """
                    UPDATE orders
                    SET
                        status = 'paid',
                        payment_provider = 'test',
                        provider_payment_id = ?,
                        paid_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                      AND status = 'pending'
                    """,
                    (
                        (
                            "test:"
                            + order["public_id"]
                        ),
                        order["order_id"],
                    ),
                )

                if cursor.rowcount != 1:
                    raise PaymentError(
                        "order_not_updated",
                        (
                            "Не удалось отметить "
                            "заказ оплаченным"
                        ),
                    )

                connection.commit()

        except Exception as exc:
            if existing_email and original_client:
                try:
                    await xui.update_client(
                        email=str(existing_email),
                        client=original_client,
                        inbound_ids=(
                            original_inbound_ids
                        ),
                    )
                except Exception:
                    raise PaymentError(
                        "rollback_failed",
                        (
                            "Не удалось откатить "
                            "изменение в 3x-ui"
                        ),
                    ) from exc

            elif vpn_created:
                try:
                    await xui.delete_client(
                        xui_email
                    )
                except Exception:
                    raise PaymentError(
                        "rollback_failed",
                        (
                            "Не удалось удалить "
                            "тестового клиента"
                        ),
                    ) from exc

            if isinstance(exc, PaymentError):
                raise

            raise PaymentError(
                "database_update_failed",
                (
                    "Не удалось сохранить "
                    "результат оплаты"
                ),
            ) from exc

        return _paid_result(
            order,
            expires_at=expires_at,
            already_paid=False,
            vpn_created=vpn_created,
        )
