# Core Concepts and Roles

This page gives you the vocabulary that appears throughout the rest of the documentation. The goal is not to turn you
into an RDF specialist, but to give you a stable mental model once you have seen SEGB running.

## One Interaction To Keep In Mind

Imagine a human says, "I am worried about tomorrow's exam," a robot listens, an emotion model labels the situation as
anxiety, and the robot answers with a calming sentence. In a conventional system, that trace might be split across
application logs, model outputs, and separate databases. In SEGB, it can be stored as one connected graph.

## Semantic Log, Turtle, And Knowledge Graph

A semantic log is a structured log represented as RDF instead of plain text. That matters because RDF stores
relationships, not just isolated lines. A message can point back to the activity that generated it, that activity can
point to the robot that performed it, and a model output can point to the model that produced it. Turtle, often written
as TTL, is the text format SEGB uses when those logs move from the robot side to the backend. Once inserted, the triples
live in a Knowledge Graph stored by Virtuoso.

When you open the reports page or the graph explorer, you are not looking at separate files. You are looking at views
built from that graph.

## Report And Shared Context

A report in SEGB is a fixed UI view generated from read-only graph queries. Participant summaries, conversation history,
emotion timelines, ML usage, and robot state are all examples of reports. Shared context is the mechanism SEGB uses
when separate observations probably describe the same real-world event, such as two robots hearing the same sentence
almost at the same time.

## The Four Runtime Pieces

| Piece | What it does |
|---|---|
| `semantic_log_generator` | creates RDF logs, serializes them to Turtle, and can publish them from a robot or simulator |
| backend API | receives logs, validates them, stores them, and exposes inspection endpoints |
| Virtuoso | stores the triples as the persistent Knowledge Graph |
| web UI | turns that graph into reports, graph views, queries, and review workflows |

## Authentication And Roles

SEGB has two practical modes. If `SECRET_KEY` is empty or unset, authentication is disabled and local learning is
easiest. If `SECRET_KEY` is set, the backend expects an HS256 JWT and enforces roles.

| Role | Typical use |
|---|---|
| `logger` | publish logs and call `/shared-context/resolve` |
| `auditor` | inspect reports, export events, and run read-only queries |
| `admin` | operate the stack, validate Turtle, delete data, review shared-context cases, and read backend logs |

A simple workflow maps cleanly onto those roles: the robot runtime publishes as `logger`, an operator or reviewer
inspects data as `auditor`, and maintenance tasks run as `admin`.

## Next Steps

If you want to return to the shortest end-to-end run, go back to [Quickstart](quickstart.md). If you are ready to
publish your own data, continue with [Publish Your First Log](../guides/publish-your-first-log.md).
