from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.migrations import apply_migrations


DB_PATH = Path("/var/lib/kad/kad.db")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT,

    is_blocked INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    plan_code TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending',

    starts_at INTEGER,
    expires_at INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vpn_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    xui_email TEXT NOT NULL UNIQUE,
    sub_id TEXT NOT NULL UNIQUE,

    inbound_id INTEGER NOT NULL DEFAULT 4,

    device_label TEXT,
    platform TEXT,

    enabled INTEGER NOT NULL DEFAULT 1,

    expiry_time INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id
    ON subscriptions(user_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_status
    ON subscriptions(status);

CREATE INDEX IF NOT EXISTS idx_vpn_clients_user_id
    ON vpn_clients(user_id);

CREATE INDEX IF NOT EXISTS idx_vpn_clients_inbound_id
    ON vpn_clients(inbound_id);

"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DB_PATH,
        timeout=10,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA busy_timeout = 10000"
    )

    return connection


def init_db() -> None:
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with closing(connect()) as connection, connection:
        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.executescript(SCHEMA)
        apply_migrations(connection)
        connection.commit()

    DB_PATH.chmod(0o600)


def upsert_user(
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
) -> int:
    with closing(connect()) as connection, connection:
        connection.execute(
            """
            INSERT INTO users (
                telegram_id,
                username,
                first_name,
                last_name,
                language_code
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                telegram_id,
                username,
                first_name,
                last_name,
                language_code,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()

        connection.commit()

    if row is None:
        raise RuntimeError(
            "Не удалось сохранить пользователя"
        )

    return int(row["id"])


def save_provisioned_state(
    *,
    user_id: int,
    plan_code: str,
    starts_at: int,
    expires_at: int,
    xui_email: str,
    sub_id: str,
    inbound_id: int,
    total_bytes: int,
) -> None:
    with closing(connect()) as connection, connection:
        connection.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                plan_code,
                status,
                starts_at,
                expires_at
            )
            VALUES (?, ?, 'active', ?, ?)
            """,
            (
                user_id,
                plan_code,
                starts_at,
                expires_at,
            ),
        )

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
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                user_id,
                xui_email,
                sub_id,
                inbound_id,
                expires_at,
                total_bytes,
            ),
        )

        connection.commit()



def list_vpn_clients_for_user(
    user_id: int,
) -> list[dict[str, Any]]:
    with closing(connect()) as connection, connection:
        rows = connection.execute(
            """
            SELECT *
            FROM vpn_clients
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_vpn_client_for_user(
    *,
    user_id: int,
    vpn_client_id: int,
) -> dict[str, Any] | None:
    with closing(connect()) as connection, connection:
        row = connection.execute(
            """
            SELECT *
            FROM vpn_clients
            WHERE id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (vpn_client_id, user_id),
        ).fetchone()

    return dict(row) if row is not None else None



def get_state_by_telegram_id(
    telegram_id: int,
) -> dict[str, Any] | None:
    with closing(connect()) as connection, connection:
        row = connection.execute(
            """
            SELECT
                u.id AS user_id,
                u.telegram_id,

                vc.xui_email,
                vc.sub_id,
                vc.inbound_id,
                vc.enabled,
                vc.expiry_time,
                vc.total_bytes,

                s.plan_code,
                s.status AS subscription_status,
                s.starts_at,
                s.expires_at

            FROM users AS u

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

            WHERE u.telegram_id = ?
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def purge_user(
    telegram_id: int,
) -> bool:
    with closing(connect()) as connection, connection:
        cursor = connection.execute(
            """
            DELETE FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )

        connection.commit()

    return cursor.rowcount > 0


def get_health() -> dict[str, Any]:
    with closing(connect()) as connection, connection:
        connection.execute("SELECT 1").fetchone()

        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        tables = [
            row["name"]
            for row in table_rows
        ]

        counts: dict[str, int] = {}

        for table in (
            "users",
            "subscriptions",
            "vpn_clients",
        ):
            row = connection.execute(
                f'SELECT COUNT(*) AS count FROM "{table}"'
            ).fetchone()

            counts[table] = int(row["count"])

    return {
        "status": "ok",
        "database": DB_PATH.name,
        "tables": tables,
        "counts": counts,
    }
