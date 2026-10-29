"""Opt-in: the blank-node limitation the validator warns about is real. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import unittest

from real_api_support import EVENTS, RealApiTestCase

WITH_BNODE = '@prefix ex: <http://example.org/> .\nex:withBlank a ex:Thing ; ex:p [ ex:q 1 ] .\n'  # 3 triples
WITH_URIS = '@prefix ex: <http://example.org/> .\nex:withUris a ex:Thing ; ex:p ex:other .\n'  # 2 triples


class TestBlankNodesReal(RealApiTestCase):
    def setUp(self) -> None:
        self.update(f"CLEAR GRAPH <{EVENTS}>")

    def _warnings(self, ttl: str) -> list[str]:
        body = self.client.post("/ttl/validate", json={"ttl_content": ttl}).json()
        return [issue["code"] for issue in body["issues"] if issue["severity"] == "warning"]

    def test_uploading_the_same_ttl_twice_duplicates_blank_nodes_but_not_uris(self) -> None:
        self.assertEqual(self.client.post("/ttl", json={"ttl_content": WITH_BNODE}).status_code, 201)
        self.assertEqual(self.count(EVENTS), 3)
        self.assertEqual(self.client.post("/ttl", json={"ttl_content": WITH_BNODE}).status_code, 201)
        # The URI triple is stored once; the two triples that involve the blank node come back as a new node: 3 + 2.
        self.assertEqual(self.count(EVENTS), 5, "blank nodes are expected to be stored again on a re-upload")

        self.update(f"CLEAR GRAPH <{EVENTS}>")
        for _ in range(2):
            self.assertEqual(self.client.post("/ttl", json={"ttl_content": WITH_URIS}).status_code, 201)
        self.assertEqual(self.count(EVENTS), 2, "URI resources must not be duplicated")

    def test_the_validator_warns_exactly_where_the_duplication_happens(self) -> None:
        self.assertIn("SEM_BLANK_NODES", self._warnings(WITH_BNODE))
        self.assertNotIn("SEM_BLANK_NODES", self._warnings(WITH_URIS))


if __name__ == "__main__":
    unittest.main()
