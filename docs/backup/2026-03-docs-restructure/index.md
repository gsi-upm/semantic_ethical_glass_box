# Semantic Ethical Glass Box (SEGB)

<p align="center">
  <img src="assets/segb-logo.png" alt="SEGB logo" width="520" />
</p>

SEGB is a semantic logging stack for human–robot interactions.
Its goal is to **record events and interactions as structured knowledge (RDF)**, enable **ethical analysis and transparency**, and support **inspection and auditing** through a web interface.

## Architecture (high-level)

> **TODO (required to render the figure):** add the architecture diagram as
> `docs/assets/segb-architecture.png` (the image included in your message).
> Once the file exists at that path, include it on this page with:
>
> `![SEGB architecture](assets/segb-architecture.png)`

The high-level flow is:

1. One or more robots run a **log generator module** during interactions with humans.
2. Those logs are published to a **centralized deployment** (backend + Knowledge Graph storage).
3. An **auditor** (or operator) uses the **web interface** to review data and view reports.

## Modules and what they are for

### 1) Log Generator Module (on the robot)

**What it is:** the component that generates semantic logs (RDF) from events already observed by the robot software stack.

**In this repository:** the log generator is implemented as the Python package `semantic_log_generator` (see `packages/semantic_log_generator`).

**What it is for:**

- Build an RDF graph with interaction data.
- Serialize the log (for example, as Turtle/TTL).
- Publish it to the centralized backend (for example, using `SEGBPublisher` to `POST /ttl`).

> **Note:** this module does not read sensors or orchestrate ROS by itself. Robot software must provide the facts (ASR output, detections, state, etc.) and decide when to log and publish.

### 2) Storage Module / Knowledge Graph (centralized deployment)

**What it is:** persistent storage of logs as RDF triples inside a Knowledge Graph (KG).

**In this repository:**

- Virtuoso acts as the triple store (service `amor-segb-virtuoso` in `docker-compose.yaml`).
- The backend ingests logs and persists triples into the configured graph.

**What it is for:**

- Keep a persistent, queryable repository of RDF logs for inspection and auditing.
- Enable SPARQL querying (for example, via backend API endpoints).

### 3) Auditing Module (Web Interface)

**What it is:** the web interface used to inspect logs (and derived outputs) from an operator/auditor perspective.

**In this repository:** `segb-ui` (frontend service in `docker-compose.yaml`).

**What it is for:**

- Visually explore the Knowledge Graph.
- View and review **reports** derived from stored data.
- Use operational pages (for example, health checks and server logs).

## Concepts: report and audit

### Report

In SEGB, a **report** is a UI view (for example, the `Reports Dashboard`) that presents structured/aggregated information derived from RDF logs stored in the KG.

In the UI, reports are available at:

- `/reports` (requires `auditor` or `admin` role when authentication is enabled)

### Audit

An **audit** in SEGB consists of reviewing:

- The recorded data (RDF logs) and their traceability.
- The reports that summarize data for inspection.
- Operational evidence (for example, backend logs) when needed.

In authenticated mode (`SECRET_KEY` configured), SEGB uses roles (for example, `auditor`, `logger`, `admin`) to control what actions each user can perform.

## Use case example (with the example reports)

**Case:** an auditor wants to review an example interaction and confirm (a) who participated and (b) what model usage/activities are recorded.

### Step 1: load the report-ready dataset (example)

Prerequisites:

- Centralized stack running (see [Centralized Deployment](deployment/centralized.md)).
- Python environment with the package installed (see [Installation](package/installation.md)).

> **Warning:** this flow clears the configured graph before inserting new triples.

Auth disabled:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

Auth enabled (requires `admin`):

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

### Step 2: open the reports dashboard

1. Open `http://localhost:8080/reports`.
2. Click `Refresh reports`.

Expected: the reports dashboard renders non-empty content. The reference screenshot below shows sections labeled:

- `Report 1: Participants`
- `Report 2: ML Usage`

Reference screenshot:

![SEGB Reports Dashboard](assets/screenshots/ui-reports.png)

## Tutorials

Follow these pages in order for a first-time setup:

1. [Quickstart](getting-started/quickstart.md)
2. [Centralized Deployment (Backend + Frontend)](deployment/centralized.md)
3. [Install `semantic_log_generator`](package/installation.md)
4. [Post Your First Log to SEGB](package/usage.md)
5. [ROS4HRI Robot Simulator Tutorial](package/ros4hri-integration.md)
6. [Shared Context Tutorial](backend/shared-context.md)
7. [Validation Checklist (Optional)](getting-started/segb-features.md)

## Web UI

- [Reports Dashboard](web-ui/reports.md)
- [Web Observability (UI Tour)](operations/web-observability.md)

## Reference

- [Ontology (SEGB)](reference/ontology.md)
- [Ontology (SEGB)](reference/ontology.md)
- [Monorepo Structure](reference/monorepo-structure.md)
