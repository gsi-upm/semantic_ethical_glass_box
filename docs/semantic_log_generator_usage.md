# Use `semantic_log_generator`

This guide shows the normal production usage pattern.

## Typical Flow

1. Create logger bound to one robot namespace.
2. Register participants (for example humans).
3. Log activities, observations, messages, emotions, and robot states.
4. Serialize to Turtle.
5. Publish to backend (`/ttl`) if needed.

## Minimal Example

```python
from datetime import datetime, timezone

from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/ari/v1/",
    robot_id="ari1",
    robot_name="ARI",
)

human_uri = logger.register_human("maria", first_name="Maria")

listen_activity = logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=datetime.now(timezone.utc),
)

message_uri = logger.log_message(
    "I feel sad today",
    message_id="msg_1",
    generated_by_activity=listen_activity,
    language="en",
)

ttl_text = logger.serialize(format="turtle")

publisher = SEGBPublisher(base_url="http://localhost:5000")
publisher.publish_turtle(ttl_text, user="ari_logger")
```

## Shared Event / Shared Context (Cross-Robot)

In the full SEGB stack, shared events are meant to be resolved through the backend shared-context service.

At a glance:

- `SemanticSEGBLogger` does **not** auto-read environment variables.
- Online shared-context resolution is enabled only when you pass `shared_event_resolver=...`.
- If no resolver is provided (or resolver returns `None`), logger uses deterministic local URI generation.
- If backend auth is enabled (`SECRET_KEY` set), resolver must send a JWT with `logger` or `admin` role.

When multiple robots observe the same external event:

1. Call `get_shared_event_uri(...)`.
2. Link each local observation using `link_observation_to_shared_event(...)`.
3. Publish each robot graph normally.

TTL shape for shared events:

- Shared event node: `schema:Event` + `prov:Entity`.
- `event_kind` and `modality` are inputs for resolver/fingerprint, not serialized as `schema:eventType` / `schema:measurementTechnique`.
- If `modality` is provided (for example `speech`), logger emits a `sosa:Observation` linked to the shared event (`sosa:hasFeatureOfInterest`) and a `sosa:Procedure` (`sosa:usedProcedure`) labelled with that modality.
- Observation-to-shared-event confidence is emitted as `schema:additionalProperty` (`schema:PropertyValue` with `schema:propertyID="shared_event_confidence"`).
- Robot state properties are linked with `schema:additionalProperty`, and state location with `prov:atLocation`.

Explicit online canonical resolution:

```python
from semantic_log_generator import (
    HTTPSharedContextResolver,
    SemanticSEGBLogger,
)

resolver = HTTPSharedContextResolver(
    base_url="http://localhost:5000",
    token=None,           # set JWT when backend auth is enabled
    raise_on_error=True,  # fail fast if backend resolver is unreachable
)

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/ari/v1/",
    robot_id="ari1",
    shared_event_resolver=resolver,
)
```

Optional env-driven wiring in robot runtime (explicit, not automatic):

```python
from semantic_log_generator import (
    SemanticSEGBLogger,
    build_http_shared_context_resolver_from_env,
)

resolver = build_http_shared_context_resolver_from_env()
logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/ari/v1/",
    robot_id="ari1",
    shared_event_resolver=resolver,
)
```

`build_http_shared_context_resolver_from_env()` reads:

- `SEGB_API_URL`
- `SEGB_API_TOKEN` (when backend auth is enabled)
- Optional shared-context tuning vars:
  - `SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS`
  - `SEGB_SHARED_CONTEXT_VERIFY_TLS`
  - `SEGB_SHARED_CONTEXT_RAISE_ON_ERROR`

Important: centralized `.env` files used by backend deployment are not automatically available to distributed robot processes.

## API Surfaces You Will Use Most

- `log_activity(...)`
- `log_observation(...)`
- `log_message(...)`
- `log_emotion_annotation(...)`
- `log_robot_state(...)`
- `serialize(...)`

## Operational Rules

- Pass explicit `activity_kind` (required).
- Always provide `language` when logging end-user text messages.
- Use stable IDs for traceability, but keep `activity_id` unique per execution.
- Reusing the same `activity_id` with a different timestamp now raises `ValueError`.
- For strict ontological profiles, set `strict_result_typing=True` to avoid explicit `prov:Activity` on `segb:Result` resources.
- Keep one namespace per robot to avoid collisions.
- Publish in batches when possible.

## Where to Learn Internals

For a non-tutorial technical explanation, read:

- [How TTL is generated internally](ttl_generation_internals.md)
