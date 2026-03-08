# Centralized Deployment

## Objective

Deploy and operate the centralized SEGB stack in Docker: backend API, Virtuoso, and web UI.

## Prerequisites

- Docker Engine `24.0+` (tested with `27.3.1`)
- Docker Compose plugin `v2.20+` (tested with `v2.29.7`)
- Free host ports: `5000`, `8080`, `8890`, `1111`
- Python `3.10+` (only for simulation scripts)
- Run commands from the repository root (directory that contains `docker-compose.yaml`)

Version check:

```bash
docker version --format '{{.Server.Version}}'
docker compose version
```

## Authentication (optional)

Authentication is optional in SEGB:

- If `SECRET_KEY` is empty/unset, API authentication is disabled.
- If `SECRET_KEY` is set, JWT authentication is enabled and roles are enforced.

Token generation is explained in [Step 5: Generate JWT](#5-generate-jwt-only-if-auth-enabled).  

## Steps

### 1) Choose security mode

- `SECRET_KEY` empty/unset: authentication disabled.
- `SECRET_KEY` set: authentication enabled, JWT required and roles enforced.

### 2) Create `.env`

```bash
cp .env.example .env
```

Set required value:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Important:

- This sets the Virtuoso DBA password when the `virtuoso_data` volume is created for the first time.
- If you change `VIRTUOSO_PASSWORD` later and keep the same volume, Virtuoso keeps the old password.
- To apply a new password, recreate the volume (destructive): `docker compose -f docker-compose.yaml down -v`.

Optional secure mode:

```env
# JWT signing secret used by backend (this is NOT a JWT token)
SECRET_KEY=replace-with-a-long-random-secret
```

Generate a random value (recommended):

```bash
openssl rand -hex 32
```

### 3) Start services

Production compose pulls backend/frontend from GHCR:

- `ghcr.io/gsi-upm/semantic_ethical_glass_box/amor-segb`
- `ghcr.io/gsi-upm/semantic_ethical_glass_box/segb-ui`

Production-like stack:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

Development stack (for modifying software):

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

Install dependencies for the token tool:

```bash
python3 -m pip install pyjwt fastapi
```

Run token generation:

```bash
(
  cd apps/backend/src
  SECRET_KEY="<same_secret_value_as_.env>" python3 -m tools.generate_jwt \
    --username demo_admin \
    --role admin \
    --expires-in 3600 \
    --json
)
```

Expected: JSON output with `token`.

Important:

- `SECRET_KEY` here must be the same signing secret defined in `.env` (not the token itself).
- `SECRET_KEY` must be at least 32 characters for this tool.

### 6) Prepare simulation environment (to insert demo data)

```bash
python3 -m venv .segb_env
./.segb_env/bin/python -m pip install -U pip
./.segb_env/bin/python -m pip install -e packages/semantic_log_generator
./.segb_env/bin/python -m pip install pydantic
```

### 7) Load demo data into the graph

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Auth enabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

Warning: this flow clears the configured graph before inserting new triples.

### 8) Inspect services

- UI (prod): `http://localhost:8080`
- UI (dev): `http://localhost:5173`
- OpenAPI: `http://localhost:5000/docs`

### 9) Stop or reset (optional, do this after validation)

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

If auth is enabled, use:

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_jwt>" \
  -d '{"user":"operator"}'
```

You can do the same reset from the web UI (`/logs/delete`):

- Open `http://localhost:8080/logs/delete`
- Type `DELETE`
- Click `Delete all TTLs`

Reference screenshot:

![SEGB Delete TTLs](../assets/screenshots/ui-delete-ttls.png)

## Validation

Run this validation before Step 9 reset actions (`down -v` or `/ttl/delete_all`), because those operations clear persisted data.

Run:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
curl -s http://localhost:5000/auth/mode
```

Expected:

- `{"live": true}`
- `{"ready": true, "virtuoso": true}`
- `{"auth_enabled": false}` or `{"auth_enabled": true}`

If you ran Step 7 and did not reset yet, validate graph data is present:

Auth disabled:

```bash
curl -s http://localhost:5000/events | head -n 20
```

Auth enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

Expected: non-empty Turtle output.

If you already ran a reset action in Step 9, empty output is expected until you run Step 7 again.

## Troubleshooting

- Backend not ready: check `docker compose -f docker-compose.yaml logs -f amor-segb`.
- Virtuoso not reachable: check `docker compose -f docker-compose.yaml logs -f amor-segb-virtuoso`.
- `401/403`: verify token roles (`admin`, `auditor`, `logger`) and token expiration.
- Port conflicts: run `lsof -i :5000 -i :8080 -i :8890 -i :1111`.
- Empty reports/graph: run Step 7 again and refresh `/reports` and `/kg-graph`.

## Next

- Continue to Step 2: [Install `semantic_log_generator`](../package/installation.md)
