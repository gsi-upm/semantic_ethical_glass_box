# Quickstart

This guide gives you the shortest complete SEGB run. You will easily deploy the backend and frontend, load the UC-02 report-ready dataset,
and verify that the reports and graph explorer are showing real interaction data. The underlying script can be found in the GitHub repo as
`examples/simulations/run_use_case_02_report_ready_dataset.py`.

## Mental Model First

This guide uses UC-02, which is a simulation-like script that generate and ingest TTL in the SEGB with demo purposes. It populates the parts of the graph that make SEGB reports 
easy to understand: participants, messages, model usage, emotions, and robot state. 


## Before You Start

You need:

- Docker Engine and Docker Compose v2
- free host ports `5000`, `8080`, `8890`, and `1111`
- Python `3.10+`


If you do not yet have a local checkout, clone the repository and enter it now:

```bash
git clone https://github.com/gsi-upm/semantic_ethical_glass_box.git
cd semantic_ethical_glass_box
```

All commands below assume you are working from the repository root.

## Step 1: Create The Local Environment File

Copy the example file and set the Virtuoso password:

```bash
cp .env.example .env
```

Set at least this value:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Only `VIRTUOSO_PASSWORD` must be set for the first run. The value is used only when the `virtuoso_data` volume is
created for the first time, so changing it later does not update an existing database password. 

To keep the first run simple, it is recommended to keep authentication disabled by leaving `SECRET_KEY` empty in `.env`


## Step 2: Start The Centralized Stack

Run:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

This compose file starts the published backend and frontend images from GHCR. 

## Step 3: Wait For The Backend To Become Ready

Run:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
```

You want `{"live": true}` and `{"ready": true, "virtuoso": true}`. If readiness stays `false`, stop here and check
[Centralized Deployment](../operations/centralized-deployment.md).

## Step 4: Create A Small Python Environment For The Demo Loader

The next step uses one of the simulation scripts that ships with the repository. Create a small local environment for
it:

```bash
python3 -m venv .segb_env
./.segb_env/bin/python -m pip install -U pip
./.segb_env/bin/python -m pip install -e packages/semantic_log_generator
./.segb_env/bin/python -m pip install pydantic
```

`pydantic` is needed because some simulation flows validate backend JSON responses with typed contracts, but it is not part of the SEGB toolkit.

## Step 5: Load The UC-02 Demo Dataset

Let's load the UC-02 demo dataset. The script clears the configured graph before inserting new data, so treat it as a resettable demo loader rather than as an additive import.

If authentication is disabled (recommended):

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

If you chose protected mode and still need a token, use
[Authentication and JWT](../operations/authentication-and-jwt.md) first and come back when you have an `admin` token.

## Step 6: Open The UI

Open `http://localhost:8080/reports` and `http://localhost:8080/kg-graph`.

If authentication is enabled, open `http://localhost:8080/session` first and paste a token with the `admin` or `auditor` role.

## Step 7: Verify That The Run Is Meaningful

On `/reports`, you should see actual content such as
participants, conversation history, model usage, emotions, or robot state. On `/kg-graph`, you should see connected
nodes rather than an empty canvas, with links between robots, humans, activities, messages, and other entities from the
demo dataset. Check [Explore the Web UI](../guides/explore-the-web-ui.md) for better interpretability of the webpage. The backend should also export non-empty Turtle:

If authentication is disabled (recommended):

```bash
curl -s http://localhost:5000/events | head -n 20
```

If authentication is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

If that export is non-empty and the UI pages are populated, you have completed the full SEGB loop.

## If Something Does Not Work

- `ready=false` on `/healthz/ready`: the backend cannot talk to Virtuoso yet. Check `docker compose -f docker-compose.yaml logs -f amor-segb amor-segb-virtuoso`.
- `401/403` while loading the demo dataset: you enabled auth, but the script is missing a valid `admin` token.
- reports are empty: run the dataset loader again and refresh `/reports`.
- `Connection refused`: check whether the compose stack is still running with `docker compose -f docker-compose.yaml ps`.

## Next Steps

Now that you have a working stack, read [Core Concepts and Roles](core-concepts-and-roles.md), then continue with
[Publish Your First Log](../guides/publish-your-first-log.md) and
[Explore the Web UI](../guides/explore-the-web-ui.md).
