"""Opt-in: GET /history and GET /log against a real Virtuoso. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import unittest
import uuid

from rdflib import Graph
from rdflib.compare import isomorphic

from real_api_support import AUDIT, RealApiTestCase

TTL_A = '@prefix ex: <http://example.org/> .\nex:a1 a ex:Greeting ; ex:text "héllo" .\n'
TTL_B = '@prefix ex: <http://example.org/> .\nex:b1 a ex:Greeting .\nex:b2 ex:p ex:b1 .\n'


class TestEmptyHistoryReal(RealApiTestCase):
    def test_history_of_a_fresh_store_is_an_empty_list(self) -> None:
        response = self.client.get("/history")
        self.assertEqual((response.status_code, response.json()), (200, []))


class TestAuditReadReal(RealApiTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.id_a = cls.client.post("/ttl", json={"ttl_content": TTL_A}).json()["log_id"]
        cls.id_b = cls.client.post("/ttl", json={"ttl_content": TTL_B}).json()["log_id"]
        cls.id_del = cls.client.post("/ttl/delete_all", json={}).json()["log_id"]

    def test_history_lists_every_entry_oldest_first_with_the_0_4_keys(self) -> None:
        response = self.client.get("/history")

        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertEqual([e["_id"] for e in history], [self.id_a, self.id_b, self.id_del])
        self.assertEqual([e["action_type"] for e in history], ["insertion", "insertion", "deletion"])
        first = history[0]
        self.assertTrue({"_id", "uploaded_at", "origin_ip", "action_type", "action", "user_details"} <= set(first))
        self.assertTrue(first["uploaded_at"].endswith("Z"))
        self.assertEqual(first["origin_ip"], "192.168.1.20")
        self.assertEqual(first["user_details"], {"username": "alice", "roles": ["admin", "logger"]})
        self.assertEqual((first["route"], history[2]["route"]), ("POST /ttl", "POST /ttl/delete_all"))
        # The list stays light: payloads are only served by /log.
        self.assertTrue(all("ttl" not in key for e in history for key in e))

    def test_log_returns_the_insertion_with_its_ttl_and_subjects(self) -> None:
        response = self.client.get("/log", params={"log_id": self.id_b})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["log"]["_id"], self.id_b)
        self.assertEqual(body["action"]["ttl_content"], TTL_B)
        self.assertEqual(body["action"]["subjects"], ["http://example.org/b1", "http://example.org/b2"])

    def test_log_returns_the_deletion_with_the_removed_graph(self) -> None:
        body = self.client.get("/log", params={"log_id": self.id_del}).json()

        self.assertEqual(body["log"]["action_type"], "deletion")
        removed = Graph().parse(data=body["action"]["ttl_deleted_graph"], format="turtle")
        expected = Graph().parse(data=TTL_A + "\n" + TTL_B.split("\n", 1)[1], format="turtle")
        self.assertTrue(isomorphic(removed, expected))

    def test_missing_unknown_and_malformed_ids(self) -> None:
        self.assertEqual(self.client.get("/log").status_code, 400)
        self.assertEqual(self.client.get("/log", params={"log_id": str(uuid.uuid4())}).status_code, 404)
        self.assertEqual(self.client.get("/log", params={"log_id": "not-an-id"}).status_code, 404)

    def test_a_crafted_id_cannot_inject_sparql_and_changes_nothing(self) -> None:
        before = self.count(AUDIT)
        evil = self.id_a + "> ?p ?o } ; CLEAR GRAPH <" + AUDIT + "> ; SELECT * WHERE { <urn:x"

        response = self.client.get("/log", params={"log_id": evil})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.count(AUDIT), before)


if __name__ == "__main__":
    unittest.main()
