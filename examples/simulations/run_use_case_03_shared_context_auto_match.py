"""Use case 03: online shared-context resolver with automatic created/matched flow."""

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
from examples.simulations.contracts import SharedContextResolvePayload
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
class SharedContextAutoMatchResult:
    """Artifacts generated for automatic shared-context matching."""

    graph: Graph
    human_uri: URIRef
    shared_context_uri: str
    first_resolution: SharedContextResolvePayload
    second_resolution: SharedContextResolvePayload
    ari_message_uri: URIRef
    tiago_message_uri: URIRef


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


def run_shared_context_auto_match_use_case(
    *,
    api_client: SimulationApiClient | None = None,
    api_config: ApiConfig | None = None,
    nonce: str | None = None,
) -> SharedContextAutoMatchResult:
    """Runs use case 03 using backend `/shared-context/resolve`."""
    client = _coerce_api_client(api_client=api_client, api_config=api_config)

    run_nonce = (nonce or uuid.uuid4().hex[:8]).lower()
    graph, ari_logger, tiago_logger = build_loggers(shared_event_resolver=None)

    human_uri = ari_logger.register_human(f"maria_auto_{run_nonce}", first_name="Maria")
    observed_at = datetime.now(timezone.utc)
    utterance = f"Could you share one positive science headline? ref={run_nonce}"

    first_payload = {
        "event_kind": "human_utterance",
        "observed_at": observed_at.isoformat(),
        "subject_uri": str(human_uri),
        "modality": "speech",
        "text": utterance,
        "robot_uri": str(ari_logger.robot_uri),
        "observation_uri": str(ari_logger.resource_uri("message", f"ari_auto_observation_{run_nonce}_1")),
    }
    second_payload = {
        "event_kind": "human_utterance",
        "observed_at": (observed_at + timedelta(milliseconds=800)).isoformat(),
        "subject_uri": str(human_uri),
        "modality": "speech",
        "text": utterance.replace("headline?", "headline"),
        "robot_uri": str(tiago_logger.robot_uri),
        "observation_uri": str(tiago_logger.resource_uri("message", f"tiago_auto_observation_{run_nonce}_1")),
    }

    first_resolution = _resolve_shared_context(client, first_payload)
    second_resolution = _resolve_shared_context(client, second_payload)

    shared_context_uri = first_resolution.shared_context_uri
    if shared_context_uri != second_resolution.shared_context_uri:
        raise RuntimeError("Resolver did not return the same shared context URI for both robots.")

    if first_resolution.status not in {"created", "matched"}:
        raise RuntimeError(f"Unexpected first resolver status: {first_resolution.status}")
    if second_resolution.status != "matched":
        raise RuntimeError(f"Expected second resolver status='matched', got: {second_resolution.status}")

    ari_listening = ari_logger.log_activity(
        activity_id=f"ari_auto_listening_{run_nonce}",
        activity_kind=ActivityKind.LISTENING,
        started_at=observed_at,
        ended_at=observed_at + timedelta(seconds=1),
        related_shared_events=[shared_context_uri],
    )
    ari_message = ari_logger.log_message(
        utterance,
        message_id=f"ari_auto_heard_{run_nonce}",
        generated_by_activity=ari_listening,
        message_types=[ORO.InitialMessage],
        language="en",
        sender=human_uri,
    )
    ari_logger.link_observation_to_shared_event(ari_message, shared_context_uri, confidence=0.96)

    tiago_listening = tiago_logger.log_activity(
        activity_id=f"tiago_auto_listening_{run_nonce}",
        activity_kind=ActivityKind.LISTENING,
        started_at=observed_at + timedelta(milliseconds=700),
        ended_at=observed_at + timedelta(seconds=2),
        related_shared_events=[shared_context_uri],
    )
    tiago_message = tiago_logger.log_message(
        utterance,
        message_id=f"tiago_auto_heard_{run_nonce}",
        generated_by_activity=tiago_listening,
        message_types=[ORO.InitialMessage],
        language="en",
        sender=human_uri,
    )
    tiago_logger.link_observation_to_shared_event(tiago_message, shared_context_uri, confidence=0.94)

    return SharedContextAutoMatchResult(
        graph=graph,
        human_uri=human_uri,
        shared_context_uri=shared_context_uri,
        first_resolution=first_resolution,
        second_resolution=second_resolution,
        ari_message_uri=ari_message,
        tiago_message_uri=tiago_message,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run use case 03 (shared-context created/matched), optionally publish to SEGB, and export Turtle."
    )
    add_ttl_output_arguments(parser)
    add_publish_arguments(parser, include_no_publish=True)
    parser.add_argument("--seed", default=None, help="Optional seed/nonce suffix for deterministic run IDs.")
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
    result = run_shared_context_auto_match_use_case(api_client=api_client, nonce=args.seed)

    if not args.no_publish:
        publish_report = publish_graph(result.graph, config=base_config)
        print(json.dumps(publish_report, ensure_ascii=True, indent=2))

    ttl_text = graph_to_ttl_text(result.graph)
    output_path = write_ttl_output(ttl_text, args.ttl_output)
    if output_path is not None:
        print(f"Wrote Turtle to: {output_path}")

    summary = {
        "use_case": "03-shared-context-auto-match",
        "shared_context_uri": result.shared_context_uri,
        "first_status": result.first_resolution.status,
        "second_status": result.second_resolution.status,
        "first_confidence": result.first_resolution.confidence,
        "second_confidence": result.second_resolution.confidence,
        "triples_generated": len(result.graph),
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))

    if not args.no_print_ttl:
        print(ttl_text)


if __name__ == "__main__":
    main()
