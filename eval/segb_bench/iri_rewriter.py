"""Turn one real trace into N distinct-but-isomorphic copies.

Why this exists
---------------
The boss's constraint is that the TTL must come from a *real* interaction, but
the scalability experiment needs volume and *distinct* logs (re-posting the
identical TTL would be collapsed by the backend's redundancy handling and would
not grow the KG). Rewriting only the per-run instance IRIs gives a faithful
copy of the real interaction with its own identity, which is exactly what the
boss sanctioned ("a partir de ese TTL puedo generar simulaciones de envío").

What it touches
---------------
ONLY URIRefs whose string starts with one of ``data_prefixes`` (the instance
namespaces of a concrete run). Vocabulary IRIs (onyx:, oro:, prov:, segb:,
schema:, sosa:, oa:) never start with those prefixes, so they are preserved.
Blank nodes are re-minted automatically by rdflib on each parse, so every copy
is internally consistent and globally distinct.

For the shared-context convergence test (B3) pass the shared-event namespace in
``preserve_prefixes`` so every robot keeps pointing at the *same* event.
"""
from __future__ import annotations

import uuid
from typing import Iterable, Optional

from rdflib import Graph, URIRef


def rewrite_session(
    ttl_text: str,
    data_prefixes: Iterable[str],
    preserve_prefixes: Iterable[str] = (),
    session_token: Optional[str] = None,
    fmt: str = "turtle",
) -> tuple[str, str]:
    """Return ``(rewritten_ttl, session_token)``."""
    token = session_token or uuid.uuid4().hex[:12]
    data_prefixes = tuple(data_prefixes)
    preserve_prefixes = tuple(preserve_prefixes)

    src = Graph()
    src.parse(data=ttl_text, format=fmt)
    out = Graph()
    for pfx, ns in src.namespaces():
        out.bind(pfx, ns)

    def remap(term):
        if isinstance(term, URIRef):
            s = str(term)
            if any(s.startswith(p) for p in preserve_prefixes):
                return term
            for p in data_prefixes:
                if s.startswith(p):
                    return URIRef(p + token + "/" + s[len(p):])
        return term

    for s, p, o in src:
        out.add((remap(s), remap(p), remap(o)))
    return out.serialize(format=fmt), token
