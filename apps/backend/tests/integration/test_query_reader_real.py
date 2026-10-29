"""Opt-in: GET /query runs on a read-only Virtuoso account. Run with SEGB_INTEGRATION=1.

The lexical scope check in ``utils.query_scope`` is switched off in several tests on purpose: they check local
triple access and updates independently of that filter. Graph-name metadata and remote SERVICE identities are
separate boundaries: the dataset pin and the SERVICE rejection remain necessary.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from unittest import mock

import requests
from rdflib import Graph
from requests.auth import HTTPDigestAuth

import virtuoso_harness as harness
from models.virtuoso_model import VirtuosoModel
from real_api_support import AUDIT, EVENTS, RealApiTestCase

OTHER = "urn:it:other"
TTL = '@prefix ex: <http://example.org/> .\nex:reader1 a ex:Greeting ; ex:text "reader-visible" .\n'

AUDIT_READS = {
    "bare triple pattern": "SELECT * WHERE { ?s ?p ?o }",
    "from audit": f"SELECT * FROM <{AUDIT}> WHERE {{ ?s ?p ?o }}",
    "from named audit": f"SELECT * FROM NAMED <{AUDIT}> WHERE {{ GRAPH ?g {{ ?s ?p ?o }} }}",
    "graph audit": f"SELECT * WHERE {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }}",
    "graph variable": "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }",
    "construct from audit": f"CONSTRUCT {{ ?s ?p ?o }} FROM <{AUDIT}> WHERE {{ ?s ?p ?o }}",
    "describe an audit entry": f"DESCRIBE ?e FROM <{AUDIT}> WHERE {{ ?e ?p ?o }}",
}
ORACLE = f"SELECT ?b WHERE {{ BIND(EXISTS {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }} AS ?b) }}"
SQL_ESCAPES = {
    "bif:exec clears events": f"PREFIX bif: <bif:> SELECT (bif:exec('SPARQL CLEAR GRAPH <{EVENTS}>') AS ?o) WHERE {{}}",
    "bif:exec clears audit": f"PREFIX bif: <bif:> SELECT (bif:exec('SPARQL CLEAR GRAPH <{AUDIT}>') AS ?o) WHERE {{}}",
    "bif:exec grants update": "PREFIX bif: <bif:> SELECT (bif:exec('GRANT SPARQL_UPDATE TO segb_reader') AS ?o) WHERE {}",
    "bif:exec counts raw audit rows": (
        "PREFIX bif: <bif:> SELECT (bif:exec(\"select count(*) from DB.DBA.RDF_QUAD "
        f"where G = iri_to_id('{AUDIT}')\") AS ?o) WHERE {{}}"
    ),
    "bif:exec reads raw audit subjects": (
        "PREFIX bif: <bif:> SELECT (bif:exec(\"select id_to_iri(S) from DB.DBA.RDF_QUAD "
        f"where G = iri_to_id('{AUDIT}')\") AS ?o) WHERE {{}}"
    ),
}


def _updates(graph: str) -> dict[str, str]:
    return {
        "insert": f"INSERT DATA {{ GRAPH <{graph}> {{ <urn:it:x> <urn:it:p> 'injected' }} }}",
        "delete": f"DELETE WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}",
        "clear": f"CLEAR GRAPH <{graph}>",
        "drop": f"DROP SILENT GRAPH <{graph}>",
        "copy over it": f"COPY <{OTHER}> TO <{graph}>",
    }


def _audit_free(test: unittest.TestCase, body: str) -> None:
    for fragment in ("segb/audit", "audit#", "/entry/"):
        test.assertNotIn(fragment, body)


def _filter_disabled():
    """Turns the lexical scope check into a no-op, leaving only Virtuoso's own permissions."""
    return mock.patch("models.virtuoso_model.check_read_query_scope", lambda query, graph: None)


@unittest.skipUnless(harness.integration_enabled(), "set SEGB_INTEGRATION=1 to run against a real Virtuoso")
class TestFreshReaderProvisioningReal(unittest.TestCase):
    def test_fresh_image_matches_the_reviewed_manifest(self) -> None:
        with harness.VirtuosoTestInstance() as virtuoso:
            virtuoso.provision_query_reader()

    def test_a_routine_with_inherited_execute_is_executable_by_the_reader_and_refused_by_provisioning(self) -> None:
        # Characterization: EXECUTE inherited from PUBLIC or SPARQL_SELECT lets GET /query-style SPARQL run a
        # definer-rights procedure that writes a SQL table. Provisioning must refuse such an account.
        for grantee in ("PUBLIC", "SPARQL_SELECT"):
            with self.subTest(grantee=grantee), harness.VirtuosoTestInstance() as virtuoso:
                reader = virtuoso.provision_query_reader(user="segb_preexisting", password="pw")
                virtuoso.sql("create table DB.DBA.SEGB_IT_PREEXISTING (N integer)")
                virtuoso.sql(
                    "create procedure DB.DBA.SEGB_IT_PREEXISTING_WRITE () "
                    "{ insert into DB.DBA.SEGB_IT_PREEXISTING values (1); return 1; }"
                )
                virtuoso.sql(f"GRANT EXECUTE ON DB.DBA.SEGB_IT_PREEXISTING_WRITE TO {grantee}")
                response = requests.post(
                    virtuoso.endpoint,
                    data={"query": "PREFIX sql: <sql:> SELECT (sql:SEGB_IT_PREEXISTING_WRITE() AS ?x) WHERE {}"},
                    headers={"Accept": "application/sparql-results+json"},
                    auth=HTTPDigestAuth(reader["VIRTUOSO_READER_USER"], reader["VIRTUOSO_READER_PASSWORD"]),
                    timeout=60,
                )
                self.assertEqual(response.status_code, 200, response.text)
                count = virtuoso.sql("select count (*) from DB.DBA.SEGB_IT_PREEXISTING")
                self.assertRegex(count, re.compile(r"^\s*1\s*$", re.MULTILINE), count)

                with self.assertRaises(harness.ProvisioningError) as raised:
                    virtuoso.provision_query_reader(user="segb_preexisting", password="pw")
                self.assertIn("SEGB_IT_PREEXISTING_WRITE", raised.exception.stderr)

    def test_a_shipped_routine_replaced_after_provisioning_is_detected(self) -> None:
        with harness.VirtuosoTestInstance() as virtuoso:
            virtuoso.provision_query_reader(user="segb_body_reader", password="pw")
            before = virtuoso.sql("select DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT ('segb_body_reader')")
            self.assertRegex(before, re.compile(r"^\s*0\s*$", re.MULTILINE), before)

            virtuoso.sql("create procedure DB.DBA.VSPX_CONTROL_EXISTS () { return 1; }")

            after = virtuoso.sql("select DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT ('segb_body_reader')")
            self.assertRegex(after, re.compile(r"^\s*1\s*$", re.MULTILINE), after)
            with self.assertRaises(harness.ProvisioningError):
                virtuoso.provision_query_reader(user="segb_body_reader", password="pw")

    def test_an_object_owned_by_the_reader_is_detected_after_provisioning_and_blocks_it(self) -> None:
        # Owner rights need no SYS_GRANTS row, so they must be listed by the policy check itself.
        with harness.VirtuosoTestInstance() as virtuoso:
            virtuoso.provision_query_reader(user="segb_owner", password="pw")
            clean = virtuoso.sql("select DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT ('segb_owner')")
            self.assertRegex(clean, re.compile(r"^\s*0\s*$", re.MULTILINE), clean)

            virtuoso.sql("create table DB.segb_owner.OWNED_PROBE (N integer)")

            # The stored digest from the successful run is still in place, so this is runtime detection.
            drift = virtuoso.sql("select DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT ('segb_owner')")
            self.assertRegex(drift, re.compile(r"^\s*1\s*$", re.MULTILINE), drift)
            with self.assertRaises(harness.ProvisioningError) as raised:
                virtuoso.provision_query_reader(user="segb_owner", password="pw")
            self.assertIn("OWNS|DB.segb_owner.OWNED_PROBE", raised.exception.stderr)

    def test_native_sql_access_with_the_reader_credentials_is_not_graph_isolated(self) -> None:
        # Known boundary, recorded rather than hidden: graph ACLs are enforced by the SPARQL compiler, and the pinned
        # engine has no native SQL row protection, so the reader's credentials must never reach untrusted clients.
        with harness.VirtuosoTestInstance() as virtuoso:
            virtuoso.provision_query_reader(user="segb_native", password="pw")
            virtuoso.sql(f"SPARQL INSERT DATA {{ GRAPH <{AUDIT}> {{ <urn:it:a> <urn:it:p> 'au' }} }}")
            result = virtuoso._docker([
                "exec", virtuoso.container_name, "isql", "1111", "segb_native", "pw",
                f"exec=select count (*) from DB.DBA.RDF_QUAD where G = iri_to_id('{AUDIT}')",
            ])
            self.assertRegex(result.stdout, re.compile(r"^\s*[1-9][0-9]*\s*$", re.MULTILINE), result.stdout)

    def test_a_shipped_load_routine_called_as_the_reader_cannot_write_a_graph(self) -> None:
        with harness.VirtuosoTestInstance() as virtuoso:
            reader = virtuoso.provision_query_reader(user="segb_load", password="pw")
            target = "urn:it:load-target"
            source = "http://localhost:8890/sparql?query=CONSTRUCT+%7B%3Fs+%3Fp+%3Fo%7D+WHERE+%7B%3Fs+%3Fp+%3Fo%7D"
            response = requests.post(
                virtuoso.endpoint,
                data={"query": f'PREFIX sql: <sql:> SELECT (sql:SPARUL_LOAD_SERVICE_DATA("{source}", "{target}", '
                               f'"{reader["VIRTUOSO_READER_USER"]}", 0, 0, 0, 0) AS ?x) WHERE {{}}'},
                headers={"Accept": "application/sparql-results+json"},
                auth=HTTPDigestAuth(reader["VIRTUOSO_READER_USER"], reader["VIRTUOSO_READER_PASSWORD"]),
                timeout=60,
            )
            self.assertGreaterEqual(response.status_code, 400, response.text)
            self.assertIn("SR619", response.text)
            count = virtuoso.sql(f"select count (*) from DB.DBA.RDF_QUAD where G = iri_to_id('{target}')")
            self.assertRegex(count, re.compile(r"^\s*0\s*$", re.MULTILINE), count)

    def test_the_backend_drops_the_reader_when_privileges_change_after_startup(self) -> None:
        with harness.VirtuosoTestInstance() as virtuoso:
            reader = virtuoso.provision_query_reader(user="segb_late", password="pw")
            env = {
                **virtuoso.environ(), **reader,
                "VIRTUOSO_GRAPH_URI": EVENTS, "VIRTUOSO_AUDIT_GRAPH_URI": AUDIT,
                "VIRTUOSO_READER_POLICY_RECHECK_SECONDS": "0",
            }
            with mock.patch.dict(os.environ, env):
                saved = (VirtuosoModel._instance, VirtuosoModel._session, VirtuosoModel._reader_session)
                VirtuosoModel._instance = VirtuosoModel._session = VirtuosoModel._reader_session = None
                self.addCleanup(lambda: (
                    VirtuosoModel._instance.close_connection(),
                    setattr(VirtuosoModel, "_instance", saved[0]),
                    setattr(VirtuosoModel, "_session", saved[1]),
                    setattr(VirtuosoModel, "_reader_session", saved[2]),
                ))
                model = VirtuosoModel()
                model.connect_to_db(retries=1, delay=0)
                self.assertTrue(model.ping())
                model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")

                virtuoso.sql("create procedure DB.DBA.VSPX_CONTROL_EXISTS () { return 1; }")

                self.assertFalse(model.ping())
                self.assertIsNone(VirtuosoModel._reader_session)
                with self.assertRaisesRegex(RuntimeError, "read-only"):
                    model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")

    def test_federation_needs_a_role_the_reader_does_not_hold(self) -> None:
        # SERVICE runs at the remote endpoint under that endpoint's identity, so the local reader's graph ACLs do
        # not constrain it. Virtuoso only lets an account start it with SPARQL_SELECT_FED (or equivalent grants).
        with harness.VirtuosoTestInstance() as virtuoso:
            reader = virtuoso.provision_query_reader(user="segb_fed_reader", password="pw")
            virtuoso.sql(f"SPARQL INSERT DATA {{ GRAPH <{AUDIT}> {{ <urn:it:a> <urn:it:p> 'au' }} }}")
            virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{AUDIT}', 'SPARQL', 1)")
            query = f"SELECT ?s WHERE {{ SERVICE <http://localhost:8890/sparql> {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }} }}"

            def run() -> requests.Response:
                return requests.post(
                    virtuoso.endpoint,
                    data={"query": query},
                    headers={"Accept": "application/sparql-results+json"},
                    auth=HTTPDigestAuth(reader["VIRTUOSO_READER_USER"], reader["VIRTUOSO_READER_PASSWORD"]),
                    timeout=60,
                )

            denied = run()
            self.assertEqual(denied.status_code, 500, denied.text)
            self.assertRegex(denied.text, "SQ070|SR186")
            self.assertNotIn("urn:it:a", denied.text)

            virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_fed_reader', 'SPARQL_SELECT_FED')")
            leaked = run()  # control: the same query leaks audit through the remote identity
            self.assertEqual(leaked.status_code, 200, leaked.text)
            self.assertIn("urn:it:a", leaked.text)
            drift = virtuoso.sql("select DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT ('segb_fed_reader')")
            self.assertRegex(drift, re.compile(r"^\s*1\s*$", re.MULTILINE), drift)

            virtuoso.provision_query_reader(user="segb_fed_reader", password="pw")
            self.assertEqual(run().status_code, 500)


@unittest.skipUnless(harness.integration_enabled(), "set SEGB_INTEGRATION=1 to run against a real Virtuoso")
class TestNestedRoleIsolationReal(unittest.TestCase):
    def test_an_unexpected_role_nested_in_sparql_select_makes_provisioning_fail(self) -> None:
        # Isolate role mutations: an isql call may fail after changing the catalog.
        with harness.VirtuosoTestInstance() as virtuoso:
            virtuoso.sql("DB.DBA.USER_ROLE_CREATE('segb_it_polluted_select')")

            def role_is_assigned() -> bool:
                result = virtuoso.sql(
                    "select count (*) from DB.DBA.SYS_ROLE_GRANTS G, DB.DBA.SYS_USERS U, DB.DBA.SYS_USERS R "
                    "where G.GI_SUPER = U.U_ID and G.GI_SUB = R.U_ID and G.GI_DIRECT = 1 "
                    "and U.U_NAME = 'SPARQL_SELECT' and R.U_NAME = 'segb_it_polluted_select'"
                )
                return bool(re.search(r"^\s*[1-9][0-9]*\s*$", result, re.MULTILINE))

            if not role_is_assigned():
                try:
                    virtuoso.sql("DB.DBA.USER_GRANT_ROLE('SPARQL_SELECT', 'segb_it_polluted_select')")
                except RuntimeError as error:
                    # Virtuoso 7.2.16 reports U0013 ("already have role ... assigned") while propagating the grant
                    # to roles that inherit SPARQL_SELECT, after the direct grant is already in the catalog.
                    if "U0013" not in str(error) or not role_is_assigned():
                        raise
            self.assertTrue(role_is_assigned(), "control: the unexpected role must be directly assigned")

            with self.assertRaises(harness.ProvisioningError) as raised:
                virtuoso.provision_query_reader(user="segb_nested_reader", password="pw")
            self.assertIn("SEGB2", raised.exception.stderr)


class TestQueryReaderAccountReal(RealApiTestCase):
    roles = ["logger", "auditor", "admin"]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.client.post("/ttl", json={"ttl_content": TTL}).raise_for_status()
        cls.virtuoso.sql(f"SPARQL INSERT DATA {{ GRAPH <{OTHER}> {{ <urn:it:o> <urn:it:p> 'other-graph' }} }}")

    def _as_reader(self, query: str | None = None, update: str | None = None) -> requests.Response:
        auth = HTTPDigestAuth(self.reader["VIRTUOSO_READER_USER"], self.reader["VIRTUOSO_READER_PASSWORD"])
        if update is not None:
            return requests.post(
                self.virtuoso.endpoint,
                data=update.encode("utf-8"),
                headers={"Content-Type": "application/sparql-update"},
                auth=auth,
                timeout=60,
            )
        return requests.post(
            self.virtuoso.endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            auth=auth,
            timeout=60,
        )

    def _counts(self) -> tuple[int, int, int]:
        return self.count(EVENTS), self.count(AUDIT), self.count(OTHER)

    def test_the_backend_holds_two_distinct_sessions(self) -> None:
        self.assertIsNotNone(VirtuosoModel._reader_session)
        self.assertIsNot(VirtuosoModel._reader_session, VirtuosoModel._session)
        self.assertEqual(VirtuosoModel._reader_session.auth.username, self.reader["VIRTUOSO_READER_USER"])
        self.assertEqual(VirtuosoModel._session.auth.username, "dba")

    def test_the_reader_can_select_the_events_graph(self) -> None:
        response = self.client.get("/query", params={"query": "SELECT * WHERE { ?s ?p ?o }"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("reader-visible", response.text)

        direct = self._as_reader(f"SELECT ?o FROM <{EVENTS}> WHERE {{ ?s ?p ?o }}")
        self.assertEqual(direct.status_code, 200, direct.text)
        self.assertIn("reader-visible", direct.text)

    def test_control_the_audit_and_other_graphs_hold_data_for_the_admin(self) -> None:
        self.assertGreater(self.count(AUDIT), 0)
        self.assertGreater(self.count(OTHER), 0)
        self.assertTrue(self.select(ORACLE)[0]["b"]["value"] in {"1", "true"})

    def test_with_the_text_filter_disabled_get_query_still_sees_no_audit_triple(self) -> None:
        with _filter_disabled():
            for name, text in AUDIT_READS.items():
                with self.subTest(name):
                    response = self.client.get("/query", params={"query": text})
                    self.assertEqual(response.status_code, 200, response.text)
                    _audit_free(self, response.text)

    def test_with_the_text_filter_disabled_the_exists_oracle_answers_false(self) -> None:
        with _filter_disabled():
            response = self.client.get("/query", params={"query": ORACLE})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("true", response.text)

    def test_the_reader_account_cannot_read_audit_or_other_graphs_even_without_the_dataset_pin(self) -> None:
        # Without the pin, Virtuoso answers exactly `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }` from its
        # list of graph names, unfiltered; that case is covered below and in the deployment notes.
        reads = {name: text for name, text in AUDIT_READS.items() if name != "graph variable"}
        for name, text in {**reads, "other graph": f"SELECT * FROM <{OTHER}> WHERE {{ ?s ?p ?o }}"}.items():
            with self.subTest(name):
                response = self._as_reader(text)
                self.assertEqual(response.status_code, 200, response.text)
                _audit_free(self, response.text)
                self.assertNotIn("other-graph", response.text)

        oracle = self._as_reader(ORACLE)
        self.assertEqual(oracle.status_code, 200, oracle.text)
        self.assertIn(oracle.json()["results"]["bindings"][0]["b"]["value"], {"0", "false"})

    def test_the_reader_account_gets_no_triple_and_no_count_from_any_graph_but_events(self) -> None:
        rows = self._as_reader("SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g")
        self.assertEqual(rows.status_code, 200, rows.text)
        self.assertEqual({row["g"]["value"] for row in rows.json()["results"]["bindings"]}, {EVENTS})

        triples = self._as_reader("SELECT ?g ?s WHERE { GRAPH ?g { ?s ?p ?o } }")
        self.assertEqual({row["g"]["value"] for row in triples.json()["results"]["bindings"]}, {EVENTS})

    def test_unpinned_graph_names_leak_metadata_while_the_api_dataset_pin_hides_it(self) -> None:
        query = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"
        direct = self._as_reader(query)
        self.assertEqual(direct.status_code, 200, direct.text)
        names = {row["g"]["value"] for row in direct.json()["results"]["bindings"]}
        self.assertTrue({EVENTS, AUDIT, OTHER} <= names, direct.text)
        # This records a limitation of the pinned engine, not permission to retrieve triples from these graphs.
        with _filter_disabled():
            pinned = self.client.get("/query", params={"query": query})
        self.assertEqual(pinned.status_code, 200, pinned.text)
        self.assertIn(EVENTS, pinned.text)
        self.assertNotIn(AUDIT, pinned.text)
        self.assertNotIn(OTHER, pinned.text)

    def test_service_is_rejected_even_when_the_remote_endpoint_can_read_audit(self) -> None:
        # SERVICE runs at the remote endpoint under that endpoint's identity. Give only the anonymous SPARQL
        # identity access on this disposable instance; this does not grant the local reader access to audit.
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{AUDIT}', 'SPARQL', 1)")
        self.addCleanup(self.virtuoso.sql, f"DB.DBA.RDF_GRAPH_USER_PERMS_DEL('{AUDIT}', 'SPARQL')")
        public = requests.get(
            self.virtuoso.endpoint.replace("/sparql-auth", "/sparql"),
            params={"query": f"ASK {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }}"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=60,
        )
        public.raise_for_status()
        self.assertTrue(public.json()["boolean"], "control: the remote identity must be able to read audit")
        query = (
            "SELECT ?s WHERE { SERVICE <http://localhost:8890/sparql> "
            f"{{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }} }}"
        )
        # The endpoint can read audit, but this does not establish that this Virtuoso reader can execute SERVICE.
        # In the pinned image that execution can fail because SPARQL_SINV_2 is not readable by the reader.
        self.assertFalse(self._as_reader(f"ASK {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }}").json()["boolean"])

        response = self.client.get("/query", params={"query": query})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("SERVICE", response.text)

    def test_service_with_text_filter_disabled_has_a_federation_positive_control(self) -> None:
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{AUDIT}', 'SPARQL', 1)")
        self.addCleanup(self.virtuoso.sql, f"DB.DBA.RDF_GRAPH_USER_PERMS_DEL('{AUDIT}', 'SPARQL')")
        query = (
            "SELECT ?s WHERE { SERVICE <http://localhost:8890/sparql> "
            f"{{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }} }}"
        )
        control = requests.post(
            self.virtuoso.endpoint, data={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            auth=HTTPDigestAuth('dba', self.virtuoso.password), timeout=60,
        )
        self.assertEqual(control.status_code, 200, control.text)
        self.assertTrue(control.json()['results']['bindings'], control.text)
        direct = self._as_reader(f"ASK {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }}")
        self.assertEqual(direct.status_code, 200, direct.text)
        self.assertFalse(direct.json()['boolean'])
        with _filter_disabled():
            response = self.client.get('/query', params={'query': query})
        # An error is an observed denial; a successful response must not contain remote audit rows.
        if response.status_code == 200:
            _audit_free(self, response.text)
            graph = Graph().parse(data=response.text, format="turtle")
            self.assertEqual(len(graph), 0, response.text)
        else:
            self.assertGreaterEqual(response.status_code, 400, response.text)

    def test_the_reader_account_cannot_modify_any_graph(self) -> None:
        before = self._counts()

        for graph in (EVENTS, AUDIT, OTHER):
            for name, statement in _updates(graph).items():
                with self.subTest(graph=graph, operation=name):
                    response = self._as_reader(update=statement)
                    self.assertGreaterEqual(response.status_code, 400, response.text)

        self.assertEqual(self._counts(), before)

    def test_with_the_text_filter_disabled_sql_escapes_fail_and_change_nothing(self) -> None:
        before = self._counts()

        with _filter_disabled():
            for name, text in SQL_ESCAPES.items():
                with self.subTest(name):
                    response = self.client.get("/query", params={"query": text})
                    self.assertEqual(response.status_code, 422, response.text)

        self.assertEqual(self._counts(), before)
        roles = self.virtuoso.sql(
            "select R.U_NAME from DB.DBA.SYS_ROLE_GRANTS, DB.DBA.SYS_USERS U, DB.DBA.SYS_USERS R "
            f"where GI_SUPER = U.U_ID and GI_SUB = R.U_ID and U.U_NAME = '{self.reader['VIRTUOSO_READER_USER']}'"
        )
        self.assertNotIn("SPARQL_UPDATE", roles)

    def test_sql_escapes_are_denied_by_the_reader_account_itself(self) -> None:
        before = self._counts()
        for name, text in SQL_ESCAPES.items():
            with self.subTest(name):
                response = self._as_reader(text)
                self.assertGreaterEqual(response.status_code, 400, response.text)
        self.assertEqual(self._counts(), before)

    def test_writes_audit_reads_and_delete_keep_using_the_admin_account(self) -> None:
        inserted = self.client.post("/ttl", json={"ttl_content": TTL.replace("reader1", "reader2")})
        self.assertEqual(inserted.status_code, 201, inserted.text)
        log_id = inserted.json()["log_id"]

        self.assertEqual(self.client.get("/log", params={"log_id": log_id}).status_code, 200)
        self.assertTrue(self.client.get("/history").json())

        audit_before = self.count(AUDIT)
        deleted = self.client.post("/ttl/delete_all", json={})
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.count(EVENTS), 0)
        self.assertGreater(self.count(AUDIT), audit_before)
        # Leave the events graph as the other tests expect it.
        self.client.post("/ttl", json={"ttl_content": TTL}).raise_for_status()


@unittest.skipUnless(harness.integration_enabled(), "set SEGB_INTEGRATION=1 to run against a real Virtuoso")
class TestReaderProvisioningAndFailClosedReal(unittest.TestCase):
    """Provisioning, privilege inheritance and the backend's refusal to fall back to the admin account."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.virtuoso = harness.VirtuosoTestInstance().start()
        cls.addClassCleanup(cls.virtuoso.stop)
        cls.virtuoso.sql(
            f"SPARQL INSERT DATA {{ GRAPH <{EVENTS}> {{ <urn:it:e> <urn:it:p> 'ev' }} "
            f"GRAPH <{AUDIT}> {{ <urn:it:a> <urn:it:p> 'au' }} }}"
        )

    def setUp(self) -> None:
        VirtuosoModel._instance = None
        VirtuosoModel._session = None
        VirtuosoModel._reader_session = None
        self.addCleanup(self._reset_model)

    @staticmethod
    def _reset_model() -> None:
        for session in (VirtuosoModel._session, VirtuosoModel._reader_session):
            if session is not None:
                session.close()
        VirtuosoModel._instance = None
        VirtuosoModel._session = None
        VirtuosoModel._reader_session = None

    def _ask(self, user: str, password: str, query: str) -> bool:
        response = requests.post(
            self.virtuoso.endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            auth=HTTPDigestAuth(user, password),
            timeout=60,
        )
        response.raise_for_status()
        return bool(response.json()["boolean"])

    def _update_status(self, user: str, password: str) -> int:
        return requests.post(
            self.virtuoso.endpoint,
            data=f"INSERT DATA {{ GRAPH <{EVENTS}> {{ <urn:it:w> <urn:it:p> 'w' }} }}".encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            auth=HTTPDigestAuth(user, password),
            timeout=60,
        ).status_code

    def _model(self, **reader_env: str) -> VirtuosoModel:
        env = {**self.virtuoso.environ(), "VIRTUOSO_GRAPH_URI": EVENTS, "VIRTUOSO_AUDIT_GRAPH_URI": AUDIT}
        env.pop("VIRTUOSO_READER_USER", None)
        env.pop("VIRTUOSO_READER_PASSWORD", None)
        env.update(reader_env)
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("VIRTUOSO_READER_USER", "VIRTUOSO_READER_PASSWORD"):
            if key not in reader_env:
                os.environ.pop(key, None)
        return VirtuosoModel()

    # --- provisioning -------------------------------------------------------------------------------------------

    def test_provisioning_is_idempotent_and_rotates_the_password(self) -> None:
        first = self.virtuoso.provision_query_reader(user="segb_rotating", password="first-pw")
        second = self.virtuoso.provision_query_reader(user="segb_rotating", password="second-pw")

        self.assertEqual(first["VIRTUOSO_READER_USER"], second["VIRTUOSO_READER_USER"])
        ask_events = f"ASK {{ GRAPH <{EVENTS}> {{ ?s ?p ?o }} }}"
        self.assertTrue(self._ask("segb_rotating", "second-pw", ask_events))
        with self.assertRaises(requests.HTTPError):
            self._ask("segb_rotating", "first-pw", ask_events)

    def test_provisioning_handles_passwords_with_sql_metacharacters(self) -> None:
        password = "it's a \\ back'slash; -- pw"
        self.virtuoso.provision_query_reader(user="segb_quoted", password=password)

        self.assertTrue(self._ask("segb_quoted", password, f"ASK {{ GRAPH <{EVENTS}> {{ ?s ?p ?o }} }}"))
        self.assertFalse(self._ask("segb_quoted", password, f"ASK {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }}"))

    def test_provisioning_refuses_privileged_or_malformed_account_names(self) -> None:
        for user in ("dba", "DBA", "nobody", "SPARQL", "bad name", "x'; drop", ""):
            with self.subTest(user=user):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.virtuoso.provision_query_reader(user=user, password="pw")

    def test_provisioning_refuses_an_existing_role_name(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            self.virtuoso.provision_query_reader(user="SPARQL_UPDATE", password="pw")

    def test_direct_sql_grants_block_reprovisioning_and_startup_until_explicitly_revoked(self) -> None:
        grants = {
            "table_read": ("SELECT", "DB.DBA.RDF_QUAD"),
            "table_write": ("UPDATE", "DB.DBA.RDF_QUAD"),
            "column_read": ("SELECT (G)", "DB.DBA.RDF_QUAD"),
            "privileged_execute": ("EXECUTE", "DB.DBA.SPARUL_CLEAR"),
            "permissions_execute": ("EXECUTE", "DB.DBA.RDF_GRAPH_USER_PERMS_SET"),
        }
        for suffix, (privilege, target) in grants.items():
            with self.subTest(grant=suffix):
                self._reset_model()
                user = f"segb_sql_{suffix}"
                reader = self.virtuoso.provision_query_reader(user=user, password="original-pw")
                self.virtuoso.sql(f"GRANT {privilege} ON {target} TO {user}")

                with self.assertRaises(subprocess.CalledProcessError) as raised:
                    self.virtuoso.provision_query_reader(user=user, password="replacement-pw")
                self.assertIn("direct SQL grants", raised.exception.stderr)
                self.assertNotIn("replacement-pw", raised.exception.stderr + raised.exception.stdout)
                self.assertTrue(self._ask(user, "original-pw", f"ASK {{ GRAPH <{EVENTS}> {{ ?s ?p ?o }} }}"))

                # The extra grant does not require an update role or unsafe graph permissions. A random graph
                # write probe still fails; startup must independently inspect SQL grants added after provisioning.
                model = self._model(**reader)
                with self.assertRaisesRegex(RuntimeError, "SQL privileges that differ"):
                    model.connect_to_db(retries=1, delay=0)
                self.assertIsNone(VirtuosoModel._reader_session)
                with self.assertRaisesRegex(RuntimeError, "read-only"):
                    model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")

                self.virtuoso.sql(f"REVOKE {privilege} ON {target} FROM {user}")
                self.virtuoso.provision_query_reader(user=user, password="original-pw")
                model.connect_to_db(retries=1, delay=0)
                self.assertIsNotNone(VirtuosoModel._reader_session)

    def _assert_inherited_sql_grant_is_rejected(self, grantee: str, user: str) -> None:
        reader = self.virtuoso.provision_query_reader(user=user, password="pw")
        # A disposable definer-rights procedure makes the SQL privilege observable without granting access to
        # Virtuoso system objects. Its table is not accessible to the reader directly.
        self.virtuoso.sql("create table DB.DBA.SEGB_IT_GRANT_PROBE (N integer)")
        self.addCleanup(self.virtuoso.sql, "drop table DB.DBA.SEGB_IT_GRANT_PROBE")
        self.virtuoso.sql(
            "create procedure DB.DBA.SEGB_IT_GRANT_WRITE () { insert into DB.DBA.SEGB_IT_GRANT_PROBE values (1); }"
        )
        self.addCleanup(self.virtuoso.sql, "drop procedure DB.DBA.SEGB_IT_GRANT_WRITE")
        self.virtuoso.sql(f"GRANT EXECUTE ON DB.DBA.SEGB_IT_GRANT_WRITE TO {grantee}")
        self.addCleanup(self.virtuoso.sql, f"REVOKE EXECUTE ON DB.DBA.SEGB_IT_GRANT_WRITE FROM {grantee}")

        result = self.virtuoso._docker(
            ["exec", self.virtuoso.container_name, "isql", "1111", user, "pw", "exec=DB.DBA.SEGB_IT_GRANT_WRITE()"]
        ).stdout
        self.assertNotIn("*** Error", result, result)
        count = self.virtuoso.sql("select count (*) from DB.DBA.SEGB_IT_GRANT_PROBE")
        self.assertRegex(count, re.compile(r"^\s*1\s*$", re.MULTILINE), count)

        # Both paths must reject an effective grant, including one added after provisioning.
        model = self._model(**reader)
        with self.subTest(check="startup"):
            with self.assertRaises(RuntimeError):
                model.connect_to_db(retries=1, delay=0)
        with self.subTest(check="reprovisioning"):
            with self.assertRaises(subprocess.CalledProcessError):
                self.virtuoso.provision_query_reader(user=user, password="pw")

    def test_sql_grant_to_sparql_select_is_not_safe_for_the_reader(self) -> None:
        self._assert_inherited_sql_grant_is_rejected("SPARQL_SELECT", "segb_role_sql")

    def test_sql_grant_to_public_is_not_safe_for_the_reader(self) -> None:
        self._assert_inherited_sql_grant_is_rejected("PUBLIC", "segb_public_sql")

    def test_inheritance_a_role_carrying_sparql_update_is_stripped_from_the_reader(self) -> None:
        self.virtuoso.provision_query_reader(user="segb_role_reader", password="pw")
        self.virtuoso.sql("DB.DBA.USER_ROLE_CREATE('segb_it_writer_role')")
        self.virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_it_writer_role', 'SPARQL_UPDATE')")
        self.virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_role_reader', 'segb_it_writer_role')")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{EVENTS}', 'segb_role_reader', 3)")
        self.assertLess(self._update_status("segb_role_reader", "pw"), 400, "control: the inherited role must grant writes")
        self.virtuoso.sql(f"SPARQL CLEAR GRAPH <{EVENTS}>")
        self.virtuoso.sql(f"SPARQL INSERT DATA {{ GRAPH <{EVENTS}> {{ <urn:it:e> <urn:it:p> 'ev' }} }}")

        self.virtuoso.provision_query_reader(user="segb_role_reader", password="pw")

        self.assertGreaterEqual(self._update_status("segb_role_reader", "pw"), 400)
        roles = self.virtuoso.sql(
            "select R.U_NAME from DB.DBA.SYS_ROLE_GRANTS, DB.DBA.SYS_USERS U, DB.DBA.SYS_USERS R "
            "where GI_SUPER = U.U_ID and GI_SUB = R.U_ID and U.U_NAME = 'segb_role_reader'"
        )
        self.assertNotIn("SPARQL_UPDATE", roles)
        self.assertNotIn("segb_it_writer_role", roles)

    def test_inheritance_a_grant_to_nobody_on_the_audit_graph_makes_provisioning_fail(self) -> None:
        self.virtuoso.provision_query_reader(user="segb_nobody_reader", password="pw")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{AUDIT}', 'nobody', 1)")
        self.addCleanup(self.virtuoso.sql, f"DB.DBA.RDF_GRAPH_USER_PERMS_DEL('{AUDIT}', 'nobody')")
        ask_audit = f"ASK {{ GRAPH <{AUDIT}> {{ ?s ?p ?o }} }}"
        self.assertTrue(self._ask("segb_nobody_reader", "pw", ask_audit), "control: every user inherits nobody's grant")

        with self.assertRaises(subprocess.CalledProcessError) as raised:
            self.virtuoso.provision_query_reader(user="segb_nobody_reader", password="pw")

        self.assertIn("audit graph", raised.exception.stderr)
        self.assertNotIn("'pw'", raised.exception.stderr + raised.exception.stdout)

    def test_inheritance_a_write_grant_to_nobody_on_the_events_graph_makes_provisioning_fail(self) -> None:
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{EVENTS}', 'nobody', 3)")
        self.addCleanup(self.virtuoso.sql, f"DB.DBA.RDF_GRAPH_USER_PERMS_DEL('{EVENTS}', 'nobody')")

        with self.assertRaises(subprocess.CalledProcessError) as raised:
            self.virtuoso.provision_query_reader(user="segb_nobody_writer", password="pw")

        # Virtuoso itself refuses to give the reader less than nobody holds on that graph.
        self.assertIn(EVENTS, raised.exception.stderr)

    def test_reprovisioning_removes_stale_grants_on_other_graphs(self) -> None:
        user = "segb_stale_reader"
        self.virtuoso.provision_query_reader(user=user, password="pw")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{OTHER}', '{user}', 3)")
        self.virtuoso.sql(f"SPARQL INSERT DATA {{ GRAPH <{OTHER}> {{ <urn:stale> <urn:p> 'secret' }} }}")
        query = f"ASK {{ GRAPH <{OTHER}> {{ ?s ?p ?o }} }}"
        self.assertTrue(self._ask(user, "pw", query), "control: the stale grant exposes the other graph")

        self.virtuoso.provision_query_reader(user=user, password="pw")

        self.assertFalse(self._ask(user, "pw", query))

    # --- the backend fails closed -------------------------------------------------------------------------------

    def test_backend_refuses_to_connect_without_reader_credentials(self) -> None:
        model = self._model()

        with self.assertRaisesRegex(RuntimeError, "VIRTUOSO_READER_USER"):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)
        with self.assertRaises(RuntimeError):
            model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")

    def test_backend_refuses_the_admin_account_as_reader(self) -> None:
        for user in ("dba", "DBA"):
            with self.subTest(user=user):
                VirtuosoModel._instance = None
                model = self._model(VIRTUOSO_READER_USER=user, VIRTUOSO_READER_PASSWORD=self.virtuoso.password)
                with self.assertRaisesRegex(RuntimeError, "read-only"):
                    model.connect_to_db(retries=1, delay=0)
                self.assertIsNone(VirtuosoModel._reader_session)

    def test_backend_refuses_a_reader_that_can_write(self) -> None:
        self.virtuoso.sql("DB.DBA.USER_CREATE('segb_it_writer', 'pw')")
        self.virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_it_writer', 'SPARQL_UPDATE')")
        self.virtuoso.sql("DB.DBA.RDF_DEFAULT_USER_PERMS_SET('segb_it_writer', 15)")
        model = self._model(VIRTUOSO_READER_USER="segb_it_writer", VIRTUOSO_READER_PASSWORD="pw")

        with self.assertRaisesRegex(RuntimeError, "can modify"):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_backend_refuses_a_reader_that_can_see_the_audit_graph(self) -> None:
        self.virtuoso.sql("DB.DBA.USER_CREATE('segb_it_peeker', 'pw')")
        self.virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_it_peeker', 'SPARQL_SELECT')")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{AUDIT}', 'segb_it_peeker', 1)")
        model = self._model(VIRTUOSO_READER_USER="segb_it_peeker", VIRTUOSO_READER_PASSWORD="pw")

        with self.assertRaisesRegex(RuntimeError, "audit graph"):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_backend_does_not_fall_back_when_the_reader_password_is_wrong(self) -> None:
        self.virtuoso.provision_query_reader(user="segb_wrong_pw", password="right")
        model = self._model(VIRTUOSO_READER_USER="segb_wrong_pw", VIRTUOSO_READER_PASSWORD="wrong")

        with self.assertRaises(ConnectionError):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)
        with self.assertRaises(RuntimeError):
            model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")

    def test_backend_refuses_audit_permission_even_when_the_audit_graph_is_empty(self) -> None:
        empty_audit = "urn:it:empty-audit"
        reader = self.virtuoso.provision_query_reader(user="segb_empty_peeker", password="pw")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{empty_audit}', 'segb_empty_peeker', 1)")
        model = self._model(**reader, VIRTUOSO_AUDIT_GRAPH_URI=empty_audit)

        with self.assertRaisesRegex(RuntimeError, "audit graph"):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_backend_refuses_a_reader_without_events_permission(self) -> None:
        reader = self.virtuoso.provision_query_reader(user="segb_blind_reader", password="pw")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_DEL('{EVENTS}', 'segb_blind_reader')")
        model = self._model(**reader)

        with self.assertRaisesRegex(RuntimeError, "events graph"):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_backend_refuses_an_inherited_update_role_with_only_graph_specific_writes(self) -> None:
        reader = self.virtuoso.provision_query_reader(user="segb_partial_writer", password="pw")
        self.virtuoso.sql("DB.DBA.USER_ROLE_CREATE('segb_it_partial_writer_role')")
        self.virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_it_partial_writer_role', 'SPARQL_UPDATE')")
        self.virtuoso.sql("DB.DBA.USER_GRANT_ROLE('segb_partial_writer', 'segb_it_partial_writer_role')")
        self.virtuoso.sql(f"DB.DBA.RDF_GRAPH_USER_PERMS_SET('{OTHER}', 'segb_partial_writer', 3)")
        model = self._model(**reader)

        with self.assertRaisesRegex(RuntimeError, "can modify"):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_backend_connects_with_a_provisioned_reader(self) -> None:
        reader = self.virtuoso.provision_query_reader(user="segb_good_reader", password="pw")
        model = self._model(**reader)

        model.connect_to_db(retries=1, delay=0)

        self.assertTrue(model.ping())
        self.assertIn("ev", model.run_custom_query(f"SELECT ?o WHERE {{ <urn:it:e> ?p ?o }}"))

    def test_backend_refuses_to_start_without_the_sql_grant_checker(self) -> None:
        reader = self.virtuoso.provision_query_reader(user="segb_missing_checker", password="pw")
        self.addCleanup(self.virtuoso.provision_query_reader, user="segb_missing_checker", password="pw")
        self.virtuoso.sql("drop procedure DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT")
        model = self._model(**reader)

        with self.assertRaises((requests.HTTPError, ConnectionError)):
            model.connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)


if __name__ == "__main__":
    unittest.main()
