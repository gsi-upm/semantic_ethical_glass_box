# TTL Generation Internals

This document explains the internal pipeline that transforms robot runtime facts into Turtle and stores them in Virtuoso.

## 1) Robot-Side Graph Construction

The package `semantic_log_generator` builds an in-memory `rdflib.Graph`.

Core class:

- `SemanticSEGBLogger`

### 1.1 URI Strategy

- Every resource URI is generated inside `base_namespace` (robot-local namespace).
- URI shape is deterministic by kind and id (activity/message/observation/model/state).
- Shared events can be deterministic too (hash over normalized event fields and time bucket).

### 1.2 Triple Emission

The logger writes triples with:

- SEGB terms (activity relationships, produced results, model usage)
- PROV terms (activity/entity provenance)
- ORO / ONYX / MLS / SCHEMA / SOSA terms depending on logged artifact

Important design choice:

- The logger emits some redundant PROV triples intentionally.
- Reason: keep interoperability in stores without OWL reasoning enabled.

### 1.3 Shared Event Resolution

`get_shared_event_uri(...)` has two modes:

1. Online mode:
   - calls backend resolver via an explicitly configured `HTTPSharedContextResolver` (`POST /shared-context/resolve`)
2. Local fallback:
   - deterministic URI generated from canonical event fingerprint

If no resolver is configured, logger stays in local mode by default.

In both cases, local observations are linked with `prov:specializationOf` to the shared event node.

Shared-event serialization policy:

- Shared event resource is typed as `schema:Event` and `prov:Entity`.
- The logger does not emit non-standard Schema.org properties such as `schema:eventType` or `schema:confidence`.
- The logger does not use `schema:measurementTechnique` on `schema:Event`.
- Modality (for example, `speech`) is modeled with SOSA:
  - `sosa:Observation` with `sosa:hasFeatureOfInterest` to the shared event
  - `sosa:usedProcedure` to a `sosa:Procedure` labelled with modality
  - `sosa:resultTime` and optional `sosa:hasSimpleResult` (text)
- Observation-to-shared-event confidence is emitted as `schema:additionalProperty` (`schema:PropertyValue` with `schema:propertyID="shared_event_confidence"`).
- Robot state snapshots link properties with `schema:additionalProperty` and location with `prov:atLocation`.

## 2) Serialization and Transport

After graph construction:

- `Graph.serialize(format="turtle")` produces TTL
- `SEGBPublisher.publish_turtle(...)` sends payload to backend endpoint `POST /ttl`
- optional offline queue can store failed payloads and later `flush_queue()`

## 3) Backend Ingestion Path

Backend endpoint:

- `POST /ttl`

Server-side process:

1. Parse incoming TTL into `rdflib.Graph` (single parse pass).
2. Extract/store prefixes for later reconstruction.
3. Convert parsed graph to canonical N-Triples.
4. Execute SPARQL `INSERT DATA` into configured graph URI in Virtuoso.

This approach avoids direct string insertion of raw incoming TTL.

## 4) Read Path

### 4.1 Export current KG

- `GET /events`
- Backend runs `CONSTRUCT` over configured graph URI.
- Result is re-serialized as Turtle, rebinding known prefixes.

### 4.2 Read-only custom queries

- `GET /query`
- Mutating SPARQL verbs are blocked (`INSERT`, `DELETE`, `DROP`, etc.).
- For SELECT-like outputs, backend converts results into turtle-shaped output for UI compatibility.

## 5) What This Pipeline Deliberately Does Not Do

- No reasoning or ontology materialization in ingestion path.
- No automatic event deduplication at `/ttl` ingest.
- No robot-side sensor acquisition.

These concerns are kept outside the TTL generation pipeline to preserve predictable behavior and easier operations.
