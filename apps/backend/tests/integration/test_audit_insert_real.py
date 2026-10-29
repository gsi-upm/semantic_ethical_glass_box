"""Opt-in: audit-on-insert against a real Virtuoso. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import unittest

from real_api_support import AUDIT, AUDIT_NS, EVENTS, RealApiTestCase

TTL = '@prefix ex: <http://example.org/> .\nex:greeting1 a ex:Greeting ; ex:text "hello" .\nex:greeting2 a ex:Greeting .\n'
# Its own subjects, so the count below does not depend on test order.
DUPLICATE_TTL = '@prefix ex: <http://example.org/> .\nex:dup1 a ex:Greeting ; ex:text "twice" .\nex:dup2 a ex:Greeting .\n'


class TestAuditOnInsertReal(RealApiTestCase):
    def test_same_ttl_twice_gives_one_set_of_triples_and_two_audit_entries(self) -> None:
        events_before = self.count(EVENTS)
        entries_before = self.count(AUDIT, f"?e a <{AUDIT_NS}Insertion>")

        first = self.client.post("/ttl", json={"ttl_content": DUPLICATE_TTL})
        second = self.client.post("/ttl", json={"ttl_content": DUPLICATE_TTL})

        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertNotEqual(first.json()["log_id"], second.json()["log_id"])
        self.assertEqual(self.count(EVENTS) - events_before, 3)  # 3 triples, stored once
        entries = self.count(AUDIT, f"?e a <{AUDIT_NS}Insertion>")
        self.assertEqual(entries - entries_before, 2)

    def test_entry_has_original_ttl_subjects_route_and_actor(self) -> None:
        log_id = self.client.post("/ttl", json={"ttl_content": TTL, "user": "someone_else"}).json()["log_id"]
        entry = f"<https://example.org/segb/audit/entry/{log_id}>"

        def values(prop: str) -> set[str]:
            return self.entry_values(log_id, prop)

        self.assertEqual(values("ttl"), {TTL})
        self.assertEqual(values("route"), {"POST /ttl"})
        self.assertEqual(values("originIP"), {"192.168.1.20"})
        self.assertEqual(values("actorRole"), {"logger", "admin"})
        self.assertEqual(values("mentionsSubject"), {"http://example.org/greeting1", "http://example.org/greeting2"})
        agents = self.select(
            f"SELECT ?n FROM <{AUDIT}> WHERE {{ {entry} <http://www.w3.org/ns/prov#wasAssociatedWith> ?a . ?a <http://xmlns.com/foaf/0.1/accountName> ?n }}"
        )
        self.assertEqual([r["n"]["value"] for r in agents], ["alice"])  # the token, not the claimed user

    def test_failed_insert_writes_no_insertion_entry(self) -> None:
        events_before = self.count(EVENTS)
        entries_before = self.count(AUDIT)

        response = self.client.post("/ttl", json={"ttl_content": "this is not turtle"})

        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(self.count(EVENTS), events_before)
        self.assertEqual(self.count(AUDIT), entries_before)


if __name__ == "__main__":
    unittest.main()
