# Reports Dashboard (Web UI)

## Objective

Use the SEGB web UI to inspect the built-in **reports** and understand what data each report requires from the Knowledge
Graph.

## Prerequisites

- Centralized stack running (see [Centralized Deployment](../deployment/centralized.md)).
- Data loaded in the Knowledge Graph.
  - Recommended: load the report-ready demo dataset (UC-02).
- If authentication is enabled (`SECRET_KEY` set):
  - A JWT with role `auditor` or `admin` (the `/reports` page is restricted to those roles).

## Open and refresh reports

1. Open `http://localhost:8080/reports`.
2. Click **Refresh reports**.

Expected: the page renders one card per report. If a query fails, you will see a warning banner identifying which report
block could not be loaded.

![SEGB Reports Dashboard](../assets/screenshots/ui-reports.png)

## What a “report” means in SEGB

In the SEGB UI, a **report** is a deterministic view derived from the RDF logs stored in the Knowledge Graph.

Operationally:

- The UI runs a fixed set of **read-only SPARQL `SELECT` queries** against the backend `GET /query` endpoint.
- The UI converts the query result rows into tables and charts.

If your dataset does not include the required RDF classes/properties for a report, that report will render as empty.

## Report catalog (what each report shows)

This section describes what each report card is built from, based on the SPARQL queries used by the UI.

### Report 1: Participants

Shows:

- Humans (participants) and the robots they interacted with.
- Robots (participants) and the humans/robots they interacted with.

Requires the graph to include:

- Activities typed as `segb:LoggedActivity`.
- Performer links `segb:wasPerformedBy` from activities to robot resources (typed `oro:Robot`).
- Human resources typed as `oro:Human`, with optional display name `foaf:firstName`.
- Human linkage can come from shared events (`schema:about`), explicit requests (`segb:wasRequestedBy`), or ownership (`oro:belongsTo`).

### Report 2: ML Usage

Shows:

- Activities that declare an ML model usage, including model label/version and (when present) dataset/evaluation score.
- One row per activity/model context, with activity types aggregated in the same cell to avoid duplicate rows.

Requires the graph to include:

- `segb:LoggedActivity` activities with `segb:usedMLModel`.
- Timestamps from `prov:startedAtTime` (optional but improves ordering).
- Optional MLS patterns (`mls:Run`, `mls:hasInput`, `mls:hasOutput`, `mls:ModelEvaluation`) to render dataset and score.

### Report 3: Temporal Emotions

Shows:

- Emotion intensity timelines, grouped by:
  - Human targets (“Humans” chart selector), and
  - Robot targets (“Robots” chart selector).
- Tooltip shows both intensity and model confidence; these are independent values.
- If the dataset has no robot-target emotion analyses, the robot chart stays empty.

Requires the graph to include:

- Activities typed as `onyx:EmotionAnalysis` (and also `segb:LoggedActivity`).
- Emotion containers linked from the activity via `segb:producedEntityResult` (or `prov:generated` as fallback).
- Emotions modeled with:
  - `onyx:hasEmotion`
  - `onyx:hasEmotionCategory`
  - `onyx:hasEmotionIntensity`
  - optional `onyx:algorithmConfidence`
- A single explicit target per container via `oa:hasTarget` (the UI filters containers with exactly one target).
- Timeline timestamps prioritize activity times (`prov:startedAtTime` / `prov:endedAtTime`) and fall back to shared event time.

### Report 4: Extreme Emotions (>= 75%)

Shows:

- A table of human-target emotion samples whose intensity is **>= 0.75**.
- Filtering is based on intensity only (not model confidence).

Requires the same data as **Report 3**, plus:

- Intensity values that can be parsed as numeric literals.

### Report 5: Extreme Emotion Distribution

Shows:

- A bar chart of how many “extreme emotion” samples exist per emotion category (derived from **Report 4** rows).
- The chart is rendered even when only one category is present.

### Report 6: Robot State Timeline

Shows:

- A time-ordered list of robot state samples with a location field, sorted chronologically across robots.

Requires the graph to include:

- State resources typed as `prov:Entity`.
- Attribution `prov:wasAttributedTo` to a robot resource typed `oro:Robot`.
- Locations via `prov:atLocation`.
- Optional timestamps from `prov:generatedAtTime` / `prov:startedAtTime` / `prov:endedAtTime`.

### Report 7: Displacement Summary

Shows:

- A per-robot summary derived from **Report 6**:
  - number of state samples,
  - number of location changes, and
  - the observed location path (`A -> B -> C` with consecutive duplicates collapsed).

### Report 8: Conversation History

Shows:

- A list of conversation sessions (human ↔ robot), each with a message timeline.

Requires the graph to include:

- Messages typed as `schema:Message` with `schema:text`.
- Each message linked to its activity via `prov:wasGeneratedBy`.
- Each activity typed as `segb:LoggedActivity` and linked to a robot via `segb:wasPerformedBy`.
- A resolvable human participant. Preferred path: explicit message sender attribution
  (`schema:sender` and/or `prov:wasAttributedTo`) pointing to the human resource.
- Backward-compatible fallbacks are still supported:
  - message/activity links through shared events (`prov:specializationOf` / `schema:about`), and
  - robot ownership (`oro:belongsTo`) when available.

Session grouping (UI behavior):

- The UI groups messages into sessions per human–robot pair.
- A pair is considered a conversation only if it contains at least one human message and one robot message.
- A new session starts when the gap between consecutive messages is **>= 2 minutes**.

## Troubleshooting (reports-specific)

### All report blocks show warnings

Likely causes:

- Backend is not ready (Virtuoso unavailable).
- You do not have permission to run queries when auth is enabled (missing `auditor`/`admin` role).

Fix:

```bash
curl -s http://localhost:5000/healthz/ready
curl -s http://localhost:5000/auth/mode
```

If auth is enabled, verify your token roles and re-open `http://localhost:8080/session`.

### Reports are empty after “Refresh reports”

Most common cause: the current graph does not contain the semantics expected by the report queries.

Fix (recommended baseline dataset):

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

## Implementation references (for high-assurance debugging)

- UI report queries: `apps/frontend/segb-ui/src/features/reports/queries.ts`
- UI report aggregation logic: `apps/frontend/segb-ui/src/features/reports/useReports.ts`
- Backend query endpoint: `GET /query` (see `apps/backend/src/api/routers/graph_ops.py`)
