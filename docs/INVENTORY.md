# KAD — Инвентаризация

> Технический паспорт компонентов проекта.

## Статусы

- `VERIFIED` — подтверждено на действующей системе
- `KNOWN` — подтверждалось ранее, но могло измениться
- `NEEDS VERIFICATION` — требуется проверить
- `PLANNED` — запланировано

## Инфраструктура

| Компонент | Известное состояние | Статус |
|---|---|---|
| VPS provider | Senko | `KNOWN` |
| OS | Ubuntu 24.04 | `KNOWN` |
| Domain | kaditsolution.site | `KNOWN` |
| VPN panel | 3x-ui | `KNOWN` |
| VPN protocol | Hysteria2 | `KNOWN` |
| Reverse proxy / web | Caddy | `KNOWN` |

## KAD backend

| Компонент | Известное состояние | Статус |
|---|---|---|
| Backend | Python / FastAPI | `KNOWN` |
| Telegram bot | aiogram 3 | `KNOWN` |
| Bot service | kad-bot | `KNOWN` |
| Backend service | kad-backend | `KNOWN` |
| Database | Требуется подтвердить текущее состояние | `NEEDS VERIFICATION` |

## Текущее состояние

VPN сообщался как недоступный 2026-08-13.

Причина пока не подтверждена.

Статус: `NEEDS VERIFICATION`

## Не хранится в публичном репозитории

- пароли;
- API-токены;
- Telegram Bot Token;
- VPN credentials;
- приватные SSH-ключи;
- реальные `.env`;
- приватные TLS-ключи;
- пользовательские данные;
- резервные копии баз данных.

Точное состояние инфраструктуры будет заполнено после read-only аудита VPS.
