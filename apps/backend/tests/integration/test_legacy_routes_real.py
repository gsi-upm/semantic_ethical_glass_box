"""Opt-in: legacy POST /log against a real Virtuoso. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import unittest

from rdflib import Graph
from rdflib.compare import isomorphic

from real_api_support import AUDIT, EVENTS, RealApiTestCase

TTL = '@prefix ex: <http://example.org/> .\nex:legacy1 a ex:Greeting ; ex:text "robot says hi" .\nex:legacy2 ex:p ex:legacy1 .\n'
TURTLE = {"content-type": "text/turtle"}


class TestLegacyRoutesReal(RealApiTestCase):
    def setUp(self) -> None:
        self.update(f"CLEAR GRAPH <{EVENTS}>")

    def _events(self) -> Graph:
        return Graph().parse(data=self.client.get("/events").text, format="turtle")

    def test_same_ttl_through_log_and_ttl_gives_the_same_events_and_one_entry_each(self) -> None:
        via_log = self.client.post("/log", content=TTL, headers=TURTLE)
        self.assertEqual((via_log.status_code, via_log.json()), (201, {"message": "Log saved successfully"}))
        events_after_log = self._events()
        entries_before = self.entry_ids("Insertion")

        self.update(f"CLEAR GRAPH <{EVENTS}>")
        via_ttl = self.client.post("/ttl", json={"ttl_content": TTL})
        self.assertEqual(via_ttl.status_code, 201)

        self.assertTrue(isomorphic(events_after_log, self._events()), "the two routes stored different triples")
        self.assertEqual(len(events_after_log), 3)
        new_entries = self.entry_ids("Insertion") - entries_before
        self.assertEqual(len(new_entries), 1)
        (ttl_entry_id,) = [i.rsplit("/", 1)[1] for i in new_entries]
        self.assertEqual(self.entry_values(ttl_entry_id, "route"), {"POST /ttl"})
        log_id_rows = self.select(
            f'SELECT ?e FROM <{AUDIT}> WHERE {{ ?e <http://www.gsi.upm.es/ontologies/segb/audit#route> "POST /log" }}'
        )
        self.assertGreaterEqual(len(log_id_rows), 1)

    def test_the_legacy_entry_has_the_original_ttl_and_the_token_identity(self) -> None:
        self.client.post("/log", content=TTL, headers=TURTLE)
        rows = self.select(
            f'SELECT ?e FROM <{AUDIT}> WHERE {{ ?e <http://www.gsi.upm.es/ontologies/segb/audit#route> "POST /log" }}'
        )
        log_id = rows[-1]["e"]["value"].rsplit("/", 1)[1]

        self.assertEqual(self.entry_values(log_id, "ttl"), {TTL})
        self.assertEqual(self.entry_values(log_id, "originIP"), {"192.168.1.20"})
        entry = self.client.get("/log", params={"log_id": log_id}).json()
        self.assertEqual(entry["log"]["user_details"]["username"], "alice")
        self.assertEqual(entry["log"]["route"], "POST /log")

    def test_the_legacy_count_goes_up_by_one_per_call_and_ignores_native_inserts(self) -> None:
        before = self.client.get("/legacy/usage").json()["routes"]["POST /log"]["count"]

        self.client.post("/log", content=TTL, headers=TURTLE)
        self.client.post("/log", content=TTL, headers=TURTLE)
        self.client.post("/ttl", json={"ttl_content": TTL})
        usage = self.client.get("/legacy/usage").json()["routes"]["POST /log"]

        self.assertEqual(usage["count"] - before, 2)
        self.assertTrue(usage["first_used_at"].endswith("Z") and usage["last_used_at"].endswith("Z"))
        self.assertLessEqual(usage["first_used_at"], usage["last_used_at"])

    def test_invalid_turtle_is_422_and_writes_neither_events_nor_audit(self) -> None:
        events_before, audit_before = self.count(EVENTS), self.count(AUDIT)
        response = self.client.post("/log", content="not turtle at all", headers=TURTLE)

        self.assertEqual(response.status_code, 422)
        self.assertEqual((self.count(EVENTS), self.count(AUDIT)), (events_before, audit_before))

    def test_health_is_plain_text_and_adds_no_audit_entry(self) -> None:
        audit_before = self.count(AUDIT)
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertEqual(response.headers["deprecation"], "true")
        self.assertEqual(self.count(AUDIT), audit_before)


if __name__ == "__main__":
    unittest.main()
