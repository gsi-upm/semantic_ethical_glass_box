# Shared Context Resolution (Tutorial)

## Objective

Understand shared-context behavior with one execution flow oriented to the web UI: auto-match, ambiguous case, manual review, and final validation.

## Prerequisites

- Steps 1-4 of the recommended path completed
- Backend + UI running (`http://localhost:5000`, `http://localhost:8080`)
- Python env ready (`./.segb_env`) with simulation dependencies
- Run commands from repository root (`semantic_ethical_glass_box/`)

If auth is enabled (`SECRET_KEY` set):

1. Open `http://localhost:8080/session`
2. Set an `admin` token (required for `/shared-context` page actions)

## Event Types That Usually Need Shared Context

Shared context is useful when multiple robots/sensors observe the same real-world event and you want one canonical URI.

Typical event kinds:

- `human_utterance`: same spoken sentence captured by different robots.
- `human_expression`: same facial expression observed by different cameras.
- `human_gesture` or `human_action`: same gesture/action detected by different perception stacks.
- Domain events with shared references (for example object mentions), if they include aligned metadata.

In practice, matching works better when observations share:

- close timestamps (`observed_at`)
- compatible `subject_uri`
- compatible `modality`
- semantically close `text` (when present)

## Tutorial Flow

### 1) Open the Resolver Console (UI-first)

Open:

- `http://localhost:8080/shared-context`

This page is your main workspace for shared-context review:

- summary cards (`Pending reviews`, `Unresolved contexts`, `Active contexts`, `Merged contexts`, `Alias mappings`)
- `Pending Queue`
- `Decision Area` (accept/reject)

### 2) Run UC-03 (auto-match) and inspect what happened

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Auth enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

What happens in this use case:

1. First observation is sent (`human_utterance`, robot A, base text).
2. Second observation is sent 800 ms later (`human_utterance`, robot B, almost same text).
3. Resolver should reuse the same shared context URI (`matched`).

Relevant snippet from `run_use_case_03_shared_context_auto_match.py`:

```python
first_payload = {
    "event_kind": "human_utterance",
    "observed_at": observed_at.isoformat(),
    "subject_uri": str(human_uri),
    "modality": "speech",
    "text": utterance,
    "robot_uri": str(ari_logger.robot_uri),
}
second_payload = {
    "event_kind": "human_utterance",
    "observed_at": (observed_at + timedelta(milliseconds=800)).isoformat(),
    "subject_uri": str(human_uri),
    "modality": "speech",
    "text": utterance.replace("headline?", "headline"),
    "robot_uri": str(tiago_logger.robot_uri),
}

first_resolution = _resolve_shared_context(client, first_payload)
second_resolution = _resolve_shared_context(client, second_payload)
```

How to read the JSON summary:

- `first_status`: usually `created` (or `matched` if context already existed)
- `second_status`: expected `matched`
- `shared_context_uri`: canonical URI reused by both observations

UI check after UC-03:

- `Pending reviews` should stay `0` (no ambiguity introduced in this case).
- `Active contexts` should increase.

### 3) Run UC-04 (ambiguous) and review it in the UI

Run with `--decision none` first, so you can review manually in the web page:

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision none \
  --no-print-ttl
```

Auth enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --decision none \
  --no-print-ttl
```

Why this creates ambiguity (snippet from `run_use_case_04_shared_context_ambiguous_review.py`):

```python
created_resolution = _resolve_shared_context(client, {
    "event_kind": event_kind,
    "observed_at": observed_at.isoformat(),
    "subject_uri": str(human_uri),
    "modality": "speech",
    "text": base_text,
    "robot_uri": str(ari_logger.robot_uri),
})
ambiguous_resolution = _resolve_shared_context(client, {
    "event_kind": event_kind,
    "observed_at": (observed_at + timedelta(milliseconds=500)).isoformat(),
    "subject_uri": None,
    "modality": "speech",
    "text": base_text,
    "robot_uri": str(tiago_logger.robot_uri),
})
```

Interpretation:

- same event kind + close time + similar text
- but incomplete subject alignment (`subject_uri=None`) creates uncertainty
- resolver marks second context as `ambiguous`

UI check after UC-04 (`--decision none`):

- `Pending reviews` should increase
- a case should appear in `Pending Queue`
- candidate options should appear in `Decision Area`

Reference screenshot (pending case in Resolver Console):

![SEGB Shared Context Pending Case](../assets/screenshots/ui-shared-context-pending.png)

### 4) Resolve from the UI and verify counters

In `Decision Area`, choose one action:

- `Accept this merge` (merge into canonical context)
- `Keep contexts separate` (reject merge)

Then click `Refresh summary`.

What should change:

- accepted merge usually increases `Merged contexts`
- accepted merge usually increases `Alias mappings`
- `Pending reviews` should decrease (or remain >0 if there are older pending cases)

Reference screenshot (after review activity):

![SEGB Shared Context After Review](../assets/screenshots/ui-shared-context-review.png)

### 5) Optional backend/debug checks (behind the UI)

Use these only if you need raw backend payloads while debugging:

Review queue:

```bash
curl -s http://localhost:5000/shared-context/review/pending
```

Stats:

```bash
curl -s http://localhost:5000/shared-context/stats
```

If auth is enabled, add:

```bash
curl -s http://localhost:5000/shared-context/review/pending \
  -H "Authorization: Bearer <admin_jwt>"

curl -s http://localhost:5000/shared-context/stats \
  -H "Authorization: Bearer <admin_jwt>"
```

## Validation

- UC-03 reports `second_status = matched`.
- UC-04 reports `ambiguous_status = ambiguous` when run with `--decision none`.
- Resolver Console shows pending cases and decision actions.
- After manual decision in UI, summary cards update consistently.

## Troubleshooting

- No cases in `Pending Queue` after UC-04:
  run again with a different `--seed` to generate another ambiguous pair.
- `403` on `/shared-context`:
  token missing `admin` role.
- `Pending reviews` does not change after decision:
  click `Refresh queue` and `Refresh summary`, then check backend logs if needed.
- Always `created` in UC-03:
  observations are too different (text/subject/modality/time) to be matched.
