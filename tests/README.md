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

Requires a working `docker` CLI. The image `openlink/virtuoso-opensource-7:7.2.16@sha256:e7a5cd1915569d70d8363503dc62f6bf818b485f1501b230c7608cde8528c72d` is pulled on first use.

To verify query account isolation specifically, using the installed virtual environment:

```bash
SEGB_INTEGRATION=1 PYTHONPATH=apps/backend/src:apps/backend/tests/integration \
  .venv/bin/python -m unittest discover -s apps/backend/tests/integration -p 'test_query*real.py'
```

The reader suite runs the same provisioning script as Compose. It tests event SELECTs, audit isolation with the lexical
filter disabled, direct authenticated audit reads without dataset pinning, the unpinned graph-name metadata leak,
the API's dataset pin, a SERVICE endpoint with a different identity, denied updates and SQL escapes (including raw
SQL audit row/count reads through `bif:exec`), unchanged graph contents, writer/auditor/deletion behavior, password
rotation, stale graph grants, `nobody` permissions, inherited update roles, and startup refusal without a safe reader
account (including an empty audit graph). Direct grants, EXECUTE inherited from `PUBLIC` or `SPARQL_SELECT` on a
writing routine (also run through the reader's SPARQL), an extra role such as `SPARQL_SELECT_FED` (with the
federation leak as control), and a shipped routine replaced after provisioning must all block reprovisioning and
startup. A missing drift check must block startup too. The reviewed manifest is
`apps/backend/virtuoso/reader-sql-policy.manifest`.
See the deployment notes for the
[metadata, federation, and raw SQL boundaries](../docs/operations/centralized-deployment.md#query-account-isolation).
Database privilege tests are never replaced with mocks or silently skipped when `SEGB_INTEGRATION=1` and Docker
is unavailable.

The harness (`apps/backend/tests/integration/virtuoso_harness.py`, class `VirtuosoTestInstance`) starts a disposable Virtuoso per test class or run:

- its own container and volume, both named `segb-it-<random id>` and labelled `segb.integration-test=<id>`;
- a random DBA password and a host port chosen by the Docker daemon, bound to `127.0.0.1` only (no fixed 5000/8890/1111);
- teardown removes exactly that container and volume (`docker rm -f -v` and `docker volume rm` by name), never `prune`.

Two runs in parallel therefore do not interfere, and no existing container or volume (for example a deployment's `virtuoso_data`) is touched. Use it as a context manager and point the backend at it with `instance.environ()`:

```python
with VirtuosoTestInstance() as virtuoso:
    os.environ.update({**virtuoso.environ(), **virtuoso.provision_query_reader()})
    ...
```

If a run is killed before teardown, list leftovers with `docker ps -a --filter label=segb.integration-test` and `docker volume ls --filter label=segb.integration-test`.
