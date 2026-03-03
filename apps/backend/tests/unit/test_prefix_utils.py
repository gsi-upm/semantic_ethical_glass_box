import unittest

from utils.prefix_utils import clean_prefixes_with_numbers


class TestPrefixUtils(unittest.TestCase):
    def test_keeps_numeric_prefixes_when_collapsing_would_collide(self) -> None:
        ttl = """
@prefix ns1: <http://kb.openrobots.org#> .
@prefix ns2: <http://schema.org/> .
@prefix ns3: <http://www.w3.org/ns/mls#> .

ns1:Robot ns2:name "ARI" .
ns3:Model ns2:version "1.0" .
""".strip()

        cleaned = clean_prefixes_with_numbers(ttl)

        self.assertIn("@prefix ns1: <http://kb.openrobots.org#> .", cleaned)
        self.assertIn("@prefix ns2: <http://schema.org/> .", cleaned)
        self.assertIn("@prefix ns3: <http://www.w3.org/ns/mls#> .", cleaned)
        self.assertNotIn("@prefix ns: <http://kb.openrobots.org#> .", cleaned)
        self.assertNotIn("@prefix ns: <http://schema.org/> .", cleaned)
        self.assertNotIn("@prefix ns: <http://www.w3.org/ns/mls#> .", cleaned)

    def test_collapses_suffix_digits_when_safe(self) -> None:
        ttl = """
@prefix ex1: <https://example.org/> .
@prefix ex2: <https://example.org/> .

ex1:alpha ex1:knows ex2:beta .
""".strip()

        cleaned = clean_prefixes_with_numbers(ttl)

        self.assertIn("@prefix ex: <https://example.org/> .", cleaned)
        self.assertNotIn("@prefix ex1:", cleaned)
        self.assertNotIn("@prefix ex2:", cleaned)
        self.assertIn("ex:alpha ex:knows ex:beta .", cleaned)

    def test_does_not_override_existing_base_prefix_for_different_uri(self) -> None:
        ttl = """
@prefix schema: <http://schema.org/> .
@prefix schema1: <https://schema.org/> .

schema:Thing schema:name "A" .
schema1:Thing schema1:name "B" .
""".strip()

        cleaned = clean_prefixes_with_numbers(ttl)

        self.assertIn("@prefix schema: <http://schema.org/> .", cleaned)
        self.assertIn("@prefix schema1: <https://schema.org/> .", cleaned)
        self.assertIn('schema:Thing schema:name "A" .', cleaned)
        self.assertIn('schema1:Thing schema1:name "B" .', cleaned)


if __name__ == "__main__":
    unittest.main()
