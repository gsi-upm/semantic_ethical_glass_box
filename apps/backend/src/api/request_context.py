"""Request-scoped helpers for actor and logging context handling."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from fastapi import Request

from core.logging import bind_log_context, reset_log_context


def resolve_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "-"


def resolve_actor(*candidates: str | None) -> str:
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "anonymous"


@dataclass(slots=True, frozen=True)
class RequestActor:
    actor: str
    origin_ip: str


def build_request_actor(request: Request, *actor_candidates: str | None) -> RequestActor:
    return RequestActor(
        actor=resolve_actor(*actor_candidates),
        origin_ip=resolve_client_ip(request),
    )


@contextmanager
def request_actor_context(request: Request, request_actor: RequestActor) -> Iterator[RequestActor]:
    request.state.actor = request_actor.actor
    context_tokens = bind_log_context(actor=request_actor.actor, origin_ip=request_actor.origin_ip)
    try:
        yield request_actor
    finally:
        reset_log_context(context_tokens)
