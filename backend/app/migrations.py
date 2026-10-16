from __future__ import annotations

import sqlite3


MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (
        1,
        "create_plans",
        """
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT,

            duration_unit TEXT NOT NULL
                CHECK (duration_unit IN ('day', 'month')),
            duration_value INTEGER NOT NULL
                CHECK (duration_value > 0),

            price_minor INTEGER
                CHECK (price_minor IS NULL OR price_minor >= 0),
            currency TEXT NOT NULL DEFAULT 'RUB',

            device_limit INTEGER
                CHECK (device_limit IS NULL OR device_limit > 0),

            is_public INTEGER NOT NULL DEFAULT 1
                CHECK (is_public IN (0, 1)),
            is_active INTEGER NOT NULL DEFAULT 1
                CHECK (is_active IN (0, 1)),

            sort_order INTEGER NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_plans_public_active
            ON plans(is_public, is_active, sort_order);

        INSERT OR IGNORE INTO plans (
            code,
            title,
            description,
            duration_unit,
            duration_value,
            price_minor,
            currency,
            device_limit,
            is_public,
            is_active,
            sort_order
        )
        VALUES
            (
                'internal_test',
                'Тестовый доступ',
                'Служебный тариф администратора',
                'day',
                1,
                0,
                'RUB',
                NULL,
                0,
                1,
                0
            ),
            (
                'month_1',
                '1 месяц',
                'Доступ к KAD VPN на 1 месяц',
                'month',
                1,
                15000,
                'RUB',
                NULL,
                1,
                1,
                10
            ),
            (
                'month_3',
                '3 месяца',
                'Доступ к KAD VPN на 3 месяца',
                'month',
                3,
                45000,
                'RUB',
                NULL,
                1,
                1,
                20
            ),
            (
                'month_6',
                '6 месяцев',
                'Доступ к KAD VPN на 6 месяцев',
                'month',
                6,
                90000,
                'RUB',
                NULL,
                1,
                1,
                30
            ),
            (
                'month_12',
                '12 месяцев',
                'Доступ к KAD VPN на 12 месяцев',
                'month',
                12,
                180000,
                'RUB',
                NULL,
                1,
                1,
                40
            );
        """,
    ),
)



MIGRATIONS += (
    (
        2,
        "create_public_subscription_tokens",
        """
        CREATE TABLE IF NOT EXISTS public_subscription_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            vpn_client_id INTEGER NOT NULL UNIQUE,

            public_id TEXT NOT NULL UNIQUE,
            token_hash TEXT NOT NULL,

            is_active INTEGER NOT NULL DEFAULT 1
                CHECK (is_active IN (0, 1)),

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            last_used_at TEXT,
            revoked_at TEXT,

            FOREIGN KEY (vpn_client_id)
                REFERENCES vpn_clients(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS
            idx_public_subscription_tokens_active
        ON public_subscription_tokens(
            public_id,
            is_active
        );
        """,
    ),
)


MIGRATIONS += (
    (
        3,
        "create_orders",
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            public_id TEXT NOT NULL UNIQUE,

            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,

            plan_code TEXT NOT NULL,
            plan_title TEXT NOT NULL,

            duration_unit TEXT NOT NULL
                CHECK (
                    duration_unit IN (
                        'day',
                        'month'
                    )
                ),

            duration_value INTEGER NOT NULL
                CHECK (duration_value > 0),

            amount_minor INTEGER NOT NULL
                CHECK (amount_minor >= 0),

            currency TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (
                    status IN (
                        'pending',
                        'paid',
                        'failed',
                        'cancelled',
                        'refunded'
                    )
                ),

            payment_provider TEXT,
            provider_payment_id TEXT,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            paid_at TEXT,
            cancelled_at TEXT,
            failed_at TEXT,
            refunded_at TEXT,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (plan_id)
                REFERENCES plans(id)
        );

        CREATE INDEX IF NOT EXISTS
            idx_orders_user_created
        ON orders(
            user_id,
            created_at DESC,
            id DESC
        );

        CREATE INDEX IF NOT EXISTS
            idx_orders_status
        ON orders(status);

        CREATE UNIQUE INDEX IF NOT EXISTS
            idx_orders_one_pending_per_user
        ON orders(user_id)
        WHERE status = 'pending';

        CREATE UNIQUE INDEX IF NOT EXISTS
            idx_orders_provider_payment
        ON orders(
            payment_provider,
            provider_payment_id
        )
        WHERE provider_payment_id IS NOT NULL;
        """,
    ),
)


def apply_migrations(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    rows = connection.execute(
        """
        SELECT version
        FROM schema_migrations
        """
    ).fetchall()

    applied = {
        int(row[0])
        for row in rows
    }

    for version, name, sql in MIGRATIONS:
        if version in applied:
            continue

        connection.executescript(sql)

        connection.execute(
            """
            INSERT INTO schema_migrations (
                version,
                name
            )
            VALUES (?, ?)
            """,
            (version, name),
        )
