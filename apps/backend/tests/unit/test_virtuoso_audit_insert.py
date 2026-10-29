from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from models.virtuoso_model import VirtuosoModel
from utils.audit import AuditContext

TTL = "@prefix ex: <http://example.org/> .\nex:s ex:p ex:o .\n"
CONTEXT = AuditContext(username="alice", roles=("logger",), origin_ip="10.0.0.1", route="POST /ttl")


class TestInsertWritesAuditInTheSameRequest(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()
        self.session.post.return_value = Mock(raise_for_status=Mock())
        self._session_before = VirtuosoModel._session
        VirtuosoModel._session = self.session
        patcher = patch.multiple("models.virtuoso_model", save_prefixes=Mock(), load_prefixes=Mock(return_value={}))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, VirtuosoModel, "_session", self._session_before)
        self.env = patch.dict(
            "os.environ",
            {"VIRTUOSO_GRAPH_URI": "http://segb/events", "VIRTUOSO_AUDIT_GRAPH_URI": "http://segb/audit",
             "AUDIT_BASE_IRI": "https://example.org/segb/audit/", "VIRTUOSO_PASSWORD": "x"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_one_update_writes_events_and_audit_and_returns_the_log_id(self) -> None:
        log_id = VirtuosoModel().insert_ttl(TTL, audit=CONTEXT)

        self.assertEqual(self.session.post.call_count, 1)
        update = self.session.post.call_args.kwargs["data"].decode()
        self.assertIn("GRAPH <http://segb/events>", update)
        self.assertIn("GRAPH <http://segb/audit>", update)
        self.assertIn(f"https://example.org/segb/audit/entry/{log_id}", update)
        self.assertIn("http://www.gsi.upm.es/ontologies/segb/audit#Insertion", update)

    def test_failed_update_raises_and_nothing_else_is_attempted(self) -> None:
        self.session.post.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        with self.assertRaises(requests.HTTPError):
            VirtuosoModel().insert_ttl(TTL, audit=CONTEXT)
        self.assertEqual(self.session.post.call_count, 1)

    def test_invalid_ttl_sends_nothing(self) -> None:
        with self.assertRaises(Exception):
            VirtuosoModel().insert_ttl("this is not turtle", audit=CONTEXT)
        self.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
