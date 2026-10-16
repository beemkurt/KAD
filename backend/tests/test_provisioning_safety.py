import asyncio
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeXUIError(RuntimeError):
    pass


def fake_module(name, **items):
    module = types.ModuleType(name)
    for key, value in items.items():
        setattr(module, key, value)
    return module


db = fake_module(
    "app.db",
    get_state_by_telegram_id=Mock(),
    upsert_user=Mock(),
    save_provisioned_state=Mock(),
    purge_user=Mock(),
)

fakes = {
    "app.config": fake_module("app.config", Settings=object),
    "app.connection_tokens": fake_module(
        "app.connection_tokens",
        get_or_create_connection=Mock(return_value=None),
    ),
    "app.db": db,
    "app.xui": fake_module(
        "app.xui",
        XUIClient=object,
        XUIError=FakeXUIError,
    ),
}

with patch.dict(sys.modules, fakes):
    from app.provisioning import ProvisioningService


class ProvisioningSafetyTests(unittest.TestCase):

    def setUp(self):
        for name in (
            "get_state_by_telegram_id",
            "upsert_user",
            "save_provisioned_state",
            "purge_user",
        ):
            getattr(db, name).reset_mock(
                return_value=True,
                side_effect=True,
            )

        db.upsert_user.return_value = 42

        self.xui = SimpleNamespace(
            create_client=AsyncMock(),
            get_client=AsyncMock(),
            delete_client=AsyncMock(),
        )

        self.service = ProvisioningService(
            SimpleNamespace(xui_inbound_id=4),
            self.xui,
        )

    def test_existing_user_survives_error(self):
        db.get_state_by_telegram_id.return_value = {
            "user_id": 42,
            "telegram_id": 1001,
            "xui_email": None,
        }

        self.xui.create_client.side_effect = FakeXUIError(
            "Test failure"
        )

        with self.assertRaises(FakeXUIError):
            asyncio.run(
                self.service.provision_test_client(
                    telegram_id=1001,
                    duration_minutes=10,
                )
            )

        db.upsert_user.assert_not_called()
        db.purge_user.assert_not_called()

    def test_new_user_not_deleted_on_error(self):
        db.get_state_by_telegram_id.return_value = None

        self.xui.create_client.side_effect = FakeXUIError(
            "Test failure"
        )

        with self.assertRaises(FakeXUIError):
            asyncio.run(
                self.service.provision_test_client(
                    telegram_id=1002,
                    duration_minutes=10,
                )
            )

        db.upsert_user.assert_called_once()
        db.purge_user.assert_not_called()

    def test_xui_client_rollback(self):
        db.get_state_by_telegram_id.return_value = {
            "user_id": 42,
            "telegram_id": 1003,
            "xui_email": None,
        }

        self.xui.get_client.return_value = {
            "client": {}
        }

        with self.assertRaises(Exception) as error:
            asyncio.run(
                self.service.provision_test_client(
                    telegram_id=1003,
                    duration_minutes=10,
                )
            )

        self.assertEqual(
            type(error.exception).__name__,
            "ProvisioningError",
        )

        self.xui.delete_client.assert_awaited_once()
        db.purge_user.assert_not_called()

    def test_existing_user_id_reused(self):
        db.get_state_by_telegram_id.side_effect = [
            {
                "user_id": 42,
                "telegram_id": 1004,
                "xui_email": None,
            },
            {
                "user_id": 42,
                "telegram_id": 1004,
                "xui_email": "test",
            },
        ]

        self.xui.get_client.return_value = {
            "client": {"subId": "fake-sub-id"}
        }

        with patch.object(
            ProvisioningService,
            "_public_state",
            return_value={"ok": True},
        ):
            result = asyncio.run(
                self.service.provision_test_client(
                    telegram_id=1004,
                    duration_minutes=10,
                )
            )

        self.assertTrue(result["created"])
        db.upsert_user.assert_not_called()

        self.assertEqual(
            db.save_provisioned_state.call_args.kwargs[
                "user_id"
            ],
            42,
        )

        db.purge_user.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
