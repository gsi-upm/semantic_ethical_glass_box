# SEGB Simulation Use Cases

This directory contains a complete set of simulation use cases for SEGB.

## Use Case Matrix

| Use Case | Script | Purpose |
|---|---|---|
| UC-01 | `run_simulation.py` | Baseline cross-robot interaction in one shared graph. |
| UC-02 | `run_use_case_02_report_ready_dataset.py` | Enriches UC-01 with ML/evaluation/emotion/state data for UI reports. |
| UC-03 | `run_use_case_03_shared_context_auto_match.py` | Calls `/shared-context/resolve` and demonstrates automatic `created` + `matched`. |
| UC-04 | `run_use_case_04_shared_context_ambiguous_review.py` | Demonstrates `ambiguous` resolution plus manual admin review (`accept` or `reject`). |
| UC-05 | `run_use_case_05_ttl_validate_insert.py` | Demonstrates `/ttl/validate`, `/ttl`, and `/events` in one end-to-end workflow. |

## Common Prerequisites

- Backend API available (default `http://localhost:5000`)
- Virtuoso available and backend ready (`GET /healthz/ready`)
- Python environment with package installed:

```bash
./.venv/bin/python -m pip install -e packages/semantic_log_generator
./.venv/bin/python -m pip install pydantic
```

`pydantic` is used by simulation payload contracts (typed validation of backend JSON responses in UC-03/UC-04/UC-05).

## Example Commands

UC-01:

```bash
./.venv/bin/python -m examples.simulations.run_simulation \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

UC-02:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

UC-03:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

UC-04:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision accept \
  --no-print-ttl
```

UC-05:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_05_ttl_validate_insert \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

## Notes

- Most use cases call destructive graph replacement when publishing (`/ttl/delete_all` then `/ttl`).
- If backend auth is enabled, provide a JWT token with required roles via `--token`.

## Tests

Simulation integration tests are in `examples/simulations/tests/integration`.

```bash
PYTHONPATH=packages/semantic_log_generator/src:apps/backend/src ./.venv/bin/python -m unittest discover -s examples/simulations/tests/integration -p 'test_*.py'
```
