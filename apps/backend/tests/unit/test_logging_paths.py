import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import logging as logging_utils
from core.logging import resolve_log_file_path


class TestLoggingPaths(unittest.TestCase):
    def test_resolve_log_file_path_uses_server_log_dir_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"SERVER_LOG_DIR": tmp_dir}, clear=False):
                log_path = resolve_log_file_path("segb.log")

            self.assertEqual(log_path, Path(tmp_dir) / "segb.log")

    def test_resolve_log_file_path_skips_non_writable_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            non_writable = base / "non_writable"
            writable = base / "writable"
            non_writable.mkdir()
            writable.mkdir()
            non_writable.chmod(0o555)
            try:
                with patch.object(logging_utils, "_candidate_logs_dirs", return_value=[non_writable, writable]):
                    log_path = resolve_log_file_path("segb.log")
            finally:
                non_writable.chmod(0o755)

            self.assertEqual(log_path, writable / "segb.log")


if __name__ == "__main__":
    unittest.main()
