# API And Roles

## What This Page Is

This is the compact reference for the backend routes and the UI access model.

## Authentication Rule

SEGB behaves differently depending on `SECRET_KEY`.

- if `SECRET_KEY` is empty or unset, auth is disabled and the backend grants all roles locally,
- if `SECRET_KEY` is set, the backend expects a valid HS256 JWT and enforces roles.

## Backend Endpoints

| Method | Path | Role when auth is enabled | Purpose |
|---|---|---|---|
| `GET` | `/healthz/live` | public | Liveness probe |
| `GET` | `/healthz/ready` | public | Readiness probe, including Virtuoso status |
| `GET` | `/auth/mode` | public | Reports whether auth is enabled |
| `POST` | `/ttl/validate` | `admin` | Validate Turtle before insertion |
| `POST` | `/ttl` | `logger` or `admin` | Insert Turtle into the graph |
| `GET` | `/events` | `auditor` or `admin` | Export the current graph as Turtle |
| `GET` | `/query` | `auditor` or `admin` | Execute a read-only SPARQL query |
| `POST` | `/query/validate` | `auditor` or `admin` | Validate a read-only SPARQL query |
| `POST` | `/ttl/delete_all` | `admin` | Delete graph content |
| `GET` | `/logs/server` | `admin` | Read backend server logs |
| `POST` | `/shared-context/resolve` | `logger` or `admin` | Resolve or create a shared context |
| `POST` | `/shared-context/reconcile` | `admin` | Re-run backend-side shared-context reconciliation |
| `GET` | `/shared-context/stats` | `auditor` or `admin` | Shared-context summary metrics |
| `GET` | `/shared-context/review/pending` | `admin` | Pending review queue |
| `POST` | `/shared-context/review/{case_id}/accept` | `admin` | Accept a shared-context merge |
| `POST` | `/shared-context/review/{case_id}/reject` | `admin` | Reject a shared-context merge |

## UI Routes

| Route | Role when auth is enabled | Purpose |
|---|---|---|
| `/reports` | `auditor` or `admin` | Dashboards and summaries |
| `/kg-graph` | `auditor` or `admin` | Visual graph exploration |
| `/query` | `auditor` or `admin` | Read-only SPARQL workbench |
| `/logs/insert` | `admin` | Manual Turtle validation and insert |
| `/logs/delete` | `admin` | Graph deletion from the UI |
| `/shared-context` | `admin` | Shared-context review console |
| `/system/logs` | `admin` | Backend system logs in the UI |
| `/health` | public | Browser-side live and ready checks |
| `/session` | public | JWT session management |

## Request Shape Cheatsheet

These are the request shapes you will use most often.

### Validate Turtle

`POST /ttl/validate`

```json
{
  "ttl_content": "@prefix ex: <https://example.org/> .",
  "user": "robot_or_operator"
}
```

### Insert Turtle

`POST /ttl`

```json
{
  "ttl_content": "...",
  "user": "robot_or_operator"
}
```

### Validate Query

`POST /query/validate`

```json
{
  "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
}
```

### Delete Graph Content

`POST /ttl/delete_all`

```json
{
  "user": "operator"
}
```

## Common Permission Patterns

Use these simple rules when deciding which role you need:

- If you publish logs, use `logger`
- If you inspect and query data, use `auditor`
- If you operate, validate, delete, or review, use `admin`

## Related Pages

- [Authentication and JWT](../operations/authentication-and-jwt.md)
- [Explore the Web UI](../guides/explore-the-web-ui.md)
- [Shared Context Workflow](../guides/shared-context-workflow.md)
