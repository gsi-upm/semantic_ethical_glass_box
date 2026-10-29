from __future__ import annotations

import os
import unittest
from unittest import mock

from models.virtuoso_model import VirtuosoModel


class TestDefaultNames(unittest.TestCase):
    def test_defaults_do_not_carry_the_amor_prefix(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            model = VirtuosoModel()
        self.assertEqual(model.endpoint, "http://segb-virtuoso:8890/sparql-auth")
        self.assertEqual(model.graph_uri, "http://segb/events")


if __name__ == "__main__":
    unittest.main()
