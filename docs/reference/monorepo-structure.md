# Monorepo Structure

## Objective

Provide a deterministic map of where code, tests, and docs live in this repository.

## Prerequisites

- Repository cloned locally
- Basic shell navigation (`ls`, `cd`, `rg`)

## Steps

### 1) Locate runtime applications

- `apps/backend`: FastAPI backend and API services
- `apps/frontend`: Vue UI (`segb-ui`) and frontend packaging

### 2) Locate reusable package

- `packages/semantic_log_generator`: Python package for RDF logging

### 3) Locate examples and tests

- `examples`: simulations, mocks, notebooks
- `apps/backend/tests`: backend unit/integration tests
- `packages/semantic_log_generator/tests`: package unit tests
- `examples/simulations/tests`: simulation integration tests
- `apps/frontend/segb-ui/tests`: frontend unit tests

### 4) Locate documentation

- `docs`: deploy, operations, package, backend, internals, reference pages

## Validation

You should be able to answer these quickly:

- Where backend endpoint logic lives: `apps/backend/src/api`
- Where simulation entry points live: `examples/simulations`
- Where package API lives: `packages/semantic_log_generator/src/semantic_log_generator`

## Troubleshooting

- Unsure where to start: read repository `README.md`, then [Centralized Deployment](../deployment/centralized.md).
- Looking for tests of a component: check the component-local `tests` directory first.
