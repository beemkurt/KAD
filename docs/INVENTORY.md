# KAD — Инвентаризация

> Технический паспорт компонентов. Значения без свежей серверной проверки не повышаются выше `KNOWN`.

Последнее обновление: **2026-08-25** (репозиторий проверен; VPS не опрашивался).

## Репозиторий

| Компонент | Состояние | Статус |
|---|---|---|
| GitHub repository | `beemkurt/KAD`, public | `VERIFIED` 2026-08-25 |
| Default branch | `main` | `VERIFIED` 2026-08-25 |
| Repository scope | Документация и история решений | `VERIFIED` 2026-08-25 |
| Application source code | В GitHub пока отсутствует | `VERIFIED` 2026-08-25 |

## Инфраструктура

| Компонент | Последнее известное состояние | Статус |
|---|---|---|
| VPS provider | Senko | `KNOWN` |
| OS | Ubuntu 24.04 | `KNOWN` |
| Domain | `kaditsolution.site` | `KNOWN` |
| VPN panel | 3x-ui | `KNOWN` |
| VPN protocol | Hysteria2 | `KNOWN` |
| VPN availability | Ранее сообщался как недоступный | `NEEDS VERIFICATION` |
| Reverse proxy / web | Caddy | `KNOWN` |
| SSH hardening | Вход по ключам; парольный вход и root login отключались | `KNOWN` |
| Firewall / protection | UFW и fail2ban настраивались | `KNOWN` |
| TLS renewal | Механизм требует проверки надёжности | `NEEDS VERIFICATION` |
| Backups | Состояние и восстановимость не подтверждены | `NEEDS VERIFICATION` |

## Приложение

| Компонент | Последнее известное состояние | Статус |
|---|---|---|
| Backend | Python / FastAPI | `KNOWN` |
| Backend service | `kad-backend`, ранее работал | `KNOWN` |
| Telegram bot | aiogram 3 | `KNOWN` |
| Bot service | `kad-bot`, ранее работал | `KNOWN` |
| Database | SQLite | `KNOWN` |
| Mini App | Существует как часть продукта; точное состояние не инвентаризировано | `NEEDS VERIFICATION` |
| Source locations | Требуется определить на VPS | `NEEDS VERIFICATION` |

## Намеренно не хранится в публичном репозитории

- пароли, API- и bot-токены;
- VPN credentials и пользовательские ссылки;
- приватные SSH- и TLS-ключи;
- реальные `.env`;
- production-база и пользовательские данные;
- резервные копии и дампы;
- логи с чувствительными данными.

Следующая актуализация выполняется после [read-only аудита VPS](runbooks/README.md#read-only-аудит-vps).

## Навигация

[README](../README.md) · [Текущее состояние](CURRENT.md) · [Архитектура](ARCHITECTURE.md) · [Runbooks](runbooks/README.md)
