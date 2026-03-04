# Backend (`apps/backend`)

This service exposes the centralized SEGB API and persists triples in Virtuoso.

## Responsibilities

- Accept TTL payloads from robots (`POST /ttl`)
- Store/retrieve graph data in Virtuoso
- Provide read-only query endpoint for analysis
- Provide shared-context resolution endpoints
- Expose health endpoints for operations

## Internal Structure

- `src/api`: request/response layer and route handlers
- `src/services`: use-case services (`LogService`, `SharedContextService`)
- `src/models`: infrastructure adapters (`VirtuosoModel`)
- `src/utils`: shared-context engine and helpers
- `src/core`: settings, security, logging
- `src/tools`: operational CLI tools (JWT generation)
- `api_info`: OpenAPI metadata/description files
- `static`: static assets used by backend package/distribution

## API Endpoints

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/healthz/live` | public | Liveness probe |
| `GET` | `/healthz/ready` | public | Readiness probe (includes Virtuoso status) |
| `GET` | `/auth/mode` | public | Current auth mode (`auth_enabled`) |
| `POST` | `/ttl/validate` | `admin` | Validate Turtle payload syntax/semantics before insertion |
| `POST` | `/ttl` | `logger`, `admin` | Insert Turtle payload into KG |
| `GET` | `/events` | `auditor`, `admin` | Export current KG as turtle |
| `POST` | `/query/validate` | `auditor`, `admin` | Validate read-only SPARQL query |
| `GET` | `/query` | `auditor`, `admin` | Run read-only SPARQL query |
| `POST` | `/ttl/delete_all` | `admin` | Clear graph content |
| `GET` | `/logs/server` | `admin` | Read backend server logs with filters |
| `POST` | `/shared-context/resolve` | `logger`, `admin` | Resolve canonical shared context URI |
| `POST` | `/shared-context/reconcile` | `admin` | Refresh unresolved contexts and auto-merge confident matches |
| `GET` | `/shared-context/review/pending` | `admin` | List unresolved contexts and pending manual review cases |
| `POST` | `/shared-context/review/{case_id}/accept` | `admin` | Accept one pending shared-context merge |
| `POST` | `/shared-context/review/{case_id}/reject` | `admin` | Reject one pending shared-context merge |
| `GET` | `/shared-context/stats` | `auditor`, `admin` | Resolver stats |

Security behavior:

- If `SECRET_KEY` is not set, backend runs in local no-auth mode.
- If `SECRET_KEY` is set, JWT is required and roles are enforced.

Optional API metadata file overrides:

- `API_INFO_FILE_PATH`: path to OpenAPI info JSON.
- `API_DESCRIPTION_FILE_PATH`: path to OpenAPI description markdown.
- `SERVER_LOG_DIR`: optional log directory override (default `/logs`; then `./logs`; final fallback `/tmp/segb-logs`).

## OpenAPI

- Swagger UI: `http://localhost:5000/docs`
- OpenAPI JSON: `http://localhost:5000/openapi.json`

## JWT (when `SECRET_KEY` is set)

SEGB expects an HS256 JWT with (at minimum):

- `username` (string)
- `roles` (list of strings)
- `exp` (unix timestamp, seconds)

Recommended (secure CLI, 1 hour):

```bash
PYTHONPATH=apps/backend/src ./.venv/bin/python -m tools.generate_jwt \
  --username demo_admin \
  --role admin \
  --expires-in 3600 \
  --json
```

By default the script reads `SECRET_KEY` from environment or asks for it with hidden prompt (no secret in command history).
Paste the token in the UI `/session` page or pass it as a bearer token to API calls.

## Run

### With Docker Compose (recommended)

From repository root:

```bash
docker compose -f docker-compose.yaml up --build
```

### Local development (backend only)

```bash
PYTHONPATH=apps/backend/src ./.venv/bin/python -m uvicorn main:app --reload --port 5000
```

## Tests

Backend-specific tests are in `apps/backend/tests`.

```bash
# Unit
PYTHONPATH=apps/backend/src:packages/semantic_log_generator/src ./.venv/bin/python -m unittest discover -s apps/backend/tests/unit -p 'test_*.py'

# Integration (backend API behavior)
PYTHONPATH=apps/backend/src:packages/semantic_log_generator/src ./.venv/bin/python -m unittest discover -s apps/backend/tests/integration -p 'test_*.py'
```

## Related Docs

- Shared-context internals: [`docs/backend/shared-context.md`](../../docs/backend/shared-context.md)
- Centralized deployment: [`docs/deployment/centralized.md`](../../docs/deployment/centralized.md)
