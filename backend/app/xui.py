from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


class XUIError(RuntimeError):
    """Безопасная ошибка взаимодействия с 3x-ui."""


class XUIClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.xui_base_url.rstrip("/")
        token = settings.xui_api_token
        self.api_token = (
            token.get_secret_value()
            if hasattr(token, "get_secret_value")
            else str(token)
        )
        self.verify_tls = settings.xui_verify_tls

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                verify=self.verify_tls,
                timeout=15.0,
            ) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    json=json,
                )

                response.raise_for_status()
                payload = response.json()

        except httpx.HTTPError as exc:
            raise XUIError(
                "3x-ui недоступен или вернул ошибку HTTP"
            ) from exc

        except ValueError as exc:
            raise XUIError(
                "3x-ui вернул некорректный JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise XUIError(
                "3x-ui вернул неожиданный формат ответа"
            )

        if not payload.get("success"):
            raise XUIError(
                payload.get("msg")
                or "Операция 3x-ui завершилась ошибкой"
            )

        return payload

    async def get_inbound(
        self,
        inbound_id: int,
    ) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            f"/panel/api/inbounds/get/{inbound_id}",
        )

        inbound = payload.get("obj")

        if not isinstance(inbound, dict):
            raise XUIError(
                "Inbound отсутствует в ответе 3x-ui"
            )

        return inbound

    async def create_client(
        self,
        *,
        email: str,
        inbound_id: int,
        expiry_time: int,
        total_bytes: int,
    ) -> None:
        await self._request(
            "POST",
            "/panel/api/clients/add",
            json={
                "client": {
                    "email": email,
                    "totalGB": total_bytes,
                    "expiryTime": expiry_time,
                    "tgId": 0,
                    "limitIp": 0,
                    "enable": True,
                },
                "inboundIds": [inbound_id],
            },
        )

    async def get_client(
        self,
        email: str,
    ) -> dict[str, Any]:
        safe_email = quote(email, safe="")

        payload = await self._request(
            "GET",
            f"/panel/api/clients/get/{safe_email}",
        )

        obj = payload.get("obj")

        if not isinstance(obj, dict):
            raise XUIError(
                "Клиент отсутствует в ответе 3x-ui"
            )

        client = obj.get("client") or obj

        if not isinstance(client, dict):
            raise XUIError(
                "Некорректные данные клиента 3x-ui"
            )

        inbound_ids = (
            obj.get("inboundIds")
            or obj.get("inbound_ids")
            or []
        )

        return {
            "client": client,
            "inbound_ids": inbound_ids,
        }

    async def update_client(
        self,
        *,
        email: str,
        client: dict[str, Any],
        inbound_ids: list[int],
    ) -> None:
        safe_email = quote(email, safe="")
        source = dict(client)

        def integer(
            key: str,
            default: int = 0,
        ) -> int:
            try:
                return int(
                    source.get(key)
                    if source.get(key) is not None
                    else default
                )
            except (TypeError, ValueError):
                return default

        # GET /clients/get возвращает ClientRecord:
        # его id является числовым ID строки базы.
        #
        # POST /clients/update принимает model.Client:
        # его id является строковым UUID протокола.
        wire_id = source.get("uuid")

        if not isinstance(wire_id, str):
            candidate = source.get("id")

            wire_id = (
                candidate
                if isinstance(candidate, str)
                else ""
            )

        payload: dict[str, Any] = {
            "id": wire_id,
            "security": str(
                source.get("security") or ""
            ),
            "password": str(
                source.get("password") or ""
            ),
            "flow": str(
                source.get("flow") or ""
            ),
            "auth": str(
                source.get("auth") or ""
            ),
            "email": str(
                source.get("email") or email
            ),
            "limitIp": integer("limitIp"),
            "totalGB": integer("totalGB"),
            "expiryTime": integer("expiryTime"),
            "enable": bool(
                source.get("enable", True)
            ),
            "tgId": integer("tgId"),
            "subId": str(
                source.get("subId") or ""
            ),
            "group": str(
                source.get("group") or ""
            ),
            "comment": str(
                source.get("comment") or ""
            ),
            "reset": integer("reset"),
        }

        reverse = source.get("reverse")

        if isinstance(reverse, dict):
            payload["reverse"] = reverse

        inbound_filter = ",".join(
            str(int(inbound_id))
            for inbound_id in inbound_ids
        )

        request_path = (
            "/panel/api/clients/update/"
            f"{safe_email}"
        )

        if inbound_filter:
            request_path += (
                "?inboundIds="
                + quote(
                    inbound_filter,
                    safe=",",
                )
            )

        await self._request(
            "POST",
            request_path,
            json=payload,
        )

    async def delete_client(
        self,
        email: str,
    ) -> None:
        safe_email = quote(email, safe="")

        await self._request(
            "POST",
            f"/panel/api/clients/del/{safe_email}",
        )
