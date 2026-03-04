# Centralized Deployment

## Objective

Deploy and operate the centralized SEGB stack in Docker: backend API, Virtuoso, and web UI.

## Prerequisites

- Docker Engine + Docker Compose v2
- Free host ports: `5000`, `8080`, `8890`, `1111`
- Python 3.10+ (only for simulation scripts)
- Run commands from repository root (`semantic_ethical_glass_box/`)

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

Important:

- This sets the Virtuoso DBA password when the `virtuoso_data` volume is created for the first time.
- If you change `VIRTUOSO_PASSWORD` later and keep the same volume, Virtuoso keeps the old password.
- To apply a new password, recreate the volume (destructive): `docker compose -f docker-compose.yaml down -v`.

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
python3 -m pip install pyjwt fastapi
PYTHONPATH=apps/backend/src SECRET_KEY="<same_secret_as_env>" python3 -m tools.generate_jwt \
  --username demo_admin \
  --role admin \
  --expires-in 3600 \
  --json
```

Expected: JSON output with `token`.  
Note: `SECRET_KEY` must be at least 32 characters for this tool.

### 6) Inspect services

- UI (prod): `http://localhost:8080`
- UI (dev): `http://localhost:5173`
- OpenAPI: `http://localhost:5000/docs`

### 7) Stop or reset

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

## Validation

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

## Troubleshooting

- Backend not ready: check `docker compose -f docker-compose.yaml logs -f amor-segb`.
- Virtuoso not reachable: check `docker compose -f docker-compose.yaml logs -f amor-segb-virtuoso`.
- `401/403`: verify token roles (`admin`, `auditor`, `logger`) and token expiration.
- Port conflicts: run `lsof -i :5000 -i :8080 -i :8890 -i :1111`.

## Next

- Continue to Step 2: [Install `semantic_log_generator`](../package/installation.md)
