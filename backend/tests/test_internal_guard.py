import ast
import asyncio
import copy
import hmac
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock


class FakeResponse:
    def __init__(self, status_code, content=None):
        self.status_code = status_code
        self.content = content


class FakeSecret:
    def __init__(self, value):
        self.value = value

    def get_secret_value(self):
        return self.value


SOURCE = Path(__file__).resolve().parents[1] / "app/main.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

functions = [
    node for node in tree.body
    if isinstance(node, ast.AsyncFunctionDef)
    and node.name == "protect_internal"
]

if len(functions) != 1:
    raise RuntimeError("Функция protect_internal не найдена")

guard_node = copy.deepcopy(functions[0])
guard_node.decorator_list = []

module = ast.fix_missing_locations(
    ast.Module(body=[guard_node], type_ignores=[])
)

context = {
    "Request": object,
    "JSONResponse": FakeResponse,
    "compare_digest": hmac.compare_digest,
}

exec(compile(module, str(SOURCE), "exec"), context)

guard = context["protect_internal"]


class InternalGuardTests(unittest.TestCase):

    def check_request(self, path, configured, supplied=None):
        context["settings"] = SimpleNamespace(
            internal_api_token=(
                FakeSecret(configured)
                if configured is not None
                else None
            )
        )

        request = SimpleNamespace(
            url=SimpleNamespace(path=path),
            headers=(
                {"X-KAD-Internal-Token": supplied}
                if supplied is not None
                else {}
            ),
        )

        call_next = AsyncMock(
            return_value=FakeResponse(200, {"ok": True})
        )

        response = asyncio.run(guard(request, call_next))
        return response.status_code, call_next.await_count

    def test_closed_by_default(self):
        status, calls = self.check_request(
            "/internal/db/health", None
        )
        self.assertEqual((status, calls), (404, 0))

    def test_closed_without_token(self):
        status, calls = self.check_request(
            "/internal/test/provision", "test-secret"
        )
        self.assertEqual((status, calls), (404, 0))

    def test_wrong_token_rejected(self):
        status, calls = self.check_request(
            "/internal/test/purge/123",
            "test-secret",
            "wrong-secret",
        )
        self.assertEqual((status, calls), (404, 0))

    def test_valid_token_accepted(self):
        status, calls = self.check_request(
            "/internal/test/provision",
            "test-secret",
            "test-secret",
        )
        self.assertEqual((status, calls), (200, 1))

    def test_public_api_unaffected(self):
        status, calls = self.check_request(
            "/api/v1/me", None
        )
        self.assertEqual((status, calls), (200, 1))

    def test_internal_root_protected(self):
        status, calls = self.check_request(
            "/internal", None
        )
        self.assertEqual((status, calls), (404, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
