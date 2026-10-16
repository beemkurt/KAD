import sqlite3
import unittest

from app.db import SCHEMA
from app.migrations import MIGRATIONS, apply_migrations


class MultiDeviceMigrationTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)

        self.db.executescript(SCHEMA)

        self.db.execute(
            "INSERT INTO users (telegram_id) VALUES (?)",
            (12345,),
        )

        self.db.execute(
            """
            INSERT INTO vpn_clients
                (user_id, xui_email, sub_id)
            VALUES (1, 'device_a', 'sub_a')
            """
        )

    def add_second_device(self):
        self.db.execute(
            """
            INSERT INTO vpn_clients
                (user_id, xui_email, sub_id)
            VALUES (1, 'device_b', 'sub_b')
            """
        )

    def test_new_database_supports_multiple_devices(self):
        apply_migrations(self.db)

        self.add_second_device()

        count = self.db.execute(
            "SELECT COUNT(*) FROM vpn_clients WHERE user_id = 1"
        ).fetchone()[0]

        self.assertEqual(count, 2)

    def test_migration_preserves_existing_client(self):
        self.db.execute(
            """
            CREATE UNIQUE INDEX uq_vpn_clients_user
            ON vpn_clients(user_id)
            """
        )

        self.db.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )

        self.db.executemany(
            """
            INSERT INTO schema_migrations (version, name)
            VALUES (?, ?)
            """,
            [
                (version, name)
                for version, name, _ in MIGRATIONS
                if version < 4
            ],
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.add_second_device()

        apply_migrations(self.db)

        self.add_second_device()
        apply_migrations(self.db)

        clients = self.db.execute(
            """
            SELECT xui_email
            FROM vpn_clients
            WHERE user_id = 1
            ORDER BY id
            """
        ).fetchall()

        self.assertEqual(
            [row[0] for row in clients],
            ["device_a", "device_b"],
        )

        self.assertEqual(
            self.db.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0],
            "ok",
        )

        self.assertEqual(
            self.db.execute(
                """
                SELECT COUNT(*)
                FROM schema_migrations
                WHERE version = 4
                """
            ).fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
