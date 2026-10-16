from __future__ import annotations

import secrets
import sqlite3
from typing import Any

from app.db import connect


class OrderError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)

        self.code = code
        self.status_code = status_code


def _serialize_order(
    row: sqlite3.Row,
) -> dict[str, Any]:
    return {
        "id": row["public_id"],
        "status": row["status"],
        "plan": {
            "code": row["plan_code"],
            "title": row["plan_title"],
            "duration": {
                "unit": row["duration_unit"],
                "value": row["duration_value"],
            },
        },
        "price": {
            "amount_minor": row["amount_minor"],
            "currency": row["currency"],
        },
        "payment": {
            "provider": row["payment_provider"],
            "provider_payment_id": (
                row["provider_payment_id"]
            ),
        },
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "paid_at": row["paid_at"],
        "cancelled_at": row["cancelled_at"],
    }


def _select_order(
    connection: sqlite3.Connection,
    order_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT
            id,
            public_id,
            user_id,
            plan_id,
            plan_code,
            plan_title,
            duration_unit,
            duration_value,
            amount_minor,
            currency,
            status,
            payment_provider,
            provider_payment_id,
            created_at,
            updated_at,
            paid_at,
            cancelled_at
        FROM orders
        WHERE id = ?
        LIMIT 1
        """,
        (order_id,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            "Заказ не найден после сохранения"
        )

    return row


def create_order(
    telegram_id: int,
    plan_code: str,
) -> tuple[dict[str, Any], bool]:
    with connect() as connection:
        user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE telegram_id = ?
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()

        if user is None:
            raise OrderError(
                "user_not_found",
                "Пользователь не зарегистрирован",
                status_code=404,
            )

        plan = connection.execute(
            """
            SELECT
                id,
                code,
                title,
                duration_unit,
                duration_value,
                price_minor,
                currency
            FROM plans
            WHERE code = ?
              AND is_public = 1
              AND is_active = 1
              AND price_minor IS NOT NULL
            LIMIT 1
            """,
            (plan_code,),
        ).fetchone()

        if plan is None:
            raise OrderError(
                "plan_unavailable",
                "Тариф недоступен для покупки",
                status_code=404,
            )

        pending = connection.execute(
            """
            SELECT
                id,
                plan_code
            FROM orders
            WHERE user_id = ?
              AND status = 'pending'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user["id"],),
        ).fetchone()

        if (
            pending is not None
            and pending["plan_code"] == plan["code"]
        ):
            return (
                _serialize_order(
                    _select_order(
                        connection,
                        pending["id"],
                    )
                ),
                False,
            )

        if pending is not None:
            raise OrderError(
                "pending_order_exists",
                (
                    "У вас уже есть заказ, "
                    "ожидающий оплаты"
                ),
                status_code=409,
            )

        public_id = secrets.token_urlsafe(18)

        cursor = connection.execute(
            """
            INSERT INTO orders (
                public_id,
                user_id,
                plan_id,
                plan_code,
                plan_title,
                duration_unit,
                duration_value,
                amount_minor,
                currency,
                status
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                'pending'
            )
            """,
            (
                public_id,
                user["id"],
                plan["id"],
                plan["code"],
                plan["title"],
                plan["duration_unit"],
                plan["duration_value"],
                plan["price_minor"],
                plan["currency"],
            ),
        )

        order = _select_order(
            connection,
            int(cursor.lastrowid),
        )

    return _serialize_order(order), True


def get_current_order(
    telegram_id: int,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                o.id,
                o.public_id,
                o.user_id,
                o.plan_id,
                o.plan_code,
                o.plan_title,
                o.duration_unit,
                o.duration_value,
                o.amount_minor,
                o.currency,
                o.status,
                o.payment_provider,
                o.provider_payment_id,
                o.created_at,
                o.updated_at,
                o.paid_at,
                o.cancelled_at
            FROM orders AS o

            INNER JOIN users AS u
                ON u.id = o.user_id

            WHERE u.telegram_id = ?

            ORDER BY o.id DESC
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()

    if row is None:
        return None

    return _serialize_order(row)
