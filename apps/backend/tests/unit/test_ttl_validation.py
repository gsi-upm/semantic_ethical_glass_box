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


class TestBlankNodeWarning(unittest.TestCase):
    PREFIX = "@prefix ex: <https://example.org/> .\n"

    def _blank_node_issues(self, body: str):
        result = validate_ttl_content(self.PREFIX + body)
        return result, [issue for issue in result.issues if issue.code == "SEM_BLANK_NODES"]

    def test_anonymous_node_gives_a_warning_and_the_ttl_stays_valid(self) -> None:
        result, issues = self._blank_node_issues("ex:a ex:p [ ex:q 1 ] .")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertTrue(result.valid and result.syntax_ok and result.semantic_ok)

    def test_labelled_blank_node_gives_the_warning(self) -> None:
        _, issues = self._blank_node_issues("_:b0 ex:p ex:o .")
        self.assertEqual(len(issues), 1)

    def test_empty_brackets_give_the_warning(self) -> None:
        _, issues = self._blank_node_issues("ex:a ex:p [] .")
        self.assertEqual(len(issues), 1)

    def test_blank_node_as_subject_or_object_counts_once_per_node(self) -> None:
        _, issues = self._blank_node_issues("_:b0 ex:p _:b1 .\n_:b1 ex:q ex:o .\nex:a ex:p _:b0 .")

        self.assertEqual(len(issues), 1)
        self.assertIn("2 blank nodes", issues[0].message)

    def test_a_collection_counts_as_blank_nodes(self) -> None:
        _, issues = self._blank_node_issues("ex:a ex:list ( 1 2 ) .")
        self.assertEqual(len(issues), 1)

    def test_message_states_the_limitation_and_recommends_uris(self) -> None:
        _, (issue,) = self._blank_node_issues("ex:a ex:p [] .")

        self.assertIn("again", issue.message)
        self.assertIn("URIs", issue.message)

    def test_ttl_without_blank_nodes_gives_no_warning(self) -> None:
        for body in ("ex:a ex:p ex:o .", 'ex:a ex:p "text" .'):
            _, issues = self._blank_node_issues(body)
            self.assertEqual(issues, [], body)
        self.assertFalse([i for i in validate_ttl_content(VALID_TTL).issues if i.code == "SEM_BLANK_NODES"])

    def test_empty_document_stays_an_error_without_the_warning(self) -> None:
        result = validate_ttl_content(self.PREFIX)
        self.assertFalse(result.valid)
        self.assertFalse([i for i in result.issues if i.code == "SEM_BLANK_NODES"])


if __name__ == "__main__":
    unittest.main()
