"""Legacy 0.4.x routes (POST /log, GET /health) and their usage count, against a fake store."""

from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest import mock

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.router import router
from core import security
from core.security import User, validate_token
from test_api_endpoints_e2e import FakeVirtuosoStore

TTL = "@prefix ex: <https://example.org/> .\nex:a a ex:B .\n"
TURTLE = {"content-type": "text/turtle"}


def _client(*, roles: list[str] | None = None, authenticate: bool = True) -> tuple[TestClient, FakeVirtuosoStore]:
    app = FastAPI(version="1.2.0-test")
    app.include_router(router)
    store = FakeVirtuosoStore()
    app.state.services = SimpleNamespace(virtuoso=store, shared_context=mock.Mock(), virtuoso_ok=True)
    if authenticate:

        async def _user() -> User:
            return User(username="robot1", roles=roles or ["logger"])

        app.dependency_overrides[validate_token] = _user
    return TestClient(app), store


class TestPostLog(unittest.TestCase):
    def test_saves_the_log_with_the_0_4_response(self) -> None:
        client, store = _client()
        response = client.post("/log", content=TTL, headers=TURTLE)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"message": "Log saved successfully"})
        self.assertEqual(store.inserted_payloads, [TTL])

    def test_audit_records_the_legacy_route_and_the_token_identity(self) -> None:
        client, store = _client(roles=["logger"])
        client.post("/log", content=TTL, headers=TURTLE)

        (audit,) = store.audits
        self.assertEqual((audit.route, audit.username, audit.roles), ("POST /log", "robot1", ("logger",)))

    def test_admin_may_log_too(self) -> None:
        client, _ = _client(roles=["admin"])
        self.assertEqual(client.post("/log", content=TTL, headers=TURTLE).status_code, 201)

    def test_auditor_alone_is_forbidden_and_nothing_is_stored(self) -> None:
        client, store = _client(roles=["auditor"])
        response = client.post("/log", content=TTL, headers=TURTLE)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(store.inserted_payloads, [])

    def test_invalid_turtle_is_422_and_nothing_is_stored(self) -> None:
        client, store = _client()
        response = client.post("/log", content="this is not turtle", headers=TURTLE)

        self.assertEqual(response.status_code, 422)
        self.assertEqual((store.inserted_payloads, store.audits), ([], []))

    def test_empty_and_non_utf8_bodies_are_422(self) -> None:
        client, store = _client()
        self.assertEqual(client.post("/log", content=b"", headers=TURTLE).status_code, 422)
        self.assertEqual(client.post("/log", content=b"\xff\xfe\x00", headers=TURTLE).status_code, 422)
        self.assertEqual(store.inserted_payloads, [])

    def test_the_body_is_read_as_turtle_whatever_the_content_type(self) -> None:
        client, store = _client()
        self.assertEqual(client.post("/log", content=TTL).status_code, 201)
        self.assertEqual(store.inserted_payloads, [TTL])


class TestGetHealth(unittest.TestCase):
    def test_is_plain_text_with_the_version_and_needs_no_token(self) -> None:
        client, store = _client(authenticate=False)
        with mock.patch.object(security, "SECRET_KEY", "secret"):
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertIn("1.2.0-test", response.text)
        self.assertEqual(store.audits, [])  # logged, never audited


class TestDeprecationHeaders(unittest.TestCase):
    def _assert_deprecated(self, response) -> None:
        self.assertEqual(response.headers["deprecation"], "true")
        link = response.headers["link"]
        self.assertIn('rel="deprecation"', link)
        self.assertIn("/reference/legacy-api/", link)

    def test_every_response_of_the_legacy_routes_carries_them(self) -> None:
        client, _ = _client(roles=["logger"])
        self._assert_deprecated(client.post("/log", content=TTL, headers=TURTLE))  # 201
        self._assert_deprecated(client.post("/log", content="nope", headers=TURTLE))  # 422
        self._assert_deprecated(client.get("/health"))  # 200

        forbidden, _ = _client(roles=["auditor"])
        response = forbidden.post("/log", content=TTL, headers=TURTLE)
        self.assertEqual(response.status_code, 403)
        self._assert_deprecated(response)

    def test_a_missing_token_gets_401_with_the_headers(self) -> None:
        client, _ = _client(authenticate=False)
        with mock.patch.object(security, "SECRET_KEY", "secret"):
            response = client.post("/log", content=TTL, headers=TURTLE)
        self.assertEqual(response.status_code, 401)
        self._assert_deprecated(response)
        self.assertIn("www-authenticate", response.headers)

    def test_native_routes_do_not_carry_them(self) -> None:
        client, _ = _client(roles=["logger"])
        response = client.post("/ttl", json={"ttl_content": TTL})
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("deprecation", response.headers)
        self.assertNotIn("deprecation", client.get("/healthz/live").headers)


class TestTokenRules(unittest.TestCase):
    def _token(self, **claims) -> str:
        return jwt.encode({"username": "robot1", "roles": ["logger"], **claims}, "secret", algorithm="HS256")

    def test_a_token_without_exp_is_401_on_both_the_legacy_and_the_native_route(self) -> None:
        client, store = _client(authenticate=False)
        headers = {"authorization": f"Bearer {self._token()}"}
        with mock.patch.object(security, "SECRET_KEY", "secret"):
            legacy = client.post("/log", content=TTL, headers={**headers, **TURTLE})
            native = client.post("/ttl", json={"ttl_content": TTL}, headers=headers)

        self.assertEqual((legacy.status_code, native.status_code), (401, 401))
        self.assertEqual(store.inserted_payloads, [])

    def test_a_token_with_exp_is_accepted_on_both(self) -> None:
        client, store = _client(authenticate=False)
        headers = {"authorization": f"Bearer {self._token(exp=int(time.time()) + 600)}"}
        with mock.patch.object(security, "SECRET_KEY", "secret"):
            legacy = client.post("/log", content=TTL, headers={**headers, **TURTLE})
            native = client.post("/ttl", json={"ttl_content": TTL}, headers=headers)

        self.assertEqual((legacy.status_code, native.status_code), (201, 201))
        self.assertEqual([a.route for a in store.audits], ["POST /log", "POST /ttl"])


class TestLegacyUsage(unittest.TestCase):
    def test_admin_sees_the_count_of_the_legacy_route(self) -> None:
        client, store = _client(roles=["admin"])
        store.usage["POST /log"] = {"count": 3, "first_used_at": "a", "last_used_at": "b"}
        response = client.get("/legacy/usage")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["routes"]["POST /log"], {"count": 3, "first_used_at": "a", "last_used_at": "b"})
        self.assertNotIn("deprecation", response.headers)

    def test_unused_legacy_route_counts_zero(self) -> None:
        client, _ = _client(roles=["admin"])
        self.assertEqual(client.get("/legacy/usage").json()["routes"]["POST /log"]["count"], 0)

    def test_only_admin_may_read_it(self) -> None:
        for role in ("auditor", "logger"):
            client, _ = _client(roles=[role])
            self.assertEqual(client.get("/legacy/usage").status_code, 403, role)


if __name__ == "__main__":
    unittest.main()
