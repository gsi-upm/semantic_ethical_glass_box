"""Opt-in: the audit graph cannot be read through GET /query. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import unittest

from real_api_support import AUDIT, EVENTS, RealApiTestCase

TTL = '@prefix ex: <http://example.org/> .\nex:isolation1 a ex:Greeting ; ex:text "visible-in-events" .\n'

ORACLE = (
    "SELECT ?b WHERE { BIND(EXISTS { GRAPH <@AUDIT@> { ?s ?p ?o } } AS ?b) }"
)

REJECTED = {
    "from audit": "SELECT * FROM <@AUDIT@> WHERE { ?s ?p ?o }",
    "from named audit": "SELECT * FROM NAMED <@AUDIT@> WHERE { GRAPH ?g { ?s ?p ?o } }",
    "graph audit": "SELECT * WHERE { GRAPH <@AUDIT@> { ?s ?p ?o } }",
    "graph audit through a prefix": "PREFIX g: <http://segb/> SELECT * WHERE { GRAPH g:audit { ?s ?p ?o } }",
    "graph audit with a unicode escape": "SELECT * WHERE { GRAPH <http://segb/\\u0061udit> { ?s ?p ?o } }",
    "exists oracle": ORACLE,
    "nested not exists oracle": "SELECT * WHERE { ?s ?p ?o FILTER EXISTS { ?s ?p ?o FILTER NOT EXISTS { GRAPH <@AUDIT@> { ?x ?y ?z } } } }",
    "service": "SELECT * WHERE { SERVICE <http://localhost:8890/sparql> { ?s ?p ?o } }",
    "bif:exec that clears the audit graph": "PREFIX bif: <bif:> SELECT (bif:exec('SPARQL CLEAR GRAPH <@AUDIT@>') AS ?o) WHERE {}",
    "bif:exec that clears the events graph": "PREFIX bif: <bif:> SELECT (bif:exec('SPARQL CLEAR GRAPH <@EVENTS@>') AS ?o) WHERE {}",
    "bif:exec without a prefix declaration": "SELECT (bif:exec('select 1') AS ?o) WHERE {}",
    "sql procedure": "SELECT (sql:sprintf('%d', 1) AS ?o) WHERE {}",
}


class TestQueryIsolationReal(RealApiTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.client.post("/ttl", json={"ttl_content": TTL})

    def _query(self, text: str):
        return self.client.get("/query", params={"query": text.replace("@AUDIT@", AUDIT).replace("@EVENTS@", EVENTS)})

    def _assert_no_audit(self, body: str) -> None:
        for fragment in ("segb/audit", "audit#", "/entry/"):
            self.assertNotIn(fragment, body)

    def test_control_the_audit_graph_does_exist_and_a_bare_query_would_see_it(self) -> None:
        self.assertGreater(self.count(AUDIT), 0)
        unpinned = self.select("SELECT ?s WHERE { ?s ?p ?o FILTER(CONTAINS(STR(?s), 'segb/audit/entry/')) } LIMIT 1")
        self.assertTrue(unpinned, "without the pin Virtuoso would return audit triples")

    def test_an_unqualified_query_returns_events_and_no_audit(self) -> None:
        response = self._query("SELECT * WHERE { ?s ?p ?o }")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("visible-in-events", response.text)
        self._assert_no_audit(response.text)

    def test_graph_variable_only_ranges_over_events(self) -> None:
        response = self._query("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(EVENTS, response.text)
        self._assert_no_audit(response.text)

    def test_explicit_events_graph_still_works(self) -> None:
        for text in (
            "SELECT * FROM <@EVENTS@> WHERE { ?s ?p ?o }",
            "SELECT * WHERE { GRAPH <@EVENTS@> { ?s ?p ?o } }",
        ):
            with self.subTest(text):
                response = self._query(text)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("visible-in-events", response.text)

    def test_queries_that_reach_other_graphs_are_rejected_with_422(self) -> None:
        for name, text in REJECTED.items():
            with self.subTest(name):
                response = self._query(text)
                self.assertEqual(response.status_code, 422, response.text)
                self._assert_no_audit(response.text.replace(AUDIT, ""))

    def test_a_read_query_cannot_erase_a_graph(self) -> None:
        victim = "urn:it:victim"
        self.update(f"INSERT DATA {{ GRAPH <{victim}> {{ <urn:a> <urn:p> 'x' }} }}")
        audit_before, events_before = self.count(AUDIT), self.count(EVENTS)
        clear = "PREFIX bif: <bif:> SELECT (bif:exec('SPARQL CLEAR GRAPH <%s>') AS ?o) WHERE {}"

        # Control: this Virtuoso really lets a SELECT run SQL. If a future image stops doing so, this fails loudly.
        self.select(clear % victim)
        self.assertEqual(self.count(victim), 0, "the control query no longer clears the graph")

        for target in (AUDIT, EVENTS):
            response = self._query(clear % target)
            self.assertEqual(response.status_code, 422, response.text)

        self.assertEqual((self.count(AUDIT), self.count(EVENTS)), (audit_before, events_before))

    def test_validation_endpoint_reports_them_as_invalid(self) -> None:
        response = self.client.post("/query/validate", json={"query": ORACLE.replace("@AUDIT@", AUDIT)})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["valid"])


if __name__ == "__main__":
    unittest.main()
