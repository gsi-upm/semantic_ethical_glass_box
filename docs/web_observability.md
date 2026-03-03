# Web UI: Observing Data

This page explains how to use the SEGB web UI to inspect logs already stored in Virtuoso.

## Access

- Production compose: `http://localhost:8080`
- Development compose: `http://localhost:5173`

## First Step: Session Page

Go to `/session`.

- If backend runs without `SECRET_KEY`, auth is disabled and token is ignored.
- If backend security is enabled (`SECRET_KEY` set), paste a JWT with required roles.

Recommended:

- If you want the full UI experience (Reports + Query + operations), use an `admin` token.

## Role Cheat Sheet

Backend roles are enforced only when `SECRET_KEY` is set.
If `SECRET_KEY` is missing/empty, backend grants all roles to every request.

- `admin`: full access (reports, query workbench, graph clear, shared-context review, server logs)
- `auditor`: read-only graph access and querying (`/events`, `/query`, `/query/validate`, `/shared-context/stats`)
- `logger`: write-oriented robot ingestion/resolution only (`POST /ttl`, `POST /shared-context/resolve`)

## Generate a JWT (local)

SEGB expects an HS256 JWT with (at minimum):

- `username` (string)
- `roles` (list of strings)
- `exp` (unix timestamp, seconds)

Recommended (secure CLI, 1 hour):

```bash
PYTHONPATH=apps/backend/src SECRET_KEY="<32+ char secret>" ./.venv/bin/python -m tools.generate_jwt \
  --username demo_admin \
  --role admin \
  --expires-in 3600 \
  --json
```

This command uses the project script at `apps/backend/src/tools/generate_jwt.py`.
If `SECRET_KEY` is not in environment, the script asks for it with hidden prompt.
The script enforces a minimum secret length of 32 chars by default.

Alternative (without exporting `SECRET_KEY` in shell history):

```bash
printf '%s' '<32+ char secret>' > /tmp/segb_jwt_secret.txt
PYTHONPATH=apps/backend/src ./.venv/bin/python -m tools.generate_jwt \
  --secret-file /tmp/segb_jwt_secret.txt \
  --username demo_admin \
  --role admin \
  --expires-in 3600 \
  --json
```

Paste the token into `/session`.

If you see `ModuleNotFoundError: No module named 'jwt'`, install PyJWT in your environment:

```bash
python -m pip install pyjwt
```

## Main Pages and What They Are For

| Route | Purpose | Backend Endpoints | Roles (when enabled) |
|---|---|---|---|
| `/reports` | High-level analytics dashboards (participants, ML usage, emotions, displacement) | `GET /query` | `auditor` or `admin` |
| `/kg-graph` | Interactive graph exploration with filters | `GET /events` | `auditor` or `admin` |
| `/logs/insert` | Insert raw TTL and inspect current KG turtle | `POST /ttl/validate`, `POST /ttl`, `GET /events` | `admin` |
| `/query` | Read-only SPARQL workbench | `POST /query/validate`, `GET /query` | `auditor` or `admin` |
| `/shared-context` | Shared-context diagnostics and manual review | `POST /shared-context/reconcile`, `GET /shared-context/review/pending`, `POST /shared-context/review/{case_id}/accept`, `POST /shared-context/review/{case_id}/reject`, `GET /shared-context/stats` | `admin` |
| `/system/logs` | Backend server logs with filters | `GET /logs/server` | `admin` |
| `/health` | Backend readiness/live checks | `GET /healthz/live`, `GET /healthz/ready` | public |

## Recommended Operator Workflow

1. Open `/session` and set token if needed.
2. Open `/reports` and click **Refresh reports**.
3. Open `/kg-graph` and inspect nodes/edges with filters.
4. Use `/query` for custom read-only checks.
5. Use `/shared-context` only for resolver diagnostics/operations.
6. Use `/system/logs` for backend operational troubleshooting.

## Quick Interpretation Tips

- If Reports are empty, verify data ingestion first (run the demo loader + check a `/kg-graph` snapshot; admins can also inspect `/logs/insert`).
- If KG Graph has too many nodes, use time filters and participant filter.
- If queries fail with 403, check token roles.
- If health says `ready=false`, check Virtuoso availability.
