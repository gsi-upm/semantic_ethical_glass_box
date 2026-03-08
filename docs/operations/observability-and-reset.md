# Observability And Reset

## What This Page Is For

This page is about practical system checks. Use it when the stack is running but you need to answer questions such as:

- is the backend alive?
- is Virtuoso reachable?
- why does the UI look empty?
- where do I inspect logs?
- what exactly gets deleted when I reset something?

## Health Checks

These are the three quickest backend checks:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
curl -s http://localhost:5000/auth/mode
```

How to read them:

- `/healthz/live` tells you whether the backend process is alive,
- `/healthz/ready` tells you whether the backend is ready to work with Virtuoso,
- `/auth/mode` tells you whether JWT auth is enabled.

## Useful UI Pages For Inspection

The UI itself is part of your observability toolbox.

### `/health`

Use this page for quick live and ready checks from the browser.

### `/reports`

Use this when you want to know whether the current graph is rich enough to drive meaningful dashboards.

### `/kg-graph`

Use this when you need to inspect relationships directly instead of only seeing aggregated report cards.

### `/system/logs`

Use this when you need backend server evidence from the UI.

## Docker-Side Checks

Check container state:

```bash
docker compose -f docker-compose.yaml ps
```

Follow backend logs:

```bash
docker compose -f docker-compose.yaml logs -f amor-segb
```

Follow Virtuoso logs:

```bash
docker compose -f docker-compose.yaml logs -f amor-segb-virtuoso
```

These checks usually answer most startup and readiness problems.

## Backend Server Logs

SEGB also exposes backend logs through:

- API: `GET /logs/server`
- UI: `/system/logs`

This is useful when the service is running but a specific operation keeps failing and you want a filtered view of the
backend messages.

## Reset Options

Not all resets are the same. This distinction matters.

### Reset The Graph Only

This removes graph content but keeps the Virtuoso volume.

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

You can also do this from the UI at `/logs/delete`.

### Reset The Virtuoso Volume

This removes the persisted database entirely:

```bash
docker compose -f docker-compose.yaml down -v
```

Use this only when you truly want a clean storage state, for example after changing the initial Virtuoso password or when
you want to discard the entire local dataset.

## Recovery Playbooks

### The UI Opens But Reports Are Empty

Most common cause: the graph does not contain the expected report semantics yet.

Typical fix: reload the UC-02 demo dataset from Quickstart.

### `/healthz/ready` Returns `false`

Most common cause: the backend cannot reach Virtuoso.

What to check:

- backend logs,
- Virtuoso logs,
- whether the compose stack is fully up.

### You Get `401` Or `403`

Most common cause: the token is missing, expired, or has the wrong role.

Read [Authentication and JWT](authentication-and-jwt.md).

### You Changed `VIRTUOSO_PASSWORD` But It Still Does Not Work

Most common cause: the old `virtuoso_data` volume is still present.

If you really need the new password to take effect, reset the volume with `down -v`.

## Related Pages

- [Centralized Deployment](centralized-deployment.md)
- [Authentication and JWT](authentication-and-jwt.md)
- [Explore the Web UI](../guides/explore-the-web-ui.md)
