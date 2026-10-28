"""Shared-context resolution utilities for cross-robot event linking.

The resolver is deterministic and rule-based (no ML requirement):
- each robot sends one independent observation payload,
- backend scores candidates and returns one canonical shared-context URI,
- admin can review ambiguous candidates and accept/reject integration manually.
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(slots=True)
class SharedContextPolicy:
    """Deterministic scoring and decision policy."""

    namespace: str = "https://gsi.upm.es/segb/shared-events/"
    resolver_version: str = "shared-context-v1-rules"
    time_window_seconds: float = 3.0
    candidate_window_multiplier: float = 2.0
    match_threshold: float = 0.85
    ambiguous_threshold: float = 0.70
    close_score_margin: float = 0.05
    strict_subject_mismatch: bool = True
    strict_modality_mismatch: bool = False
    weight_time: float = 0.30
    weight_text: float = 0.35
    weight_subject: float = 0.20
    weight_modality: float = 0.10


class SharedContextResolveRequest(BaseModel):
    """One independent robot observation that should map to a shared context."""

    event_kind: str
    observed_at: datetime
    subject_uri: str | None = None
    modality: str | None = None
    text: str | None = None
    observation_uri: str | None = None
    robot_uri: str | None = None
    time_window_seconds: float | None = None


class SharedContextResolveResponse(BaseModel):
    """Resolution result for a robot observation."""

    shared_context_uri: str
    status: Literal["matched", "created", "ambiguous"]
    confidence: float
    resolver_version: str
    candidate_count: int
    matched_candidate_uri: str | None = None
    close_candidates: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class SharedContextReconcileResponse(BaseModel):
    """Result report for one review refresh run."""

    scanned_ambiguous: int
    merged_count: int
    mappings: dict[str, str]
    resolver_version: str
    pending_cases: int = 0


class SharedContextReviewAcceptRequest(BaseModel):
    """Admin decision payload to accept one proposed merge."""

    target_context_uri: str


class SharedContextReviewObservation(BaseModel):
    observed_at: datetime
    subject_uri: str | None = None
    modality: str | None = None
    text: str | None = None
    observation_uri: str | None = None
    robot_uri: str | None = None


class SharedContextReviewRecord(BaseModel):
    uri: str
    event_kind: str
    status: Literal["active", "ambiguous", "merged"]
    observed_at: datetime
    subject_uri: str | None = None
    modality: str | None = None
    canonical_text: str = ""
    observation_count: int
    observations: list[SharedContextReviewObservation] = Field(default_factory=list)


class SharedContextReviewCandidate(BaseModel):
    context_uri: str
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class SharedContextReviewCase(BaseModel):
    case_id: str
    source_context_uri: str
    candidates: list[SharedContextReviewCandidate] = Field(default_factory=list)
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime
    decided_at: datetime | None = None
    selected_context_uri: str | None = None


class SharedContextReviewQueueResponse(BaseModel):
    resolver_version: str
    unresolved_count: int
    pending_count: int
    unresolved_contexts: list[SharedContextReviewRecord] = Field(default_factory=list)
    contexts: list[SharedContextReviewRecord] = Field(default_factory=list)
    pending_cases: list[SharedContextReviewCase] = Field(default_factory=list)


class SharedContextReviewDecisionResponse(BaseModel):
    case_id: str
    status: Literal["accepted", "rejected"]
    source_context_uri: str
    selected_context_uri: str | None = None
    resulting_context_uri: str | None = None
    resolver_version: str


@dataclass(slots=True)
class SharedContextObservationRecord:
    observed_at: datetime
    subject_uri: str | None
    modality: str | None
    text: str | None
    observation_uri: str | None
    robot_uri: str | None


@dataclass(slots=True)
class SharedContextRecord:
    """Stored shared-context candidate in resolver memory."""

    uri: str
    event_kind: str
    observed_at: datetime
    subject_uri: str | None
    modality: str | None
    canonical_text: str
    status: Literal["active", "ambiguous", "merged"]
    created_at: datetime
    updated_at: datetime
    observation_count: int = 1
    observations: list[SharedContextObservationRecord] = field(default_factory=list)


@dataclass(slots=True)
class SharedContextReviewCandidateRecord:
    context_uri: str
    score: float
    score_breakdown: dict[str, float]


@dataclass(slots=True)
class SharedContextReviewCaseRecord:
    case_id: str
    source_context_uri: str
    candidates: list[SharedContextReviewCandidateRecord]
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime
    decided_at: datetime | None = None
    selected_context_uri: str | None = None


@dataclass(slots=True)
class ResolveRequestContext:
    observed_at: datetime
    event_kind: str
    subject_uri: str | None
    modality: str | None
    normalized_text: str
    raw_text: str | None
    observation_uri: str | None
    robot_uri: str | None
    time_window_seconds: float


@dataclass(slots=True)
class RankedCandidate:
    score: float
    record: SharedContextRecord
    score_breakdown: dict[str, float]


class SharedContextResolver:
    """In-memory deterministic resolver for canonical shared-context URIs."""

    def __init__(self, *, policy: SharedContextPolicy | None = None) -> None:
        self.policy = policy if policy is not None else SharedContextPolicy()
        self._contexts: dict[str, SharedContextRecord] = {}
        self._aliases: dict[str, str] = {}
        self._review_cases: dict[str, SharedContextReviewCaseRecord] = {}
        self._rejected_pairs: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        lowered = value.lower().strip()
        lowered = re.sub(r"[^\w\s]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    @staticmethod
    def _normalize_atom(value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().lower()
        return text or None

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @staticmethod
    def _pair_key(left: str, right: str) -> tuple[str, str]:
        if left <= right:
            return (left, right)
        return (right, left)

    def _resolve_alias(self, uri: str) -> str:
        current = uri
        while current in self._aliases:
            current = self._aliases[current]
        return current

    def _make_context_uri(self, event_kind: str) -> str:
        base = self.policy.namespace.rstrip("/")
        slug = re.sub(r"[^a-z0-9]+", "_", event_kind.lower().strip()).strip("_") or "event"
        return f"{base}/{slug}_{uuid.uuid4().hex[:16]}"

    def _subject_score(self, a: str | None, b: str | None) -> float:
        if a and b:
            return 1.0 if a == b else 0.0
        return 0.5

    def _modality_score(self, a: str | None, b: str | None) -> float:
        if a and b:
            return 1.0 if a == b else 0.0
        return 0.5

    def _text_score(self, a: str, b: str) -> float | None:
        if not a or not b:
            return None
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        token_union = tokens_a | tokens_b
        token_jaccard = 1.0 if not token_union else len(tokens_a & tokens_b) / len(token_union)
        sequence_similarity = SequenceMatcher(a=a, b=b).ratio()
        return 0.5 * token_jaccard + 0.5 * sequence_similarity

    def _time_score(self, delta_seconds: float, *, window_seconds: float) -> float:
        if delta_seconds >= window_seconds:
            return 0.0
        return max(0.0, 1.0 - (delta_seconds / window_seconds))

    def _score_candidate(
        self,
        *,
        request_observed_at: datetime,
        request_subject_uri: str | None,
        request_modality: str | None,
        request_text: str,
        record: SharedContextRecord,
        window_seconds: float,
    ) -> tuple[float, dict[str, float]]:
        delta_seconds = abs((request_observed_at - record.observed_at).total_seconds())
        score_time = self._time_score(delta_seconds, window_seconds=window_seconds)
        score_text = self._text_score(request_text, record.canonical_text)
        score_subject = self._subject_score(request_subject_uri, record.subject_uri)
        score_modality = self._modality_score(request_modality, record.modality)

        weighted_values: list[tuple[str, float, float]] = [
            ("time", self.policy.weight_time, score_time),
            ("subject", self.policy.weight_subject, score_subject),
            ("modality", self.policy.weight_modality, score_modality),
        ]
        if score_text is not None:
            weighted_values.append(("text", self.policy.weight_text, score_text))

        weight_sum = sum(weight for _, weight, _ in weighted_values)
        if weight_sum <= 0:
            return 0.0, {}

        breakdown: dict[str, float] = {}
        total = 0.0
        for name, weight, score in weighted_values:
            normalized_weight = weight / weight_sum
            breakdown[name] = score
            total += normalized_weight * score
        return total, breakdown

    def _candidate_records(
        self,
        *,
        request_observed_at: datetime,
        request_event_kind: str,
        request_subject_uri: str | None,
        request_modality: str | None,
        request_time_window: float,
    ) -> list[SharedContextRecord]:
        max_candidate_delta = request_time_window * self.policy.candidate_window_multiplier
        candidates: list[SharedContextRecord] = []
        for record in self._contexts.values():
            if record.status == "merged":
                continue
            if record.event_kind != request_event_kind:
                continue
            delta_seconds = abs((request_observed_at - record.observed_at).total_seconds())
            if delta_seconds > max_candidate_delta:
                continue
            if (
                self.policy.strict_subject_mismatch
                and request_subject_uri is not None
                and record.subject_uri is not None
                and request_subject_uri != record.subject_uri
            ):
                continue
            if (
                self.policy.strict_modality_mismatch
                and request_modality is not None
                and record.modality is not None
                and request_modality != record.modality
            ):
                continue
            candidates.append(record)
        return candidates

    def _build_observation_record(
        self,
        *,
        observed_at: datetime,
        subject_uri: str | None,
        modality: str | None,
        text: str | None,
        observation_uri: str | None,
        robot_uri: str | None,
    ) -> SharedContextObservationRecord:
        return SharedContextObservationRecord(
            observed_at=observed_at,
            subject_uri=subject_uri,
            modality=modality,
            text=text,
            observation_uri=observation_uri,
            robot_uri=robot_uri,
        )

    @staticmethod
    def _append_observation(record: SharedContextRecord, observation: SharedContextObservationRecord) -> None:
        record.observations.append(observation)
        record.observation_count += 1

    def _create_record(
        self,
        *,
        uri: str,
        request_observed_at: datetime,
        request_event_kind: str,
        request_subject_uri: str | None,
        request_modality: str | None,
        request_text: str,
        observation: SharedContextObservationRecord,
        status: Literal["active", "ambiguous"],
    ) -> SharedContextRecord:
        now = datetime.now(tz=timezone.utc)
        return SharedContextRecord(
            uri=uri,
            event_kind=request_event_kind,
            observed_at=request_observed_at,
            subject_uri=request_subject_uri,
            modality=request_modality,
            canonical_text=request_text,
            status=status,
            created_at=now,
            updated_at=now,
            observation_count=1,
            observations=[observation],
        )

    def _normalize_resolve_request(self, request: SharedContextResolveRequest) -> ResolveRequestContext:
        observed_at = self._to_utc(request.observed_at)
        event_kind = self._normalize_atom(request.event_kind)
        if event_kind is None:
            raise ValueError("Parameter 'event_kind' must be a non-empty string.")

        return ResolveRequestContext(
            observed_at=observed_at,
            event_kind=event_kind,
            subject_uri=self._normalize_atom(request.subject_uri),
            modality=self._normalize_atom(request.modality),
            normalized_text=self._normalize_text(request.text),
            raw_text=self._normalize_optional_text(request.text),
            observation_uri=self._normalize_optional_text(request.observation_uri),
            robot_uri=self._normalize_optional_text(request.robot_uri),
            time_window_seconds=float(request.time_window_seconds or self.policy.time_window_seconds),
        )

    def _rank_candidates(
        self,
        *,
        request_context: ResolveRequestContext,
        candidates: list[SharedContextRecord],
    ) -> list[RankedCandidate]:
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            score, breakdown = self._score_candidate(
                request_observed_at=request_context.observed_at,
                request_subject_uri=request_context.subject_uri,
                request_modality=request_context.modality,
                request_text=request_context.normalized_text,
                record=candidate,
                window_seconds=request_context.time_window_seconds,
            )
            ranked.append(
                RankedCandidate(
                    score=score,
                    record=candidate,
                    score_breakdown=breakdown,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    def _build_created_or_ambiguous_response(
        self,
        *,
        request_context: ResolveRequestContext,
        observation: SharedContextObservationRecord,
        ranked: list[RankedCandidate],
    ) -> SharedContextResolveResponse:
        best = ranked[0] if ranked else None
        second = ranked[1] if len(ranked) > 1 else None

        if best is not None and best.score >= self.policy.ambiguous_threshold:
            uri = self._make_context_uri(request_context.event_kind)
            record = self._create_record(
                uri=uri,
                request_observed_at=request_context.observed_at,
                request_event_kind=request_context.event_kind,
                request_subject_uri=request_context.subject_uri,
                request_modality=request_context.modality,
                request_text=request_context.normalized_text,
                observation=observation,
                status="ambiguous",
            )
            self._contexts[uri] = record
            close_candidates = [best.record.uri]
            if second is not None:
                close_candidates.append(second.record.uri)
            return SharedContextResolveResponse(
                shared_context_uri=uri,
                status="ambiguous",
                confidence=best.score,
                resolver_version=self.policy.resolver_version,
                candidate_count=len(ranked),
                matched_candidate_uri=best.record.uri,
                close_candidates=close_candidates,
                score_breakdown=best.score_breakdown,
            )

        uri = self._make_context_uri(request_context.event_kind)
        record = self._create_record(
            uri=uri,
            request_observed_at=request_context.observed_at,
            request_event_kind=request_context.event_kind,
            request_subject_uri=request_context.subject_uri,
            request_modality=request_context.modality,
            request_text=request_context.normalized_text,
            observation=observation,
            status="active",
        )
        self._contexts[uri] = record
        return SharedContextResolveResponse(
            shared_context_uri=uri,
            status="created",
            confidence=0.0 if best is None else best.score,
            resolver_version=self.policy.resolver_version,
            candidate_count=len(ranked),
            matched_candidate_uri=None if best is None else best.record.uri,
            score_breakdown={} if best is None else best.score_breakdown,
        )

    def _try_match_existing_context(
        self,
        *,
        request_context: ResolveRequestContext,
        observation: SharedContextObservationRecord,
        ranked: list[RankedCandidate],
    ) -> SharedContextResolveResponse | None:
        if not ranked:
            return None

        best = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        if not self._should_auto_merge(best_score=best.score, second_score=None if second is None else second.score):
            return None

        record = best.record
        self._append_observation(record, observation)
        record.updated_at = datetime.now(tz=timezone.utc)
        record.observed_at = request_context.observed_at
        if record.subject_uri is None and request_context.subject_uri is not None:
            record.subject_uri = request_context.subject_uri
        if record.modality is None and request_context.modality is not None:
            record.modality = request_context.modality
        if not record.canonical_text and request_context.normalized_text:
            record.canonical_text = request_context.normalized_text
        return SharedContextResolveResponse(
            shared_context_uri=self._resolve_alias(record.uri),
            status="matched",
            confidence=best.score,
            resolver_version=self.policy.resolver_version,
            candidate_count=len(ranked),
            matched_candidate_uri=record.uri,
            score_breakdown=best.score_breakdown,
        )

    def _find_pending_case_for_source_locked(self, source_context_uri: str) -> SharedContextReviewCaseRecord | None:
        resolved_source_uri = self._resolve_alias(source_context_uri)
        for case in self._review_cases.values():
            if case.status != "pending":
                continue
            case_source_uri = self._resolve_alias(case.source_context_uri)
            if case_source_uri == resolved_source_uri:
                return case
        return None

    def _should_auto_merge(self, *, best_score: float, second_score: float | None) -> bool:
        if best_score < self.policy.match_threshold:
            return False
        if second_score is None:
            return True
        return (best_score - second_score) >= self.policy.close_score_margin

    def _merge_contexts_locked(self, source_uri: str, target_uri: str) -> tuple[str, str]:
        source_resolved_uri = self._resolve_alias(source_uri)
        target_resolved_uri = self._resolve_alias(target_uri)
        if source_resolved_uri == target_resolved_uri:
            raise ValueError("Source and target context cannot be the same.")

        source_record = self._contexts.get(source_resolved_uri)
        target_record = self._contexts.get(target_resolved_uri)
        if source_record is None or source_record.status != "ambiguous":
            raise ValueError("Source context is no longer pending review.")
        if target_record is None or target_record.status == "merged":
            raise ValueError("Target context is not available.")

        now = datetime.now(tz=timezone.utc)
        self._aliases[source_record.uri] = target_record.uri

        source_record.status = "merged"
        source_record.updated_at = now

        target_record.status = "active"
        target_record.observations.extend(source_record.observations)
        target_record.observation_count += source_record.observation_count
        target_record.updated_at = now
        target_record.observed_at = max(target_record.observed_at, source_record.observed_at)
        if target_record.subject_uri is None and source_record.subject_uri is not None:
            target_record.subject_uri = source_record.subject_uri
        if target_record.modality is None and source_record.modality is not None:
            target_record.modality = source_record.modality
        if not target_record.canonical_text and source_record.canonical_text:
            target_record.canonical_text = source_record.canonical_text

        return source_record.uri, target_record.uri

    def _record_to_view(self, record: SharedContextRecord) -> SharedContextReviewRecord:
        sorted_observations = sorted(record.observations, key=lambda item: item.observed_at, reverse=True)
        return SharedContextReviewRecord(
            uri=record.uri,
            event_kind=record.event_kind,
            status=record.status,
            observed_at=record.observed_at,
            subject_uri=record.subject_uri,
            modality=record.modality,
            canonical_text=record.canonical_text,
            observation_count=record.observation_count,
            observations=[
                SharedContextReviewObservation(
                    observed_at=observation.observed_at,
                    subject_uri=observation.subject_uri,
                    modality=observation.modality,
                    text=observation.text,
                    observation_uri=observation.observation_uri,
                    robot_uri=observation.robot_uri,
                )
                for observation in sorted_observations
            ],
        )

    def _case_to_view(self, case: SharedContextReviewCaseRecord) -> SharedContextReviewCase:
        return SharedContextReviewCase(
            case_id=case.case_id,
            source_context_uri=case.source_context_uri,
            candidates=[
                SharedContextReviewCandidate(
                    context_uri=candidate.context_uri,
                    score=candidate.score,
                    score_breakdown=candidate.score_breakdown,
                )
                for candidate in case.candidates
            ],
            status=case.status,
            created_at=case.created_at,
            decided_at=case.decided_at,
            selected_context_uri=case.selected_context_uri,
        )

    def _mark_obsolete_pending_cases_locked(self, *, now: datetime) -> None:
        for case in self._review_cases.values():
            if case.status != "pending":
                continue
            source_record = self._contexts.get(self._resolve_alias(case.source_context_uri))
            if source_record is None or source_record.status != "ambiguous":
                case.status = "rejected"
                case.decided_at = now
                case.selected_context_uri = None

    def _review_candidates_for_source_locked(
        self,
        *,
        source: SharedContextRecord,
    ) -> list[SharedContextReviewCandidateRecord]:
        candidates: list[SharedContextReviewCandidateRecord] = []
        for candidate in self._candidate_records(
            request_observed_at=source.observed_at,
            request_event_kind=source.event_kind,
            request_subject_uri=source.subject_uri,
            request_modality=source.modality,
            request_time_window=self.policy.time_window_seconds,
        ):
            if candidate.uri == source.uri:
                continue
            if candidate.status not in ("active", "ambiguous"):
                continue
            candidate_pair = self._pair_key(
                self._resolve_alias(source.uri),
                self._resolve_alias(candidate.uri),
            )
            if candidate_pair in self._rejected_pairs:
                continue

            score, score_breakdown = self._score_candidate(
                request_observed_at=source.observed_at,
                request_subject_uri=source.subject_uri,
                request_modality=source.modality,
                request_text=source.canonical_text,
                record=candidate,
                window_seconds=self.policy.time_window_seconds,
            )
            if score < self.policy.ambiguous_threshold:
                continue
            candidates.append(
                SharedContextReviewCandidateRecord(
                    context_uri=candidate.uri,
                    score=round(score, 4),
                    score_breakdown=score_breakdown,
                )
            )
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def _upsert_pending_case_locked(
        self,
        *,
        source_uri: str,
        candidates: list[SharedContextReviewCandidateRecord],
        max_candidates: int,
    ) -> None:
        limited_candidates = candidates[:max_candidates]
        existing_case = self._find_pending_case_for_source_locked(source_uri)
        if existing_case is not None:
            existing_case.candidates = limited_candidates
            return

        case_id = f"review_{uuid.uuid4().hex[:12]}"
        self._review_cases[case_id] = SharedContextReviewCaseRecord(
            case_id=case_id,
            source_context_uri=source_uri,
            candidates=limited_candidates,
            status="pending",
            created_at=datetime.now(tz=timezone.utc),
        )

    def _close_stale_pending_cases_locked(self, *, pending_sources: set[str], now: datetime) -> None:
        for case in self._review_cases.values():
            if case.status != "pending":
                continue
            source_record = self._contexts.get(self._resolve_alias(case.source_context_uri))
            if source_record is None or source_record.status != "ambiguous":
                case.status = "rejected"
                case.decided_at = now
                case.selected_context_uri = None
                continue
            if source_record.uri not in pending_sources:
                case.status = "rejected"
                case.decided_at = now
                case.selected_context_uri = None

    def _refresh_review_cases_locked(self, *, max_candidates: int = 3) -> tuple[int, dict[str, str]]:
        ambiguous_sources = [record for record in self._contexts.values() if record.status == "ambiguous"]
        ambiguous_sources.sort(key=lambda record: (record.created_at, record.uri))
        scanned_ambiguous = len(ambiguous_sources)
        mappings: dict[str, str] = {}
        self._mark_obsolete_pending_cases_locked(now=datetime.now(tz=timezone.utc))

        pending_sources: set[str] = set()

        for source in ambiguous_sources:
            if source.status != "ambiguous":
                continue
            candidates = self._review_candidates_for_source_locked(source=source)
            if not candidates:
                continue

            best = candidates[0]
            second = candidates[1] if len(candidates) > 1 else None

            if self._should_auto_merge(best_score=best.score, second_score=None if second is None else second.score):
                merged_source_uri, merged_target_uri = self._merge_contexts_locked(source.uri, best.context_uri)
                mappings[merged_source_uri] = merged_target_uri

                existing_case = self._find_pending_case_for_source_locked(merged_source_uri)
                if existing_case is not None:
                    existing_case.candidates = candidates[:max_candidates]
                    existing_case.status = "accepted"
                    existing_case.decided_at = datetime.now(tz=timezone.utc)
                    existing_case.selected_context_uri = merged_target_uri
                continue

            pending_sources.add(source.uri)
            self._upsert_pending_case_locked(
                source_uri=source.uri,
                candidates=candidates,
                max_candidates=max_candidates,
            )

        self._close_stale_pending_cases_locked(
            pending_sources=pending_sources,
            now=datetime.now(tz=timezone.utc),
        )

        return scanned_ambiguous, mappings

    def resolve(self, request: SharedContextResolveRequest) -> SharedContextResolveResponse:
        request_context = self._normalize_resolve_request(request)
        observation = self._build_observation_record(
            observed_at=request_context.observed_at,
            subject_uri=request_context.subject_uri,
            modality=request_context.modality,
            text=request_context.raw_text,
            observation_uri=request_context.observation_uri,
            robot_uri=request_context.robot_uri,
        )

        with self._lock:
            candidates = self._candidate_records(
                request_observed_at=request_context.observed_at,
                request_event_kind=request_context.event_kind,
                request_subject_uri=request_context.subject_uri,
                request_modality=request_context.modality,
                request_time_window=request_context.time_window_seconds,
            )
            ranked = self._rank_candidates(
                request_context=request_context,
                candidates=candidates,
            )
            matched_response = self._try_match_existing_context(
                request_context=request_context,
                observation=observation,
                ranked=ranked,
            )
            if matched_response is not None:
                return matched_response
            return self._build_created_or_ambiguous_response(
                request_context=request_context,
                observation=observation,
                ranked=ranked,
            )

    def review_queue(self) -> SharedContextReviewQueueResponse:
        with self._lock:
            self._refresh_review_cases_locked(max_candidates=4)

            unresolved_records = [record for record in self._contexts.values() if record.status == "ambiguous"]
            unresolved_records.sort(key=lambda record: record.updated_at, reverse=True)

            visible_contexts = [record for record in self._contexts.values() if record.status in ("active", "ambiguous")]
            visible_contexts.sort(key=lambda record: record.updated_at, reverse=True)

            pending_cases = [case for case in self._review_cases.values() if case.status == "pending"]
            pending_cases.sort(key=lambda case: case.created_at, reverse=True)

            return SharedContextReviewQueueResponse(
                resolver_version=self.policy.resolver_version,
                unresolved_count=len(unresolved_records),
                pending_count=len(pending_cases),
                unresolved_contexts=[self._record_to_view(record) for record in unresolved_records],
                contexts=[self._record_to_view(record) for record in visible_contexts],
                pending_cases=[self._case_to_view(case) for case in pending_cases],
            )

    def accept_review_case(self, case_id: str, *, target_context_uri: str) -> SharedContextReviewDecisionResponse:
        with self._lock:
            self._refresh_review_cases_locked(max_candidates=4)
            case = self._review_cases.get(case_id)
            if case is None:
                raise ValueError("Review case not found.")
            if case.status != "pending":
                raise ValueError("Review case is not pending.")

            source_uri = self._resolve_alias(case.source_context_uri)
            source_record = self._contexts.get(source_uri)
            if source_record is None or source_record.status != "ambiguous":
                raise ValueError("Source context is no longer pending review.")

            target_uri_raw = target_context_uri.strip()
            if not target_uri_raw:
                raise ValueError("target_context_uri is required.")
            target_uri = self._resolve_alias(target_uri_raw)

            allowed_targets = {self._resolve_alias(candidate.context_uri) for candidate in case.candidates}
            if target_uri not in allowed_targets:
                raise ValueError("Selected target context is not part of this review case.")
            merged_source_uri, merged_target_uri = self._merge_contexts_locked(source_uri, target_uri)

            now = datetime.now(tz=timezone.utc)
            case.status = "accepted"
            case.decided_at = now
            case.selected_context_uri = merged_target_uri

            return SharedContextReviewDecisionResponse(
                case_id=case.case_id,
                status="accepted",
                source_context_uri=merged_source_uri,
                selected_context_uri=merged_target_uri,
                resulting_context_uri=merged_target_uri,
                resolver_version=self.policy.resolver_version,
            )

    def reject_review_case(self, case_id: str) -> SharedContextReviewDecisionResponse:
        with self._lock:
            self._refresh_review_cases_locked(max_candidates=4)
            case = self._review_cases.get(case_id)
            if case is None:
                raise ValueError("Review case not found.")
            if case.status != "pending":
                raise ValueError("Review case is not pending.")

            source_uri = self._resolve_alias(case.source_context_uri)
            for candidate in case.candidates:
                candidate_uri = self._resolve_alias(candidate.context_uri)
                if source_uri == candidate_uri:
                    continue
                self._rejected_pairs.add(self._pair_key(source_uri, candidate_uri))

            now = datetime.now(tz=timezone.utc)
            case.status = "rejected"
            case.decided_at = now
            case.selected_context_uri = None

            return SharedContextReviewDecisionResponse(
                case_id=case.case_id,
                status="rejected",
                source_context_uri=case.source_context_uri,
                selected_context_uri=None,
                resulting_context_uri=None,
                resolver_version=self.policy.resolver_version,
            )

    def reconcile_pending(self) -> SharedContextReconcileResponse:
        """Recomputes unresolved contexts, auto-merges clear matches, and refreshes review cases."""
        with self._lock:
            scanned_ambiguous, mappings = self._refresh_review_cases_locked(max_candidates=4)
            pending_cases = [case for case in self._review_cases.values() if case.status == "pending"]
            return SharedContextReconcileResponse(
                scanned_ambiguous=scanned_ambiguous,
                merged_count=len(mappings),
                mappings=mappings,
                resolver_version=self.policy.resolver_version,
                pending_cases=len(pending_cases),
            )

    def stats(self) -> dict[str, int | str]:
        with self._lock:
            active = sum(1 for record in self._contexts.values() if record.status == "active")
            ambiguous = sum(1 for record in self._contexts.values() if record.status == "ambiguous")
            merged = sum(1 for record in self._contexts.values() if record.status == "merged")
            aliases = len(self._aliases)
        return {
            "resolver_version": self.policy.resolver_version,
            "active_contexts": active,
            "ambiguous_contexts": ambiguous,
            "merged_contexts": merged,
            "aliases": aliases,
        }
