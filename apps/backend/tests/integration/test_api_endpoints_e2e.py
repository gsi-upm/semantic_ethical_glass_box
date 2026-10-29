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
        self.audits: list[object] = []
        self.history: list[dict] = []
        self.usage: dict[str, dict] = {}
        self.entries: dict[str, dict] = {}
        self.last_validated_query: tuple[str, bool] | None = None
        self.last_executed_query: tuple[str, bool] | None = None
        self.ttl_text = "@prefix ex: <https://example.org/> ."

    def connect_to_db(self, retries: int = 10, delay: float = 5.0) -> object:
        return object()

    def close_connection(self) -> None:
        return None

    def ping(self, timeout_s: float = 1.0) -> bool:
        return True

    def insert_ttl(self, ttl_content: str, *, audit: object) -> str:
        self.inserted_payloads.append(ttl_content)
        self.audits.append(audit)
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

    def route_usage(self, route: str) -> dict:
        return self.usage.get(route, {"count": 0, "first_used_at": None, "last_used_at": None})

    def list_audit_entries(self) -> list[dict]:
        return list(self.history)

    def get_audit_entry(self, log_id: str) -> dict | None:
        return self.entries.get(log_id)

    def delete_all_triples(self, *, audit: object) -> str | None:
        self.audits.append(audit)
        return "del-log-id"


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

    def test_ttl_insert_audits_the_authenticated_identity_not_the_claimed_user(self) -> None:
        client, services = _build_test_app(roles=["logger"], virtuoso_ok=True)
        try:
            response = client.post(
                "/ttl",
                json={"ttl_content": "@prefix ex: <https://example.org/> .", "user": "someone_else"},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 201)
        (audit,) = services.virtuoso.audits
        self.assertEqual(audit.username, "test_user")
        self.assertEqual(audit.roles, ("logger",))
        self.assertEqual(audit.route, "POST /ttl")

    def test_delete_all_audits_the_authenticated_identity_and_returns_the_log_id(self) -> None:
        client, services = _build_test_app(roles=["admin"], virtuoso_ok=True)
        try:
            response = client.post("/ttl/delete_all", json={"user": "someone_else"})
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["log_id"], "del-log-id")
        (audit,) = services.virtuoso.audits
        self.assertEqual((audit.username, audit.roles, audit.route), ("test_user", ("admin",), "POST /ttl/delete_all"))

    def test_history_and_log_need_the_auditor_or_admin_role(self) -> None:
        client, _ = _build_test_app(roles=["logger"])
        try:
            self.assertEqual(client.get("/history").status_code, 403)
            self.assertEqual(client.get("/log", params={"log_id": "x"}).status_code, 403)
        finally:
            client.close()

    def test_history_of_an_empty_audit_is_an_empty_list(self) -> None:
        client, _ = _build_test_app(roles=["auditor"])
        try:
            response = client.get("/history")
        finally:
            client.close()
        self.assertEqual((response.status_code, response.json()), (200, []))

    def test_history_lists_the_summaries(self) -> None:
        client, services = _build_test_app(roles=["admin"])
        services.virtuoso.history = [{"_id": "a", "action_type": "insertion"}, {"_id": "b", "action_type": "deletion"}]
        try:
            response = client.get("/history")
        finally:
            client.close()
        self.assertEqual([e["_id"] for e in response.json()], ["a", "b"])

    def test_log_without_id_is_400_unknown_id_is_404_known_id_returns_log_and_action(self) -> None:
        client, services = _build_test_app(roles=["auditor"])
        services.virtuoso.entries["known"] = {"log": {"_id": "known"}, "action": {"ttl_content": "x"}}
        try:
            self.assertEqual(client.get("/log").status_code, 400)
            self.assertEqual(client.get("/log", params={"log_id": ""}).status_code, 400)
            self.assertEqual(client.get("/log", params={"log_id": "nope"}).status_code, 404)
            known = client.get("/log", params={"log_id": "known"})
        finally:
            client.close()
        self.assertEqual((known.status_code, known.json()["action"]), (200, {"ttl_content": "x"}))

    def test_validate_reports_blank_nodes_as_a_warning_not_an_error(self) -> None:
        client, services = _build_test_app(roles=["admin"])
        try:
            response = client.post(
                "/ttl/validate", json={"ttl_content": "@prefix ex: <https://example.org/> .\nex:a ex:p [ ex:q 1 ] ."}
            )
        finally:
            client.close()

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["valid"])
        (issue,) = [i for i in body["issues"] if i["code"] == "SEM_BLANK_NODES"]
        self.assertEqual(issue["severity"], "warning")
        self.assertEqual(services.virtuoso.inserted_payloads, [])

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
