"""Service-layer ports (abstractions) for backend dependencies."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from utils.shared_context import (
    SharedContextReviewDecisionResponse,
    SharedContextReviewQueueResponse,
    SharedContextReconcileResponse,
    SharedContextResolveRequest,
    SharedContextResolveResponse,
)


@runtime_checkable
class GraphStorePort(Protocol):
    """Abstract graph-store contract used by application services."""

    def connect_to_db(self, retries: int = 10, delay: float = 5.0) -> Any:
        ...

    def close_connection(self) -> None:
        ...

    def ping(self, timeout_s: float = 1.0) -> bool:
        ...

    def insert_ttl(self, ttl_content: str) -> str:
        ...

    def get_ttls(self) -> str:
        ...

    def validate_query(self, query: str, *, allow_updates: bool = False) -> dict[str, Any]:
        ...

    def run_custom_query(self, query: str, *, allow_updates: bool = False) -> str:
        ...

    def delete_all_triples(self) -> None:
        ...


@runtime_checkable
class SharedContextResolverPort(Protocol):
    """Abstract contract for shared-context resolution workflows."""

    def resolve(self, request: SharedContextResolveRequest) -> SharedContextResolveResponse:
        ...

    def reconcile_pending(self) -> SharedContextReconcileResponse:
        ...

    def review_queue(self) -> SharedContextReviewQueueResponse:
        ...

    def accept_review_case(self, case_id: str, *, target_context_uri: str) -> SharedContextReviewDecisionResponse:
        ...

    def reject_review_case(self, case_id: str) -> SharedContextReviewDecisionResponse:
        ...

    def stats(self) -> dict[str, int | str]:
        ...
