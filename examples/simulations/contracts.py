"""Typed payload contracts used by simulation workflows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SharedContextResolvePayload(BaseModel):
    shared_context_uri: str
    status: Literal["matched", "created", "ambiguous"]
    confidence: float
    resolver_version: str | None = None
    candidate_count: int | None = None
    matched_candidate_uri: str | None = None
    close_candidates: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class SharedContextReviewCandidatePayload(BaseModel):
    context_uri: str
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class SharedContextReviewCasePayload(BaseModel):
    case_id: str
    source_context_uri: str
    candidates: list[SharedContextReviewCandidatePayload] = Field(default_factory=list)
    status: Literal["pending", "accepted", "rejected"] | str
    created_at: str | None = None
    decided_at: str | None = None
    selected_context_uri: str | None = None


class SharedContextReviewQueuePayload(BaseModel):
    resolver_version: str | None = None
    unresolved_count: int | None = None
    pending_count: int = 0
    pending_cases: list[SharedContextReviewCasePayload] = Field(default_factory=list)
    unresolved_contexts: list[dict[str, object]] = Field(default_factory=list)
    contexts: list[dict[str, object]] = Field(default_factory=list)


class SharedContextReconcilePayload(BaseModel):
    scanned_ambiguous: int
    merged_count: int
    mappings: dict[str, str] = Field(default_factory=dict)
    resolver_version: str | None = None
    pending_cases: int | None = None


class SharedContextReviewDecisionPayload(BaseModel):
    case_id: str
    status: Literal["accepted", "rejected"] | str
    source_context_uri: str
    selected_context_uri: str | None = None
    resulting_context_uri: str | None = None
    resolver_version: str | None = None


class SharedContextStatsPayload(BaseModel):
    resolver_version: str | None = None
    active_contexts: int = 0
    ambiguous_contexts: int = 0
    merged_contexts: int = 0
    aliases: int = 0


class TtlValidationPayload(BaseModel):
    valid: bool
    syntax_ok: bool
    semantic_ok: bool
    triple_count: int
    issues: list[dict[str, object]] = Field(default_factory=list)
