from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from models.virtuoso_model import VirtuosoModel
from utils.audit import AuditContext

DUMP = "@prefix ex: <http://example.org/> .\nex:s ex:p ex:o .\n"
CONTEXT = AuditContext(username="alice", roles=("admin",), origin_ip="10.0.0.1", route="POST /ttl/delete_all")


class TestDeleteAllWritesAuditInTheSameRequest(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()
        self.session.post.return_value = Mock(raise_for_status=Mock())
        before = VirtuosoModel._session
        VirtuosoModel._session = self.session
        self.addCleanup(setattr, VirtuosoModel, "_session", before)
        self.dump_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [f.unlink() for f in self.dump_dir.iterdir()] and None or self.dump_dir.rmdir())
        env = patch.dict(
            "os.environ",
            {"VIRTUOSO_GRAPH_URI": "http://segb/events", "VIRTUOSO_AUDIT_GRAPH_URI": "http://segb/audit",
             "AUDIT_BASE_IRI": "https://example.org/segb/audit/", "VIRTUOSO_PASSWORD": "x",
             "AUDIT_DUMP_DIR": str(self.dump_dir), "AUDIT_INLINE_TTL_MAX_BYTES": "1000"},
        )
        env.start()
        self.addCleanup(env.stop)

    def _delete(self, dump: str = DUMP):
        with patch.object(VirtuosoModel, "get_ttls", return_value=dump):
            return VirtuosoModel().delete_all_triples(audit=CONTEXT)

    def test_one_update_stores_the_dump_then_clears_only_events(self) -> None:
        log_id = self._delete()

        self.assertEqual(self.session.post.call_count, 1)
        update = self.session.post.call_args.kwargs["data"].decode()
        self.assertIn("GRAPH <http://segb/audit>", update)
        self.assertIn(f"https://example.org/segb/audit/entry/{log_id}", update)
        self.assertIn("http://www.gsi.upm.es/ontologies/segb/audit#Deletion", update)
        self.assertIn("CLEAR GRAPH <http://segb/events>", update)
        self.assertNotIn("CLEAR GRAPH <http://segb/audit>", update)
        self.assertNotIn("CLEAR ALL", update.upper())
        self.assertLess(update.index("INSERT DATA"), update.index("CLEAR GRAPH"))

    def test_empty_graph_is_a_no_op_without_entry(self) -> None:
        self.assertIsNone(self._delete(dump="  \n"))
        self.session.post.assert_not_called()

    def test_failed_update_raises(self) -> None:
        self.session.post.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        with self.assertRaises(requests.HTTPError):
            self._delete()
        self.assertEqual(self.session.post.call_count, 1)


BIG = "@prefix ex: <http://example.org/> .\n" + "".join(f"ex:s{i} ex:p {i} .\n" for i in range(200))  # > 1000 bytes


class TestLargeDumpsGoToAFile(TestDeleteAllWritesAuditInTheSameRequest):
    def test_small_dump_stays_inline_and_writes_no_file(self) -> None:
        self._delete()
        self.assertEqual(list(self.dump_dir.iterdir()), [])
        self.assertIn("audit#ttl>", self.session.post.call_args.kwargs["data"].decode())

    def test_large_dump_is_written_to_a_file_and_referenced_with_its_hash(self) -> None:
        log_id = self._delete(dump=BIG)

        (written,) = self.dump_dir.iterdir()
        self.assertEqual(written.name, f"{log_id}.ttl")
        self.assertEqual(written.read_text(encoding="utf-8"), BIG)
        update = self.session.post.call_args.kwargs["data"].decode()
        self.assertIn("audit#ttlFile>", update)
        self.assertIn(hashlib.sha256(BIG.encode()).hexdigest(), update)
        self.assertNotIn("audit#ttl>", update)
        self.assertNotIn("ex:s199", update)  # the dump itself is not in the statement

    def test_failed_update_removes_the_orphan_file(self) -> None:
        self.session.post.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        with self.assertRaises(requests.HTTPError):
            self._delete(dump=BIG)
        self.assertEqual(list(self.dump_dir.iterdir()), [])

    def test_unwritable_dump_dir_fails_before_anything_is_cleared(self) -> None:
        blocker = self.dump_dir / "not-a-dir"
        blocker.write_text("x")
        with patch.dict("os.environ", {"AUDIT_DUMP_DIR": str(blocker)}):
            with self.assertRaises(OSError):
                self._delete(dump=BIG)
        self.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
