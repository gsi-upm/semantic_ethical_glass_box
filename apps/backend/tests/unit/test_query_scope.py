from __future__ import annotations

import unittest

from utils.query_scope import QueryScopeError, check_read_query_scope

EVENTS = "http://segb/events"
AUDIT = "http://segb/audit"


def _q(text: str) -> str:
    """Queries are written with @EVENTS@ and @AUDIT@ so that SPARQL braces stay readable."""
    return text.replace("@EVENTS@", EVENTS).replace("@AUDIT@", AUDIT)


ACCEPTED = {
    "plain": "SELECT * { ?s ?p ?o }",
    "from events": "SELECT * FROM <@EVENTS@> { ?s ?p ?o }",
    "from named events": "SELECT * FROM NAMED <@EVENTS@> { GRAPH ?g { ?s ?p ?o } }",
    "graph events": "SELECT * { GRAPH <@EVENTS@> { ?s ?p ?o } }",
    "graph variable": "SELECT * { GRAPH ?g { ?s ?p ?o } }",
    "subselect": "SELECT * { { SELECT ?s { ?s ?p ?o } } }",
    "ask": "ASK { ?s ?p ?o }",
    "construct": "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
    "describe": "DESCRIBE <http://example.org/a>",
    "prefixed name that resolves to events": "PREFIX g: <http://segb/> SELECT * { GRAPH g:events { ?s ?p ?o } }",
    "relative iri that resolves to events": "BASE <http://segb/> SELECT * { GRAPH <events> { ?s ?p ?o } }",
    "exists over events": "SELECT * { ?s ?p ?o FILTER EXISTS { ?s ?q ?r } }",
    "graph events in exists": "SELECT * { ?s ?p ?o FILTER EXISTS { GRAPH <@EVENTS@> { ?s ?q ?r } } }",
    "keywords in a comment": "# GRAPH <@AUDIT@> and SERVICE\nSELECT * { ?s ?p ?o }",
    "keywords inside a string": 'SELECT * { ?s ?p "FROM <@AUDIT@> GRAPH SERVICE" }',
    "keywords inside a long string": "SELECT * { ?s ?p '''GRAPH <@AUDIT@> \" ' FROM''' }",
    "hash inside an iri is not a comment": "SELECT * { GRAPH <@EVENTS@> { <http://example.org/a#b> ?p ?o } }",
    "a name that merely contains graph": "SELECT * { ?graph ?from ?service }",
    "lowercase keywords over events": "select * from <@EVENTS@> where { graph <@EVENTS@> { ?s ?p ?o } }",
    "variable graph written without a space": "SELECT * { GRAPH?g { ?s ?p ?o } }",
    "xsd cast with a prefix": "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> SELECT (xsd:integer(?o) AS ?n) { ?s ?p ?o }",
    "xsd cast with a full iri": "SELECT (<http://www.w3.org/2001/XMLSchema#integer>(?o) AS ?n) { ?s ?p ?o }",
    "standard builtin functions": "SELECT * { ?s ?p ?o FILTER(REGEX(STR(?o), 'a') && CONTAINS(STR(?s), 'b') && !BOUND(?x)) }",
    "bif only inside a string": "SELECT * { ?s ?p 'bif:exec(1) sql:x' }",
    "bif only inside a comment": "# bif:exec('x')\nSELECT * { ?s ?p ?o }",
    "a variable named bif": "SELECT ?bif { ?bif ?p ?o }",
    "a local name that looks like a function": "PREFIX ex: <http://example.org/> SELECT * { ?s ex:bif ?o . ?s ex:sql ?x }",
    "a prefix label that merely contains bif": "PREFIX notbif: <http://example.org/> SELECT * { ?s notbif:p ?o }",
}

REJECTED = {
    "from audit": "SELECT * FROM <@AUDIT@> { ?s ?p ?o }",
    "from another graph": "SELECT * FROM <http://example.org/other> { ?s ?p ?o }",
    "from events and audit": "SELECT * FROM <@EVENTS@> FROM <@AUDIT@> { ?s ?p ?o }",
    "from named audit": "SELECT * FROM NAMED <@AUDIT@> { GRAPH ?g { ?s ?p ?o } }",
    "graph audit": "SELECT * { GRAPH <@AUDIT@> { ?s ?p ?o } }",
    "graph another": "SELECT * { GRAPH <http://example.org/other> { ?s ?p ?o } }",
    "prefixed name that resolves to audit": "PREFIX g: <http://segb/> SELECT * { GRAPH g:audit { ?s ?p ?o } }",
    "relative iri that resolves to audit": "BASE <http://segb/> SELECT * { GRAPH <audit> { ?s ?p ?o } }",
    "graph audit in a sub-select": "SELECT * { { SELECT * { GRAPH <@AUDIT@> { ?s ?p ?o } } } }",
    "graph audit in optional": "SELECT * { ?s ?p ?o OPTIONAL { GRAPH <@AUDIT@> { ?s ?q ?r } } }",
    "graph audit in union": "SELECT * { { ?s ?p ?o } UNION { GRAPH <@AUDIT@> { ?s ?p ?o } } }",
    "graph audit in minus": "SELECT * { ?s ?p ?o MINUS { GRAPH <@AUDIT@> { ?s ?p ?o } } }",
    "graph audit in filter exists": "SELECT * { ?s ?p ?o FILTER EXISTS { GRAPH <@AUDIT@> { ?s ?q ?r } } }",
    "graph audit in filter not exists": "SELECT * { ?s ?p ?o FILTER NOT EXISTS { GRAPH <@AUDIT@> { ?s ?q ?r } } }",
    "graph audit in nested exists": "SELECT * { ?s ?p ?o FILTER EXISTS { ?s ?q ?r FILTER NOT EXISTS { GRAPH <@AUDIT@> { ?s ?x ?y } } } }",
    "graph audit in bind exists": "SELECT * { ?s ?p ?o BIND(EXISTS { GRAPH <@AUDIT@> { ?s ?q ?r } } AS ?b) }",
    "graph audit in having exists": "SELECT ?s { ?s ?p ?o } GROUP BY ?s HAVING(EXISTS { GRAPH <@AUDIT@> { ?s ?q ?r } })",
    "graph audit in order by exists": "SELECT * { ?s ?p ?o } ORDER BY (EXISTS { GRAPH <@AUDIT@> { ?s ?q ?r } })",
    "graph audit in select expression": "SELECT (EXISTS { GRAPH <@AUDIT@> { ?s ?q ?r } } AS ?b) { ?s ?p ?o }",
    "prefixed audit in exists": "PREFIX g: <http://segb/> SELECT * { ?s ?p ?o FILTER EXISTS { GRAPH g:audit { ?s ?q ?r } } }",
    "relative audit in exists": "BASE <http://segb/> SELECT * { ?s ?p ?o FILTER EXISTS { GRAPH <audit> { ?s ?q ?r } } }",
    "graph audit in a sub-select in exists": "SELECT * { ?s ?p ?o FILTER EXISTS { SELECT * { GRAPH <@AUDIT@> { ?s ?q ?r } } } }",
    "events from but audit graph": "SELECT * FROM <@EVENTS@> { GRAPH <@AUDIT@> { ?s ?p ?o } }",
    "ask on audit": "ASK { GRAPH <@AUDIT@> { ?s ?p ?o } }",
    "construct from named audit": "CONSTRUCT { ?s ?p ?o } FROM NAMED <@AUDIT@> WHERE { GRAPH ?g { ?s ?p ?o } }",
    "describe from audit": "DESCRIBE <http://example.org/a> FROM <@AUDIT@>",
    "service": "SELECT * { SERVICE <http://example.org/sparql> { ?s ?p ?o } }",
    "service silent": "SELECT * { SERVICE SILENT <http://example.org/sparql> { ?s ?p ?o } }",
    "service variable": "SELECT * { BIND(<http://example.org/sparql> AS ?e) SERVICE ?e { ?s ?p ?o } }",
    "service in exists": "SELECT * { ?s ?p ?o FILTER EXISTS { SERVICE <http://example.org/s> { ?s ?q ?r } } }",
    "lowercase keywords": "select * from <@AUDIT@> where { ?s ?p ?o }",
    "mixed case graph": "SELECT * { GrApH <@AUDIT@> { ?s ?p ?o } }",
    "no space before the iri": "SELECT * { GRAPH<@AUDIT@>{ ?s ?p ?o } }",
    "newline and tab between tokens": "SELECT *\nFROM\n\t<@AUDIT@>\nWHERE { ?s ?p ?o }",
    "comment between graph and iri": "SELECT * { GRAPH # hide\n <@AUDIT@> { ?s ?p ?o } }",
    "unicode escape in the keyword": "SELECT * { GR\\u0041PH <@AUDIT@> { ?s ?p ?o } }",
    "unicode escape in the iri": "SELECT * { GRAPH <http://segb/\\u0061udit> { ?s ?p ?o } }",
    "long unicode escape in the iri": "SELECT * { GRAPH <http://segb/\\U00000061udit> { ?s ?p ?o } }",
    "escaped service": "SELECT * { \\u0053ERVICE <http://example.org/s> { ?s ?p ?o } }",
    "relative iri without a base": "SELECT * { GRAPH <events> { ?s ?p ?o } }",
    "relative from without a base": "SELECT * FROM <events> { ?s ?p ?o }",
    "empty prefix": "PREFIX : <http://segb/> SELECT * { GRAPH :audit { ?s ?p ?o } }",
    "prefix redeclared to audit": "PREFIX g: <http://example.org/> PREFIX g: <http://segb/> SELECT * { GRAPH g:audit { ?s ?p ?o } }",
    "dot-segment iri": "BASE <http://segb/events/> SELECT * { GRAPH <../audit> { ?s ?p ?o } }",
    "graph followed by something odd": "SELECT * { GRAPH (?x) { ?s ?p ?o } }",
    "bif:exec with a declared prefix": "PREFIX bif: <bif:> SELECT (bif:exec('SPARQL CLEAR GRAPH <@AUDIT@>') AS ?o) {}",
    "bif:exec without any prefix declaration": "SELECT (bif:exec('select 1') AS ?o) {}",
    "bif under another prefix label": "PREFIX b: <bif:> SELECT (b:exec('select 1') AS ?o) {}",
    "bif through its namespace iri": "PREFIX b: <http://www.openlinksw.com/schemas/bif#> SELECT (b:exec('select 1') AS ?o) {}",
    "bif as an iriref function": "SELECT (<bif:exec>('select 1') AS ?o) {}",
    "bif in uppercase": "SELECT (BIF:exec('select 1') AS ?o) {}",
    "bif with a unicode escape": "SELECT (b\\u0069f:exec('select 1') AS ?o) {}",
    "bif magic predicate": "PREFIX bif: <bif:> SELECT ?o { ?s ?p ?o . ?o bif:contains 'x' }",
    "bif inside exists": "SELECT * { ?s ?p ?o FILTER EXISTS { BIND(bif:exec('select 1') AS ?x) } }",
    "sql procedure call": "PREFIX sql: <sql:> SELECT (sql:sprintf('%d', 1) AS ?o) {}",
    "sql without a declaration": "SELECT (sql:sprintf('%d', 1) AS ?o) {}",
    "sql iriref function": "SELECT (<sql:sprintf>('%d', 1) AS ?o) {}",
    "a custom function under an ordinary namespace": "SELECT (<http://example.org/fn>(?o) AS ?n) { ?s ?p ?o }",
    "a custom function with a prefixed name": "PREFIX ex: <http://example.org/> SELECT (ex:fn(?o) AS ?n) { ?s ?p ?o }",
    "a custom aggregate": "PREFIX ex: <http://example.org/> SELECT (ex:agg(DISTINCT ?o) AS ?n) { ?s ?p ?o }",
    "rdf collection after an iri is treated as a function call (known limitation)": "PREFIX ex: <http://example.org/> SELECT * { ?s ex:list (1 2) }",
    "audit after a comment inside nested exists": "SELECT * { ?s ?p ?o # c\n FILTER EXISTS { ?s ?q ?r FILTER NOT EXISTS { GRAPH <@AUDIT@> { ?s ?x ?y } } } }",
}


class TestQueryScope(unittest.TestCase):
    def test_queries_over_events_are_accepted(self) -> None:
        for name, query in ACCEPTED.items():
            with self.subTest(name):
                check_read_query_scope(_q(query), EVENTS)

    def test_queries_that_reach_any_other_graph_or_a_service_are_rejected(self) -> None:
        for name, query in REJECTED.items():
            with self.subTest(name):
                with self.assertRaises(QueryScopeError):
                    check_read_query_scope(_q(query), EVENTS)

    def test_the_message_names_the_offending_graph(self) -> None:
        with self.assertRaises(QueryScopeError) as context:
            check_read_query_scope(_q("SELECT * { GRAPH <@AUDIT@> { ?s ?p ?o } }"), EVENTS)
        self.assertIn(AUDIT, str(context.exception))
        self.assertIn(EVENTS, str(context.exception))

    def test_the_allowed_graph_is_a_parameter(self) -> None:
        check_read_query_scope(_q("SELECT * FROM <@AUDIT@> { ?s ?p ?o }"), AUDIT)
        with self.assertRaises(QueryScopeError):
            check_read_query_scope(_q("SELECT * FROM <@EVENTS@> { ?s ?p ?o }"), AUDIT)


if __name__ == "__main__":
    unittest.main()
