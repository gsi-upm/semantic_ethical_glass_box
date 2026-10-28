"""Prefix persistence helpers for TTL ingestion and retrieval."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

PREFIX_FILE = Path(os.getenv("PREFIX_FILE_PATH", "prefixes.json"))


def clean_prefixes_with_numbers(ttl_text: str) -> str:
    """Normalizes suffix digits in prefixes only when it is collision-safe.

    Example:
    - Safe: ``prov1`` -> ``prov`` when ``prov`` is unused.
    - Unsafe: ``ns1``, ``ns2``, ``ns3`` with different URIs stay unchanged.
    """
    prefix_pattern = re.compile(r"^@prefix\s+([a-zA-Z_][a-zA-Z0-9\-_]*):\s+<([^>]+)>\s+\.\s*$")
    declarations: list[tuple[int, str, str]] = []
    lines = ttl_text.splitlines()

    for index, line in enumerate(lines):
        match = prefix_pattern.match(line)
        if not match:
            continue
        declarations.append((index, match.group(1), match.group(2)))

    base_to_uris: dict[str, set[str]] = {}
    for _, prefix, uri in declarations:
        base = re.sub(r"\d+$", "", prefix)
        base_to_uris.setdefault(base, set()).add(uri)

    claimed_targets: dict[str, str] = {}
    replacements: dict[str, str] = {}

    for _, original_prefix, uri in declarations:
        target_prefix = original_prefix
        candidate = re.sub(r"\d+$", "", original_prefix)
        if candidate and candidate != original_prefix:
            if len(base_to_uris.get(candidate, set())) == 1:
                existing_uri = claimed_targets.get(candidate)
                if existing_uri is None or existing_uri == uri:
                    target_prefix = candidate

        replacements[original_prefix] = target_prefix
        claimed_targets.setdefault(target_prefix, uri)

    rewrite_order = sorted(
        (prefix for prefix in replacements if replacements[prefix] != prefix),
        key=len,
        reverse=True,
    )
    seen_declarations: set[tuple[str, str]] = set()
    cleaned_lines: list[str] = []

    for line in lines:
        match = prefix_pattern.match(line)
        if match:
            original_prefix = match.group(1)
            uri = match.group(2)
            target_prefix = replacements.get(original_prefix, original_prefix)
            declaration_key = (target_prefix, uri)
            if declaration_key in seen_declarations:
                continue
            seen_declarations.add(declaration_key)
            cleaned_lines.append(f"@prefix {target_prefix}: <{uri}> .")
            continue

        rewritten = line
        for original_prefix in rewrite_order:
            target_prefix = replacements[original_prefix]
            rewritten = re.sub(
                rf"(?<![A-Za-z0-9\-_]){re.escape(original_prefix)}:",
                f"{target_prefix}:",
                rewritten,
            )
        cleaned_lines.append(rewritten)

    return "\n".join(cleaned_lines)


def save_prefixes(new_prefixes: dict[str, str]) -> None:
    existing = load_prefixes()
    existing.update(new_prefixes)
    PREFIX_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def load_prefixes() -> dict[str, str]:
    if not PREFIX_FILE.exists():
        return {}
    return json.loads(PREFIX_FILE.read_text(encoding="utf-8"))


def extract_prefixes(ttl_text: str) -> dict[str, str]:
    matches = re.findall(r"@prefix\s+([a-zA-Z0-9\-_]+):\s+<([^>]+)>", ttl_text)
    return {prefix: namespace for prefix, namespace in matches}
