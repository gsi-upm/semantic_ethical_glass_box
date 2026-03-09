# SEGB in 2 Minutes

This page is the shortest practical picture of what SEGB does. Instead of defining the system in abstract terms, it
walks through one small interaction and shows how that interaction moves through the stack.

## A Small Interaction

Imagine a person tells a robot, "I am worried about tomorrow's exam." The robot listens, an emotion model labels the
situation as anxiety, and the robot answers with a calming sentence. If you only keep ordinary application logs, that
moment may end up split across several unrelated places. In SEGB, the same moment is kept as one connected trace.

## The Same Moment, Step By Step

1. The robot or simulator decides this moment is worth recording. It uses `semantic_log_generator` to build a semantic
   log that links the human, the robot, the listening activity, the model output, and the response that followed.
2. That log is serialized as Turtle and sent to the backend API. Turtle is simply the text form used to transport the
   RDF log.
3. The backend validates the payload and stores it in the Knowledge Graph. In this repository the storage layer behind
   the backend is Virtuoso, but you normally do not interact with it directly.
4. The web UI reads that stored trace and turns it into reports, graph views, queries, and review workflows. That is
   why the same interaction can later appear both as a readable dashboard and as a connected graph.

```text
Robot or simulator
  -> semantic_log_generator
  -> backend API
  -> Virtuoso Knowledge Graph
  -> reports, graph view, queries, audits
```

## What You Would See Afterwards

After that interaction is stored, `/reports` can show you participants, conversation history, model usage, emotion
timelines, and robot state. If something looks strange, `/kg-graph` lets you inspect how the same pieces connect behind
those reports. That is the practical value of SEGB: one interaction, kept as evidence that can be read, queried, and
reviewed later.

## Recommended Next Step

Continue with the [Quickstart](quickstart.md). It brings up the full stack, loads the dataset that makes the UI
meaningful, and gives you the shortest end-to-end path from zero to a working SEGB instance.
