from __future__ import annotations

import unittest
from datetime import datetime, timezone

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF, XSD

from utils.audit import AUDIT, DCTERMS, PROV, AuditContext, build_insertion_entry, subject_uris

BASE = "https://example.org/segb/audit/"
LOG_ID = "6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10"
ENTRY = URIRef(f"{BASE}entry/{LOG_ID}")
TTL = '@prefix ex: <http://example.org/> .\nex:greeting1 a ex:Greeting ; ex:text "hi \\"there\\"" .\n'
NOW = datetime(2026, 10, 29, 10, 15, 42, 123000, tzinfo=timezone.utc)
CONTEXT = AuditContext(username="alice", roles=("logger", "admin"), origin_ip="192.168.1.20", route="POST /ttl")


def _entry(**overrides) -> Graph:
    args = dict(log_id=LOG_ID, context=CONTEXT, ttl_content=TTL, base_iri=BASE, now=NOW)
    args.update(overrides)
    return build_insertion_entry(**args)


class TestInsertionEntry(unittest.TestCase):
    def test_entry_is_an_insertion_with_the_log_id(self) -> None:
        g = _entry()
        self.assertIn((ENTRY, RDF.type, AUDIT.Insertion), g)
        self.assertEqual(g.value(ENTRY, DCTERMS.identifier), Literal(LOG_ID))

    def test_time_is_utc_with_z_suffix(self) -> None:
        value = _entry().value(ENTRY, PROV.startedAtTime)
        self.assertEqual(value.datatype, XSD.dateTime)
        self.assertEqual(str(value), "2026-10-29T10:15:42.123Z")

    def test_agent_roles_ip_and_route(self) -> None:
        g = _entry()
        agent = URIRef(f"{BASE}agent/alice")
        self.assertIn((ENTRY, PROV.wasAssociatedWith, agent), g)
        self.assertIn((agent, RDF.type, PROV.Agent), g)
        self.assertEqual(g.value(agent, FOAF.accountName), Literal("alice"))
        self.assertEqual({str(o) for o in g.objects(ENTRY, AUDIT.actorRole)}, {"logger", "admin"})
        self.assertEqual(g.value(ENTRY, AUDIT.originIP), Literal("192.168.1.20"))
        self.assertEqual(g.value(ENTRY, AUDIT.route), Literal("POST /ttl"))

    def test_original_ttl_is_stored_verbatim(self) -> None:
        self.assertEqual(str(_entry().value(ENTRY, AUDIT.ttl)), TTL)

    def test_mentioned_subjects_are_the_uri_subjects_only(self) -> None:
        ttl = '@prefix ex: <http://example.org/> .\nex:a ex:p ex:b .\nex:c ex:p [ ex:q "x" ] .\n_:n1 ex:p ex:d .\n'
        subjects = {str(o) for o in _entry(ttl_content=ttl).objects(ENTRY, AUDIT.mentionsSubject)}
        self.assertEqual(subjects, {"http://example.org/a", "http://example.org/c"})

    def test_username_is_percent_encoded_in_the_agent_iri_but_kept_in_account_name(self) -> None:
        g = _entry(context=AuditContext("ana maría/x", ("admin",), "-", "POST /ttl"))
        agent = URIRef(f"{BASE}agent/ana%20mar%C3%ADa%2Fx")
        self.assertIn((agent, RDF.type, PROV.Agent), g)
        self.assertEqual(g.value(agent, FOAF.accountName), Literal("ana maría/x"))

    def test_base_iri_without_trailing_slash_is_normalised(self) -> None:
        g = _entry(base_iri="https://example.org/segb/audit")
        self.assertIn((ENTRY, RDF.type, AUDIT.Insertion), g)

    def test_naive_datetime_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _entry(now=datetime(2026, 10, 29, 10, 0, 0))


class TestSubjectUris(unittest.TestCase):
    def test_blank_nodes_are_skipped_and_result_is_sorted_and_unique(self) -> None:
        g = Graph()
        g.add((URIRef("http://e/b"), URIRef("http://e/p"), Literal(1)))
        g.add((URIRef("http://e/a"), URIRef("http://e/p"), Literal(2)))
        g.add((URIRef("http://e/a"), URIRef("http://e/q"), Literal(3)))
        g.add((BNode(), URIRef("http://e/p"), Literal(4)))
        self.assertEqual(subject_uris(g), [URIRef("http://e/a"), URIRef("http://e/b")])


if __name__ == "__main__":
    unittest.main()
