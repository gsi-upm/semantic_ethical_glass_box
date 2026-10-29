"""Audit entries for the audit graph (vocabulary: docs/reference/audit-vocabulary.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from datetime import datetime, timedelta
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, RDF, XSD

AUDIT = Namespace("http://www.gsi.upm.es/ontologies/segb/audit#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCTERMS = Namespace("http://purl.org/dc/terms/")


@dataclass(slots=True, frozen=True)
class AuditContext:
    """Who did what, as known to the backend (the authenticated identity, not a client claim)."""

    username: str
    roles: tuple[str, ...]
    origin_ip: str
    route: str


def subject_uris(graph: Graph) -> list[URIRef]:
    """URI subjects of a graph, sorted and unique; blank nodes have no stable IRI and are skipped."""
    return sorted({s for s in graph.subjects() if isinstance(s, URIRef)})


def _utc_literal(moment: datetime) -> Literal:
    if moment.tzinfo is None or moment.utcoffset() != timedelta(0):
        raise ValueError("Audit timestamps must be timezone-aware UTC datetimes.")
    text = moment.isoformat(timespec="microseconds").removesuffix("+00:00") + "Z"
    return Literal(text, datatype=XSD.dateTime, normalize=False)


def _build_entry(
    *,
    kind: URIRef,
    log_id: str,
    context: AuditContext,
    ttl_content: str | None,
    base_iri: str,
    now: datetime,
    ttl_file: str | None = None,
    ttl_sha256: str | None = None,
) -> tuple[Graph, URIRef]:
    base = base_iri if base_iri.endswith("/") else f"{base_iri}/"
    entry = URIRef(f"{base}entry/{log_id}")
    agent = URIRef(f"{base}agent/{quote(context.username, safe='')}")

    graph = Graph()
    graph.add((entry, RDF.type, kind))
    graph.add((entry, DCTERMS.identifier, Literal(log_id)))
    graph.add((entry, PROV.startedAtTime, _utc_literal(now)))
    graph.add((entry, PROV.wasAssociatedWith, agent))
    graph.add((agent, RDF.type, PROV.Agent))
    graph.add((agent, FOAF.accountName, Literal(context.username)))
    for role in context.roles:
        graph.add((entry, AUDIT.actorRole, Literal(role)))
    graph.add((entry, AUDIT.originIP, Literal(context.origin_ip)))
    graph.add((entry, AUDIT.route, Literal(context.route)))
    if ttl_content is not None:
        graph.add((entry, AUDIT.ttl, Literal(ttl_content)))
    if ttl_file is not None and ttl_sha256 is not None:
        graph.add((entry, AUDIT.ttlFile, Literal(ttl_file)))
        graph.add((entry, AUDIT.ttlSha256, Literal(ttl_sha256)))
    return graph, entry


def build_insertion_entry(
    *,
    log_id: str,
    context: AuditContext,
    ttl_content: str,
    base_iri: str,
    now: datetime,
) -> Graph:
    """Builds the audit entry of one TTL upload."""
    graph, entry = _build_entry(
        kind=AUDIT.Insertion, log_id=log_id, context=context, ttl_content=ttl_content, base_iri=base_iri, now=now
    )
    uploaded = Graph()
    uploaded.parse(data=ttl_content, format="turtle")
    for subject in subject_uris(uploaded):
        graph.add((entry, AUDIT.mentionsSubject, subject))
    return graph


def build_deletion_entry(
    *,
    log_id: str,
    context: AuditContext,
    ttl_content: str | None,
    base_iri: str,
    now: datetime,
    ttl_file: str | None = None,
    ttl_sha256: str | None = None,
) -> Graph:
    """Builds the audit entry of a deletion.

    The graph that is about to be removed is either embedded (``ttl_content``) or, when it is too large for one
    SPARQL statement, kept in a file and referenced by name and SHA-256 (``ttl_file`` and ``ttl_sha256``).
    """
    if (ttl_content is None) == (ttl_file is None):
        raise ValueError("Provide either the embedded ttl_content or a ttl_file, not both or neither.")
    if ttl_file is not None and not ttl_sha256:
        raise ValueError("A dump kept in a file needs its SHA-256.")
    graph, _ = _build_entry(
        kind=AUDIT.Deletion,
        log_id=log_id,
        context=context,
        ttl_content=ttl_content,
        base_iri=base_iri,
        now=now,
        ttl_file=ttl_file,
        ttl_sha256=ttl_sha256,
    )
    return graph


@dataclass(slots=True, frozen=True)
class AuditEntryView:
    """One audit entry as served by ``GET /history`` (``summary``) and ``GET /log`` (``summary`` + ``action``)."""

    summary: dict[str, Any]
    action: dict[str, Any]


_RDF_TYPE = str(RDF.type)
_KINDS = {str(AUDIT.Insertion): "insertion", str(AUDIT.Deletion): "deletion"}


def entries_from_rows(rows: list[dict[str, str]], agent_names: dict[str, str]) -> list[AuditEntryView]:
    """Groups ``{"e", "p", "o"}`` rows of the audit graph into entry views, oldest first.

    The summary keeps the keys of the 0.4.x history (``_id``, ``uploaded_at``, ``origin_ip``, ``action_type``,
    ``action``, ``user_details``); ``route`` is new and ``user_details`` is an object instead of a string.
    """
    grouped: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        grouped.setdefault(row["e"], {}).setdefault(row["p"], []).append(row["o"])

    def first(props: dict[str, list[str]], predicate: Any) -> str | None:
        values = props.get(str(predicate))
        return values[0] if values else None

    views = []
    for props in grouped.values():
        kind = next((_KINDS[t] for t in props.get(_RDF_TYPE, []) if t in _KINDS), None)
        if kind is None:
            continue
        entry_id = first(props, DCTERMS.identifier) or ""
        agent = first(props, PROV.wasAssociatedWith)
        summary = {
            "_id": entry_id,
            "uploaded_at": first(props, PROV.startedAtTime),
            "origin_ip": first(props, AUDIT.originIP),
            "action_type": kind,
            "action": entry_id,
            "user_details": {
                "username": agent_names.get(agent) if agent else None,
                "roles": sorted(props.get(str(AUDIT.actorRole), [])),
            },
            "route": first(props, AUDIT.route),
        }
        ttl = first(props, AUDIT.ttl)
        if kind == "insertion":
            action: dict[str, Any] = {
                "ttl_content": ttl,
                "subjects": sorted(props.get(str(AUDIT.mentionsSubject), [])),
            }
        elif ttl is not None:
            action = {"ttl_deleted_graph": ttl}
        else:
            action = {
                "ttl_deleted_graph_file": first(props, AUDIT.ttlFile),
                "ttl_deleted_graph_sha256": first(props, AUDIT.ttlSha256),
            }
        views.append(AuditEntryView(summary=summary, action=action))
    return sorted(views, key=lambda v: (v.summary["uploaded_at"] or "", v.summary["_id"]))
