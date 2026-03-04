# Shared Context Resolution

## Objective

Resolve independent robot observations into one canonical cross-robot context URI.

## Prerequisites

- Backend running
- Access to `/shared-context/*` endpoints
- Robot logger configured with `shared_event_resolver` (for online mode)

Auth requirements when `SECRET_KEY` is set:

- `/shared-context/resolve`: `logger` or `admin`
- `/shared-context/reconcile`: `admin`
- `/shared-context/review/*`: `admin`
- `/shared-context/stats`: `auditor` or `admin`

## Steps

### 1) Send resolve requests from robot runtime

Endpoint:

- `POST /shared-context/resolve`

Minimal request:

```json
{
  "event_kind": "human_utterance",
  "observed_at": "2026-02-11T09:12:13.150Z",
  "subject_uri": "https://example.org/human/maria",
  "modality": "speech",
  "text": "Could you show me climate news?"
}
```

### 2) Understand resolver decision order

For candidate score `S_best` and optional `S_second`:

1. `matched` if `S_best >= match_threshold` and clear margin.
2. `ambiguous` if `S_best >= ambiguous_threshold` but no clear margin.
3. `created` otherwise.

### 3) Reconcile and review ambiguous contexts

- Trigger refresh/auto-merge: `POST /shared-context/reconcile`
- List pending manual review: `GET /shared-context/review/pending`
- Accept a merge: `POST /shared-context/review/{case_id}/accept`
- Reject a merge: `POST /shared-context/review/{case_id}/reject`

### 4) Inspect resolver state

- Resolver statistics: `GET /shared-context/stats`

### 5) Tune policy (environment variables)

- `SHARED_CONTEXT_NAMESPACE`
- `SHARED_CONTEXT_TIME_WINDOW_SECONDS`
- `SHARED_CONTEXT_MATCH_THRESHOLD`
- `SHARED_CONTEXT_AMBIGUOUS_THRESHOLD`
- `SHARED_CONTEXT_CLOSE_MARGIN`

## Validation

Use simulation flows:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Expected: first status `created|matched`, second status `matched`.

```bash
./.venv/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision accept \
  --no-print-ttl
```

Expected: `ambiguous` flow generated and pending review handled.

## Troubleshooting

- Always `created`: time window too strict or input text/subject normalization mismatch.
- Too many `ambiguous`: reduce noise, adjust thresholds/margins.
- `401/403`: token missing role required by endpoint.
- No pending review after ambiguous events: reconcile may have auto-merged cases.

## Next

- Runtime deployment: [Centralized Deployment](../deployment/centralized.md)
- Logger integration: [Package Usage](../package/usage.md)
