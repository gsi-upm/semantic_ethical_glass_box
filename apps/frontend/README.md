# Frontend (`apps/frontend`)

This project provides the SEGB web UI for operational observability.

## Responsibilities

- Show report dashboards from KG queries
- Explore KG visually
- Run read-only SPARQL queries
- Insert/view raw TTL for debugging
- Operate shared-context reconcile/review/stats endpoints
- Check backend health

## Structure

- `segb-ui`: Vue 3 + TypeScript application (source code)
- `infrastructure/nginx.conf`: runtime reverse proxy/static serving config
- `Dockerfile`: production image build (Vite build + Nginx runtime)

## Main Routes

| Route | Purpose |
|---|---|
| `/reports` | Analytics dashboard |
| `/kg-graph` | Interactive graph explorer |
| `/logs/insert` | Insert raw TTL and inspect graph snapshot |
| `/logs/delete` | Delete graph content (admin operation) |
| `/query` | SPARQL workbench (read-only) |
| `/shared-context` | Shared-context unresolved queue, manual merge review, and stats |
| `/system/logs` | Backend operational logs viewer |
| `/health` | Live/ready probes |
| `/session` | JWT token management in session storage |

## Run

### Local UI development

```bash
cd apps/frontend/segb-ui
npm ci
npm run dev
```

By default, UI runs on `http://localhost:5173`.

### Docker production image

From repository root:

```bash
docker compose -f docker-compose.yaml up --build
```

## Auth Note

- Token is optional only when backend runs without `SECRET_KEY`.
- If backend security is enabled, set JWT from `/session`.

## Related Docs

- Web usage guide: [`docs/operations/web-observability.md`](../../docs/operations/web-observability.md)
