# Centralized Deployment

## Objective

Deploy and operate the centralized SEGB stack in Docker: backend API, Virtuoso, and web UI.

## Prerequisites

- Docker Engine + Docker Compose v2
- Free host ports: `5000`, `8080`, `8890`, `1111`
- Python 3.10+ (only for simulation scripts)

## Authentication (optional)

Authentication is optional in SEGB:

- If `SECRET_KEY` is empty/unset, API authentication is disabled.
- If `SECRET_KEY` is set, JWT authentication is enabled and roles are enforced.

Token generation is explained in [Step 5: Generate JWT (only if auth enabled)](#5-generate-jwt-only-if-auth-enabled).  
You also have an operator-oriented version in [Web Observability](../operations/web-observability.md).

## Steps

### 1) Choose security mode

- `SECRET_KEY` empty/unset: authentication disabled.
- `SECRET_KEY` set: JWT required and roles enforced.

### 2) Create `.env`

```bash
cp .env.example .env
```

Set required value:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Optional secure mode:

```env
SECRET_KEY=replace-with-a-long-random-secret
```

### 3) Start services

Production compose pulls backend/frontend from GHCR by default:

- `ghcr.io/gsi-upm/semantic_ethical_glass_box/amor-segb`
- `ghcr.io/gsi-upm/semantic_ethical_glass_box/segb-ui`

Optional overrides in `.env`:

- `SEGB_BACKEND_IMAGE`
- `SEGB_FRONTEND_IMAGE`
- `SEGB_IMAGE_TAG` (default `latest`)

Production-like stack:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

Development stack:

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

### 4) Check health

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
```

Expected:

- `{"live": true}`
- `{"ready": true, "virtuoso": true}`

### 5) Generate JWT (only if auth enabled)

```bash
python3 -m pip install pyjwt
PYTHONPATH=apps/backend/src SECRET_KEY="<same_secret_as_env>" python3 -m tools.generate_jwt \
  --username demo_admin \
  --role admin \
  --expires-in 3600 \
  --json
```

Expected: JSON output with `token`.

### 6) Prepare simulation environment

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip
./.venv/bin/python -m pip install -e packages/semantic_log_generator
./.venv/bin/python -m pip install pydantic
```

### 7) Load report-ready dataset

Auth disabled:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Auth enabled:

```bash
./.venv/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

Warning: this clears the configured graph before inserting new triples.

### 8) Inspect results

- UI (prod): `http://localhost:8080`
- UI (dev): `http://localhost:5173`
- OpenAPI: `http://localhost:5000/docs`

### 9) Stop or reset

Stop:

```bash
docker compose -f docker-compose.yaml down
```

Reset persisted Virtuoso data (destructive):

```bash
docker compose -f docker-compose.yaml down -v
```

Reset graph content only (destructive):

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -d '{"user":"operator"}'
```

If auth is enabled, add:

```bash
-H "Authorization: Bearer <admin_jwt>"
```

## Validation

Run:

```bash
curl -s http://localhost:5000/events | head -n 20
```

Expected: non-empty Turtle output.

## Troubleshooting

- Backend not ready: check `docker compose -f docker-compose.yaml logs -f amor-segb`.
- Virtuoso not reachable: check `docker compose -f docker-compose.yaml logs -f amor-segb-virtuoso`.
- `401/403`: verify token roles (`admin`, `auditor`, `logger`) and token expiration.
- Port conflicts: run `lsof -i :5000 -i :8080 -i :8890 -i :1111`.

## Next

- UI operations: [Web Observability](../operations/web-observability.md)
- Shared-context behavior: [Backend Shared Context](../backend/shared-context.md)
