from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.system_log_service import InvalidLogLevelError, SystemLogService


class TestSystemLogService(unittest.TestCase):
    def test_reads_and_filters_structured_logs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "segb.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-02-20 10:00:01 | INFO | segb.server | rid=req1 actor=admin ip=127.0.0.1 | startup",
                        "2026-02-20 10:00:02 | WARNING | segb.server | rid=req2 actor=admin ip=127.0.0.1 | reconnecting",
                        "2026-02-20 10:00:03 | ERROR | segb.server | rid=req3 actor=admin ip=127.0.0.1 | failed",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            service = SystemLogService(log_path=log_path)
            result = service.read_server_logs(limit=10, level="warning", contains="reconnect")

            self.assertEqual(result["count"], 1)
            self.assertEqual(result["filters"]["level"], "WARNING")
            self.assertEqual(result["entries"][0]["message"], "reconnecting")
            self.assertEqual(result["entries"][0]["request_id"], "req2")
            self.assertEqual(result["entries"][0]["actor"], "admin")

    def test_reads_unstructured_logs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "unstructured.log"
            log_path.write_text(
                "2026-02-20 10:00:04 - segb.server - INFO -> legacy format line\n",
                encoding="utf-8",
            )

            service = SystemLogService(log_path=log_path)
            result = service.read_server_logs(limit=10, level=None, contains=None)

            self.assertEqual(result["count"], 1)
            entry = result["entries"][0]
            self.assertIsNone(entry["level"])
            self.assertEqual(entry["message"], "2026-02-20 10:00:04 - segb.server - INFO -> legacy format line")
            self.assertIsNone(entry["request_id"])
            self.assertIsNone(entry["actor"])

    def test_groups_multiline_traceback_under_structured_entry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "segb.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-02-20 10:00:01 | ERROR | segb.server | rid=req1 actor=admin ip=127.0.0.1 | HTTP POST /ttl -> 500 (111.1 ms)",
                        "Traceback (most recent call last):",
                        "  File \"/app/src/api/app.py\", line 67, in access_log_middleware",
                        "    response = await call_next(request)",
                        "anyio.EndOfStream",
                        "2026-02-20 10:00:02 | INFO | segb.server | rid=req2 actor=admin ip=127.0.0.1 | recovered",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            service = SystemLogService(log_path=log_path)
            result = service.read_server_logs(limit=10, level="error", contains="EndOfStream")

            self.assertEqual(result["count"], 1)
            entry = result["entries"][0]
            self.assertEqual(entry["request_id"], "req1")
            self.assertEqual(entry["level"], "ERROR")
            self.assertIn("Traceback (most recent call last):", entry["message"])
            self.assertIn("anyio.EndOfStream", entry["message"])
            self.assertNotIn("rid=req2", entry["raw"])

    def test_returns_empty_when_file_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "missing.log"
            service = SystemLogService(log_path=missing_path)

            result = service.read_server_logs(limit=5, level=None, contains="error")

            self.assertEqual(result["count"], 0)
            self.assertEqual(result["entries"], [])
            self.assertEqual(result["filters"]["contains"], "error")

    def test_rejects_invalid_level(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "segb.log"
            log_path.write_text("", encoding="utf-8")

            service = SystemLogService(log_path=log_path)
            with self.assertRaises(InvalidLogLevelError):
                service.read_server_logs(limit=10, level="TRACE", contains=None)


if __name__ == "__main__":
    unittest.main()
