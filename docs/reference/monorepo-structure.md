# Monorepo Structure

## Why This Page Exists

SEGB is a monorepo, which is convenient once you know where things live and frustrating when you do not. This page is a
practical map of the repository.

## The Big Picture

You can think of the repository in four layers:

1. runtime applications,
2. reusable package,
3. examples and tests,
4. documentation and assets.

## Runtime Applications

### `apps/backend`

This is the FastAPI backend.

You will usually come here when you need to change:

- API routes,
- request and response handling,
- graph insertion and query behavior,
- security and token validation,
- backend operational tools.

Useful starting points:

- `apps/backend/src/api`
- `apps/backend/src/services`
- `apps/backend/src/core`

### `apps/frontend`

This is the SEGB web UI and its packaging.

You will usually come here when you need to change:

- routes such as `/reports` or `/kg-graph`,
- frontend role gating,
- report rendering,
- UI-side API calls,
- production frontend container packaging.

Useful starting points:

- `apps/frontend/segb-ui/src`
- `apps/frontend/Dockerfile`
- `apps/frontend/infrastructure/nginx.conf`

## Reusable Package

### `packages/semantic_log_generator`

This is the Python package used by robots and simulations to build semantic logs.

You will usually come here when you need to change:

- RDF generation,
- logger APIs,
- publisher behavior,
- namespace bindings,
- package metadata and distribution.

Useful starting points:

- `packages/semantic_log_generator/src`
- `packages/semantic_log_generator/tests`

## Examples And Tests

### `examples/simulations`

Ready-made use cases such as UC-01 to UC-05. These are the fastest way to exercise the stack end to end.

### `examples/notebooks`

Notebook versions of some learning and demonstration flows.

### `examples/mocks`

Small mock helpers used by the example flows.

### Test Locations

- `apps/backend/tests`: backend-focused tests
- `packages/semantic_log_generator/tests`: package tests
- `examples/simulations/tests`: simulation integration tests
- `tests`: cross-project or reserved top-level scope

## Documentation

### `docs`

This folder contains the MkDocs documentation source.

Important note:

- `docs/backup` stores preserved pre-restructure pages that are intentionally kept out of the main published navigation.

## A Quick "Where Should I Look?" Guide

If the problem is about:

- a failing API endpoint, start in `apps/backend`
- a broken UI page, start in `apps/frontend/segb-ui/src`
- a robot-side logging API, start in `packages/semantic_log_generator`
- a demo or end-to-end scenario, start in `examples/simulations`
- the docs site itself, start in `docs`

## Quick Validation

From the repository root, these commands should succeed:

```bash
test -d apps/backend && echo backend_ok
test -d apps/frontend && echo frontend_ok
test -d packages/semantic_log_generator && echo package_ok
test -d docs && echo docs_ok
```

Expected result: four `*_ok` lines.
