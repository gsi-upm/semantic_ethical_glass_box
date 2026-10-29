from __future__ import annotations

import unittest

from utils.audit import AUDIT, DCTERMS, PROV, entries_from_rows

NS = str(AUDIT)
BASE = "https://example.org/segb/audit/"
ID1 = "6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10"
ID2 = "11111111-2222-4333-8444-555555555555"
AGENT = f"{BASE}agent/alice"


def _row(entry_id: str, predicate: str, value: str) -> dict[str, str]:
    return {"e": f"{BASE}entry/{entry_id}", "p": predicate, "o": value}


def _insertion_rows(entry_id: str = ID1, when: str = "2026-10-29T10:15:42.123Z") -> list[dict[str, str]]:
    return [
        _row(entry_id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{NS}Insertion"),
        _row(entry_id, str(DCTERMS.identifier), entry_id),
        _row(entry_id, str(PROV.startedAtTime), when),
        _row(entry_id, str(PROV.wasAssociatedWith), AGENT),
        _row(entry_id, f"{NS}actorRole", "logger"),
        _row(entry_id, f"{NS}actorRole", "admin"),
        _row(entry_id, f"{NS}originIP", "192.168.1.20"),
        _row(entry_id, f"{NS}route", "POST /ttl"),
        _row(entry_id, f"{NS}ttl", "@prefix ex: <http://example.org/> .\nex:a a ex:B .\n"),
        _row(entry_id, f"{NS}mentionsSubject", "http://example.org/b"),
        _row(entry_id, f"{NS}mentionsSubject", "http://example.org/a"),
    ]


class TestEntriesFromRows(unittest.TestCase):
    def test_insertion_keeps_the_0_4_summary_keys_and_adds_route(self) -> None:
        (entry,) = entries_from_rows(_insertion_rows(), {AGENT: "alice"})
        self.assertEqual(
            entry.summary,
            {
                "_id": ID1,
                "uploaded_at": "2026-10-29T10:15:42.123Z",
                "origin_ip": "192.168.1.20",
                "action_type": "insertion",
                "action": ID1,
                "user_details": {"username": "alice", "roles": ["admin", "logger"]},
                "route": "POST /ttl",
            },
        )

    def test_insertion_detail_has_ttl_content_and_sorted_subjects(self) -> None:
        (entry,) = entries_from_rows(_insertion_rows(), {AGENT: "alice"})
        self.assertEqual(entry.action["ttl_content"], "@prefix ex: <http://example.org/> .\nex:a a ex:B .\n")
        self.assertEqual(entry.action["subjects"], ["http://example.org/a", "http://example.org/b"])

    def test_deletion_detail_is_ttl_deleted_graph(self) -> None:
        rows = [
            _row(ID2, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{NS}Deletion"),
            _row(ID2, str(PROV.startedAtTime), "2026-10-29T11:00:00.000Z"),
            _row(ID2, f"{NS}ttl", "removed"),
        ]
        (entry,) = entries_from_rows(rows, {})
        self.assertEqual(entry.summary["action_type"], "deletion")
        self.assertEqual(entry.action, {"ttl_deleted_graph": "removed"})

    def test_deletion_dump_kept_in_a_file_is_referenced(self) -> None:
        rows = [
            _row(ID2, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{NS}Deletion"),
            _row(ID2, str(PROV.startedAtTime), "2026-10-29T11:00:00.000Z"),
            _row(ID2, f"{NS}ttlFile", f"{ID2}.ttl"),
            _row(ID2, f"{NS}ttlSha256", "ab" * 32),
        ]
        (entry,) = entries_from_rows(rows, {})
        self.assertEqual(entry.action, {"ttl_deleted_graph_file": f"{ID2}.ttl", "ttl_deleted_graph_sha256": "ab" * 32})

    def test_entries_are_ordered_oldest_first_and_rows_may_arrive_mixed(self) -> None:
        rows = _insertion_rows(ID1, "2026-10-29T12:00:00.000Z") + _insertion_rows(ID2, "2026-10-29T09:00:00.000Z")
        rows = rows[::2] + rows[1::2]
        self.assertEqual([e.summary["_id"] for e in entries_from_rows(rows, {AGENT: "alice"})], [ID2, ID1])

    def test_unknown_agent_gives_a_null_username(self) -> None:
        (entry,) = entries_from_rows(_insertion_rows(), {})
        self.assertIsNone(entry.summary["user_details"]["username"])

    def test_no_rows_no_entries(self) -> None:
        self.assertEqual(entries_from_rows([], {}), [])


if __name__ == "__main__":
    unittest.main()
