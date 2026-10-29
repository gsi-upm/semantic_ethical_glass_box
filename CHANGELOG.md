# Changelog

## 1.2.0 - 2026-10-29

SEGB gets an append-only audit trail, keeps the two 0.4.x routes the robots still call, and drops the `amor-` prefix
from its own names. Tags `1.0.1` to `1.1.1` are unchanged.

### Security

- `GET /query` could run Virtuoso internal functions (`bif:`, `sql:`) with the account the backend uses, so a user with
  the `auditor` role could erase any graph from a read-only query, the events graph included. This affects the released
  1.x versions up to `1.1.1`. Queries are now checked before they run and the dataset is pinned to the events graph
  (#26). A read-only Virtuoso account for `/query` is planned for 1.3.0 (#27).

### Added

- Audit graph `http://segb/audit`. Every `POST /ttl` writes an `Insertion` entry in the same SPARQL update as the
  events, and `POST /ttl/delete_all` stores the removed graph in a `Deletion` entry before clearing; the audit graph is
  never cleared. A dump over 4 MiB is kept in the new `audit_dumps` volume, referenced by file name and SHA-256
  (#9, #10, vocabulary in #8).
- `GET /history` and `GET /log?log_id=` for the `auditor` and `admin` roles, with the 0.4.x keys (#11).
- Deprecated legacy routes `POST /log` and `GET /health`, with `Deprecation` and `Link` headers, and `GET /legacy/usage`
  (admin) to measure how much `POST /log` is still used. See `docs/reference/legacy-api.md` (#13).
- Warning `SEM_BLANK_NODES` in `POST /ttl/validate`: blank nodes are not skolemized, so a re-upload stores them again
  (#14).
- Settings `VIRTUOSO_AUDIT_GRAPH_URI`, `AUDIT_BASE_IRI`, `AUDIT_DUMP_DIR` and `AUDIT_INLINE_TTL_MAX_BYTES`.
- Opt-in integration tests against a disposable Virtuoso (`SEGB_INTEGRATION=1`), documented in `tests/README.md` (#7).

### Changed

- Names without the old `amor-` prefix: services `segb` and `segb-virtuoso`, container `segb-server`, image
  `ghcr.io/gsi-upm/semantic_ethical_glass_box/segb`, default event graph `http://segb/events` (#20).
  **Upgrading from 1.1.x:** the old graph has a different name, so set `VIRTUOSO_GRAPH_URI` to keep reading it; see
  "Upgrading From 1.1.x" in `docs/operations/centralized-deployment.md`.
- `POST /ttl/delete_all` answers with the `log_id` of its audit entry and takes the same lock as inserts.
- `/query` rejects queries that name another graph, use `SERVICE`, call `bif:`/`sql:` or call any function that is not an
  XSD cast, with `422`; an RDF collection right after an IRI is read as a function call and rejected.

### Known limitations

- A single upload above about 5,000 triples fails in Virtuoso 7.2.16 (#24, planned for 1.3.0).
- Blank nodes are duplicated on re-upload; use URIs.
- Until #27 lands, the isolation of `/query` is a text check written for Virtuoso 7.2.16.
