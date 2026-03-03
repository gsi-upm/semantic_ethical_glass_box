import unittest

from rdflib import URIRef
from rdflib.namespace import PROV

from examples.simulations.run_use_case_03_shared_context_auto_match import run_shared_context_auto_match_use_case


class FakeApiClient:
    def __init__(self, *, post_responses: list[dict[str, object]]) -> None:
        self._post_responses = list(post_responses)
        self.post_calls: list[tuple[str, dict[str, object]]] = []

    def post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        self.post_calls.append((endpoint, payload))
        if not self._post_responses:
            raise AssertionError("Unexpected POST call without configured response.")
        return self._post_responses.pop(0)

    def get_json(self, endpoint: str, *, params: dict[str, object] | None = None) -> dict[str, object]:
        raise AssertionError(f"Unexpected GET JSON call to {endpoint}")

    def get_text(self, endpoint: str, *, params: dict[str, object] | None = None) -> str:
        raise AssertionError(f"Unexpected GET TEXT call to {endpoint}")


class TestUseCase03SharedContextAutoMatch(unittest.TestCase):
    def test_auto_match_creates_shared_context_links_for_both_robots(self) -> None:
        shared_uri = "https://example.org/shared-events/context_auto_1"
        api_client = FakeApiClient(
            post_responses=[
                {"shared_context_uri": shared_uri, "status": "created", "confidence": 0.91},
                {"shared_context_uri": shared_uri, "status": "matched", "confidence": 0.94},
            ]
        )

        result = run_shared_context_auto_match_use_case(
            api_client=api_client,
            nonce="auto_case",
        )

        self.assertEqual(result.shared_context_uri, shared_uri)
        self.assertEqual(result.first_resolution.status, "created")
        self.assertEqual(result.second_resolution.status, "matched")
        self.assertEqual(len(api_client.post_calls), 2)

        shared_context_uri = URIRef(shared_uri)
        self.assertIn((result.ari_message_uri, PROV.specializationOf, shared_context_uri), result.graph)
        self.assertIn((result.tiago_message_uri, PROV.specializationOf, shared_context_uri), result.graph)


if __name__ == "__main__":
    unittest.main()
