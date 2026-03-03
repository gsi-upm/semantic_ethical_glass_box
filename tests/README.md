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
