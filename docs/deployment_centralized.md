# Centralized Deployment

This page explains how to deploy the centralized SEGB stack: backend API + Virtuoso + web UI.

## What Is Deployed

- `amor-segb`: FastAPI backend (`http://localhost:5000`)
- `amor-segb-virtuoso`: Virtuoso triple store (`http://localhost:8890`, port `1111`)
- `segb-ui`: web UI (`http://localhost:8080` in production compose)

## Prerequisites

- Docker Engine + Docker Compose v2
- Free ports: `5000`, `8080`, `8890`, `1111`
- Python 3.10+ local environment (only needed to run simulations from host)

## Security and Shared-Context (At a Glance)

| Topic | Behavior |
|---|---|
| Backend auth with `SECRET_KEY` set | JWT enforced, roles apply (`admin`, `logger`, `auditor`) |
| Backend auth with `SECRET_KEY` empty/unset | Auth disabled; every request is treated as all roles |
| Backend shared-context endpoints | Always available (`/shared-context/*`) |
| Robot-side shared-context resolution | Only active if robot code passes `shared_event_resolver=...` |
| Centralized `.env` vs robot runtime | Centralized `.env` config is **not** auto-read by distributed robot processes |

## Environment Variables

Use a `.env` file. Start from the example and set your own values:

```bash
cp .env.example .env
```

Main KG configuration:

```env
VIRTUOSO_ENDPOINT=http://amor-segb-virtuoso:8890/sparql-auth
VIRTUOSO_GRAPH_URI=http://amor-segb/events
VIRTUOSO_USER=dba
VIRTUOSO_PASSWORD=change-this-password
```

Notes:

- If you run the backend outside Docker, set `VIRTUOSO_ENDPOINT=http://localhost:8890/sparql-auth`.
- `VIRTUOSO_PASSWORD` is required by compose and backend startup.

Optional:

- `VERSION`: backend version string (used by compose)
- `SECRET_KEY`: enables JWT enforcement in backend (if missing/empty, auth is disabled and all roles are granted)
- `SERVER_LOG_DIR`: optional backend log directory override (defaults to `/logs`, then `./logs`, and finally `/tmp/segb-logs` if needed)
- `API_INFO_FILE_PATH`: optional override for OpenAPI metadata JSON file
- `API_DESCRIPTION_FILE_PATH`: optional override for OpenAPI description markdown file

Robot-side (distributed runtime, not centralized `.env`):

- `semantic_log_generator` does not auto-read env vars inside `SemanticSEGBLogger`.
- For shared-context online mode, robot launcher/code must pass `shared_event_resolver=...`.
- You can still build resolver from robot env explicitly (`build_http_shared_context_resolver_from_env`).
- See `docs/semantic_log_generator_usage.md` for exact code patterns.

## Start (Production-Like)

```bash
docker compose -f docker-compose.yaml up --build -d
```

## Start (Development)

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

Differences in dev mode:

- Frontend runs with Vite on `http://localhost:5173`
- Backend runs with autoreload

## Health Checks

```bash
curl http://localhost:5000/healthz/live
curl http://localhost:5000/healthz/ready
```

Expected:

- `/healthz/live` -> `{"live": true}`
- `/healthz/ready` -> `{"ready": true, "virtuoso": true}`

## Load Demo Data Into Virtuoso

First-time host setup (create a virtualenv + install the logger package used by simulations):

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip
./.venv/bin/python -m pip install -e packages/semantic_log_generator
./.venv/bin/python -m pip install pydantic
```

`pydantic` is required by UC-03/UC-04/UC-05 simulation contracts.
If you need to pin an interpreter, replace `python3` with `python3.10`, `python3.11`, or `python3.12`.

Run the report-ready simulation use case and publish to backend:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

⚠️ This clears the configured graph and inserts a full demo dataset.

If backend auth is enabled (`SECRET_KEY` set), provide a token with `admin` role (the loader calls `POST /ttl/delete_all`):

```bash
SEGB_API_TOKEN="<jwt>" ./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If your API is on a different host/port:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://<host>:<port> \
  --no-print-ttl
```

## Open the UI

- Production compose: `http://localhost:8080`
- Development compose: `http://localhost:5173`

## Stop

```bash
docker compose -f docker-compose.yaml down
```

Or dev:

```bash
docker compose -f docker-compose.dev.yml down
```

## Reset Data (Destructive)

Clear the configured graph content (keeps Virtuoso volume; requires `admin` when auth is enabled):

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"user":"operator"}'
```

Clear Virtuoso persisted data (removes the `virtuoso_data` volume):

```bash
docker compose -f docker-compose.yaml down -v
```

## Useful URLs

- Backend API: `http://localhost:5000`
- Backend OpenAPI docs: `http://localhost:5000/docs`
- Web UI (prod compose): `http://localhost:8080`
- Web UI server logs page (admin): `http://localhost:8080/system/logs`
- Virtuoso: `http://localhost:8890`
- Virtuoso SPARQL: `http://localhost:8890/sparql` (public) and `http://localhost:8890/sparql-auth` (digest auth)
- Virtuoso Conductor: `http://localhost:8890/conductor` (user `dba`, password = `VIRTUOSO_PASSWORD`)

## Troubleshooting

- Check container status:
  - `docker compose -f docker-compose.yaml ps`
  - `docker compose -f docker-compose.yaml logs -f amor-segb`
  - `docker compose -f docker-compose.yaml logs -f amor-segb-virtuoso`
- Port already in use:
  - Stop previous stacks: `docker compose -f docker-compose.yaml down`
  - Inspect host port usage: `lsof -i :5000` (or `:8080`, `:8890`, `:1111`)
- Backend `/healthz/ready` shows `ready=false`:
  - Verify Virtuoso is reachable: `curl -I http://localhost:8890/`
  - Check backend Virtuoso settings (`VIRTUOSO_ENDPOINT`, `VIRTUOSO_USER`, `VIRTUOSO_PASSWORD`)
- 401/403 in UI:
  - If `SECRET_KEY` is set, add a JWT in `/session` with required roles (see `docs/web_observability.md`).
