# Semantic Ethical Glass Box (SEGB)

<p align="center">
  <img src="assets/segb-logo.png" alt="SEGB logo" width="520" />
</p>

SEGB is a semantic logging stack for human-robot interaction. It helps you capture what happened during an interaction,
store it as structured RDF knowledge, and inspect it later through a backend API and a web UI.

Think of it this way: instead of keeping only plain text logs such as "the robot spoke" or "a face was detected", SEGB
lets you store richer facts such as who spoke, which robot was involved, what model was used, when it happened, and how
that event connects to the rest of the interaction.

## What Is SEGB?

SEGB is useful when you want your robot system to be easier to inspect, explain, and audit.

Typical questions SEGB can help answer are:

- Which human and robot took part in this interaction?
- Which ML model produced this result?
- What happened before and after a given message?
- Did two robots observe the same real-world event?
- What evidence do I have when I review the system later?

SEGB is not a robot framework, a sensor driver, or a ROS replacement. Your robot software still decides what to detect,
what to say, and when to act. SEGB focuses on recording those decisions and observations in a structured way.

## Architecture

SEGB has four practical pieces:

1. `semantic_log_generator` runs in the robot or simulation runtime and builds RDF logs.
2. The backend API receives Turtle payloads, validates them, and stores them in Virtuoso.
3. Virtuoso keeps the Knowledge Graph that SEGB queries later.
4. The web UI lets you explore reports, graph structure, shared-context cases, and operational data.

The usual flow looks like this:

```text
Robot or simulator
  -> semantic_log_generator
  -> POST /ttl or shared-context endpoints
  -> backend API
  -> Virtuoso Knowledge Graph
  -> reports, graph view, queries, audits
```

This repository contains the full stack:

- backend API in `apps/backend`
- frontend UI in `apps/frontend`
- reusable logging package in `packages/semantic_log_generator`
- simulations, notebooks, and tests in `examples` and `tests`

## 20 Minutes To A First Successful Run

If you want the shortest path to seeing SEGB working, follow the [Quickstart](getting-started/quickstart.md).

In that guide you will:

1. start the centralized stack with Docker Compose,
2. load a ready-made demo dataset,
3. open the UI,
4. confirm that `/reports` and `/kg-graph` show real data.

That is the fastest way to understand what SEGB does before you integrate it into your own robot software.

Reference screenshot:

![SEGB Reports Dashboard](assets/screenshots/ui-reports.png)

## Choose Your Path

Use the path that matches what you want to do next.

### I Want To Try SEGB Quickly

Start with [Quickstart](getting-started/quickstart.md). It is the shortest end-to-end path and it uses the published demo
dataset, so you can focus on understanding the product first.

### I Want To Publish Logs From Python

Go to [Publish Your First Log](guides/publish-your-first-log.md). This guide shows a minimal Python example that creates a
small semantic log, sends it to the backend, and verifies the result in both the API and the UI.

### I Want To Understand The Main Ideas First

Read [Core Concepts and Roles](getting-started/core-concepts-and-roles.md). It explains the basic vocabulary used across
the docs: semantic log, Turtle, Knowledge Graph, report, shared context, and the three main roles (`logger`, `auditor`,
and `admin`).

### I Want To Operate The Stack

Go to [Centralized Deployment](operations/centralized-deployment.md), then read [Authentication and JWT](operations/authentication-and-jwt.md)
and [Observability and Reset](operations/observability-and-reset.md).

### I Want To Integrate A Real Robot Or Simulator

Start with [Publish Your First Log](guides/publish-your-first-log.md), then continue with
[ROS4HRI Integration](guides/ros4hri-integration.md).

### I Want Protocol And Data Details

Use the reference section:

- [API and Roles](reference/api-and-roles.md)
- [Ontology](reference/ontology.md)
- [Monorepo Structure](reference/monorepo-structure.md)
- [Use-Case Matrix](reference/use-case-matrix.md)
