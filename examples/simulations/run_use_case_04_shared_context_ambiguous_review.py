"""Use case 04: online shared-context ambiguous flow and manual review decision."""

from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.simulations.bootstrap import configure_pythonpath

configure_pythonpath()

import argparse
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rdflib import Graph, URIRef

from examples.simulations.cli_common import add_publish_arguments, add_ttl_output_arguments, graph_to_ttl_text, write_ttl_output
from examples.simulations.contracts import (
    SharedContextReconcilePayload,
    SharedContextResolvePayload,
    SharedContextReviewCasePayload,
    SharedContextReviewDecisionPayload,
    SharedContextReviewQueuePayload,
    SharedContextStatsPayload,
)
from examples.simulations.http_helpers import ApiConfig, RequestsSimulationApiClient, SimulationApiClient
from examples.simulations.run_simulation import (
    PublishConfig,
    build_loggers,
    build_publish_config_from_args,
    publish_graph,
)
from semantic_log_generator import ActivityKind
from semantic_log_generator.namespaces import ORO


@dataclass(slots=True)
class SharedContextAmbiguousReviewResult:
    """Artifacts generated for ambiguous shared-context review."""

    graph: Graph
    human_uri: URIRef
    active_context_uri: str
    ambiguous_context_uri: str
    created_resolution: SharedContextResolvePayload
    ambiguous_resolution: SharedContextResolvePayload
    reconcile_before: SharedContextReconcilePayload
    review_queue_before: SharedContextReviewQueuePayload
    review_decision: SharedContextReviewDecisionPayload | None
    review_queue_after: SharedContextReviewQueuePayload
    stats: SharedContextStatsPayload


def _coerce_api_client(
    *,
    api_client: SimulationApiClient | None,
    api_config: ApiConfig | None,
) -> SimulationApiClient:
    if api_client is not None:
        return api_client
    if api_config is None:
        raise ValueError("Either api_client or api_config is required.")
    return RequestsSimulationApiClient(api_config)


def _resolve_shared_context(
    api_client: SimulationApiClient,
    payload: dict[str, object],
) -> SharedContextResolvePayload:
    body = api_client.post_json("/shared-context/resolve", payload)
    return SharedContextResolvePayload.model_validate(body)


def _find_pending_case_for_source(
    review_queue: SharedContextReviewQueuePayload,
    *,
    source_context_uri: str,
) -> SharedContextReviewCasePayload | None:
    for case in review_queue.pending_cases:
        if case.source_context_uri == source_context_uri:
            return case
    return None


def _log_local_robot_observations(
    *,
    ari_logger,
    tiago_logger,
    run_nonce: str,
    observed_at: datetime,
    base_text: str,
    active_context_uri: str,
    ambiguous_context_uri: str,
) -> None:
    ari_activity = ari_logger.log_activity(
        activity_id=f"ari_review_listening_{run_nonce}",
        activity_kind=ActivityKind.LISTENING,
        started_at=observed_at,
        ended_at=observed_at + timedelta(seconds=1),
        related_shared_events=[active_context_uri],
    )
    ari_message = ari_logger.log_message(
        base_text,
        message_id=f"ari_review_heard_{run_nonce}",
        generated_by_activity=ari_activity,
        message_types=[ORO.InitialMessage],
        language="en",
    )
    ari_logger.link_observation_to_shared_event(ari_message, active_context_uri, confidence=0.95)

    tiago_activity = tiago_logger.log_activity(
        activity_id=f"tiago_review_listening_{run_nonce}",
        activity_kind=ActivityKind.LISTENING,
        started_at=observed_at + timedelta(milliseconds=450),
        ended_at=observed_at + timedelta(seconds=1, milliseconds=450),
        related_shared_events=[ambiguous_context_uri],
    )
    tiago_message = tiago_logger.log_message(
        base_text,
        message_id=f"tiago_review_heard_{run_nonce}",
        generated_by_activity=tiago_activity,
        message_types=[ORO.InitialMessage],
        language="en",
    )
    tiago_logger.link_observation_to_shared_event(tiago_message, ambiguous_context_uri, confidence=0.89)


def _apply_manual_decision(
    *,
    api_client: SimulationApiClient,
    pending_case: SharedContextReviewCasePayload,
    decision: str,
    active_context_uri: str,
) -> SharedContextReviewDecisionPayload | None:
    if decision == "none":
        return None

    case_id = pending_case.case_id.strip()
    if not case_id:
        raise RuntimeError("Pending review case does not provide a case_id.")

    if decision == "accept":
        if not pending_case.candidates:
            raise RuntimeError("Pending review case has no candidates to accept.")
        candidate_uris = [candidate.context_uri for candidate in pending_case.candidates]
        target_context_uri = active_context_uri if active_context_uri in candidate_uris else candidate_uris[0]
        decision_payload = api_client.post_json(
            f"/shared-context/review/{case_id}/accept",
            {"target_context_uri": target_context_uri},
        )
        return SharedContextReviewDecisionPayload.model_validate(decision_payload)

    decision_payload = api_client.post_json(
        f"/shared-context/review/{case_id}/reject",
        {},
    )
    return SharedContextReviewDecisionPayload.model_validate(decision_payload)


def run_shared_context_ambiguous_review_use_case(
    *,
    decision: str,
    api_client: SimulationApiClient | None = None,
    api_config: ApiConfig | None = None,
    nonce: str | None = None,
) -> SharedContextAmbiguousReviewResult:
    """Runs use case 04 against backend review endpoints."""
    client = _coerce_api_client(api_client=api_client, api_config=api_config)
    run_nonce = (nonce or uuid.uuid4().hex[:8]).lower()
    graph, ari_logger, tiago_logger = build_loggers(shared_event_resolver=None)

    human_uri = ari_logger.register_human(f"maria_review_{run_nonce}", first_name="Maria")
    observed_at = datetime.now(timezone.utc)
    event_kind = f"human_utterance_review_{run_nonce}"
    base_text = f"Can you book me a table for tonight? ref={run_nonce}"

    created_resolution = _resolve_shared_context(
        client,
        {
            "event_kind": event_kind,
            "observed_at": observed_at.isoformat(),
            "subject_uri": str(human_uri),
            "modality": "speech",
            "text": base_text,
            "robot_uri": str(ari_logger.robot_uri),
            "observation_uri": str(ari_logger.resource_uri("message", f"ari_review_observation_{run_nonce}_1")),
        },
    )
    ambiguous_resolution = _resolve_shared_context(
        client,
        {
            "event_kind": event_kind,
            "observed_at": (observed_at + timedelta(milliseconds=500)).isoformat(),
            "subject_uri": None,
            "modality": "speech",
            "text": base_text,
            "robot_uri": str(tiago_logger.robot_uri),
            "observation_uri": str(tiago_logger.resource_uri("message", f"tiago_review_observation_{run_nonce}_1")),
        },
    )

    if created_resolution.status != "created":
        raise RuntimeError(f"Expected first resolver status='created', got: {created_resolution.status}")
    if ambiguous_resolution.status != "ambiguous":
        raise RuntimeError(f"Expected second resolver status='ambiguous', got: {ambiguous_resolution.status}")

    active_context_uri = created_resolution.shared_context_uri
    ambiguous_context_uri = ambiguous_resolution.shared_context_uri

    _log_local_robot_observations(
        ari_logger=ari_logger,
        tiago_logger=tiago_logger,
        run_nonce=run_nonce,
        observed_at=observed_at,
        base_text=base_text,
        active_context_uri=active_context_uri,
        ambiguous_context_uri=ambiguous_context_uri,
    )

    reconcile_before = SharedContextReconcilePayload.model_validate(
        client.post_json("/shared-context/reconcile", {})
    )
    review_queue_before = SharedContextReviewQueuePayload.model_validate(
        client.get_json("/shared-context/review/pending")
    )

    pending_case = _find_pending_case_for_source(review_queue_before, source_context_uri=ambiguous_context_uri)
    if pending_case is None and decision != "none":
        raise RuntimeError(
            "No pending review case found for the generated ambiguous context. Try running with a different seed."
        )

    review_decision = (
        None
        if pending_case is None
        else _apply_manual_decision(
            api_client=client,
            pending_case=pending_case,
            decision=decision,
            active_context_uri=active_context_uri,
        )
    )

    review_queue_after = SharedContextReviewQueuePayload.model_validate(
        client.get_json("/shared-context/review/pending")
    )
    stats = SharedContextStatsPayload.model_validate(client.get_json("/shared-context/stats"))

    return SharedContextAmbiguousReviewResult(
        graph=graph,
        human_uri=human_uri,
        active_context_uri=active_context_uri,
        ambiguous_context_uri=ambiguous_context_uri,
        created_resolution=created_resolution,
        ambiguous_resolution=ambiguous_resolution,
        reconcile_before=reconcile_before,
        review_queue_before=review_queue_before,
        review_decision=review_decision,
        review_queue_after=review_queue_after,
        stats=stats,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run use case 04 (shared-context ambiguous + review), optionally publish to SEGB, and export Turtle."
    )
    add_ttl_output_arguments(parser)
    add_publish_arguments(parser, include_no_publish=True)
    parser.add_argument("--seed", default=None, help="Optional seed/nonce suffix for deterministic run IDs.")
    parser.add_argument(
        "--decision",
        choices=("accept", "reject", "none"),
        default="accept",
        help="Manual review action to apply to the pending case.",
    )
    return parser.parse_args()


def _api_config_from_publish_config(config: PublishConfig) -> ApiConfig:
    return ApiConfig(
        base_url=config.base_url,
        token=config.token,
        timeout_seconds=config.timeout_seconds,
        verify_tls=config.verify_tls,
    )


def main() -> None:
    args = parse_args()
    base_config = build_publish_config_from_args(args)
    if base_config is None:
        raise RuntimeError("Could not build API configuration.")

    api_client = RequestsSimulationApiClient(_api_config_from_publish_config(base_config))
    result = run_shared_context_ambiguous_review_use_case(
        api_client=api_client,
        decision=args.decision,
        nonce=args.seed,
    )

    if not args.no_publish:
        publish_report = publish_graph(result.graph, config=base_config)
        print(json.dumps(publish_report, ensure_ascii=True, indent=2))

    ttl_text = graph_to_ttl_text(result.graph)
    output_path = write_ttl_output(ttl_text, args.ttl_output)
    if output_path is not None:
        print(f"Wrote Turtle to: {output_path}")

    summary = {
        "use_case": "04-shared-context-ambiguous-review",
        "active_context_uri": result.active_context_uri,
        "ambiguous_context_uri": result.ambiguous_context_uri,
        "created_status": result.created_resolution.status,
        "ambiguous_status": result.ambiguous_resolution.status,
        "manual_decision": None if result.review_decision is None else result.review_decision.status,
        "pending_before": result.review_queue_before.pending_count,
        "pending_after": result.review_queue_after.pending_count,
        "stats": result.stats.model_dump(),
        "triples_generated": len(result.graph),
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))

    if not args.no_print_ttl:
        print(ttl_text)


if __name__ == "__main__":
    main()
