"""GET /query runs on a separate read-only session and never falls back to the admin one."""

import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

from models.virtuoso_model import VirtuosoModel

EMPTY_RESULT = {"head": {"vars": []}, "results": {"bindings": []}}
ENV = {
    "VIRTUOSO_USER": "dba",
    "VIRTUOSO_PASSWORD": "admin-pw",
    "VIRTUOSO_READER_USER": "segb_reader",
    "VIRTUOSO_READER_PASSWORD": "reader-pw",
    "VIRTUOSO_GRAPH_URI": "http://segb/events",
    "VIRTUOSO_AUDIT_GRAPH_URI": "http://segb/audit",
}


def _session() -> Mock:
    session = Mock()
    session.get.return_value = Mock(raise_for_status=Mock(), text="", json=Mock(return_value=EMPTY_RESULT))
    session.post.return_value = Mock(raise_for_status=Mock(), text="")
    return session


class _ModelState(unittest.TestCase):
    def setUp(self) -> None:
        saved = (VirtuosoModel._instance, VirtuosoModel._session, VirtuosoModel._reader_session)
        self.addCleanup(self._restore, saved)
        VirtuosoModel._instance = None
        VirtuosoModel._session = None
        VirtuosoModel._reader_session = None
        VirtuosoModel._reader_policy_checked_at = time.monotonic()
        self.addCleanup(setattr, VirtuosoModel, "_reader_policy_checked_at", None)
        self.env = patch.dict("os.environ", ENV)
        self.env.start()
        self.addCleanup(self.env.stop)
        # Never write the repository's prefixes.json from a test.
        prefixes = patch.multiple("models.virtuoso_model", save_prefixes=Mock(), load_prefixes=Mock(return_value={}))
        prefixes.start()
        self.addCleanup(prefixes.stop)

    @staticmethod
    def _restore(saved) -> None:
        VirtuosoModel._instance, VirtuosoModel._session, VirtuosoModel._reader_session = saved


class TestReadQueriesUseTheReaderSession(_ModelState):
    def test_read_queries_are_sent_through_the_reader_session_only(self) -> None:
        VirtuosoModel._session, VirtuosoModel._reader_session = admin, reader = _session(), _session()

        VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")

        reader.get.assert_called_once()
        admin.get.assert_not_called()
        admin.post.assert_not_called()

    def test_without_a_reader_session_read_queries_fail_instead_of_using_the_admin_session(self) -> None:
        VirtuosoModel._session = admin = _session()

        with self.assertRaisesRegex(RuntimeError, "read-only"):
            VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")

        admin.get.assert_not_called()

    def test_updates_and_audit_reads_keep_using_the_admin_session(self) -> None:
        VirtuosoModel._session, VirtuosoModel._reader_session = admin, reader = _session(), _session()

        VirtuosoModel().run_custom_query("INSERT DATA { <urn:a> <urn:b> <urn:c> }", allow_updates=True)
        VirtuosoModel().list_audit_entries()

        admin.post.assert_called_once()
        admin.get.assert_called()
        reader.get.assert_not_called()
        reader.post.assert_not_called()

    def test_ping_needs_both_sessions(self) -> None:
        VirtuosoModel._session = _session()
        VirtuosoModel._session.get.return_value = Mock(status_code=200, json=Mock(return_value={"boolean": True}))
        self.assertFalse(VirtuosoModel().ping())

        VirtuosoModel._reader_session = _session()
        VirtuosoModel._reader_session.get.return_value = Mock(status_code=200, json=Mock(return_value={"boolean": True}))
        self.assertTrue(VirtuosoModel().ping())

    def test_close_connection_closes_both_sessions(self) -> None:
        VirtuosoModel._session, VirtuosoModel._reader_session = admin, reader = _session(), _session()

        VirtuosoModel().close_connection()

        admin.close.assert_called_once()
        reader.close.assert_called_once()
        self.assertIsNone(VirtuosoModel._session)
        self.assertIsNone(VirtuosoModel._reader_session)


class TestPolicyIsRecheckedAfterStartup(_ModelState):
    @staticmethod
    def _drift(value: str) -> dict:
        return {"results": {"bindings": [{"sql_policy": {"value": value}}]}}

    def _stale(self) -> tuple[Mock, Mock]:
        VirtuosoModel._session, VirtuosoModel._reader_session = admin, reader = _session(), _session()
        VirtuosoModel._reader_policy_checked_at = time.monotonic() - 3600
        return admin, reader

    def test_an_unchanged_policy_keeps_the_session_and_is_not_rechecked_again_within_the_interval(self) -> None:
        admin, reader = self._stale()
        admin.get.return_value.json.return_value = self._drift("0")

        model = VirtuosoModel()
        model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")
        model.run_custom_query("SELECT * WHERE { ?s ?p ?o }")

        admin.get.assert_called_once()
        self.assertIn("SEGB_QUERY_READER_SQL_POLICY_DRIFT", admin.get.call_args.kwargs["params"]["query"])
        self.assertEqual(reader.get.call_count, 2)

    def test_drift_drops_the_reader_session_and_refuses_the_query(self) -> None:
        admin, reader = self._stale()
        admin.get.return_value.json.return_value = self._drift("1")

        with self.assertRaisesRegex(RuntimeError, "changed after startup"):
            VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")

        reader.get.assert_not_called()
        reader.close.assert_called_once()
        self.assertIsNone(VirtuosoModel._reader_session)
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")

    def test_an_unverifiable_check_refuses_the_query_without_using_the_reader(self) -> None:
        admin, reader = self._stale()
        admin.get.return_value.json.return_value = {"results": {"bindings": []}}

        with self.assertRaises(ConnectionError):
            VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")

        reader.get.assert_not_called()

    def test_ping_is_not_ready_after_drift(self) -> None:
        admin, _ = self._stale()
        admin.get.return_value.json.side_effect = [self._drift("1")]

        self.assertFalse(VirtuosoModel().ping())

    def test_ping_is_not_ready_when_the_check_cannot_run(self) -> None:
        admin, _ = self._stale()
        admin.get.return_value.json.return_value = {"results": {"bindings": []}}

        self.assertFalse(VirtuosoModel().ping())

    def test_ping_passes_its_timeout_to_the_policy_check(self) -> None:
        admin, _ = self._stale()
        admin.get.return_value.json.return_value = self._drift("0")

        VirtuosoModel().ping(timeout_s=2.5)

        self.assertEqual(admin.get.call_args_list[0].kwargs["timeout"], 2.5)

    def test_a_slow_clean_check_cannot_return_a_session_dropped_by_a_concurrent_drift(self) -> None:
        admin, reader = self._stale()
        entered, release = threading.Event(), threading.Event()
        results = iter([self._drift("0")])

        def slow_clean(*args, **kwargs):
            entered.set()
            release.wait(5)
            return Mock(raise_for_status=Mock(), json=Mock(return_value=next(results)))

        admin.get.side_effect = slow_clean
        outcome: list = []

        def query() -> None:
            try:
                VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")
                outcome.append("ran")
            except Exception as error:  # noqa: BLE001 - the outcome is what is asserted
                outcome.append(type(error).__name__)

        thread = threading.Thread(target=query)
        thread.start()
        self.assertTrue(entered.wait(5))
        # Another path drops the session (as a drift verdict would) while the clean check is still in flight.
        with VirtuosoModel._lock:
            VirtuosoModel._reader_session = None
        release.set()
        thread.join(5)

        self.assertEqual(outcome, ["RuntimeError"])
        reader.get.assert_not_called()


class TestConnectFailsClosed(_ModelState):
    def _checked_sessions(self, sql_policy="0") -> tuple[Mock, Mock]:
        admin, reader = _session(), _session()
        reader.post.return_value = Mock(ok=False, status_code=500, text="SR186: no update role")
        reader.get.return_value.json.return_value = {"boolean": False}
        row = {name: {"value": "0"} for name in ("audit", "update_role", "sponge_role", "dba_role")}
        row["events"] = {"value": "1"}
        if sql_policy is not None:
            row["sql_policy"] = {"value": sql_policy}
        admin.get.return_value.json.return_value = {"results": {"bindings": [row]}}
        return admin, reader

    def test_direct_sql_policy_are_refused_even_with_safe_graph_permissions_and_roles(self) -> None:
        admin, reader = self._checked_sessions("1")
        with patch.object(VirtuosoModel, "_open_session", side_effect=[admin, reader]):
            with self.assertRaisesRegex(RuntimeError, "SQL privileges that differ"):
                VirtuosoModel().connect_to_db(retries=1, delay=0)
        reader.close.assert_called_once()
        self.assertIsNone(VirtuosoModel._reader_session)
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            VirtuosoModel().run_custom_query("SELECT * WHERE { ?s ?p ?o }")
        admin.post.assert_not_called()

    def test_missing_or_malformed_sql_policy_results_fail_closed(self) -> None:
        for value in (None, "unknown", "-1"):
            with self.subTest(value=value):
                admin, reader = self._checked_sessions(value)
                with patch.object(VirtuosoModel, "_open_session", side_effect=[admin, reader]):
                    VirtuosoModel._session = None
                    with self.assertRaisesRegex((RuntimeError, ConnectionError), "SQL privileges"):
                        VirtuosoModel().connect_to_db(retries=1, delay=0)
                reader.close.assert_called_once()
                self.assertIsNone(VirtuosoModel._reader_session)

    def test_a_failed_catalog_check_never_publishes_the_reader(self) -> None:
        admin, reader = self._checked_sessions()
        admin.get.return_value.raise_for_status.side_effect = ConnectionError("catalog unavailable")
        with patch.object(VirtuosoModel, "_open_session", side_effect=[admin, reader]):
            with self.assertRaisesRegex(ConnectionError, "catalog unavailable"):
                VirtuosoModel().connect_to_db(retries=1, delay=0)
        reader.close.assert_called_once()
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_a_reader_is_published_only_after_all_checks_succeed(self) -> None:
        admin, reader = self._checked_sessions()
        with patch.object(VirtuosoModel, "_open_session", side_effect=[admin, reader]):
            VirtuosoModel().connect_to_db(retries=1, delay=0)
        self.assertIs(VirtuosoModel._reader_session, reader)
        query = admin.get.call_args.kwargs["params"]["query"]
        self.assertIn('sql:SEGB_QUERY_READER_SQL_POLICY_DRIFT("segb_reader")', query)

    def test_an_inherited_update_role_is_refused_when_the_random_graph_probe_is_denied(self) -> None:
        admin, reader = _session(), _session()
        reader.post.return_value = Mock(ok=False, status_code=500, text="SR619: no permission on this graph")
        reader.get.return_value.json.return_value = {"boolean": False}
        admin.get.return_value.json.return_value = {
            "results": {"bindings": [{
                "audit": {"value": "0"}, "events": {"value": "1"},
                "update_role": {"value": "1"}, "sponge_role": {"value": "0"}, "dba_role": {"value": "0"},
            }]}
        }
        with patch.object(VirtuosoModel, "_open_session", side_effect=[admin, reader]):
            with self.assertRaisesRegex(RuntimeError, "can modify"):
                VirtuosoModel().connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_permissions_are_checked_even_when_audit_has_no_triples(self) -> None:
        admin, reader = _session(), _session()
        reader.post.return_value = Mock(ok=False, status_code=500, text="SR186: no update role")
        reader.get.return_value.json.return_value = {"boolean": False}
        admin.get.return_value.json.return_value = {
            "results": {"bindings": [{"audit": {"value": "1"}, "events": {"value": "1"}}]}
        }
        with patch.object(VirtuosoModel, "_open_session", side_effect=[admin, reader]):
            with self.assertRaisesRegex(RuntimeError, "audit graph"):
                VirtuosoModel().connect_to_db(retries=1, delay=0)
        self.assertIsNone(VirtuosoModel._reader_session)
        reader.close.assert_called_once()

    def _connect_refused(self, pattern: str, **env: str | None) -> None:
        """``None`` removes the variable."""
        with patch.dict("os.environ", {k: v for k, v in env.items() if v is not None}):
            for key in [k for k, v in env.items() if v is None]:
                os.environ.pop(key, None)
            with patch("models.virtuoso_model.requests.Session") as session_cls:
                with self.assertRaisesRegex(RuntimeError, pattern):
                    VirtuosoModel().connect_to_db(retries=1, delay=0)
        session_cls.assert_not_called()
        self.assertIsNone(VirtuosoModel._session)
        self.assertIsNone(VirtuosoModel._reader_session)

    def test_missing_reader_user_or_password_is_refused_before_any_connection(self) -> None:
        self._connect_refused("VIRTUOSO_READER_USER", VIRTUOSO_READER_USER=None)
        self._connect_refused("VIRTUOSO_READER_PASSWORD", VIRTUOSO_READER_PASSWORD=None)
        self._connect_refused("VIRTUOSO_READER_PASSWORD", VIRTUOSO_READER_PASSWORD="")

    def test_the_admin_account_is_refused_as_reader(self) -> None:
        for user in ("dba", "DBA", "segb_writer"):
            with self.subTest(user=user):
                self._connect_refused("read-only", VIRTUOSO_USER="segb_writer", VIRTUOSO_READER_USER=user)


if __name__ == "__main__":
    unittest.main()
