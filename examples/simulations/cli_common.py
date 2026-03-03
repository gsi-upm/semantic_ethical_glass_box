"""Shared CLI and TTL output helpers for simulation entrypoints."""

from __future__ import annotations

import argparse
from pathlib import Path

from rdflib import Graph


def add_ttl_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ttl-output", default=None, help="Optional output path to write generated Turtle.")
    parser.add_argument("--no-print-ttl", action="store_true", help="Do not print generated Turtle to stdout.")


def add_publish_arguments(parser: argparse.ArgumentParser, *, include_no_publish: bool = True) -> None:
    parser.add_argument("--publish-url", default=None, help="SEGB API base URL (env override: SEGB_API_URL).")
    parser.add_argument("--token", default=None, help="Bearer token for API authentication (optional).")
    parser.add_argument("--user", default=None, help="Logical user to include in API payload (optional).")
    parser.add_argument("--queue-file", default=None, help="Optional offline queue file for publication.")
    parser.add_argument("--timeout-seconds", type=float, default=None, help="HTTP timeout in seconds.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    if include_no_publish:
        parser.add_argument("--no-publish", action="store_true", help="Do not publish generated Turtle to SEGB API.")


def graph_to_ttl_text(graph: Graph) -> str:
    ttl = graph.serialize(format="turtle")
    return ttl.decode("utf-8") if isinstance(ttl, bytes) else ttl


def write_ttl_output(ttl_text: str, output_path: str | None) -> Path | None:
    if not output_path:
        return None
    resolved = Path(output_path).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(ttl_text, encoding="utf-8")
    return resolved
