# TTL Generation Pipeline

## Objective

Describe the end-to-end pipeline from robot runtime facts to persisted triples in Virtuoso.

## Prerequisites

- `semantic_log_generator` package installed
- Backend API running (for ingestion)
- Virtuoso reachable by backend

## Steps

### 1) Build graph on robot side

- `SemanticSEGBLogger` writes entities/activities in an in-memory `rdflib.Graph`.
- URIs are generated under `base_namespace`.
- Shared events are either resolved online (`/shared-context/resolve`) or created locally with deterministic fallback.

### 2) Serialize and send Turtle

- Serialize: `Graph.serialize(format="turtle")`
- Publish: `SEGBPublisher.publish_turtle(...)` to `POST /ttl`
- Optional queue: `queue_file` + `flush_queue()` for retry flows

### 3) Ingest on backend

`POST /ttl` pipeline:

1. Parse incoming Turtle into `rdflib.Graph`
2. Normalize and preserve prefixes
3. Convert to canonical N-Triples
4. Execute SPARQL `INSERT DATA` into configured graph URI

### 4) Read from backend

- `GET /events`: exports current KG as Turtle
- `GET /query`: read-only query execution (mutating verbs blocked)

### 5) Boundary of this pipeline

Not part of TTL generation internals:

- Sensor acquisition
- Ontology reasoning/materialization during ingest
- Cross-robot deduplication at `/ttl` ingest

## Validation

- `POST /ttl` returns success.
- `GET /events` returns non-empty Turtle.
- Shared-event links appear as `prov:specializationOf` when used.

## Troubleshooting

- Invalid Turtle payloads: validate with `POST /ttl/validate`.
- Insert succeeds but no data in UI: confirm correct graph URI/config and query scope.
- Resolver not used: ensure logger is created with `shared_event_resolver=...`.

## Next

- API usage examples: [Package Usage](../package/usage.md)
- Resolver details: [Shared Context Resolution](../backend/shared-context.md)
