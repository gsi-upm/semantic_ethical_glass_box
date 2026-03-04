# Web Observability

## Objective

Use the SEGB web UI to validate ingestion, inspect graph data, and monitor backend behavior.

## Prerequisites

- Centralized stack running (see [Centralized Deployment](../deployment/centralized.md))
- Demo dataset loaded
- Optional JWT token if backend auth is enabled (`SECRET_KEY` set)

## Steps

### 1) Open UI

- Production compose: `http://localhost:8080`
- Development compose: `http://localhost:5173`

### 2) Configure session

Open `/session`.

- If auth is disabled, token is ignored.
- If auth is enabled, paste a JWT with required roles.

JWT generation (admin example):

```bash
PYTHONPATH=apps/backend/src SECRET_KEY="<32+ char secret>" python3 -m tools.generate_jwt \
  --username demo_admin \
  --role admin \
  --expires-in 3600 \
  --json
```

### 3) Use core pages

| Route | Purpose | Roles when auth enabled |
|---|---|---|
| `/reports` | Analytics dashboards | `auditor` or `admin` |
| `/kg-graph` | Graph exploration | `auditor` or `admin` |
| `/query` | Read-only SPARQL workbench | `auditor` or `admin` |
| `/logs/insert` | Validate/insert TTL manually | `admin` |
| `/shared-context` | Review and reconcile shared context | `admin` |
| `/system/logs` | Backend server logs | `admin` |
| `/health` | Liveness/readiness checks | public |

### 4) Recommended operator flow

1. Open `/reports` and refresh.
2. Open `/kg-graph` and check entity/edge growth.
3. Run one read-only query in `/query`.
4. If needed, inspect `/shared-context` and `/system/logs`.

## Validation

- Reports render non-empty charts.
- KG Graph renders nodes and edges.
- `/health` shows `ready=true`.

## Troubleshooting

- Empty reports: verify ingestion by checking `/kg-graph` and `GET /events`.
- `403` on a page: token missing required role.
- Session looks valid but requests fail: token expired; create a new one.
- Health shows `ready=false`: backend cannot reach Virtuoso.

## Next

- Runtime stack operations: [Centralized Deployment](../deployment/centralized.md)
- Resolver behavior: [Shared Context Resolution](../backend/shared-context.md)
