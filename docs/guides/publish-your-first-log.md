# Publish Your First Log

Once you have seen SEGB working with the demo dataset, the next step is to publish a minimal log of your own. This
guide creates one human, one activity, and one message, then sends that data to the backend and verifies the result
through the API and the UI.

## Before You Start

You need:

- a running SEGB backend at `http://localhost:5000` (see [Quickstart](../getting-started/quickstart.md))
- Python `3.10+`
- if auth is enabled, a JWT with role `logger` or `admin`


## Step 1: Install `semantic_log_generator`

If the package is not installed yet, use the main installation guide first:
[Install `semantic_log_generator`](../package/installation.md).

Fastest option from PyPI (see [Install `semantic_log_generator`](../package/installation.md) for other options):

```bash
pip install semantic-log-generator
```
## Step 2: Write The Smallest Useful Log

A minimally useful SEGB log has three pieces: an actor, an activity, and something that activity produced. The script
below creates a human, records a listening activity, attaches a message to that activity, serializes everything to
Turtle, and sends it to the backend. Create a file called `first_log.py` with this content (for advanced examples, see [Use `semantic_log_generator`](../package/usage.md)):

```python
from datetime import datetime, timezone
import os

from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
)

human_uri = logger.register_human("maria", first_name="Maria")

listen = logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=datetime.now(timezone.utc),
)

logger.log_message(
    "Hello ARI",
    message_id="msg_1",
    generated_by_activity=listen,
    language="en",
    sender=human_uri,
)

ttl_text = logger.serialize(format="turtle")

publisher = SEGBPublisher(
    base_url="http://localhost:5000",
    token=os.getenv("SEGB_API_TOKEN"),
    default_user="demo_robot",
)
publisher.publish_turtle(ttl_text)

print("Log posted. Triples:", len(logger.graph))
```

`base_namespace` is the stable URI base for the resources created by the logger. `robot_id` and `robot_name` identify
the robot in the graph. `default_user` is the user value sent with the API request. The example is intentionally small
so the publish flow is easy to inspect.

## Step 3: Run It

If auth is disabled:

```bash
python first_log.py
```

If auth is enabled:

```bash
export SEGB_API_TOKEN="<logger_or_admin_jwt>"
python first_log.py
```

You should see:

```text
Log posted. Triples: <number>
```

## Step 4: Check The Result In The Backend

If auth is disabled:

```bash
curl -s http://localhost:5000/events | head -n 40
```

If auth is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 40
```

You should see Turtle output that includes resources related to `demo_robot` and `maria`.

## Step 5: Check The Result In The UI

Open `http://localhost:8080/reports` and `http://localhost:8080/kg-graph`. If auth is enabled, open
`http://localhost:8080/session` first, paste a valid token, and return to those pages. The graph page should show nodes
and edges related to your new data. The reports page may stay sparse with such a small dataset, but it should no longer
be an empty system.

## What Happened Behind The Scenes

The script created RDF resources with `SemanticSEGBLogger`, serialized them to Turtle, sent that Turtle to `POST /ttl`,
and stored the triples in the Knowledge Graph. That is the same pattern you will use in a larger robot integration. The
only difference is the amount of data and the events you choose to log.

## Common Problems

- `ModuleNotFoundError`: you installed the package in a different Python interpreter than the one running the script.
- `Connection refused`: the backend is not running at `http://localhost:5000`.
- `401/403`: auth is enabled and the token is missing, invalid, expired, or has the wrong role.
- the UI still looks empty: your one-log example may be too small for some report cards. This is normal. Use Quickstart's
  demo dataset if you want richer report views immediately.

## Next Steps

After this guide, the most useful next pages are [Explore the Web UI](explore-the-web-ui.md),
[Shared Context Workflow](shared-context-workflow.md), and [ROS4HRI Integration](ros4hri-integration.md).
