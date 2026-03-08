# Quickstart

## What You Will Do

This guide gives you the shortest complete SEGB run:

1. start the backend, Virtuoso, and the web UI,
2. load a ready-made demo dataset,
3. open the UI,
4. confirm that SEGB is really working.

If this is your first contact with the project, this is the right place to start.

## Before You Start

You need:

- Docker Engine and Docker Compose v2
- free host ports `5000`, `8080`, `8890`, and `1111`
- Python `3.10+`
- to run commands from the repository root

For the fastest first run, keep authentication disabled. In practice that means leaving `SECRET_KEY` empty in `.env`.
You can enable auth later by following [Authentication and JWT](../operations/authentication-and-jwt.md).

## Step 1: Create Your Local Environment File

Copy the example file:

```bash
cp .env.example .env
```

Set at least this value:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Two details matter here:

- this password is used when the `virtuoso_data` volume is created for the first time,
- if that volume already exists, changing `VIRTUOSO_PASSWORD` later does not update the old database password.

If you want the easiest first run, leave `SECRET_KEY` commented out for now.

## Step 2: Start The Centralized Stack

Run:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

This compose file starts the published backend and frontend images from GHCR. If you want hot reload while editing the
software itself, use `docker-compose.dev.yml` later. For a first run, the production-like compose is simpler.

## Step 3: Check That The Backend Is Ready

Run:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
```

Expected output:

- `{"live": true}`
- `{"ready": true, "virtuoso": true}`

If `ready` is `false`, stop here and check [Observability and Reset](../operations/observability-and-reset.md).

## Step 4: Prepare A Small Python Environment For The Demo Loader

The next step uses one of the simulation scripts that ships with the repository. Create a small local environment for it:

```bash
python3 -m venv .segb_env
./.segb_env/bin/python -m pip install -U pip
./.segb_env/bin/python -m pip install -e packages/semantic_log_generator
./.segb_env/bin/python -m pip install pydantic
```

Why `pydantic`? Some of the simulation flows validate backend JSON responses with typed contracts, so the demo tooling
needs it even though the shortest package example does not.

## Step 5: Load The Demo Dataset

This is the moment when SEGB becomes easy to understand. Instead of writing your own logger first, you load a dataset
that already contains participants, messages, model usage, emotions, and robot state.

Warning: this script clears the configured graph before inserting new data.

If authentication is disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If authentication is enabled, use an `admin` token:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

If you chose secure mode and still need a token, use [Authentication and JWT](../operations/authentication-and-jwt.md)
first, then come back here.

## Step 6: Open The UI

Open these pages in your browser:

- reports: `http://localhost:8080/reports`
- Knowledge Graph explorer: `http://localhost:8080/kg-graph`

If authentication is enabled, first open:

- session page: `http://localhost:8080/session`

Then paste a token with the right role for the page you want to visit.

## What Success Looks Like

At this point you should be able to:

- open `/reports` and see non-empty cards and charts,
- open `/kg-graph` and see nodes and edges,
- export non-empty Turtle through the backend.

To check the export:

If authentication is disabled:

```bash
curl -s http://localhost:5000/events | head -n 20
```

If authentication is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

Expected result: non-empty Turtle output.

## A Simple Mental Model

If you want a quick intuition for what just happened:

- the simulation script generated RDF logs,
- the backend stored them in Virtuoso,
- the UI queried that graph and turned the results into reports and graph views.

That is the full SEGB loop.

## If Something Does Not Work

- `ready=false` on `/healthz/ready`: the backend cannot talk to Virtuoso yet. Check `docker compose -f docker-compose.yaml logs -f amor-segb amor-segb-virtuoso`.
- `401/403` while loading the demo dataset: you enabled auth, but the script is missing a valid `admin` token.
- reports are empty: run the dataset loader again and refresh `/reports`.
- `Connection refused`: check whether the compose stack is still running with `docker compose -f docker-compose.yaml ps`.

## Next Steps

Now that you have seen the full product working, the most useful next pages are:

1. [Core Concepts and Roles](core-concepts-and-roles.md)
2. [Publish Your First Log](../guides/publish-your-first-log.md)
3. [Explore the Web UI](../guides/explore-the-web-ui.md)
