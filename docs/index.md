# Semantic Ethical Glass Box (SEGB)

<p align="center">
  <img src="assets/segb-logo.png" alt="SEGB logo" width="520" />
</p>

SEGB is a semantic logging stack for human-robot interaction. It captures interaction evidence as connected RDF
knowledge so you can inspect not only what happened, but also who did it, which model was involved, what followed, and
how the pieces belong to the same trace.

## Why Teams Use SEGB

SEGB is for systems that need more than plain application logs. It is useful when you want to reconstruct what
happened in an interaction involving several humans, robots, or components. Instead of leaving each log line isolated,
SEGB gives every observation a place in a shared Knowledge Graph where events are connected and can be searched
structurally. That makes it easier to explain a robot decision in context, compare observations from different
components, and preserve evidence that can later be reviewed by an auditor.

## Why "Ethical"

The "ethical" part is about traceability and explainability. SEGB preserves the evidence needed to review how a
robot interaction unfolded: which inputs were observed, which model or component produced an interpretation, which
action followed, and what context connected those steps. That makes transparency and post-hoc audit practical instead
of aspirational, and it helps you detect problematic behavior, understand where it came from, and correct it.

## What You Adopt

| Goal | Adopt |
|---|---|
| generate semantic logs inside your runtime | `semantic_log_generator` |
| store and query logs centrally | `semantic_log_generator` and the backend API |
| inspect interactions visually | the full stack, including the web UI |

SEGB is not a robot framework, a sensor driver, or a ROS replacement. Your robot software still decides what to
detect, what to say, and when to act. SEGB records those decisions and observations in a structured form that can be
connected and reviewed later.

## Architecture In One Pass

SEGB usually runs as a four-part loop. `semantic_log_generator` builds RDF logs inside a robot or simulator, the
backend receives Turtle payloads and stores them in the graph, and the web UI turns that graph into reports, graph
views, queries, and review flows. In this repository, the storage layer behind the backend is Virtuoso, but users
normally interact with the backend rather than with the database directly.

The usual flow looks like this:

```text
Robot or simulator
  -> semantic_log_generator
  -> POST /ttl or shared-context endpoints
  -> backend API
  -> Knowledge Graph
  -> reports, graph view, queries, audits
```

This repository contains the full stack in one place: the backend API in `apps/backend`, the frontend UI in
`apps/frontend`, the reusable logging package in `packages/semantic_log_generator`, and the simulations, notebooks, and
tests in `examples` and `tests`.

## Recommended First Path

If you are new to SEGB, start with [SEGB in 2 Minutes](getting-started/segb-in-two-minutes.md), continue with the
[Quickstart](getting-started/quickstart.md), then move to [Publish Your First Log](guides/publish-your-first-log.md)
and [Explore the Web UI](guides/explore-the-web-ui.md). That sequence gives you the product story first, the working
stack second, and the integration path third.

Reference screenshot:

![SEGB Reports Dashboard](assets/screenshots/ui-reports.png)

## Further Reading

If you want a conceptual glossary after the first run, read
[Core Concepts and Roles](getting-started/core-concepts-and-roles.md). If you are operating the stack, go to
[Centralized Deployment](operations/centralized-deployment.md),
[Authentication and JWT](operations/authentication-and-jwt.md). If you need protocol and data details, use the
reference section: [API and Roles](reference/api-and-roles.md) and [Ontology](reference/ontology.md).
