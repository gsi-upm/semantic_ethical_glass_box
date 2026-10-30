# Audit Vocabulary

## What This Page Is For

From `1.2.0` the backend keeps an append-only audit trail in its own named graph, `http://segb/audit`, separate
from the event graph `http://segb/events`. This page fixes the terms used in that graph. It is the contract for the
audit-on-insert, audit-on-delete and `/history` work; code follows this page, not the other way round.

The audit graph is built on [PROV-O](https://www.w3.org/TR/prov-o/) and the [SEGB ontology](ontology.md). It adds only
the few terms PROV-O does not cover, under a small namespace of its own.

## Namespace

| Prefix | IRI | Notes |
|---|---|---|
| `audit` | `http://www.gsi.upm.es/ontologies/segb/audit#` | New. Terms below. Not yet published as an ontology file. |
| `prov` | `http://www.w3.org/ns/prov#` | Reused. |
| `dcterms` | `http://purl.org/dc/terms/` | Reused (`identifier`). |
| `foaf` | `http://xmlns.com/foaf/0.1/` | Reused (`accountName`). |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` | Datatypes. |

## Resources

| Resource | IRI pattern | Type |
|---|---|---|
| Audit entry | `<{base}entry/{log_id}>` | `audit:Insertion` or `audit:Deletion` |
| Agent | `<{base}agent/{username}>` | `prov:Agent` |

`{base}` is the deployment's audit IRI base, a setting; the examples on this page use
`https://example.org/segb/audit/`. It is unrelated to the graph name `http://segb/audit`. `{log_id}` is the UUID that
`insert_ttl` already generates and today discards. `{username}` is the authenticated username, percent-encoded; when
authentication is disabled it is `anonymous_user`.

## Classes

| Class | Parent | Meaning |
|---|---|---|
| `audit:AuditEntry` | `prov:Activity` | Any recorded operation on the event graph. Never instantiated directly. |
| `audit:Insertion` | `audit:AuditEntry` | A Turtle upload that was written to `events`. |
| `audit:Deletion` | `audit:AuditEntry` | A deletion of the whole `events` graph. |

The entry type answers "what happened" (the action). It is the RDF type and is not repeated as a property.

## Properties

| Property | Used on | Value | Meaning |
|---|---|---|---|
| `dcterms:identifier` | entry | `xsd:string` | The `log_id` (UUID). Same value as the tail of the entry IRI. |
| `prov:startedAtTime` | entry | `xsd:dateTime` | UTC instant the backend started handling the request, with microseconds and the `Z` suffix. |
| `prov:wasAssociatedWith` | entry | agent IRI | Who did it: the authenticated user. |
| `foaf:accountName` | agent | `xsd:string` | The username. |
| `audit:actorRole` | entry | `xsd:string`, repeatable | Roles the agent held in this request (for example `admin`, `auditor`, `logger`). Kept on the entry, not on the agent, because roles are claims of one token and change over time. |
| `audit:originIP` | entry | `xsd:string` | Client address: first `X-Forwarded-For` hop if present, otherwise the socket peer. See the caveat below. |
| `audit:route` | entry | `xsd:string` | Method and path that triggered the entry, for example `POST /ttl` or `POST /log` (legacy). |
| `audit:ttl` | entry | `xsd:string` | The Turtle exactly as received (insertion) or the full export of `events` just before it was cleared (deletion). |
| `audit:ttlFile` | deletion | `xsd:string` | Only for a dump too large to embed (see "Large dumps"): name of the file in the audit dump directory that holds the Turtle. Then `audit:ttl` is absent. |
| `audit:ttlSha256` | deletion | `xsd:string` | SHA-256 (hex) of that file, so the entry proves the file was not altered. Always present with `audit:ttlFile`. |
| `audit:mentionsSubject` | insertion | IRI, repeatable | Every URI subject that appears in the upload. Blank-node subjects are not listed (see Limitations). |

## Example

An administrator uploads one log through `POST /ttl`:

```turtle
@prefix audit:   <http://www.gsi.upm.es/ontologies/segb/audit#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix foaf:    <http://xmlns.com/foaf/0.1/> .
@prefix prov:    <http://www.w3.org/ns/prov#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

<https://example.org/segb/audit/entry/6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10>
    a audit:Insertion ;
    dcterms:identifier "6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10" ;
    prov:startedAtTime "2026-10-29T10:15:42.123456Z"^^xsd:dateTime ;
    prov:wasAssociatedWith <https://example.org/segb/audit/agent/alice> ;
    audit:actorRole "admin" , "logger" ;
    audit:originIP "192.168.1.20" ;
    audit:route "POST /ttl" ;
    audit:mentionsSubject <http://example.org/greeting1> ;
    audit:ttl """@prefix ex: <http://example.org/> .
ex:greeting1 a ex:Greeting .""" .

<https://example.org/segb/audit/agent/alice>
    a prov:Agent ;
    foaf:accountName "alice" .
```

A deletion (`POST /ttl/delete_all`) has the same shape with `a audit:Deletion`, `audit:route "POST /ttl/delete_all"`, no
`audit:mentionsSubject`, and `audit:ttl` holding the removed graph exactly as `GET /events` would have returned it. Its
`log_id` is returned in the response. Deleting an empty graph removes nothing, so it writes no entry.

## Reading the audit trail

Both endpoints need the `auditor` or `admin` role and read only the audit graph.

`GET /history` returns `200` with a JSON list, oldest first (an empty audit gives `[]`). Each item:

```json
{
  "_id": "6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10",
  "uploaded_at": "2026-10-29T10:15:42.123456Z",
  "origin_ip": "192.168.1.20",
  "action_type": "insertion",
  "action": "6f1f2a4e-9c0b-4c8a-b2d5-3a7c1e5d9f10",
  "user_details": {"username": "alice", "roles": ["admin", "logger"]},
  "route": "POST /ttl"
}
```

`GET /log?log_id=<id>` returns `{"log": <the item above>, "action": ...}`, where `action` is:

| `action_type` | `action` |
|---|---|
| `insertion` | `{"ttl_content": "<the upload>", "subjects": ["<uri>", ...]}` |
| `deletion` | `{"ttl_deleted_graph": "<the removed graph>"}` |
| `deletion`, large dump | `{"ttl_deleted_graph_file": "<name>", "ttl_deleted_graph_sha256": "<hex>"}`, see "Large dumps" |

Errors: `400` without `log_id`, `404` for an unknown or malformed id, `403` for other roles.

### Differences from 0.4.x

| 0.4.x | Now |
|---|---|
| `_id` was a MongoDB ObjectId | `_id` is the UUID that `POST /ttl` and `POST /ttl/delete_all` return as `log_id` |
| `uploaded_at` was the server's local time, ISO format, no time zone | UTC with microseconds and a `Z` suffix |
| `user_details` was the string form of the token user | an object with `username` and `roles` (the authenticated user, never the `user` field of the body) |
| `action` was the id of a separate action document | the same value as `_id`: the entry holds its own payload |
| empty history: `204 No Content` | `200` with `[]` |
| no `route`, no `subjects` | `route` is new; `subjects` is new in an insertion's `action` |
| a deleted graph was always inline | a dump over 4 MiB is referenced by file name and SHA-256 |
| `/log` unknown id: `404`; malformed id: `404` | unchanged |

## Isolation from `/query`

`GET /query` is read-only and meant for `events`; the audit trail is read through `GET /history` and `GET /log`. Two
layers keep `/query` away from `audit`:

1. **The dataset is pinned.** Every read query is sent to Virtuoso with `default-graph-uri` and `named-graph-uri` set to
   the events graph. Without them Virtuoso queries the union of all graphs, so an unqualified `SELECT * { ?s ?p ?o }`
   would return audit triples, and `GRAPH ?g` would list the audit graph.
2. **The query text is checked.** A pinned dataset is not enough: a `FROM <audit>` inside the query overrides it, and
   an explicit `GRAPH <audit>` inside `FILTER EXISTS` ignores it, which would make `EXISTS` a yes/no oracle over the
   audit trail. So the text is read with a small lexer (comments, strings, IRIs, prefixes, `BASE` and `\u` escapes
   are handled) and the query is rejected with `422` if it:
   - names, in `FROM`, `FROM NAMED` or `GRAPH`, any graph other than `events` (resolved through prefixes and `BASE`);
   - uses `SERVICE`;
   - calls Virtuoso internals (`bif:`, `sql:`, or the `.../schemas/bif#` namespace, under any prefix label);
   - calls any function that is not an XSD cast.

   The same message is returned by `POST /query/validate`, with `valid: false`.

The last two rules are not about the audit graph only. In Virtuoso `bif:exec('SPARQL CLEAR GRAPH <g>')` runs with the
privileges of the account the backend uses (`dba` by default) even inside a `SELECT`, so before this check a user with the `auditor` role
could erase any graph through `/query`. The `/query` endpoint is not meant to run user-defined functions, so the rule
is deliberately broad.

Known limitations: an RDF collection written right after an IRI (`?s ex:list (1 2)`) looks like a function call and is
rejected; and the check is an allow-list written for Virtuoso 7.2.16, so it should be revisited when the image changes.

## Large dumps

Virtuoso rejects a SPARQL statement of about 10 MB, and a single literal of that size, so a big `events` graph cannot
travel inside its own deletion entry. Checked against Virtuoso 7.2.16: a literal of 5 MB is accepted and one of 10 MB
is not; splitting the dump into several literals in the same statement does not help, because the limit is on the whole
statement.

- A dump of up to `AUDIT_INLINE_TTL_MAX_BYTES` (4 MiB) is embedded as `audit:ttl`.
- A bigger one is first written and fsynced to `AUDIT_DUMP_DIR` as `<log_id>.ttl`; the entry then carries
  `audit:ttlFile` (the file name) and `audit:ttlSha256`. If the file cannot be written, nothing is cleared.
- The entry and the `CLEAR` run in one SPARQL update, so a failed clear leaves no entry; the file written for it is
  removed.
- The directory is a volume (`audit_dumps` in the compose files). Back it up together with the Virtuoso data: an entry
  that points to a missing file proves the deletion happened but cannot show what was deleted.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `VIRTUOSO_AUDIT_GRAPH_URI` | `http://segb/audit` | Named graph that holds the audit trail. |
| `AUDIT_BASE_IRI` | `http://segb/audit/` | The `{base}` of entry and agent IRIs. |
| `AUDIT_DUMP_DIR` | `/data/audit-dumps` | Where dumps too large to embed are written. |
| `AUDIT_INLINE_TTL_MAX_BYTES` | `4194304` | Largest dump embedded in the entry; above it the dump goes to a file. |

## Rules

- Every `POST /ttl` writes its audit entry in the same SPARQL update as the events, so a failed insert leaves no entry.
- The agent is the authenticated user (the token), never the `user` field of the request body, which is a client claim.
- The audit graph is append-only. No endpoint clears or edits it, including the deletion of `events`, which stores the removed graph in a `Deletion` entry first.
- Deleting `events` takes the same lock as inserting, so nothing can be added between the dump stored in the entry and the clear.
- Uploading the same Turtle twice writes one set of triples to `events` and two entries to `audit`, each with its own
  `log_id`.
- Reading `audit` needs the `auditor` or `admin` role, and only through `/history` and `/log`: `/query` cannot reach it
  (see "Isolation from `/query`").

## Limitations

- Very large event uploads can exceed Virtuoso's compiler limits when events and their audit entry are inserted
  together. Send small logs for individual events; see [Turtle insertion limits](api-and-roles.md#insert-turtle).
- `audit:originIP` is as trustworthy as the proxy in front of the backend: `X-Forwarded-For` is client-controlled
  unless a trusted proxy overwrites it.
- Blank-node subjects have no stable IRI, so they are not in `audit:mentionsSubject`. The original Turtle in
  `audit:ttl` still contains them.
- The audit stores the Turtle as sent. Prefix declarations are part of it, so entries stay readable on their own.

## Open points for review

1. Namespace `audit:` under `ontology/segb/`: keep it separate, or add the terms to `segb.ttl` later?
2. `prov:startedAtTime` as the single timestamp, or also `prov:endedAtTime` for the commit instant?
3. Roles as plain strings on the entry (chosen) versus PROV qualified associations (`prov:hadRole`).
