"""Shared setup for opt-in tests that drive the API against a real Virtuoso."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
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
AUDIT_NS = "http://www.gsi.upm.es/ontologies/segb/audit#"
ENTRY_BASE = "https://example.org/segb/audit/entry/"


@unittest.skipUnless(harness.integration_enabled(), "set SEGB_INTEGRATION=1 to run against a real Virtuoso")
class RealApiTestCase(unittest.TestCase):
    """One disposable Virtuoso per test class, reached through the real FastAPI router."""

    roles = ["logger", "admin"]

    @classmethod
    def setUpClass(cls) -> None:
        cls.virtuoso = harness.VirtuosoTestInstance().start()
        cls.addClassCleanup(cls.virtuoso.stop)
        cls.dump_dir = Path(tempfile.mkdtemp(prefix="segb-it-dumps-"))
        cls.addClassCleanup(shutil.rmtree, cls.dump_dir, True)
        env = {
            **cls.virtuoso.environ(),
            "VIRTUOSO_GRAPH_URI": EVENTS,
            "VIRTUOSO_AUDIT_GRAPH_URI": AUDIT,
            "AUDIT_BASE_IRI": "https://example.org/segb/audit/",
            "AUDIT_DUMP_DIR": str(cls.dump_dir),
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
            return User(username="alice", roles=cls.roles)

        app.dependency_overrides[validate_token] = _user
        cls.client = TestClient(app, raise_server_exceptions=False, headers={"x-forwarded-for": "192.168.1.20"})
        cls.addClassCleanup(cls.client.close)

    def select(self, query: str) -> list[dict]:
        response = requests.post(
            self.virtuoso.endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            auth=HTTPDigestAuth("dba", self.virtuoso.password),
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]

    def update(self, statement: str) -> None:
        requests.post(
            self.virtuoso.endpoint,
            data=statement.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            auth=HTTPDigestAuth("dba", self.virtuoso.password),
            timeout=120,
        ).raise_for_status()

    def count(self, graph: str, where: str = "?s ?p ?o") -> int:
        rows = self.select(f"SELECT (COUNT(*) AS ?n) FROM <{graph}> WHERE {{ {where} }}")
        return int(rows[0]["n"]["value"])

    def entry_ids(self, kind: str) -> set[str]:
        rows = self.select(f"SELECT ?e FROM <{AUDIT}> WHERE {{ ?e a <{AUDIT_NS}{kind}> }}")
        return {r["e"]["value"] for r in rows}

    def entry_values(self, log_id: str, prop: str) -> set[str]:
        entry = f"<{ENTRY_BASE}{log_id}>"
        rows = self.select(f"SELECT ?o FROM <{AUDIT}> WHERE {{ {entry} <{AUDIT_NS}{prop}> ?o }}")
        return {r["o"]["value"] for r in rows}
