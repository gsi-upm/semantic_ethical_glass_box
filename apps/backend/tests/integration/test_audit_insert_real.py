"""Opt-in: audit-on-insert against a real Virtuoso. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from requests.auth import HTTPDigestAuth

import virtuoso_harness as harness
from api.router import router
from core.security import User, validate_token
from models.virtuoso_graph_store import VirtuosoGraphStoreAdapter
from models.virtuoso_model import VirtuosoModel

EVENTS = "http://segb/events"
AUDIT = "http://segb/audit"
TTL = '@prefix ex: <http://example.org/> .\nex:greeting1 a ex:Greeting ; ex:text "hello" .\nex:greeting2 a ex:Greeting .\n'
# Its own subjects, so the count below does not depend on test order.
DUPLICATE_TTL = '@prefix ex: <http://example.org/> .\nex:dup1 a ex:Greeting ; ex:text "twice" .\nex:dup2 a ex:Greeting .\n'


@unittest.skipUnless(harness.integration_enabled(), "set SEGB_INTEGRATION=1 to run against a real Virtuoso")
class TestAuditOnInsertReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.virtuoso = harness.VirtuosoTestInstance().start()
        cls.addClassCleanup(cls.virtuoso.stop)
        env = {
            **cls.virtuoso.environ(),
            "VIRTUOSO_GRAPH_URI": EVENTS,
            "VIRTUOSO_AUDIT_GRAPH_URI": AUDIT,
            "AUDIT_BASE_IRI": "https://example.org/segb/audit/",
        }
        patcher = mock.patch.dict("os.environ", env)
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        # Never write the repository's prefixes.json from a test.
        prefixes = mock.patch.multiple(
            "models.virtuoso_model", save_prefixes=mock.Mock(), load_prefixes=mock.Mock(return_value={})
        )
        prefixes.start()
        cls.addClassCleanup(prefixes.stop)

        VirtuosoModel._instance = None
        VirtuosoModel._session = None
        cls.addClassCleanup(lambda: (setattr(VirtuosoModel, "_instance", None), setattr(VirtuosoModel, "_session", None)))
        model = VirtuosoModel()
        model.connect_to_db(retries=30, delay=2)

        app = FastAPI()
        app.include_router(router)
        app.state.services = SimpleNamespace(
            virtuoso=VirtuosoGraphStoreAdapter(client=model), shared_context=mock.Mock(), virtuoso_ok=True
        )

        async def _user() -> User:
            return User(username="alice", roles=["logger", "admin"])

        app.dependency_overrides[validate_token] = _user
        cls.client = TestClient(app, raise_server_exceptions=False, headers={"x-forwarded-for": "192.168.1.20"})
        cls.addClassCleanup(cls.client.close)

    def _select(self, query: str) -> list[dict]:
        response = requests.post(
            self.virtuoso.endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            auth=HTTPDigestAuth("dba", self.virtuoso.password),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]

    def _count(self, graph: str, where: str = "?s ?p ?o") -> int:
        rows = self._select(f"SELECT (COUNT(*) AS ?n) FROM <{graph}> WHERE {{ {where} }}")
        return int(rows[0]["n"]["value"])

    def test_same_ttl_twice_gives_one_set_of_triples_and_two_audit_entries(self) -> None:
        events_before = self._count(EVENTS)
        entries_before = self._count(AUDIT, "?e a <http://www.gsi.upm.es/ontologies/segb/audit#Insertion>")

        first = self.client.post("/ttl", json={"ttl_content": DUPLICATE_TTL})
        second = self.client.post("/ttl", json={"ttl_content": DUPLICATE_TTL})

        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertNotEqual(first.json()["log_id"], second.json()["log_id"])
        self.assertEqual(self._count(EVENTS) - events_before, 3)  # 3 triples, stored once
        entries = self._count(AUDIT, "?e a <http://www.gsi.upm.es/ontologies/segb/audit#Insertion>")
        self.assertEqual(entries - entries_before, 2)

    def test_entry_has_original_ttl_subjects_route_and_actor(self) -> None:
        log_id = self.client.post("/ttl", json={"ttl_content": TTL, "user": "someone_else"}).json()["log_id"]
        entry = f"<https://example.org/segb/audit/entry/{log_id}>"

        def values(prop: str) -> set[str]:
            rows = self._select(f"SELECT ?o FROM <{AUDIT}> WHERE {{ {entry} <http://www.gsi.upm.es/ontologies/segb/audit#{prop}> ?o }}")
            return {r["o"]["value"] for r in rows}

        self.assertEqual(values("ttl"), {TTL})
        self.assertEqual(values("route"), {"POST /ttl"})
        self.assertEqual(values("originIP"), {"192.168.1.20"})
        self.assertEqual(values("actorRole"), {"logger", "admin"})
        self.assertEqual(values("mentionsSubject"), {"http://example.org/greeting1", "http://example.org/greeting2"})
        agents = self._select(
            f"SELECT ?n FROM <{AUDIT}> WHERE {{ {entry} <http://www.w3.org/ns/prov#wasAssociatedWith> ?a . ?a <http://xmlns.com/foaf/0.1/accountName> ?n }}"
        )
        self.assertEqual([r["n"]["value"] for r in agents], ["alice"])  # the token, not the claimed user

    def test_failed_insert_writes_no_insertion_entry(self) -> None:
        events_before = self._count(EVENTS)
        entries_before = self._count(AUDIT)

        response = self.client.post("/ttl", json={"ttl_content": "this is not turtle"})

        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(self._count(EVENTS), events_before)
        self.assertEqual(self._count(AUDIT), entries_before)


if __name__ == "__main__":
    unittest.main()
