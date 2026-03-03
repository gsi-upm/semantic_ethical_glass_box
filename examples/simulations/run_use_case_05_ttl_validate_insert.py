"""Use case 05: validate Turtle, insert into backend, and verify exported KG content."""

from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.simulations.bootstrap import configure_pythonpath

configure_pythonpath()

import argparse
import json
from dataclasses import dataclass

from rdflib import Graph

from examples.simulations.cli_common import add_publish_arguments, add_ttl_output_arguments, write_ttl_output
from examples.simulations.contracts import TtlValidationPayload
from examples.simulations.http_helpers import ApiConfig, RequestsSimulationApiClient, SimulationApiClient
from examples.simulations.run_simulation import (
    PublishConfig,
    build_publish_config_from_args,
    run_basic_simulation,
)


@dataclass(slots=True)
class TTLValidationInsertResult:
    """Artifacts generated for TTL validation/insert workflow."""

    graph: Graph
    ttl_text: str
    invalid_validation: TtlValidationPayload
    valid_validation: TtlValidationPayload
    delete_response: dict[str, object] | None
    insert_response: dict[str, object] | None
    exported_ttl: str | None


def _api_config_from_publish_config(config: PublishConfig) -> ApiConfig:
    return ApiConfig(
        base_url=config.base_url,
        token=config.token,
        timeout_seconds=config.timeout_seconds,
        verify_tls=config.verify_tls,
    )


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


def run_ttl_validate_insert_use_case(
    *,
    user: str | None,
    validate_only: bool,
    delete_before_insert: bool,
    api_client: SimulationApiClient | None = None,
    api_config: ApiConfig | None = None,
) -> TTLValidationInsertResult:
    """Runs use case 05 against `/ttl/validate`, `/ttl`, and `/events`."""
    client = _coerce_api_client(api_client=api_client, api_config=api_config)

    simulation_result = run_basic_simulation()
    ttl = simulation_result.graph.serialize(format="turtle")
    ttl_text = ttl.decode("utf-8") if isinstance(ttl, bytes) else ttl

    invalid_ttl = ttl_text.replace("@prefix", "@prefx", 1)

    invalid_validation = TtlValidationPayload.model_validate(
        client.post_json(
            "/ttl/validate",
            {
                "ttl_content": invalid_ttl,
                "user": user,
            },
        )
    )
    valid_validation = TtlValidationPayload.model_validate(
        client.post_json(
            "/ttl/validate",
            {
                "ttl_content": ttl_text,
                "user": user,
            },
        )
    )

    delete_response: dict[str, object] | None = None
    insert_response: dict[str, object] | None = None
    exported_ttl: str | None = None

    if not validate_only:
        if delete_before_insert:
            delete_response = client.post_json(
                "/ttl/delete_all",
                {
                    "user": user,
                },
            )
        insert_response = client.post_json(
            "/ttl",
            {
                "ttl_content": ttl_text,
                "user": user,
            },
        )
        exported_ttl = client.get_text("/events")

    return TTLValidationInsertResult(
        graph=simulation_result.graph,
        ttl_text=ttl_text,
        invalid_validation=invalid_validation,
        valid_validation=valid_validation,
        delete_response=delete_response,
        insert_response=insert_response,
        exported_ttl=exported_ttl,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run use case 05 (TTL validate + insert), and optionally export Turtle."
    )
    add_ttl_output_arguments(parser)
    add_publish_arguments(parser, include_no_publish=False)
    parser.add_argument("--validate-only", action="store_true", help="Run only /ttl/validate checks.")
    parser.add_argument(
        "--skip-delete-all",
        action="store_true",
        help="Skip delete-all before insertion (default behavior is delete before insert).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_config = build_publish_config_from_args(args)
    if base_config is None:
        raise RuntimeError("Could not build API configuration.")

    api_client = RequestsSimulationApiClient(_api_config_from_publish_config(base_config))
    result = run_ttl_validate_insert_use_case(
        api_client=api_client,
        user=base_config.user,
        validate_only=args.validate_only,
        delete_before_insert=not args.skip_delete_all,
    )

    output_path = write_ttl_output(result.ttl_text, args.ttl_output)
    if output_path is not None:
        print(f"Wrote Turtle to: {output_path}")

    summary = {
        "use_case": "05-ttl-validate-insert",
        "invalid_valid": result.invalid_validation.valid,
        "invalid_syntax_ok": result.invalid_validation.syntax_ok,
        "valid_valid": result.valid_validation.valid,
        "valid_syntax_ok": result.valid_validation.syntax_ok,
        "valid_semantic_ok": result.valid_validation.semantic_ok,
        "validate_only": args.validate_only,
        "inserted": result.insert_response is not None,
        "triples_generated": len(result.graph),
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))

    if result.exported_ttl is not None:
        print("Export preview (first 400 chars):")
        print(result.exported_ttl[:400])

    if not args.no_print_ttl:
        print(result.ttl_text)


if __name__ == "__main__":
    main()
