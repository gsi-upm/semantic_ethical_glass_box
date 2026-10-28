from datetime import datetime, timezone
import unittest

from utils.shared_context import (
    SharedContextPolicy,
    SharedContextResolveRequest,
    SharedContextResolver,
)


class TestSharedContextResolver(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = SharedContextResolver(
            policy=SharedContextPolicy(
                namespace="https://example.org/shared-events/",
                time_window_seconds=3.0,
                match_threshold=0.85,
                ambiguous_threshold=0.70,
            )
        )

    def test_same_event_from_two_robots_matches_one_context(self) -> None:
        first = self.resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="Could you show me climate news?",
                robot_uri="https://example.org/robot/ari",
            )
        )
        second = self.resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 1, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="Could you show me climate news",
                robot_uri="https://example.org/robot/tiago",
            )
        )

        self.assertEqual(first.status, "created")
        self.assertEqual(second.status, "matched")
        self.assertEqual(first.shared_context_uri, second.shared_context_uri)
        self.assertGreaterEqual(second.confidence, 0.85)

    def test_strict_subject_mismatch_creates_new_context(self) -> None:
        first = self.resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="hello there",
            )
        )
        second = self.resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, 500000, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/john",
                modality="speech",
                text="hello there",
            )
        )

        self.assertEqual(first.status, "created")
        self.assertEqual(second.status, "created")
        self.assertNotEqual(first.shared_context_uri, second.shared_context_uri)

    def test_reconcile_auto_merges_ambiguous_when_score_surpasses_threshold(self) -> None:
        resolver = SharedContextResolver(
            policy=SharedContextPolicy(
                namespace="https://example.org/shared-events/",
                time_window_seconds=3.0,
                match_threshold=0.85,
                ambiguous_threshold=0.60,
                close_score_margin=0.03,
            )
        )
        base = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="climate change news now",
            )
        )
        self.assertEqual(base.status, "created")

        ambiguous = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, 500000, tzinfo=timezone.utc),
                modality="speech",
                text="climate change news now",
            )
        )
        self.assertEqual(ambiguous.status, "ambiguous")

        refresh_base = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, 550000, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="climate change news now",
            )
        )
        self.assertEqual(refresh_base.status, "matched")

        report = resolver.reconcile_pending()
        self.assertEqual(report.scanned_ambiguous, 1)
        self.assertEqual(report.merged_count, 1)
        self.assertIn(ambiguous.shared_context_uri, report.mappings)
        self.assertEqual(report.mappings[ambiguous.shared_context_uri], base.shared_context_uri)
        self.assertEqual(report.pending_cases, 0)

    def test_review_queue_keeps_pending_only_below_merge_threshold(self) -> None:
        resolver = SharedContextResolver(
            policy=SharedContextPolicy(
                namespace="https://example.org/shared-events/",
                time_window_seconds=3.0,
                match_threshold=0.85,
                ambiguous_threshold=0.60,
                close_score_margin=0.05,
            )
        )
        base = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="book me a table for tonight",
            )
        )
        self.assertEqual(base.status, "created")

        below_threshold = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 2, tzinfo=timezone.utc),
                modality="speech",
                text="book me a table tonight",
            )
        )
        self.assertEqual(below_threshold.status, "ambiguous")

        queue = resolver.review_queue()
        self.assertEqual(queue.pending_count, 1)
        self.assertEqual(queue.unresolved_count, 1)
        self.assertEqual(queue.pending_cases[0].source_context_uri, below_threshold.shared_context_uri)
        self.assertEqual(queue.pending_cases[0].candidates[0].context_uri, base.shared_context_uri)

    def test_accept_review_case_merges_pending_context(self) -> None:
        resolver = SharedContextResolver(
            policy=SharedContextPolicy(
                namespace="https://example.org/shared-events/",
                time_window_seconds=3.0,
                match_threshold=0.85,
                ambiguous_threshold=0.60,
                close_score_margin=0.05,
            )
        )
        base = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                subject_uri="https://example.org/human/maria",
                modality="speech",
                text="book me a table for tonight",
            )
        )
        ambiguous = resolver.resolve(
            SharedContextResolveRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 2, tzinfo=timezone.utc),
                modality="speech",
                text="book me a table tonight",
            )
        )
        self.assertEqual(base.status, "created")
        self.assertEqual(ambiguous.status, "ambiguous")

        queue = resolver.review_queue()
        self.assertEqual(queue.pending_count, 1)
        review_case = queue.pending_cases[0]

        decision = resolver.accept_review_case(
            review_case.case_id,
            target_context_uri=review_case.candidates[0].context_uri,
        )
        self.assertEqual(decision.status, "accepted")
        self.assertEqual(decision.source_context_uri, ambiguous.shared_context_uri)
        self.assertEqual(decision.resulting_context_uri, base.shared_context_uri)

        refreshed = resolver.review_queue()
        self.assertEqual(refreshed.pending_count, 0)
        self.assertEqual(refreshed.unresolved_count, 0)


if __name__ == "__main__":
    unittest.main()
