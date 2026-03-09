# Shared Context Workflow

This guide explains how SEGB handles one of its most useful ideas: two different observations may describe the same
real-world event. You will first see a clean automatic match, then an ambiguous case, and finally the manual review
flow that resolves that ambiguity.

## Why Shared Context Exists

Imagine two robots in the same room. Robot A hears a sentence and robot B hears almost the same sentence a moment
later. If you store those as unrelated events, later analysis becomes confusing. Shared context gives both observations
a common reference when the system believes they point to the same event. The same idea also helps with multi-camera
emotion analysis, gesture recognition, or any situation where several components may be observing one shared event.

## Before You Start

Follow [Quickstart](../getting-started/quickstart.md) to start the backend, Virtuoso, and the UI, and to create
`./.segb_env`. If you want the compact explanation of UC-03 and UC-04 as named scenarios, see
[Use-Case Matrix](../reference/use-case-matrix.md). If auth is enabled, create an `admin` token with
[Authentication and JWT](../operations/authentication-and-jwt.md) and store it through
`http://localhost:8080/session` before continuing.

## Step 1: Open The Shared-Context Page

Open `http://localhost:8080/shared-context`. This is the main UI for the workflow. It shows summary counters, the
pending review queue, and the decision area where ambiguous cases are accepted or rejected.

## Step 2: Run The Automatic Match Example

This example uses UC-03. It sends two very similar observations close in time.

If auth is disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If auth is enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

The result you want is simple: the first observation usually creates a shared context, the second one should match that
same context, the script output should report `second_status = matched`, the UI should still show `Pending reviews = 0`,
and the active contexts count should increase.

## Step 3: Run The Ambiguous Example

Now run UC-04 with no decision so you can review the case manually in the UI:

If auth is disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision none \
  --no-print-ttl
```

If auth is enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --decision none \
  --no-print-ttl
```

This case creates uncertainty on purpose. The observations are similar enough to suggest a connection, but not clean
enough for the resolver to merge them automatically.

After it finishes, `Pending reviews` should increase, a case should appear in the queue, and candidate targets should
be available in the decision area.

Reference screenshot:

![SEGB Shared Context Pending Case](../assets/screenshots/ui-shared-context-pending.png)

## Step 4: Review The Case Manually

In the decision area you can accept the merge or keep the contexts separate. After you make a decision, refresh the
summary and queue. The pending count should decrease, accepted merges should update the relevant counters, and the case
should disappear from the queue.

Reference screenshot:

![SEGB Shared Context After Review](../assets/screenshots/ui-shared-context-review.png)

## Step 5: Check The Backend Endpoints Behind The UI

The UI is the easiest place to work, but it helps to know the backend pieces underneath: `POST /shared-context/resolve`,
`POST /shared-context/reconcile`, `GET /shared-context/stats`, `GET /shared-context/review/pending`,
`POST /shared-context/review/{case_id}/accept`, and `POST /shared-context/review/{case_id}/reject`.

Useful raw checks:

```bash
curl -s http://localhost:5000/shared-context/stats
curl -s http://localhost:5000/shared-context/review/pending
```

If auth is enabled, add the bearer token:

```bash
curl -s http://localhost:5000/shared-context/stats \
  -H "Authorization: Bearer <admin_or_auditor_jwt>"

curl -s http://localhost:5000/shared-context/review/pending \
  -H "Authorization: Bearer <admin_jwt>"
```

## What Success Looks Like

You have completed the workflow correctly when UC-03 reports a matched second observation, UC-04 creates a pending
ambiguous case, the UI lets you review that case, and the counters update after your decision.

## Common Problems

- everything is always `created`: the observations are too different in time, subject, modality, or text to be matched.
- `/shared-context` returns `403`: your token is missing the `admin` role.
- the queue does not refresh after a decision: refresh the page and then inspect backend logs if needed.

## Next Steps

If you want the compact lookup for all use cases, read [Use-Case Matrix](../reference/use-case-matrix.md). If you want
the exact permissions behind the UI and endpoints used here, read [API and Roles](../reference/api-and-roles.md).
