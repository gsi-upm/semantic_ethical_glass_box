# Publish Your First Log

## What You Will Do

In this guide you will create a very small Python script that:

1. builds a semantic log,
2. serializes it to Turtle,
3. sends it to the SEGB backend,
4. verifies the result in the API and the UI.

This is the best next step after Quickstart if you want to move from "I saw SEGB working" to "I can publish my own
data".

## Before You Start

You need:

- a running SEGB backend at `http://localhost:5000`
- Python `3.10+`
- if auth is enabled, a JWT with role `logger` or `admin`

If you still need the centralized stack, follow [Quickstart](../getting-started/quickstart.md) first.

## Step 1: Install `semantic_log_generator`

Choose the install mode that fits your situation.

### Option A: Install From This Repository

This is the easiest option when you are already working from this checkout:

```bash
python -m pip install -e packages/semantic_log_generator
```

### Option B: Install From PyPI

Use this when the package is published and you want a regular install:

```bash
python -m pip install semantic-log-generator
```

### Option C: Install From TestPyPI

Useful when you are testing a pre-release package:

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

Expected: `ok`

## Step 2: Create A Minimal Script

Create a file called `first_log.py` with this content:

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

This example is intentionally small. It gives you one human, one activity, and one message, which is enough to
understand the full publish flow.

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

Expected output:

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

Open:

- reports: `http://localhost:8080/reports`
- graph explorer: `http://localhost:8080/kg-graph`

If auth is enabled, first open:

- session page: `http://localhost:8080/session`

Then paste a valid token and return to the UI pages above.

What you should expect:

- the graph page should show nodes and edges related to your new data,
- the reports page may stay sparse with such a small dataset, but it should no longer be an empty system.

## What Happened Behind The Scenes

The script did four useful things:

1. created RDF resources with `SemanticSEGBLogger`,
2. serialized those resources to Turtle,
3. sent the Turtle payload to `POST /ttl`,
4. stored the triples in the Knowledge Graph so they can be queried later.

That is the same pattern you will use in a larger robot integration. The only difference is the amount of data and the
events you choose to log.

## Common Problems

- `ModuleNotFoundError`: you installed the package in a different Python interpreter than the one running the script.
- `Connection refused`: the backend is not running at `http://localhost:5000`.
- `401/403`: auth is enabled and the token is missing, invalid, expired, or has the wrong role.
- the UI still looks empty: your one-log example may be too small for some report cards. This is normal. Use Quickstart's
  demo dataset if you want richer report views immediately.

## Next Steps

After this guide, the most useful next pages are:

1. [Explore the Web UI](explore-the-web-ui.md)
2. [Shared Context Workflow](shared-context-workflow.md)
3. [ROS4HRI Integration](ros4hri-integration.md)
