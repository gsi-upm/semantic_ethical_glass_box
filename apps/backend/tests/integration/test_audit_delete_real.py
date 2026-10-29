"""Opt-in: audit-on-delete against a real Virtuoso. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import hashlib
import unittest

from rdflib import Graph
from rdflib.compare import isomorphic

from real_api_support import AUDIT, AUDIT_NS, EVENTS, RealApiTestCase

SMALL_TTL = (
    '@prefix ex: <http://example.org/> .\n'
    'ex:a a ex:Greeting ; ex:text "héllo \\"quoted\\"\\nsecond line" ; ex:n 7 .\n'
    'ex:b ex:p ex:a ; ex:q [ ex:r "nested" ] .\n'
)


def _large_chunks(chunks: int, subjects_per_chunk: int = 1600) -> list[str]:
    """N-Triples chunks, each under the ~5000-triples limit of one INSERT DATA in Virtuoso."""
    result = []
    for c in range(chunks):
        lines = []
        for i in range(c * subjects_per_chunk, (c + 1) * subjects_per_chunk):
            s = f"<http://example.org/item{i}>"
            lines.append(f'{s} <http://example.org/label> "label of item number {i} with some padding text" .')
            lines.append(f"{s} <http://example.org/n> \"{i}\"^^<http://www.w3.org/2001/XMLSchema#integer> .")
            lines.append(f"{s} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Thing> .")
        result.append("\n".join(lines))
    return result


class TestAuditOnDeleteReal(RealApiTestCase):
    def setUp(self) -> None:
        self.update(f"CLEAR GRAPH <{EVENTS}>")  # start every test from an empty events graph

    def _delete_and_check(self, ttl: str) -> str:
        self.assertEqual(self.client.post("/ttl", json={"ttl_content": ttl}).status_code, 201)
        before_entries = self.count(AUDIT)
        before_ids = self.entry_ids("Insertion") | self.entry_ids("Deletion")

        response = self.client.post("/ttl/delete_all", json={})

        self.assertEqual(response.status_code, 200, response.text)
        log_id = response.json()["log_id"]
        self.assertEqual(self.count(EVENTS), 0)
        # Nothing in audit was removed: every earlier entry is still there, plus exactly one deletion.
        after_ids = self.entry_ids("Insertion") | self.entry_ids("Deletion")
        self.assertTrue(before_ids <= after_ids)
        self.assertEqual(after_ids - before_ids, {f"https://example.org/segb/audit/entry/{log_id}"})
        self.assertGreater(self.count(AUDIT), before_entries)

        (stored,) = self.entry_values(log_id, "ttl")
        expected, actual = Graph().parse(data=ttl, format="turtle"), Graph().parse(data=stored, format="turtle")
        self.assertTrue(isomorphic(expected, actual), "the stored TTL is not the graph that was deleted")
        self.assertEqual(self.entry_values(log_id, "route"), {"POST /ttl/delete_all"})
        self.assertEqual(self.entry_values(log_id, "originIP"), {"192.168.1.20"})
        return log_id

    def test_delete_all_keeps_the_audit_and_adds_a_deletion_with_the_removed_graph(self) -> None:
        self._delete_and_check(SMALL_TTL)

    def test_a_large_graph_is_kept_in_a_file_referenced_by_the_entry(self) -> None:
        chunks = _large_chunks(40)  # 40 x 4,800 = 192,000 triples, about 8 MB of Turtle
        for chunk in chunks:
            self.update(f"INSERT DATA {{ GRAPH <{EVENTS}> {{ {chunk} }} }}")
        expected = Graph().parse(data="\n".join(chunks), format="nt")
        self.assertEqual(self.count(EVENTS), len(expected))
        before_ids = self.entry_ids("Deletion")

        response = self.client.post("/ttl/delete_all", json={})

        self.assertEqual(response.status_code, 200, response.text)
        log_id = response.json()["log_id"]
        self.assertEqual(self.count(EVENTS), 0)
        self.assertEqual(self.entry_ids("Deletion") - before_ids, {f"https://example.org/segb/audit/entry/{log_id}"})
        # Too large for the statement: no embedded literal, a file and its hash instead.
        self.assertFalse(self.entry_values(log_id, "ttl"), "the large dump was embedded in the entry")
        (file_name,) = self.entry_values(log_id, "ttlFile")
        (sha256,) = self.entry_values(log_id, "ttlSha256")
        dump = (self.dump_dir / file_name).read_bytes()
        self.assertGreater(len(dump), 4 * 1024 * 1024)
        self.assertEqual(hashlib.sha256(dump).hexdigest(), sha256)
        self.assertTrue(isomorphic(expected, Graph().parse(data=dump.decode("utf-8"), format="turtle")))

    def test_delete_on_an_empty_graph_writes_no_entry(self) -> None:
        entries_before = self.count(AUDIT)
        response = self.client.post("/ttl/delete_all", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "No TTLs to delete")
        self.assertEqual(self.count(AUDIT), entries_before)

    def test_audit_is_never_cleared_by_repeated_deletes(self) -> None:
        self._delete_and_check(SMALL_TTL)
        self._delete_and_check(SMALL_TTL)
        self.assertGreaterEqual(len(self.entry_ids("Deletion")), 2)


if __name__ == "__main__":
    unittest.main()
