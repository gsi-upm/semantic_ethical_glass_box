"""Audit entries for the audit graph (vocabulary: docs/reference/audit-vocabulary.md)."""

from __future__ import annotations

from dataclasses import dataclass
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
    text = moment.isoformat(timespec="milliseconds").removesuffix("+00:00") + "Z"
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
