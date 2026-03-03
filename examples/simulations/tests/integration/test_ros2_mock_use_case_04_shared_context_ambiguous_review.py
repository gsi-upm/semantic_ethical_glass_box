import unittest

from rdflib import URIRef
from rdflib.namespace import PROV

from examples.simulations.run_use_case_04_shared_context_ambiguous_review import (
    run_shared_context_ambiguous_review_use_case,
)


class FakeApiClient:
    def __init__(
        self,
        *,
        resolve_responses: list[dict[str, object]],
        reconcile_response: dict[str, object],
        review_queue_before: dict[str, object],
        review_queue_after: dict[str, object],
        decision_response: dict[str, object],
        stats_response: dict[str, object],
    ) -> None:
        self._resolve_responses = list(resolve_responses)
        self._review_queues = [review_queue_before, review_queue_after]
        self._reconcile_response = reconcile_response
        self._decision_response = decision_response
        self._stats_response = stats_response
        self.post_calls: list[str] = []
        self.get_calls: list[str] = []

    def post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        self.post_calls.append(endpoint)
        if endpoint == "/shared-context/resolve":
            if not self._resolve_responses:
                raise AssertionError("Unexpected extra resolve call")
            return self._resolve_responses.pop(0)
        if endpoint == "/shared-context/reconcile":
            return self._reconcile_response
        if endpoint.endswith("/accept") or endpoint.endswith("/reject"):
            return self._decision_response
        raise AssertionError(f"Unexpected POST endpoint: {endpoint}")

    def get_json(self, endpoint: str, *, params: dict[str, object] | None = None) -> dict[str, object]:
        self.get_calls.append(endpoint)
        if endpoint == "/shared-context/review/pending":
            if not self._review_queues:
                raise AssertionError("Unexpected extra review queue call")
            return self._review_queues.pop(0)
        if endpoint == "/shared-context/stats":
            return self._stats_response
        raise AssertionError(f"Unexpected GET endpoint: {endpoint}")

    def get_text(self, endpoint: str, *, params: dict[str, object] | None = None) -> str:
        raise AssertionError(f"Unexpected GET text endpoint: {endpoint}")


class TestUseCase04SharedContextAmbiguousReview(unittest.TestCase):
    def test_ambiguous_review_accept_flow(self) -> None:
        active_uri = "https://example.org/shared-events/context_active_1"
        ambiguous_uri = "https://example.org/shared-events/context_ambiguous_1"

        api_client = FakeApiClient(
            resolve_responses=[
                {"shared_context_uri": active_uri, "status": "created", "confidence": 0.0},
                {"shared_context_uri": ambiguous_uri, "status": "ambiguous", "confidence": 0.79},
            ],
            reconcile_response={
                "scanned_ambiguous": 1,
                "merged_count": 0,
                "mappings": {},
                "resolver_version": "shared-context-v1-rules",
                "pending_cases": 1,
            },
            review_queue_before={
                "resolver_version": "shared-context-v1-rules",
                "unresolved_count": 1,
                "pending_count": 1,
                "pending_cases": [
                    {
                        "case_id": "review_case_1",
                        "source_context_uri": ambiguous_uri,
                        "candidates": [{"context_uri": active_uri, "score": 0.81}],
                        "status": "pending",
                        "created_at": "2026-02-25T10:00:00Z",
                        "decided_at": None,
                        "selected_context_uri": None,
                    }
                ],
                "unresolved_contexts": [],
                "contexts": [],
            },
            review_queue_after={
                "resolver_version": "shared-context-v1-rules",
                "unresolved_count": 0,
                "pending_count": 0,
                "pending_cases": [],
                "unresolved_contexts": [],
                "contexts": [],
            },
            decision_response={
                "case_id": "review_case_1",
                "status": "accepted",
                "source_context_uri": ambiguous_uri,
                "selected_context_uri": active_uri,
                "resulting_context_uri": active_uri,
                "resolver_version": "shared-context-v1-rules",
            },
            stats_response={
                "resolver_version": "shared-context-v1-rules",
                "active_contexts": 1,
                "ambiguous_contexts": 0,
                "merged_contexts": 1,
                "aliases": 1,
            },
        )

        result = run_shared_context_ambiguous_review_use_case(
            api_client=api_client,
            decision="accept",
            nonce="review_case",
        )

        self.assertEqual(result.active_context_uri, active_uri)
        self.assertEqual(result.ambiguous_context_uri, ambiguous_uri)
        self.assertEqual(result.created_resolution.status, "created")
        self.assertEqual(result.ambiguous_resolution.status, "ambiguous")
        self.assertIsNotNone(result.review_decision)
        assert result.review_decision is not None
        self.assertEqual(result.review_decision.status, "accepted")
        self.assertEqual(result.review_queue_before.pending_count, 1)
        self.assertEqual(result.review_queue_after.pending_count, 0)

        self.assertIn((URIRef(result.active_context_uri), None, None), result.graph)
        self.assertIn((URIRef(result.ambiguous_context_uri), None, None), result.graph)

        linked_contexts = set(result.graph.objects(None, PROV.specializationOf))
        self.assertIn(URIRef(active_uri), linked_contexts)
        self.assertIn(URIRef(ambiguous_uri), linked_contexts)


if __name__ == "__main__":
    unittest.main()
