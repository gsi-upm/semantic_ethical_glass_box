# ROS4HRI Integration

## What This Guide Covers

This guide shows how to move from a plain ROS4HRI interaction flow to a flow that also records semantic evidence in
SEGB.

The idea is simple:

1. keep your robot behavior,
2. add semantic logging around the important events,
3. publish those logs to the SEGB backend,
4. inspect the result in the UI.

This page is specific to the ROS4HRI emotion mirror example. It is not meant to be a universal robot integration recipe.

## Before You Start

You need:

- the ROS4HRI tutorial completed through Part 3:
  <https://ros4hri.github.io/ros4hri-tutorials/interactive-social-robots/#part-3-building-a-simple-social-behaviour>
- a working ROS 2 workspace with `emotion_mirror`
- access to this SEGB repository
- a running SEGB backend
- if auth is enabled, a JWT with role `logger` or `admin`

Reference implementation:

- local path: `ros4hri-exchange/ws/src/emotion_mirror/emotion_mirror/mission_controller.py`
- repository URL:
  <https://github.com/gsi-upm/semantic_ethical_glass_box/blob/main/ros4hri-exchange/ws/src/emotion_mirror/emotion_mirror/mission_controller.py>

## Step 1: Start The SEGB Backend

From the SEGB repository root:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
curl -s http://localhost:5000/healthz/ready
```

Expected:

```json
{"ready": true, "virtuoso": true}
```

If auth is enabled, generate a token before you continue. The exact flow is described in
[Authentication and JWT](../operations/authentication-and-jwt.md).

## Step 2: Install `semantic_log_generator` In The ROS Runtime

Inside the Python environment used by your ROS runtime, install the package.

From a local checkout:

```bash
python -m pip install -e /path/to/semantic_ethical_glass_box/packages/semantic_log_generator
```

Or from TestPyPI:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "semantic-log-generator>=1.0.0,<2.0.0"
```

Quick check:

```bash
python -c "from semantic_log_generator import SemanticSEGBLogger; print('ok')"
```

## Step 3: Decide What You Want To Log

Before touching code, decide which robot events matter enough to become semantic evidence.

In the emotion mirror example, good candidates are:

- the incoming user utterance,
- the robot reply,
- the detected facial expression,
- the robot expression command,
- optional model metadata if you use an LLM or classifier in the loop.

This step matters because SEGB works best when you log meaningful interaction milestones, not every internal detail.

## Step 4: Add The Core Imports And Configuration

In `mission_controller.py`, add the logging package imports and a few configuration values.

Example:

```python
from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger


class MissionController(Node):
    SEGB_BASE_URL = "http://localhost:5000"
    SEGB_BASE_NAMESPACE = "https://example.org/segb/robots/emotion-mirror/v1/"
```

If auth is enabled, read the token from an environment variable rather than hard-coding it.

## Step 5: Initialize The Logger And Publisher

Create the logger and publisher once in `__init__`.

Example:

```python
self.segb_logger = SemanticSEGBLogger(
    base_namespace=self.SEGB_BASE_NAMESPACE,
    robot_id="emotion_mirror_robot",
    robot_name="Emotion Mirror Robot",
)

self.segb_publisher = SEGBPublisher(
    base_url=self.SEGB_BASE_URL,
    token=os.getenv("SEGB_API_TOKEN"),
    default_user="emotion_mirror_robot",
)
```

The logger builds the RDF graph in memory. The publisher is the part that sends Turtle to the backend.

## Step 6: Instrument The Main Interaction Points

You do not need to rewrite the whole node. Start by wrapping the meaningful events.

### When A User Utterance Arrives

Log:

- a listening activity,
- the human message,
- optional metadata such as language or source.

### When The Robot Produces A Reply

Log:

- a response activity,
- the reply message,
- links back to the human message when possible.

### When A Facial Expression Is Observed

Log:

- the observation activity,
- the detected expression,
- timestamps and robot attribution.

The reference implementation in `ros4hri-exchange/.../mission_controller.py` is the best place to compare exact code
placement.

## Step 7: Publish The Graph

Once you have produced enough meaningful data, serialize and publish it:

```python
ttl_text = self.segb_logger.serialize(format="turtle")
self.segb_publisher.publish_turtle(ttl_text)
```

You can publish after each relevant interaction or batch publications depending on your runtime needs. For a first
integration, keeping the flow simple is usually better.

## Step 8: Run The Robot And Verify In SEGB

After running the robot scenario, verify the result in two places.

### In The API

If auth is disabled:

```bash
curl -s http://localhost:5000/events | head -n 40
```

If auth is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 40
```

### In The UI

Open:

- `/reports`
- `/kg-graph`

What you want to confirm:

- new robot and human resources exist,
- messages are linked to activities,
- interaction traces are visible in the graph and reports.

## Practical Advice

- start with a small number of logged events,
- publish clean, meaningful interaction steps first,
- only add model metadata and richer provenance after the basic flow works,
- use the graph explorer to confirm relationships before debugging the reports.

## Common Problems

- publish succeeds but the UI looks sparse: your logged data is still too small or does not match the report queries yet.
- `401/403` on publish: the ROS runtime token is missing, invalid, expired, or has the wrong role.
- package import works locally but not inside ROS runtime: the package was installed in a different interpreter or container layer.

## Next Steps

After a first robot integration, these pages usually help most:

1. [Explore the Web UI](explore-the-web-ui.md)
2. [Authentication and JWT](../operations/authentication-and-jwt.md)
3. [API and Roles](../reference/api-and-roles.md)
