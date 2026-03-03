# Examples

This directory contains runnable material to validate and demonstrate the SEGB stack.

## Structure

- `mocks/`: robot behavior mocks (ARI, TIAGo)
- `simulations/`: executable simulation use cases (UC-01 .. UC-05)
- `notebooks/`: tutorial notebooks mapped to simulation use cases
- `data/`: optional input data

## Simulation Use Cases

The simulation catalog is documented at:

- [`simulations/README.md`](simulations/README.md)

Tutorial notebooks (one per use case):

- `notebooks/tutorial_uc01_basic_interaction.ipynb`
- `notebooks/tutorial_uc02_report_ready_dataset.ipynb`
- `notebooks/tutorial_uc03_shared_context_auto_match.ipynb`
- `notebooks/tutorial_uc04_shared_context_ambiguous_review.ipynb`
- `notebooks/tutorial_uc05_ttl_validate_insert.ipynb`

## Run Report-Ready Dataset (Recommended for First UI Tour)

Prerequisites:

- SEGB stack running (see `docs/deployment_centralized.md`)
- A local Python virtualenv with `semantic_log_generator` installed (see repo `README.md`)

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

This use case clears the configured graph before inserting new triples.
