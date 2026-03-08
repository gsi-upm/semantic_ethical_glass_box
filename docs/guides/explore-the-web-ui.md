# Explore The Web UI

## What You Will Do

This guide walks you through the main SEGB UI pages and explains what each one is for. The goal is not only to click
around, but to build a simple operator's mental model of the system.

## Before You Start

You need:

- the centralized stack running
- some data already loaded into the graph
- if auth is enabled, a valid token for the pages you want to open

For the easiest experience, load the UC-02 demo dataset first with [Quickstart](../getting-started/quickstart.md).

## Step 1: Open The UI

Use the URL that matches your stack mode:

- production-like compose: `http://localhost:8080`
- development compose: `http://localhost:5173`

If the shell loads correctly, you should see the application layout with sidebar navigation.

## Step 2: Set Your Session Token If Needed

Open the session page:

- `/session`

What to do there:

- if auth is disabled, you can ignore the token input,
- if auth is enabled, paste a JWT and keep it in the browser session.

Reference screenshot:

![SEGB Session](../assets/screenshots/ui-session.png)

## Step 3: Visit The Main Pages

This table is the quickest way to understand the product surface.

| Route | What it is for | Role when auth is enabled |
|---|---|---|
| `/reports` | Human-friendly dashboards built from graph queries | `auditor` or `admin` |
| `/kg-graph` | Visual graph exploration | `auditor` or `admin` |
| `/query` | Read-only SPARQL workbench | `auditor` or `admin` |
| `/shared-context` | Review and reconcile shared-context cases | `admin` |
| `/logs/insert` | Manual Turtle validation and insertion | `admin` |
| `/logs/delete` | Delete graph content from the UI | `admin` |
| `/system/logs` | Inspect backend server logs | `admin` |
| `/health` | Check live and ready status | public |
| `/session` | Manage the JWT stored in the browser session | public |

## Step 4: Start With Reports

Open:

- `http://localhost:8080/reports`

Then click `Refresh reports`.

This page is usually the easiest way to understand whether your dataset is meaningful. Instead of raw triples, you see
interpreted views such as:

- participants,
- ML usage,
- emotion timelines,
- robot state timelines,
- conversation history.

Reference screenshot:

![SEGB Reports Dashboard](../assets/screenshots/ui-reports.png)

## Step 5: Open The Knowledge Graph Explorer

Open:

- `http://localhost:8080/kg-graph`

Use this page when you want to inspect the data structure more directly:

- which nodes exist,
- how they connect,
- whether a message links back to an activity,
- whether a robot, human, and shared event are all part of the same trace.

This page is especially useful when a report looks strange and you want to inspect the raw relationships behind it.

Reference screenshot:

![SEGB KG Graph Explorer](../assets/screenshots/ui-kg-graph.png)

## Step 6: Use The Query Workbench

Open:

- `http://localhost:8080/query`

This page is for read-only SPARQL queries. A practical way to use it is:

1. confirm that a specific class or property is present,
2. count resources,
3. inspect a small slice of the graph before you change your pipeline.

It is a debugging and exploration page, not a reporting page.

## Step 7: Check Operational Pages

Two pages are especially useful when you are operating or debugging the system:

### `/shared-context`

Use this when you work with multi-robot event matching and review pending cases.

### `/system/logs`

Use this when you need backend evidence:

- warnings,
- validation failures,
- request-side errors,
- operational traces.

Reference screenshot:

![SEGB Operator Flow](../assets/screenshots/ui-operator-flow.png)

## A Good First Tour

If you are not sure where to begin, this sequence works well:

1. open `/reports` and refresh,
2. open `/kg-graph` and inspect the main nodes,
3. open `/query` and run one small read-only query,
4. if you are testing multi-robot flows, open `/shared-context`,
5. if something looks wrong, inspect `/health` and `/system/logs`.

## Common Problems

- page redirects to `/session`: auth is enabled and your token is missing or lacks the required role.
- reports are empty: the graph does not yet contain the semantics expected by the report queries. Reload the UC-02 demo dataset.
- health shows `ready=false`: the backend cannot reach Virtuoso.
- the UI loads but requests fail: your token may be expired even if the page layout itself opens.

## Next Steps

If you want to go deeper after this UI tour:

1. [Shared Context Workflow](shared-context-workflow.md)
2. [Observability and Reset](../operations/observability-and-reset.md)
3. [API and Roles](../reference/api-and-roles.md)
