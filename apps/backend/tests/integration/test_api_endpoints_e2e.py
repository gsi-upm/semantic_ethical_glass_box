from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.router import router
from core.security import User, validate_token
from utils.shared_context import SharedContextResolveResponse


class FakeVirtuosoStore:
    def __init__(self) -> None:
        self.inserted_payloads: list[str] = []
        self.last_validated_query: tuple[str, bool] | None = None
        self.last_executed_query: tuple[str, bool] | None = None
        self.ttl_text = "@prefix ex: <https://example.org/> ."

    def connect_to_db(self, retries: int = 10, delay: float = 5.0) -> object:
        return object()

    def close_connection(self) -> None:
        return None

    def ping(self, timeout_s: float = 1.0) -> bool:
        return True

    def insert_ttl(self, ttl_content: str) -> str:
        self.inserted_payloads.append(ttl_content)
        return "log-id-123"

    def get_ttls(self) -> str:
        return self.ttl_text

    def validate_query(self, query: str, *, allow_updates: bool = False) -> dict[str, object]:
        self.last_validated_query = (query, allow_updates)
        return {
            "valid": True,
            "query_kind": "select",
            "allows_update_execution": allow_updates,
            "message": "Valid SPARQL query.",
        }

    def run_custom_query(self, query: str, *, allow_updates: bool = False) -> str:
        self.last_executed_query = (query, allow_updates)
        return "@prefix ex: <https://example.org/> ."

    def delete_all_triples(self) -> None:
        return None


def _build_test_app(*, roles: list[str], virtuoso_ok: bool = True) -> tuple[TestClient, SimpleNamespace]:
    app = FastAPI()
    app.include_router(router)

    services = SimpleNamespace(
        virtuoso=FakeVirtuosoStore(),
        shared_context=Mock(),
        virtuoso_ok=virtuoso_ok,
    )
    app.state.services = services

    async def _override_validate_token() -> User:
        return User(username="test_user", roles=roles)

    app.dependency_overrides[validate_token] = _override_validate_token
    return TestClient(app), services


class TestApiEndpointsE2E(unittest.TestCase):
    def test_health_endpoints_report_liveness_and_readiness(self) -> None:
        client, _ = _build_test_app(roles=["admin"], virtuoso_ok=False)
        try:
            live = client.get("/healthz/live")
            ready = client.get("/healthz/ready")
        finally:
            client.close()

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"live": True})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {"ready": False, "virtuoso": False})

    def test_ttl_insert_and_export_work_with_ready_graph_store(self) -> None:
        client, services = _build_test_app(roles=["admin"], virtuoso_ok=True)
        try:
            insert_response = client.post("/ttl", json={"ttl_content": "@prefix ex: <https://example.org/> ."})
            events_response = client.get("/events")
        finally:
            client.close()

        self.assertEqual(insert_response.status_code, 201)
        self.assertEqual(insert_response.json()["message"], "TTL inserted into Virtuoso")
        self.assertEqual(insert_response.json()["log_id"], "log-id-123")
        self.assertEqual(len(services.virtuoso.inserted_payloads), 1)

        self.assertEqual(events_response.status_code, 200)
        self.assertEqual(events_response.text, services.virtuoso.ttl_text)
        self.assertIn("text/turtle", events_response.headers["content-type"])

    def test_ttl_insert_returns_503_when_virtuoso_is_not_ready(self) -> None:
        client, _ = _build_test_app(roles=["admin"], virtuoso_ok=False)
        try:
            response = client.post("/ttl", json={"ttl_content": "@prefix ex: <https://example.org/> ."})
        finally:
            client.close()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Virtuoso is unavailable")

    def test_ttl_insert_is_forbidden_for_non_logger_role(self) -> None:
        client, _ = _build_test_app(roles=["auditor"], virtuoso_ok=True)
        try:
            response = client.post("/ttl", json={"ttl_content": "@prefix ex: <https://example.org/> ."})
        finally:
            client.close()

        self.assertEqual(response.status_code, 403)
        self.assertIn("permission", response.json()["detail"])

    def test_query_endpoints_enforce_read_only_mode(self) -> None:
        client, services = _build_test_app(roles=["admin"], virtuoso_ok=True)
        try:
            validate_response = client.post("/query/validate", json={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"})
            execute_response = client.get("/query", params={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"})
        finally:
            client.close()

        self.assertEqual(validate_response.status_code, 200)
        self.assertTrue(validate_response.json()["valid"])
        self.assertEqual(services.virtuoso.last_validated_query, ("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1", False))

        self.assertEqual(execute_response.status_code, 200)
        self.assertIn("@prefix ex:", execute_response.text)
        self.assertEqual(services.virtuoso.last_executed_query, ("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1", False))

    def test_shared_context_resolve_returns_structured_payload(self) -> None:
        client, services = _build_test_app(roles=["admin"], virtuoso_ok=True)
        services.shared_context.resolve.return_value = SharedContextResolveResponse(
            shared_context_uri="https://example.org/shared-events/context_1",
            status="matched",
            confidence=0.93,
            resolver_version="shared-context-v1-rules",
            candidate_count=2,
            matched_candidate_uri="https://example.org/shared-events/context_1",
        )
        payload = {
            "event_kind": "human_utterance",
            "observed_at": datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "subject_uri": "https://example.org/human/maria",
            "modality": "speech",
            "text": "hello",
        }

        try:
            response = client.post("/shared-context/resolve", json=payload)
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "matched")
        self.assertEqual(body["shared_context_uri"], "https://example.org/shared-events/context_1")
        self.assertEqual(body["candidate_count"], 2)


if __name__ == "__main__":
    unittest.main()
