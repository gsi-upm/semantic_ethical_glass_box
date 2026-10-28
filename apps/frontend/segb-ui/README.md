# SEGB UI (Vue 3)

Production-oriented frontend aligned with the current backend API.

## Goals

- Keep a clean, modular structure (`app`, `core`, `features`, `shared`).
- Prioritize report-oriented analysis views from the notebook.
- Keep API integration explicit and typed.

## Project Structure

```text
src/
  app/
    layout/
    router.ts
  core/
    api/
    auth/
    config/
  features/
    reports/
    logs/
    query/
    shared-context/
    health/
    session/
  shared/
    charts/
    rdf/
    ui/
    utils/
```

## Main Routes

- `/reports`: notebook-style analytics dashboard
- `/kg-graph`: interactive KG graph explorer
- `/logs/insert`: insert TTL and inspect KG snapshot
- `/logs/delete`: clear KG graph (admin-only operation)
- `/query`: read-only SPARQL workbench
- `/shared-context`: resolver/reconcile/stats console
- `/system/logs`: backend server logs viewer
- `/health`: backend probes
- `/session`: bearer token setup

## Backend Match

The UI maps directly to these backend endpoints:

- `GET /healthz/live`
- `GET /healthz/ready`
- `GET /auth/mode`
- `POST /ttl/validate`
- `POST /ttl`
- `GET /events`
- `POST /query/validate`
- `GET /query`
- `POST /ttl/delete_all`
- `POST /shared-context/resolve`
- `POST /shared-context/reconcile`
- `GET /shared-context/review/pending`
- `POST /shared-context/review/{case_id}/accept`
- `POST /shared-context/review/{case_id}/reject`
- `GET /shared-context/stats`
- `GET /logs/server`

## Security Notes

- Token is stored in `sessionStorage` (not persisted across browser restarts).
- Authorization header is attached only when token exists.
- Query workbench blocks non-read-only verbs client-side; backend still enforces policy.
- No HTML injection rendering is used in report/result components.

## Dev

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Testing

Frontend unit/component tests are local to this project:

- Location: `tests/unit/**`
- Runner: Vitest (`npm run test` / `npm run test:run`)

This repository keeps cross-project integration tests in the root `tests/` folder, while project-specific tests stay inside each app/package.
