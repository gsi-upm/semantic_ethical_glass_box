# AMOR-SEGB Monorepo

SEGB is a centralized semantic logging stack for robot interactions:

- robots generate RDF logs with `semantic_log_generator`
- backend ingests and stores triples in Virtuoso
- web UI helps inspect reports, graph structure, shared-context resolution, and backend server logs

This repository contains the centralized SEGB stack (backend, frontend, logger package, docs, tests).

## Repository Structure (Quick View)

| Path | Purpose |
|---|---|
| `apps/backend` | FastAPI backend, API metadata, Dockerfile |
| `apps/frontend` | Vue 3 web UI + frontend Docker packaging |
| `packages/semantic_log_generator` | Reusable Python package for semantic RDF logging |
| `examples/mocks` | Mock robot behaviors used by simulations |
| `examples/simulations` | End-to-end simulation use cases (UC-01 .. UC-05) |
| `examples/notebooks` | Tutorial notebooks mapped to simulation use cases |
| `examples/data` | Input data for demos |
| `docs` | Documentation intended for Read the Docs |
| `apps/backend/tests` | Backend unit + backend integration tests |
| `packages/semantic_log_generator/tests` | `semantic_log_generator` unit tests |
| `examples/simulations/tests` | Simulation integration tests (use-case flows) |
| `tests` | Global/cross-project tests (reserved scope) |
| `docker-compose.yaml` | Production-like centralized deployment |
| `docker-compose.dev.yml` | Development deployment with hot reload |

Notes:

- `tests/` is reserved for cross-project checks; project-specific tests live with each project.
- External robot runtime workspaces are local-only and are not part of the versioned source tree.

## Quick Start (Full Flow)

### 0) Configure environment

Docker Compose has sensible defaults. In most cases, you only need to set `VIRTUOSO_PASSWORD` in `.env`:

```bash
cp .env.example .env
```

Important:

- This `.env` config applies to centralized services (backend/web/virtuoso).
- Distributed robot processes running `semantic_log_generator` do not auto-read this centralized `.env`.
- If `SECRET_KEY` is empty/unset, backend auth is disabled and all roles are effectively open.

### 1) Start the centralized stack

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

### 2) Create a Python environment for simulations (one-time)

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip
./.venv/bin/python -m pip install -e packages/semantic_log_generator
./.venv/bin/python -m pip install pydantic
```

SEGB supports Python 3.10, 3.11, and 3.12 (3.10+ recommended for ROS2 compatibility).
`pydantic` is required by UC-03/UC-04/UC-05 simulation contracts.
If you need to pin an interpreter, replace `python3` with `python3.10`, `python3.11`, or `python3.12`.

### 3) Publish a complete demo dataset to Virtuoso

⚠️ This demo loader clears the configured graph before inserting new triples.

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If the API is not at `localhost:5000`, override `--publish-url`.

For the full use-case matrix and commands, see [`examples/simulations/README.md`](examples/simulations/README.md).

### 4) Open the UI and inspect results

- Reports dashboard: `http://localhost:8080/reports`
- KG graph explorer: `http://localhost:8080/kg-graph`
- System logs (admin): `http://localhost:8080/system/logs`
- Backend OpenAPI docs: `http://localhost:5000/docs`

## UI Screenshots

### Reports Dashboard

![SEGB Reports Dashboard](docs/assets/screenshots/ui-reports.png)

### KG Graph Explorer

![SEGB KG Graph Explorer](docs/assets/screenshots/ui-kg-graph.png)

## Detailed Documentation

Detailed deployment, package usage, web usage, and internal TTL generation docs are available at:

- `https://segb.readthedocs.io/en/latest/`
- Local docs entry point: [`docs/index.md`](docs/index.md)

To serve docs locally:

```bash
./.venv/bin/python -m pip install -r docs/requirements.txt
./.venv/bin/mkdocs serve
```
