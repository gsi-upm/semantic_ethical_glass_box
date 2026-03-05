# Validate Core SEGB Features (Optional Checklist)

## Purpose

This guide is an optional verification checklist, not a first-time tutorial.

Use it to confirm that the main SEGB capabilities work end-to-end with ready-made simulation scripts.

## What You Should Learn From This Page

- Which script validates each core capability.
- What success looks like for each capability.
- Whether your current deployment is ready for real integrations.

## Prerequisites

- Steps 1-3 completed:
  - [Centralized Deployment](../deployment/centralized.md)
  - [Install `semantic_log_generator`](../package/installation.md)
  - [Basic Use: Post Your First Log](../package/usage.md)
- Python environment `.segb_env` prepared as in deployment docs.
- Run commands from repository root (directory that contains `docker-compose.yaml`).

If auth is enabled (`SECRET_KEY` set), export an `admin` token:

```bash
export SEGB_API_TOKEN="<jwt>"
```

Important: UC-02/03/04 and UC-05 can clear the configured graph before inserting data.

## Checklist

### 1) Ingestion and KG persistence (UC-02)

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Auth enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "$SEGB_API_TOKEN" \
  --no-print-ttl
```

Pass criteria:

- Script finishes without errors.
- `http://localhost:8080/reports` and `http://localhost:8080/kg-graph` show data.

### 2) Shared-context auto-match (UC-03)

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
  --token "$SEGB_API_TOKEN" \
  --no-print-ttl
```

Pass criteria:

- First compatible context is created.
- Next compatible context is matched to the existing one.

Details: [Shared Context Resolution](../backend/shared-context.md).

### 3) Ambiguous context and manual review (UC-04)

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision accept \
  --no-print-ttl
```

Auth enabled (requires `admin`):

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --token "$SEGB_API_TOKEN" \
  --decision accept \
  --no-print-ttl
```

Pass criteria:

- Ambiguous candidates are created.
- Review decision updates case state and selected mapping.

Details: [Shared Context Resolution](../backend/shared-context.md).

### 4) TTL validation and controlled insertion (UC-05)

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_05_ttl_validate_insert \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Auth enabled (requires `admin`):

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_05_ttl_validate_insert \
  --publish-url http://localhost:5000 \
  --token "$SEGB_API_TOKEN" \
  --no-print-ttl
```

Pass criteria:

- Invalid Turtle is rejected by validation endpoint.
- Valid Turtle is inserted and can be exported through `/events`.

## Final Validation

Auth disabled:

```bash
curl -s http://localhost:5000/events | head -n 20
```

Auth enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

Expected: non-empty Turtle output.

## Troubleshooting

- `401/403` in scripts: token missing, expired, or wrong role.
- Empty UI after running a use case: rerun UC-02 and refresh `/reports` and `/kg-graph`.
- Shared-context scripts fail unexpectedly: verify backend readiness at `/healthz/ready`.

## Next

- Continue with the full integration flow: [Real Use Case with Robot Simulator](../package/ros4hri-integration.md)
