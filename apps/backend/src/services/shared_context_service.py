"""Application service around shared-context resolver."""

from __future__ import annotations

from dataclasses import dataclass

from utils.shared_context import (
    SharedContextReviewDecisionResponse,
    SharedContextReviewQueueResponse,
    SharedContextReconcileResponse,
    SharedContextResolveRequest,
    SharedContextResolveResponse,
)
from services.ports import SharedContextResolverPort


@dataclass(slots=True)
class SharedContextService:
    resolver: SharedContextResolverPort

    def resolve(self, payload: SharedContextResolveRequest) -> SharedContextResolveResponse:
        """Resolves one local observation into a canonical shared context."""
        return self.resolver.resolve(payload)

    def reconcile(self) -> SharedContextReconcileResponse:
        """Refreshes unresolved contexts, auto-merges clear matches, and updates review queue."""
        return self.resolver.reconcile_pending()

    def review_queue(self) -> SharedContextReviewQueueResponse:
        return self.resolver.review_queue()

    def accept_review_case(self, *, case_id: str, target_context_uri: str) -> SharedContextReviewDecisionResponse:
        return self.resolver.accept_review_case(case_id, target_context_uri=target_context_uri)

    def reject_review_case(self, *, case_id: str) -> SharedContextReviewDecisionResponse:
        return self.resolver.reject_review_case(case_id)

    def stats(self) -> dict[str, int | str]:
        return self.resolver.stats()
