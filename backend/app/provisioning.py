from __future__ import annotations

import secrets
import time
from typing import Any

from app.config import Settings
from app.connection_tokens import get_or_create_connection
from app.db import (
    get_state_by_telegram_id,
    purge_user,
    save_provisioned_state,
    upsert_user,
)
from app.xui import XUIClient, XUIError


class ProvisioningError(RuntimeError):
    pass


class ProvisioningService:
    def __init__(
        self,
        settings: Settings,
        xui: XUIClient,
    ) -> None:
        self.settings = settings
        self.xui = xui

    async def provision_test_client(
        self,
        *,
        telegram_id: int,
        duration_minutes: int,
    ) -> dict[str, Any]:
        existing = get_state_by_telegram_id(
            telegram_id
        )

        if existing and existing.get("xui_email"):
            return {
                "created": False,
                **self._public_state(existing),
            }

        if existing is not None:
            user_id = int(existing["user_id"])
        else:
            user_id = upsert_user(
                telegram_id,
                first_name="Internal test",
                language_code="ru",
            )

        xui_email = (
            f"kad_{secrets.token_hex(12)}"
        )

        now_ms = int(time.time() * 1000)

        expiry_ms = (
            now_ms
            + duration_minutes * 60 * 1000
        )

        # В 3x-ui значение 0 означает отсутствие
        # тарифного ограничения по трафику.
        total_bytes = 0

        xui_created = False

        try:
            await self.xui.create_client(
                email=xui_email,
                inbound_id=self.settings.xui_inbound_id,
                expiry_time=expiry_ms,
                total_bytes=total_bytes,
            )

            xui_created = True

            xui_state = await self.xui.get_client(
                xui_email
            )

            client = xui_state["client"]

            sub_id = (
                client.get("subId")
                or client.get("sub_id")
            )

            if not sub_id:
                raise ProvisioningError(
                    "3x-ui не вернул subId"
                )

            save_provisioned_state(
                user_id=user_id,
                plan_code="internal_test",
                starts_at=now_ms,
                expires_at=expiry_ms,
                xui_email=xui_email,
                sub_id=str(sub_id),
                inbound_id=self.settings.xui_inbound_id,
                total_bytes=total_bytes,
            )

        except Exception as exc:
            if xui_created:
                try:
                    await self.xui.delete_client(
                        xui_email
                    )
                except XUIError:
                    pass

            # Не удаляем пользователя при ошибке выдачи VPN.
            # Он мог существовать до начала этой операции.
            if isinstance(
                exc,
                (XUIError, ProvisioningError),
            ):
                raise

            raise ProvisioningError(
                "Не удалось сохранить выданного клиента"
            ) from exc

        state = get_state_by_telegram_id(
            telegram_id
        )

        if state is None:
            raise ProvisioningError(
                "Состояние клиента не найдено после создания"
            )

        return {
            "created": True,
            **self._public_state(state),
        }

    def get_state(
        self,
        telegram_id: int,
    ) -> dict[str, Any] | None:
        state = get_state_by_telegram_id(
            telegram_id
        )

        if state is None:
            return None

        return self._public_state(state)

    async def purge_test_client(
        self,
        telegram_id: int,
    ) -> bool:
        state = get_state_by_telegram_id(
            telegram_id
        )

        if state is None:
            return False

        xui_email = state.get("xui_email")

        if xui_email:
            await self.xui.delete_client(
                str(xui_email)
            )

        purge_user(telegram_id)

        return True

    def _public_state(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        telegram_id = state.get("telegram_id")

        connection = (
            get_or_create_connection(
                int(telegram_id)
            )
            if telegram_id is not None
            else None
        )

        return {
            "telegram_id": telegram_id,
            "xui_email": state.get("xui_email"),
            "inbound_id": state.get("inbound_id"),
            "enabled": bool(state.get("enabled")),
            "expiry_time": state.get("expiry_time"),
            "total_bytes": state.get("total_bytes"),
            "subscription_status": (
                state.get("subscription_status")
            ),
            "subscription_url": (
                connection.get("subscription_url")
                if connection
                and connection.get("available")
                else None
            ),
        }
