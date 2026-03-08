# Validation Checklist

## When To Use This Page

This page is not the best first tutorial. Use it when you already have SEGB running and you want a practical checklist
to confirm that the main features work end to end.

Typical moments to use it:

- before a demo,
- after a deployment change,
- after backend or UI refactoring,
- as a quick regression smoke test.

## Before You Start

You need:

- the centralized stack running,
- the local Python environment `./.segb_env` ready,
- to run commands from the repository root.

If auth is enabled, export an admin token for convenience:

```bash
export SEGB_API_TOKEN="<admin_jwt>"
```

Important: UC-02, UC-03, UC-04, and UC-05 may replace the current graph content.

## Check 1: Ingestion And Report-Ready Data (UC-02)

If auth is disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If auth is enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "$SEGB_API_TOKEN" \
  --no-print-ttl
```

Pass criteria:

- the script finishes without errors,
- `/reports` shows non-empty content,
- `/kg-graph` shows a populated graph.

## Check 2: Shared-Context Auto-Match (UC-03)

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
  --token "$SEGB_API_TOKEN" \
  --no-print-ttl
```

Pass criteria:

- the first observation creates or reuses a context cleanly,
- the second observation is reported as `matched`.

## Check 3: Ambiguous Review Workflow (UC-04)

If auth is disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision accept \
  --no-print-ttl
```

If auth is enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --token "$SEGB_API_TOKEN" \
  --decision accept \
  --no-print-ttl
```

Pass criteria:

- an ambiguous case is created,
- the review decision is accepted and persisted,
- the UI summary updates consistently.

## Check 4: TTL Validation And Controlled Insert (UC-05)

If auth is disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_05_ttl_validate_insert \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If auth is enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_05_ttl_validate_insert \
  --publish-url http://localhost:5000 \
  --token "$SEGB_API_TOKEN" \
  --no-print-ttl
```

Pass criteria:

- invalid Turtle is rejected by validation,
- valid Turtle is accepted,
- the inserted data can be exported through `/events`.

## Final Check: Export The Graph

If auth is disabled:

```bash
curl -s http://localhost:5000/events | head -n 20
```

If auth is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

Expected result: non-empty Turtle output.

## If A Check Fails

- `401/403`: the token is missing, expired, or does not have the required role.
- reports are empty after UC-02: reload the dataset and refresh the UI.
- shared-context checks behave unexpectedly: inspect `/shared-context` and `/shared-context/stats`.
- `/healthz/ready` returns `false`: fix backend-to-Virtuoso connectivity first.

## Related Pages

- [Quickstart](../getting-started/quickstart.md)
- [Shared Context Workflow](shared-context-workflow.md)
- [Use-Case Matrix](../reference/use-case-matrix.md)
