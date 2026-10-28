# `semantic_log_generator`

`semantic_log_generator` is the Python library used to create SEGB-compatible RDF logs inside a robot runtime or a
simulation. You can use it in two modes:

- package-only: create RDF graphs locally and serialize them to Turtle
- backend-backed: publish those logs to a SEGB backend and optionally resolve shared context across robots

This page is the package-first entry point. If you arrived from PyPI and do not need the rest of the SEGB stack yet,
start here.

## Python-First By Default

The normal integration path is intentionally Python-first. In most cases, you should not need to write ontology terms
such as `oro:ListeningEvent` or `onyx:EmotionAnalysis` yourself.

Instead, the package gives you higher-level inputs:

- `ActivityKind` for the main activity categories
- specific logger methods such as `register_human()`, `log_message()`, and `log_robot_state()`
- plain strings, IDs, and Python data structures that the logger expands into RDF

If you do need custom RDF typing, the package still allows it. The precise boundary between the default abstraction and
the advanced RDF extension points is documented in [API Reference](api-reference.md).

## What You Can Do Without The Backend

With the package alone, you can:

- create actors, activities, messages, observations, emotion annotations, and robot state snapshots
- serialize the resulting RDF graph to Turtle
- inspect or persist that Turtle in your own runtime

Minimal local example:

```python
from semantic_log_generator import ActivityKind, SemanticSEGBLogger

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
)

logger.log_activity(activity_id="listen_1", activity_kind=ActivityKind.LISTENING)
print(logger.serialize(format="turtle"))
```

## What Requires The Backend

Some features depend on SEGB backend routes:

- `SEGBPublisher` requires `POST /ttl`
- read-back verification examples usually use `GET /events`
- backend shared-context resolution requires `POST /shared-context/resolve`

If you only need local Turtle generation, you do not need Docker, Virtuoso, the Web UI, or JWT setup.

## Compatibility And Runtime Contract

- distribution name for `pip`: `semantic-log-generator`
- import name in Python: `semantic_log_generator`
- supported Python versions: `3.10`, `3.11`, `3.12`
- safest deployment path: keep the package and the SEGB backend on the same repository release or tag

The package can generate RDF locally without the backend. Publication and shared-context resolution are the only parts
that depend on backend availability and endpoint compatibility.

## Recommended Reading Path

1. [Install `semantic_log_generator`](installation.md)
2. [API Reference](api-reference.md)
3. [Use `semantic_log_generator`](usage.md)

If you want the entire stack running locally first, use [Quickstart](../getting-started/quickstart.md).
