from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from models.virtuoso_model import VirtuosoModel

LOG_ID = "6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10"


def _json(bindings: list[dict]) -> Mock:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"results": {"bindings": bindings}}
    return response


class TestAuditReads(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()
        before = VirtuosoModel._session
        VirtuosoModel._session = self.session
        self.addCleanup(setattr, VirtuosoModel, "_session", before)
        env = patch.dict(
            "os.environ",
            {"VIRTUOSO_AUDIT_GRAPH_URI": "http://segb/audit", "AUDIT_BASE_IRI": "https://example.org/segb/audit/",
             "VIRTUOSO_PASSWORD": "x"},
        )
        env.start()
        self.addCleanup(env.stop)

    def _queries(self) -> list[str]:
        return [call.kwargs["params"]["query"] for call in self.session.get.call_args_list]

    def test_history_reads_only_the_audit_graph(self) -> None:
        self.session.get.return_value = _json([])
        self.assertEqual(VirtuosoModel().list_audit_entries(), [])
        for query in self._queries():
            self.assertIn("FROM <http://segb/audit>", query)
            self.assertNotIn("events", query)

    def test_get_entry_rejects_ids_that_are_not_uuids_without_querying(self) -> None:
        for bad in ("", "abc", "../x", LOG_ID + "> } DROP", "<urn:x>", f"{LOG_ID}\n"):
            self.assertIsNone(VirtuosoModel().get_audit_entry(bad), bad)
        self.session.get.assert_not_called()

    def test_get_entry_returns_none_when_unknown(self) -> None:
        self.session.get.return_value = _json([])
        self.assertIsNone(VirtuosoModel().get_audit_entry(LOG_ID))
        self.assertIn(f"<https://example.org/segb/audit/entry/{LOG_ID}>", self._queries()[0])


class TestQueryIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()
        self.session.get.return_value = Mock(
            raise_for_status=Mock(), text="", json=Mock(return_value={"head": {"vars": []}, "results": {"bindings": []}})
        )
        before = VirtuosoModel._session
        VirtuosoModel._session = self.session
        self.addCleanup(setattr, VirtuosoModel, "_session", before)
        env = patch.dict(
            "os.environ",
            {"VIRTUOSO_GRAPH_URI": "http://segb/events", "VIRTUOSO_AUDIT_GRAPH_URI": "http://segb/audit",
             "VIRTUOSO_PASSWORD": "x"},
        )
        env.start()
        self.addCleanup(env.stop)

    def test_read_queries_pin_both_the_default_and_the_named_graphs_to_events(self) -> None:
        VirtuosoModel().run_custom_query("SELECT * { ?s ?p ?o }")

        params = self.session.get.call_args.kwargs["params"]
        self.assertEqual(params["default-graph-uri"], "http://segb/events")
        self.assertEqual(params["named-graph-uri"], "http://segb/events")

    def test_a_query_that_reaches_the_audit_graph_is_invalid_and_never_sent(self) -> None:
        query = "SELECT * { GRAPH <http://segb/audit> { ?s ?p ?o } }"

        result = VirtuosoModel().validate_query(query)
        self.assertFalse(result["valid"])
        self.assertIn("http://segb/audit", result["message"])
        with self.assertRaises(ValueError):
            VirtuosoModel().run_custom_query(query)
        self.session.get.assert_not_called()

    def test_queries_over_events_stay_valid(self) -> None:
        for query in ("SELECT * { ?s ?p ?o }", "SELECT * FROM <http://segb/events> { ?s ?p ?o }"):
            self.assertTrue(VirtuosoModel().validate_query(query)["valid"], query)


if __name__ == "__main__":
    unittest.main()
