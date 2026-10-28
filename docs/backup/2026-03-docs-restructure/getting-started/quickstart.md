# Quickstart

## Objective

Run SEGB end-to-end in the shortest possible path: backend + Virtuoso + UI + demo dataset.

## Prerequisites

- Docker Engine + Docker Compose v2
- Free host ports: `5000`, `8080`, `8890`, `1111`
- Python 3.10+
- Run commands from repository root (`semantic_ethical_glass_box/`)

## Steps

### 1) Configure environment

```bash
cp .env.example .env
```

Set at least:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Important:

- This initializes the Virtuoso DBA password only on first volume creation.
- If you already have `virtuoso_data`, changing `VIRTUOSO_PASSWORD` in `.env` does not update the existing DB password.

If auth is enabled (`SECRET_KEY` set), generate a token as documented in
[Centralized Deployment: Step 5](../deployment/centralized.md#5-generate-jwt-only-if-auth-enabled).

### 2) Start centralized services

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

### 3) Check backend readiness

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
```

Expected:

- `{"live": true}`
- `{"ready": true, "virtuoso": true}`

### 4) Prepare Python environment

```bash
python3 -m venv .segb_env
./.segb_env/bin/python -m pip install -U pip
./.segb_env/bin/python -m pip install -e packages/semantic_log_generator
./.segb_env/bin/python -m pip install pydantic
```

### 5) Load demo dataset

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

Warning: this flow clears the configured graph before insertion.

### 6) Open the UI

- Reports: `http://localhost:8080/reports`
- KG Graph: `http://localhost:8080/kg-graph`

## Validation

If auth is disabled:

```bash
curl -s http://localhost:5000/events | head -n 20
```

If auth is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

Expected: non-empty Turtle output.

## Troubleshooting

- `ready=false` on `/healthz/ready`: check `docker compose -f docker-compose.yaml logs -f amor-segb amor-segb-virtuoso`.
- `401/403` while loading demo data: provide a valid `--token` with `admin` role.
- Empty reports: run the dataset load step again and refresh `/reports`.
