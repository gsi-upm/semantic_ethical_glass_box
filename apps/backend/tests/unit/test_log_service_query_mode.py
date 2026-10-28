from unittest.mock import Mock
import unittest

from services.log_service import LogService


class TestLogServiceQueryMode(unittest.TestCase):
    def test_execute_query_enforces_read_only_mode(self) -> None:
        virtuoso = Mock()
        virtuoso.run_custom_query.return_value = "@prefix ex: <https://example.org/> ."
        service = LogService(virtuoso=virtuoso)

        result = service.execute_query(
            query="SELECT ?s WHERE { ?s ?p ?o } LIMIT 1",
            actor="admin",
            origin_ip="127.0.0.1",
        )

        self.assertIsInstance(result, str)
        virtuoso.run_custom_query.assert_called_once_with(
            "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1",
            allow_updates=False,
        )

    def test_validate_query_enforces_read_only_mode(self) -> None:
        virtuoso = Mock()
        virtuoso.validate_query.return_value = {
            "valid": True,
            "query_kind": "select",
            "allows_update_execution": False,
            "message": "Valid SPARQL query.",
        }
        service = LogService(virtuoso=virtuoso)

        result = service.validate_query(
            query="SELECT ?s WHERE { ?s ?p ?o } LIMIT 1",
            actor="admin",
            origin_ip="127.0.0.1",
        )

        self.assertTrue(result["valid"])
        virtuoso.validate_query.assert_called_once_with(
            "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1",
            allow_updates=False,
        )


if __name__ == "__main__":
    unittest.main()
