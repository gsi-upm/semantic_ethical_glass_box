"""SEGB's own names must not carry the old ``amor-`` project prefix."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OLD_NAMES = ("amor" + "-segb", "amor" + "_segb")


class TestNaming(unittest.TestCase):
    def test_no_old_segb_names_in_tracked_files(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO, check=True, capture_output=True, text=True
        ).stdout.split("\0")
        offenders = []
        for name in filter(None, tracked):
            path = REPO / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(old in text for old in OLD_NAMES):
                offenders.append(name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
