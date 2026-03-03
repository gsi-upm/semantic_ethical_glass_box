import unittest

from services.ttl_validation import validate_ttl_content


VALID_TTL = """
@prefix ex: <https://example.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix onyx: <http://www.gsi.upm.es/ontologies/onyx/ns#> .
@prefix emoml: <http://www.gsi.upm.es/ontologies/onyx/vocabularies/emotionml/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:activity_1 a prov:Activity ;
  prov:wasAssociatedWith ex:robot_ari ;
  prov:startedAtTime "2026-02-24T10:00:00Z"^^xsd:dateTime .

ex:emotion_1 a onyx:Emotion ;
  onyx:hasEmotionCategory emoml:big6_happiness ;
  onyx:hasEmotionIntensity "0.74"^^xsd:double .
"""


class TestTtlValidation(unittest.TestCase):
    def test_reports_syntax_error(self) -> None:
        invalid_ttl = "@prefix ex: <https://example.org/> ex:activity_1 a <https://example.org/Activity> ."
        result = validate_ttl_content(invalid_ttl)

        self.assertFalse(result.valid)
        self.assertFalse(result.syntax_ok)
        self.assertFalse(result.semantic_ok)
        self.assertEqual(result.triple_count, 0)
        self.assertEqual(result.issues[0].code, "TTL_SYNTAX_ERROR")

    def test_reports_semantic_error_for_intensity_out_of_range(self) -> None:
        ttl = VALID_TTL.replace('"0.74"^^xsd:double', '"1.74"^^xsd:double')
        result = validate_ttl_content(ttl)

        self.assertTrue(result.syntax_ok)
        self.assertFalse(result.valid)
        self.assertFalse(result.semantic_ok)
        codes = {issue.code for issue in result.issues}
        self.assertIn("SEM_INTENSITY_OUT_OF_RANGE", codes)

    def test_reports_semantic_error_for_wrong_datetime_datatype(self) -> None:
        ttl = VALID_TTL.replace(
            '"2026-02-24T10:00:00Z"^^xsd:dateTime',
            '"2026-02-24T10:00:00Z"',
        )
        result = validate_ttl_content(ttl)

        self.assertTrue(result.syntax_ok)
        self.assertFalse(result.valid)
        codes = {issue.code for issue in result.issues}
        self.assertIn("SEM_DATETIME_WRONG_DATATYPE", codes)

    def test_returns_warning_for_untyped_semantic_subject(self) -> None:
        ttl = """
@prefix ex: <https://example.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .

ex:activity_without_type prov:wasAssociatedWith ex:robot_ari .
"""
        result = validate_ttl_content(ttl)

        self.assertTrue(result.valid)
        self.assertTrue(result.syntax_ok)
        self.assertTrue(result.semantic_ok)
        self.assertEqual(result.triple_count, 1)
        self.assertTrue(any(issue.code == "SEM_SUBJECT_WITHOUT_TYPE" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
