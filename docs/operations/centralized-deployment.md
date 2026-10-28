# Centralized Deployment

## When To Use This Page

Use this page when you want to operate the full SEGB stack in Docker.

If your goal is simply to get SEGB running once and see data in the UI, start with
[Quickstart](../getting-started/quickstart.md). This page is for:

- choosing the right compose file
- understanding `.env`
- checking health
- stopping or resetting the stack safely

## What Gets Deployed

The centralized stack includes:

- the backend API
- the Virtuoso Knowledge Graph
- the SEGB web UI

## Before You Start

You need:

- Docker Engine `24.0+`
- Docker Compose plugin `v2.20+`
- free host ports `5000`, `8080`, `8890`, and `1111`
- to run commands from the repository root

Version check:

```bash
docker version --format '{{.Server.Version}}'
docker compose version
```

## Step 1: Choose Your Stack Mode

SEGB ships with two compose files.

### Production-Like Compose

Use this when you want the published images from GHCR:

- `docker-compose.yaml`

This is the best choice for demos, quick evaluation, and reproducible local runs. The web UI runs on port `8080` and set the API server on port `5000`

### Development Compose

Use this when you are editing the software itself and want hot reload:

- `docker-compose.dev.yml`

This mode runs the frontend on port `5173` and also set the API server on port `5000`

## Step 2: Create `.env`

Copy the example file:

```bash
cp .env.example .env
```

Set the required value:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Important details:

- this value initializes the Virtuoso DBA password only when the `virtuoso_data` volume is created for the first time,
- if the volume already exists, changing `VIRTUOSO_PASSWORD` later does not change the stored database password,
- if you really need a fresh password, you must recreate the volume with a destructive reset.

Optional secure mode:

```env
SECRET_KEY=replace-with-a-long-random-secret
```

If you set `SECRET_KEY`, SEGB enables JWT authentication and enforces roles. If you leave it empty, local auth is
disabled.

## Step 3: Start The Stack

Production-like stack:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

Development stack:

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

## Step 4: Check Health

Run:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
curl -s http://localhost:5000/auth/mode
```

Expected outputs:

- `{"live": true}`
- `{"ready": true, "virtuoso": true}`
- `{"auth_enabled": false}` or `{"auth_enabled": true}`

## Step 5: Load Data If You Want A Useful First Inspection

The stack can be healthy and still look empty. To make the UI meaningful, load some data.

The fastest option is the report-ready demo dataset used in [Quickstart](../getting-started/quickstart.md).

## Step 6: Open The Services

Typical URLs:

- Backend OpenAPI docs: `http://localhost:5000/docs`
- UI in production-like mode: `http://localhost:8080`
- UI in development mode: `http://localhost:5173`

## Stop And Reset

### Stop The Stack

Production-like mode:

```bash
docker compose -f docker-compose.yaml down
```

Development mode:

```bash
docker compose -f docker-compose.dev.yml down
```

### Reset Only The Graph Content

If auth is disabled:

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -d '{"user":"operator"}'
```

If auth is enabled:

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_jwt>" \
  -d '{"user":"operator"}'
```

This removes graph data but keeps the Virtuoso volume.

### Reset The Entire Virtuoso Volume

Production-like mode:

```bash
docker compose -f docker-compose.yaml down -v
```

This is destructive. It deletes the persisted database volume.

## Common Problems

- backend not ready: check `docker compose -f docker-compose.yaml logs -f amor-segb`
- Virtuoso not reachable: check `docker compose -f docker-compose.yaml logs -f amor-segb-virtuoso`
- Port conflicts: run `lsof -i :5000 -i :8080 -i :8890 -i :1111`
- Auth errors: read [Authentication and JWT](authentication-and-jwt.md)

## Related Pages

- [Quickstart](../getting-started/quickstart.md)
- [Authentication and JWT](authentication-and-jwt.md)
