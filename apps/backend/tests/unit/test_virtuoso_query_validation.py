import unittest

from models.virtuoso_model import VirtuosoModel


class TestVirtuosoQueryValidation(unittest.TestCase):
    def test_rejects_update_queries_before_execution(self) -> None:
        model = VirtuosoModel()
        with self.assertRaises(PermissionError):
            model.run_custom_query("INSERT DATA { <https://a> <https://b> <https://c> . }")

    def test_rejects_invalid_syntax_before_execution(self) -> None:
        model = VirtuosoModel()
        with self.assertRaises(ValueError):
            model.run_custom_query("SELECT ?s WHERE { ?s ?p ?o ")

    def test_prepares_update_with_default_graph_when_graph_clause_missing(self) -> None:
        model = VirtuosoModel()
        query = "INSERT DATA { <https://example.org/a> <https://example.org/b> <https://example.org/c> . }"
        prepared = model._prepare_update_query(query)

        self.assertIn("DEFINE input:default-graph-uri <", prepared)
        self.assertIn(query, prepared)

    def test_keeps_update_unchanged_when_graph_clause_present(self) -> None:
        model = VirtuosoModel()
        query = (
            "INSERT DATA { GRAPH <http://amor-segb/events> "
            "{ <https://example.org/a> <https://example.org/b> <https://example.org/c> . } }"
        )
        prepared = model._prepare_update_query(query)

        self.assertEqual(query, prepared)

    def test_validate_query_rejects_unknown_operation_keyword(self) -> None:
        model = VirtuosoModel()
        result = model.validate_query("FOOBAR ?s WHERE { ?s ?p ?o }")

        self.assertFalse(result["valid"])
        self.assertEqual(result["query_kind"], "unknown")


if __name__ == "__main__":
    unittest.main()
