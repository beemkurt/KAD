from __future__ import annotations

from typing import Any

from app.db import connect


def get_public_plans() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                code,
                title,
                description,
                duration_unit,
                duration_value,
                price_minor,
                currency,
                device_limit
            FROM plans
            WHERE is_public = 1
              AND is_active = 1
            ORDER BY sort_order, id
            """
        ).fetchall()

    return [
        {
            "code": row["code"],
            "title": row["title"],
            "description": row["description"],
            "duration": {
                "unit": row["duration_unit"],
                "value": row["duration_value"],
            },
            "price": {
                "amount_minor": row["price_minor"],
                "currency": row["currency"],
            },
            "traffic": {
                "unlimited": True,
                "display": "∞",
            },
            "device_limit": row["device_limit"],
        }
        for row in rows
    ]
