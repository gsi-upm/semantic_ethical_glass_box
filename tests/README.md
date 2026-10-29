# Tests (Global Scope)

This root `tests/` folder is reserved for truly cross-project suites.

Project-specific tests now live with their owning project:

- Backend: `apps/backend/tests`
- Logger package: `packages/semantic_log_generator/tests`
- Simulation use cases: `examples/simulations/tests`
- Frontend: `apps/frontend/segb-ui/tests`

## Run

```bash
# Backend unit tests
PYTHONPATH=apps/backend/src:packages/semantic_log_generator/src python -m unittest discover -s apps/backend/tests/unit -p 'test_*.py'

# Backend integration tests
PYTHONPATH=apps/backend/src:packages/semantic_log_generator/src python -m unittest discover -s apps/backend/tests/integration -p 'test_*.py'

# Logger package unit tests
PYTHONPATH=packages/semantic_log_generator/src:apps/backend/src python -m unittest discover -s packages/semantic_log_generator/tests/unit -p 'test_*.py'

# Simulation integration tests
PYTHONPATH=packages/semantic_log_generator/src:apps/backend/src python -m unittest discover -s examples/simulations/tests/integration -p 'test_*.py'
```

## Integration tests against a real Virtuoso (opt-in)

Backend integration tests that need a real triple store are skipped unless you opt in, so the default run stays offline:

```bash
SEGB_INTEGRATION=1 PYTHONPATH=apps/backend/src:packages/semantic_log_generator/src \
  python -m unittest discover -s apps/backend/tests/integration -p 'test_*.py'
```

Requires a working `docker` CLI. The image `openlink/virtuoso-opensource-7:7.2.16` is pulled on first use.

The harness (`apps/backend/tests/integration/virtuoso_harness.py`, class `VirtuosoTestInstance`) starts a disposable Virtuoso per test class or run:

- its own container and volume, both named `segb-it-<random id>` and labelled `segb.integration-test=<id>`;
- a random DBA password and a host port chosen by the Docker daemon, bound to `127.0.0.1` only (no fixed 5000/8890/1111);
- teardown removes exactly that container and volume (`docker rm -f -v` and `docker volume rm` by name), never `prune`.

Two runs in parallel therefore do not interfere, and no existing container or volume (for example a deployment's `virtuoso_data`) is touched. Use it as a context manager and point the backend at it with `instance.environ()`:

```python
with VirtuosoTestInstance() as virtuoso:
    os.environ.update(virtuoso.environ())
    ...
```

If a run is killed before teardown, list leftovers with `docker ps -a --filter label=segb.integration-test` and `docker volume ls --filter label=segb.integration-test`.
