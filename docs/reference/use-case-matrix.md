# Use-Case Matrix

## Why This Page Exists

SEGB ships with several ready-made simulation flows. They are useful because each one demonstrates a specific capability
of the stack.

This page gives you the fast lookup view: what each use case does, when to run it, and what you should expect from it.

## Use Cases At A Glance

| Use case | Script | What it demonstrates | Good moment to use it |
|---|---|---|---|
| UC-01 | `run_simulation.py` | Basic cross-robot interaction in one shared graph | when you want a minimal interaction baseline |
| UC-02 | `run_use_case_02_report_ready_dataset.py` | Rich dataset for reports, emotions, ML usage, and robot state | when you want the UI to look meaningful quickly |
| UC-03 | `run_use_case_03_shared_context_auto_match.py` | Automatic shared-context matching | when you want to test clean multi-observation matching |
| UC-04 | `run_use_case_04_shared_context_ambiguous_review.py` | Ambiguous shared-context review flow | when you want to test manual review in the UI |
| UC-05 | `run_use_case_05_ttl_validate_insert.py` | Turtle validation and controlled insertion | when you want to test validation and export endpoints |

## Common Prerequisites

For all use cases, you normally need:

- backend API running at `http://localhost:5000`
- backend readiness confirmed through `/healthz/ready`
- a Python environment with the local package installed

Typical setup:

```bash
python3 -m venv .segb_env
./.segb_env/bin/python -m pip install -U pip
./.segb_env/bin/python -m pip install -e packages/semantic_log_generator
./.segb_env/bin/python -m pip install pydantic
```

If auth is enabled, add `--token "<jwt>"` to the use-case commands that publish or review data.

## Common Commands

### UC-01

```bash
./.segb_env/bin/python -m examples.simulations.run_simulation \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

### UC-02

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

### UC-03

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_03_shared_context_auto_match \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

### UC-04

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_04_shared_context_ambiguous_review \
  --publish-url http://localhost:5000 \
  --decision accept \
  --no-print-ttl
```

### UC-05

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_05_ttl_validate_insert \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

## Important Note About Data Replacement

Most of these flows replace the graph content before inserting their own dataset. This is very convenient for repeatable
testing, but it also means you should not treat them as additive data loaders.

## Which Page Uses Which Use Case

| Page | Main use case |
|---|---|
| [Quickstart](../getting-started/quickstart.md) | UC-02 |
| [Shared Context Workflow](../guides/shared-context-workflow.md) | UC-03 and UC-04 |
| [Validation Checklist](../guides/validation-checklist.md) | UC-02 to UC-05 |

## Related Pages

- [Quickstart](../getting-started/quickstart.md)
- [Validation Checklist](../guides/validation-checklist.md)
- [Shared Context Workflow](../guides/shared-context-workflow.md)
