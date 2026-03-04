# Basic Use: Post Your First Log to SEGB

## Objective

Create one minimal semantic log in Python and post it to a running SEGB backend.

## Prerequisites

- `semantic_log_generator` installed (see [Installation](installation.md))
- Centralized SEGB running at `http://localhost:5000` (see [Centralized Deployment](../deployment/centralized.md))
- If auth is enabled (`SECRET_KEY` set), a valid JWT with `logger` or `admin` role

## Steps

### 1) Create a minimal script

Create `first_log.py`:

```python
from datetime import datetime, timezone

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
)

ttl_text = logger.serialize(format="turtle")

publisher = SEGBPublisher(
    base_url="http://localhost:5000",
    token=None,  # replace with JWT string if auth is enabled
    default_user="demo_robot",
)
publisher.publish_turtle(ttl_text)

print("Log posted. Triples:", len(logger.graph))
```

### 2) Run it

```bash
python first_log.py
```

Expected: output like `Log posted. Triples: <number>`.

### 3) Verify in backend

If auth is disabled:

```bash
curl -s http://localhost:5000/events | head -n 40
```

If auth is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 40
```

Expected: Turtle output containing your `demo_robot` resources.

## Validation

- Script runs without exceptions.
- `POST /ttl` succeeds.
- `GET /events` returns non-empty Turtle including new entities.

## Troubleshooting

- `401/403` on publish: missing/invalid token or missing role.
- `Connection refused`: backend not running on `http://localhost:5000`.
- `ModuleNotFoundError`: install package in the same Python interpreter used to run the script.

## Next

- Understand the core platform capabilities with minimal code: [Learn Main SEGB Features (Simple)](../getting-started/segb-features.md)
- UI operation details: [Web Observability](../operations/web-observability.md)
