from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class DeviceQueryTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        path_patch = patch.object(
            db,
            "DB_PATH",
            Path(self.temp.name) / "kad.db",
        )
        path_patch.start()
        self.addCleanup(path_patch.stop)

        db.init_db()

        with closing(db.connect()) as conn, conn:
            self.user_a = conn.execute(
                "INSERT INTO users (telegram_id) VALUES (10001)"
            ).lastrowid

            self.user_b = conn.execute(
                "INSERT INTO users (telegram_id) VALUES (10002)"
            ).lastrowid

            self.device_a = conn.execute(
                """
                INSERT INTO vpn_clients
                    (user_id, xui_email, sub_id)
                VALUES (?, 'iphone', 'sub_iphone')
                """,
                (self.user_a,),
            ).lastrowid

            self.device_b = conn.execute(
                """
                INSERT INTO vpn_clients
                    (user_id, xui_email, sub_id)
                VALUES (?, 'macbook', 'sub_macbook')
                """,
                (self.user_a,),
            ).lastrowid

            self.device_c = conn.execute(
                """
                INSERT INTO vpn_clients
                    (user_id, xui_email, sub_id)
                VALUES (?, 'android', 'sub_android')
                """,
                (self.user_b,),
            ).lastrowid

    def test_user_sees_only_own_devices(self):
        devices = db.list_vpn_clients_for_user(
            self.user_a
        )

        self.assertEqual(
            [device["id"] for device in devices],
            [self.device_a, self.device_b],
        )

        self.assertEqual(
            db.list_vpn_clients_for_user(999999),
            [],
        )

    def test_user_cannot_access_foreign_device(self):
        own = db.get_vpn_client_for_user(
            user_id=self.user_a,
            vpn_client_id=self.device_a,
        )

        foreign = db.get_vpn_client_for_user(
            user_id=self.user_a,
            vpn_client_id=self.device_c,
        )

        self.assertIsNotNone(own)
        self.assertEqual(own["id"], self.device_a)
        self.assertIsNone(foreign)


if __name__ == "__main__":
    unittest.main()
