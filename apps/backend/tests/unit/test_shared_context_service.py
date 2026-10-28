from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from services.shared_context_service import SharedContextService
from utils.shared_context import (
    SharedContextReconcileResponse,
    SharedContextResolveRequest,
    SharedContextResolveResponse,
    SharedContextReviewDecisionResponse,
    SharedContextReviewQueueResponse,
)


class TestSharedContextService(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = Mock()
        self.service = SharedContextService(resolver=self.resolver)

    def test_resolve_delegates_to_resolver(self) -> None:
        payload = SharedContextResolveRequest(
            event_kind="human_utterance",
            observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
            subject_uri="https://example.org/human/maria",
            modality="speech",
            text="hello",
        )
        expected = SharedContextResolveResponse(
            shared_context_uri="https://example.org/shared-events/context_1",
            status="created",
            confidence=0.91,
            resolver_version="shared-context-v1-rules",
            candidate_count=0,
        )
        self.resolver.resolve.return_value = expected

        result = self.service.resolve(payload)

        self.assertEqual(result, expected)
        self.resolver.resolve.assert_called_once_with(payload)

    def test_reconcile_delegates_to_resolver(self) -> None:
        expected = SharedContextReconcileResponse(
            scanned_ambiguous=2,
            merged_count=1,
            mappings={"a": "b"},
            resolver_version="shared-context-v1-rules",
            pending_cases=1,
        )
        self.resolver.reconcile_pending.return_value = expected

        result = self.service.reconcile()

        self.assertEqual(result, expected)
        self.resolver.reconcile_pending.assert_called_once_with()

    def test_review_queue_delegates_to_resolver(self) -> None:
        expected = SharedContextReviewQueueResponse(
            resolver_version="shared-context-v1-rules",
            unresolved_count=0,
            pending_count=0,
        )
        self.resolver.review_queue.return_value = expected

        result = self.service.review_queue()

        self.assertEqual(result, expected)
        self.resolver.review_queue.assert_called_once_with()

    def test_accept_review_case_delegates_target_context(self) -> None:
        expected = SharedContextReviewDecisionResponse(
            case_id="case_1",
            status="accepted",
            source_context_uri="https://example.org/shared-events/source",
            selected_context_uri="https://example.org/shared-events/target",
            resulting_context_uri="https://example.org/shared-events/target",
            resolver_version="shared-context-v1-rules",
        )
        self.resolver.accept_review_case.return_value = expected

        result = self.service.accept_review_case(
            case_id="case_1",
            target_context_uri="https://example.org/shared-events/target",
        )

        self.assertEqual(result, expected)
        self.resolver.accept_review_case.assert_called_once_with(
            "case_1",
            target_context_uri="https://example.org/shared-events/target",
        )

    def test_reject_review_case_delegates_case_id(self) -> None:
        expected = SharedContextReviewDecisionResponse(
            case_id="case_2",
            status="rejected",
            source_context_uri="https://example.org/shared-events/source",
            resolver_version="shared-context-v1-rules",
        )
        self.resolver.reject_review_case.return_value = expected

        result = self.service.reject_review_case(case_id="case_2")

        self.assertEqual(result, expected)
        self.resolver.reject_review_case.assert_called_once_with("case_2")

    def test_stats_delegates_to_resolver(self) -> None:
        expected = {
            "resolver_version": "shared-context-v1-rules",
            "active_contexts": 2,
            "ambiguous_contexts": 1,
            "merged_contexts": 0,
            "aliases": 1,
        }
        self.resolver.stats.return_value = expected

        result = self.service.stats()

        self.assertEqual(result, expected)
        self.resolver.stats.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
