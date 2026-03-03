import unittest
from unittest.mock import Mock

from models.virtuoso_graph_store import VirtuosoGraphStoreAdapter


class TestVirtuosoGraphStoreAdapter(unittest.TestCase):
    def test_adapter_delegates_all_graph_store_operations(self) -> None:
        client = Mock()
        client.connect_to_db.return_value = "session"
        client.ping.return_value = True
        client.insert_ttl.return_value = "log-id-123"
        client.get_ttls.return_value = "@prefix ex: <https://example.org/> ."
        client.validate_query.return_value = {"valid": True}
        client.run_custom_query.return_value = "@prefix ex: <https://example.org/> ."

        adapter = VirtuosoGraphStoreAdapter(client=client)

        self.assertEqual(adapter.connect_to_db(retries=2, delay=0.5), "session")
        self.assertTrue(adapter.ping(timeout_s=2.5))
        self.assertEqual(adapter.insert_ttl("ttl"), "log-id-123")
        self.assertEqual(adapter.get_ttls(), "@prefix ex: <https://example.org/> .")
        self.assertEqual(adapter.validate_query("SELECT * WHERE {}", allow_updates=False), {"valid": True})
        self.assertEqual(
            adapter.run_custom_query("SELECT ?s WHERE { ?s ?p ?o }", allow_updates=False),
            "@prefix ex: <https://example.org/> .",
        )
        adapter.delete_all_triples()
        adapter.close_connection()

        client.connect_to_db.assert_called_once_with(retries=2, delay=0.5)
        client.ping.assert_called_once_with(timeout_s=2.5)
        client.insert_ttl.assert_called_once_with("ttl")
        client.get_ttls.assert_called_once_with()
        client.validate_query.assert_called_once_with("SELECT * WHERE {}", allow_updates=False)
        client.run_custom_query.assert_called_once_with("SELECT ?s WHERE { ?s ?p ?o }", allow_updates=False)
        client.delete_all_triples.assert_called_once_with()
        client.close_connection.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
