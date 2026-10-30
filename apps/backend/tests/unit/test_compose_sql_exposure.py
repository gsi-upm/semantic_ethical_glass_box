"""The default deployments must not publish Virtuoso's native SQL listener."""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[4]


class ComposeSqlExposureTests(unittest.TestCase):
    def test_virtuoso_sql_port_is_not_published(self) -> None:
        for compose_file in ("docker-compose.yaml", "docker-compose.dev.yml"):
            with self.subTest(compose_file=compose_file):
                service = yaml.safe_load((ROOT / compose_file).read_text())["services"]["segb-virtuoso"]
                self.assertNotEqual(service.get("network_mode"), "host")
                for port in service.get("ports", []):
                    target = str(port["target"]) if isinstance(port, dict) else str(port).split(":")[-1]
                    target = target.split("/")[0]
                    bounds = [int(value) for value in target.split("-")]
                    self.assertFalse(bounds[0] <= 1111 <= bounds[-1], port)
