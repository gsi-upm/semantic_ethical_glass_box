# Use `semantic_log_generator`

This page is the practical companion to [API Reference](api-reference.md). It shows two complete integration flows:

1. a basic publish flow with one human, one activity, and one message
2. a richer flow with shared context, model provenance, causality, and robot state

The goal is not only to give you runnable code, but to explain why each part exists and what semantic meaning it adds
to the graph.

## Before You Start

You need:

- package installed (see [Install `semantic_log_generator`](installation.md))
- backend API available at `http://localhost:5000` if you want to publish
- if auth is enabled, a JWT with role `logger` or `admin`

For the advanced example, backend shared-context resolution is optional. If `SEGB_API_URL` is not set,
`build_http_shared_context_resolver_from_env()` returns `None` and the logger still works with local shared-event
resolution.

## Two Execution Modes

- local-only: use `SemanticSEGBLogger`, build the graph, and call `serialize()`
- backend-backed: add `SEGBPublisher` when you want to send Turtle to `POST /ttl`

## Basic Example

This is the smallest end-to-end script that still produces a meaningful semantic trace and publishes it to the backend.

Scenario: a user called Maria says "Hello robot". We want to keep three facts connected:

- who spoke
- which activity recorded the utterance
- which message was produced by that activity

Create `basic_semantic_log.py`:

```python
from datetime import datetime, timezone
import os

from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger
from semantic_log_generator.namespaces import ORO

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
)

human_uri = logger.register_human("maria", first_name="Maria")

listen_activity = logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=datetime.now(timezone.utc),
)

logger.log_message(
    "Hello robot",
    message_id="human_msg_1",
    generated_by_activity=listen_activity,
    message_types=[ORO.InitialMessage],
    language="en",
    sender=human_uri,
)

publisher = SEGBPublisher(
    base_url="http://localhost:5000",
    token=os.getenv("SEGB_API_TOKEN"),
    default_user="demo_robot",
)

publish_result = publisher.publish_graph(logger.graph)
print("Published:", publish_result)
print("Triples:", len(logger.graph))
```

Run it:

```bash
python basic_semantic_log.py
```

### Why Each Part Is There

| Code | Why it is there | What it means in practice |
|---|---|---|
| `datetime, timezone` | to timestamp the activity in UTC | activity times become explicit RDF provenance instead of implicit local runtime time |
| `ActivityKind` | to classify the activity at the Python API level | you say "this is a listening step" without manually choosing ontology classes |
| `SEGBPublisher` | to send the generated graph to the backend | the package can work locally without it, but publishing requires it |
| `SemanticSEGBLogger(...)` | to create the in-memory RDF graph and define how local identifiers become URIs | `base_namespace` is the stable URI base, `robot_id` identifies the runtime, `robot_name` adds a readable label |
| `register_human("maria", ...)` | to create the human actor once and reuse its URI | later messages and activities can point to the same person resource |
| `log_activity(...)` | to record one causal step in the trace | `activity_id` keeps the URI stable, `activity_kind` selects the default semantic class, `started_at` records when it happened |
| `log_message(...)` | to record the human utterance as an entity produced by that activity | `generated_by_activity` ties the message to the listening event, `sender` attributes it to Maria, `ORO.InitialMessage` marks it as human input, and `language` is mandatory for that semantic type |
| `SEGBPublisher(...)` | to configure how the graph is sent to the backend | `base_url` points to the API, `token` is used only when auth is enabled, `default_user` fills the backend `user` field |
| `publish_graph(logger.graph)` | to serialize the graph and post it to `/ttl` | you publish the actual RDF graph created so far |
| `print(...)` | to make the result observable during integration | useful as a smoke check before you inspect `/events` or the UI |

### What This Example Gives You

This basic script already produces a trace with:

- one robot
- one human
- one listening activity
- one input message
- provenance between activity and message
- sender attribution
- publish to backend

That is the minimum useful unit for debugging and for checking that your runtime is producing connected RDF, not just
isolated entities.

## Advanced Example

Scenario: Maria says, "I am worried about tomorrow's exam." The robot hears the utterance, treats it as a shared event
that could also be observed by another robot, runs a decision step with a dialogue model, replies, and records its own
state after replying.

This version adds the pieces that usually matter in a real integration:

- shared context for cross-robot event alignment
- explicit causality between input and decision
- model provenance with `ModelUsage`
- response generation
- robot state captured as a result of the decision
- optional retry queue in the publisher

Instead of dropping the whole script at once, build it in the same order as the actual interaction.

### Step 1: Prepare Imports, Time, And Optional Shared-Context Resolution

Start with the imports and the runtime values that several later steps will reuse:

```python
from datetime import datetime, timezone
import os

from semantic_log_generator import (
    ActivityKind,
    ModelUsage,
    RobotStateSnapshot,
    SEGBPublisher,
    SemanticSEGBLogger,
    build_http_shared_context_resolver_from_env,
)
from semantic_log_generator.namespaces import ORO

now = datetime.now(timezone.utc)

resolver = build_http_shared_context_resolver_from_env()
```

Why this comes first:

- `now` gives the example one stable reference time instead of several unrelated timestamps
- `ModelUsage` and `RobotStateSnapshot` are needed only in the richer flow
- `build_http_shared_context_resolver_from_env()` activates backend shared-context resolution only if the environment is
  configured for it; otherwise it returns `None` and the example still works

### Step 2: Create The Logger And Register The Main Actors

Now define the RDF namespace used by this runtime and create stable actor URIs:

```python
logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
    shared_event_resolver=resolver,
)

human_uri = logger.register_human("maria", first_name="Maria")
robot_uri = logger.register_robot()
```

Why this matters:

- `base_namespace` decides how local identifiers such as `listen_1` or `human_msg_1` become URIs
- `robot_id` is the stable logical identity of the runtime
- `robot_name` gives the robot a readable label in the graph and the UI
- `shared_event_resolver=resolver` is what actually enables backend-assisted shared-context resolution
- `human_uri` and `robot_uri` let later messages and activities point to the same agents instead of recreating them

### Step 3: Resolve The Underlying Shared Event

Before logging the robot-side activities, define the real-world event they are about:

```python
shared_event_uri = logger.get_shared_event_uri(
    event_kind="spoken_utterance",
    observed_at=now,
    subject=human_uri,
    text="I am worried about tomorrow's exam",
    modality="speech",
)
```

Why this matters:

- the user utterance is not only a message, it is also a real-world event that several observations may refer to
- `event_kind`, `text`, `modality`, and `subject` give the resolver enough evidence to align this event across robots
- if backend shared-context resolution is active, the logger can get a canonical URI from the backend; otherwise it can
  still resolve one locally

### Step 4: Log The Listening Activity And The Input Message

Now log what the robot observed and the message entity produced from that observation:

```python
listen_activity = logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=now,
    related_shared_events=[shared_event_uri],
)

input_message = logger.log_message(
    "I am worried about tomorrow's exam",
    message_id="human_msg_1",
    generated_by_activity=listen_activity,
    message_types=[ORO.InitialMessage],
    language="en",
    sender=human_uri,
)
```

What this adds:

- `listen_activity` records that one listening step happened at a known time
- `related_shared_events=[shared_event_uri]` says that this activity is about the shared spoken event
- `generated_by_activity=listen_activity` keeps the message connected to the listening step that produced it
- `message_types=[ORO.InitialMessage]` marks the message as human input
- `language="en"` is required for `ORO.InitialMessage`
- `sender=human_uri` attributes the utterance to Maria

### Step 5: Log The Decision Activity And Its Model Provenance

The next step is the internal decision that consumes the input and uses a dialogue model:

```python
decision_activity = logger.log_activity(
    activity_id="decision_1",
    activity_kind=ActivityKind.DECISION,
    started_at=now,
    triggered_by_entity=input_message,
    used_entities=[input_message],
    related_shared_events=[shared_event_uri],
    model_usages=[
        ModelUsage(
            model="https://example.org/models/dialogue_v1",
            parameters={"temperature": 0.2, "top_p": 0.9},
            implementation="dialogue_impl_v1",
            software_label="ollama",
            software_version="0.6.0",
        )
    ],
)
```

Why this part is important:

- `triggered_by_entity=input_message` captures causality: the decision happened because of that utterance
- `used_entities=[input_message]` captures data dependency: the message was actually consumed by the decision
- `related_shared_events=[shared_event_uri]` keeps the decision tied to the same episode as the listening step
- `ModelUsage(...)` records which model, parameters, implementation, and software version participated in the decision
- this is the difference between a graph that says "the robot answered" and a graph that says "the robot answered
  because of this input, using this model configuration"

### Step 6: Log The Robot Reply And The Robot State

Once the decision is made, record both the outward reply and the operational state after that reply:

```python
reply_message = logger.log_message(
    "I am here with you. Would you like to talk about what worries you most?",
    message_id="robot_reply_1",
    generated_by_activity=decision_activity,
    sender=robot_uri,
)

state_uri = logger.log_robot_state(
    RobotStateSnapshot(
        timestamp=now,
        battery_level=0.78,
        autonomy_mode="dialogue_support",
        location="room_a",
        note="State captured after generating the response.",
    ),
    state_id="state_after_reply",
    source_activity=decision_activity,
)
```

Why this matters:

- `reply_message` is the actual entity produced by the decision
- `generated_by_activity=decision_activity` keeps the response connected to the step that created it
- `sender=robot_uri` makes the robot explicitly responsible for the reply
- `RobotStateSnapshot(...)` lets you capture operational context in Python form
- `source_activity=decision_activity` says that this state belongs to that same decision phase instead of floating
  independently in the graph

### Step 7: Publish The Graph

Only after the graph is complete do you configure the HTTP publisher and send the accumulated RDF:

```python
publisher = SEGBPublisher(
    base_url="http://localhost:5000",
    token=os.getenv("SEGB_API_TOKEN"),
    default_user="demo_robot",
    queue_file=".segb_publish.queue",
)

publish_result = publisher.publish_graph(logger.graph)
print("Published:", publish_result)
print("Triples:", len(logger.graph))
print("Reply URI:", reply_message)
print("State URI:", state_uri)
```

Why the publisher is configured at the end:

- the logger is responsible for building the graph in memory
- the publisher is only responsible for transport to the backend
- `queue_file` is useful if you want retryable publication behavior in unstable environments

### Complete Advanced Script

Once the steps above are clear, this is the whole script in one place:

```python
from datetime import datetime, timezone
import os

from semantic_log_generator import (
    ActivityKind,
    ModelUsage,
    RobotStateSnapshot,
    SEGBPublisher,
    SemanticSEGBLogger,
    build_http_shared_context_resolver_from_env,
)
from semantic_log_generator.namespaces import ORO

now = datetime.now(timezone.utc)

resolver = build_http_shared_context_resolver_from_env()

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
    shared_event_resolver=resolver,
)

human_uri = logger.register_human("maria", first_name="Maria")
robot_uri = logger.register_robot()

shared_event_uri = logger.get_shared_event_uri(
    event_kind="spoken_utterance",
    observed_at=now,
    subject=human_uri,
    text="I am worried about tomorrow's exam",
    modality="speech",
)

listen_activity = logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=now,
    related_shared_events=[shared_event_uri],
)

input_message = logger.log_message(
    "I am worried about tomorrow's exam",
    message_id="human_msg_1",
    generated_by_activity=listen_activity,
    message_types=[ORO.InitialMessage],
    language="en",
    sender=human_uri,
)

decision_activity = logger.log_activity(
    activity_id="decision_1",
    activity_kind=ActivityKind.DECISION,
    started_at=now,
    triggered_by_entity=input_message,
    used_entities=[input_message],
    related_shared_events=[shared_event_uri],
    model_usages=[
        ModelUsage(
            model="https://example.org/models/dialogue_v1",
            parameters={"temperature": 0.2, "top_p": 0.9},
            implementation="dialogue_impl_v1",
            software_label="ollama",
            software_version="0.6.0",
        )
    ],
)

reply_message = logger.log_message(
    "I am here with you. Would you like to talk about what worries you most?",
    message_id="robot_reply_1",
    generated_by_activity=decision_activity,
    sender=robot_uri,
)

state_uri = logger.log_robot_state(
    RobotStateSnapshot(
        timestamp=now,
        battery_level=0.78,
        autonomy_mode="dialogue_support",
        location="room_a",
        note="State captured after generating the response.",
    ),
    state_id="state_after_reply",
    source_activity=decision_activity,
)

publisher = SEGBPublisher(
    base_url="http://localhost:5000",
    token=os.getenv("SEGB_API_TOKEN"),
    default_user="demo_robot",
    queue_file=".segb_publish.queue",
)

publish_result = publisher.publish_graph(logger.graph)
print("Published:", publish_result)
print("Triples:", len(logger.graph))
print("Reply URI:", reply_message)
print("State URI:", state_uri)
```

Run it:

```bash
python advanced_semantic_log.py
```

### How To Read The Advanced Graph

This second script gives you a more realistic semantic chain:

1. the human utterance is recognized as one event
2. the listening activity records that event
3. the input message is generated by the listening activity
4. the decision activity is triggered by and uses that message
5. model provenance is attached to the decision
6. the robot reply is generated by the decision
7. the post-decision robot state is recorded and linked back to the same activity

That is the kind of structure that starts to pay off in real audits, reports, and post-hoc debugging.

## In A Real Robot, This Logic Is Usually Distributed

The advanced example above is intentionally written as one script so the full semantic chain is easy to understand.
Real robots usually do not have one giant file that hears, decides, replies, and records state in one place.

In practice, log generation is often spread across several applications or nodes:

- an ASR or dialogue-input component logs the listening activity and the incoming message
- a decision or dialogue-policy component logs the decision activity and model usage
- a response component logs the robot reply
- a telemetry or supervision component logs robot state snapshots

The important part is not that one process owns every log call. The important part is that all of them use:

- the same `robot_id`
- a stable `base_namespace`
- deterministic IDs where possible
- shared-event resolution or shared identifiers when several components refer to the same episode

### ROS 2 Example: Dialogue Callback

In a ROS 2 system, one node might log the dialogue-side part of the interaction when a subscriber callback receives a
user utterance:

```python
from datetime import datetime, timezone

from rclpy.node import Node

from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger
from semantic_log_generator.namespaces import ORO


class DialogueNode(Node):
    def __init__(self) -> None:
        super().__init__("dialogue_node")
        self.segb = SemanticSEGBLogger(
            base_namespace="https://example.org/segb/robots/demo/v1/",
            robot_id="demo_robot",
            robot_name="Demo Robot",
        )
        self.publisher = SEGBPublisher(base_url="http://localhost:5000", default_user="demo_robot")

    def on_user_utterance(self, user_id: str, text: str) -> None:
        now = datetime.now(timezone.utc)
        human_uri = self.segb.register_human(user_id, first_name=user_id.capitalize())
        listen_activity = self.segb.log_activity(
            activity_id=f"listen_{user_id}_{int(now.timestamp())}",
            activity_kind=ActivityKind.LISTENING,
            started_at=now,
        )
        self.segb.log_message(
            text,
            message_id=f"msg_{user_id}_{int(now.timestamp())}",
            generated_by_activity=listen_activity,
            message_types=[ORO.InitialMessage],
            language="en",
            sender=human_uri,
        )
        self.publisher.publish_graph(self.segb.graph)
```

This callback does not try to represent the whole robot. It logs only the part that actually happens in that node:
the robot received an utterance from a human.

### ROS 2 Example: State Monitor

Another ROS 2 node can log state snapshots independently:

```python
from datetime import datetime, timezone

from semantic_log_generator import RobotStateSnapshot, SemanticSEGBLogger


def log_state_tick(logger: SemanticSEGBLogger, battery_level: float, autonomy_mode: str) -> None:
    logger.log_robot_state(
        RobotStateSnapshot(
            timestamp=datetime.now(timezone.utc),
            battery_level=battery_level,
            autonomy_mode=autonomy_mode,
            location="room_a",
        )
    )
```

This is often a better architecture than forcing one central component to know everything. Each node logs what it
really observes or produces, and the backend later stores those fragments in one queryable graph.

## Verify The Result

If auth is disabled:

```bash
curl -s http://localhost:5000/events | head -n 40
```

If auth is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 40
```

You should see resources related to your `demo_robot`, `maria`, the logged activities, and the generated messages.

## Failure Modes To Expect

- `SEGBPublisher.publish_turtle()` and `publish_graph()` raise `RuntimeError` on backend HTTP errors.
- Those same methods raise `requests.RequestException` on network failures.
- If you need retryable offline behavior, create the publisher with `queue_file=...` and flush it later with
  `flush_queue()`.
- `oro:InitialMessage` requires an explicit `language`; otherwise `log_message()` raises `ValueError`.
- `build_http_shared_context_resolver_from_env()` returns `None` when `SEGB_API_URL` is not set; this does not break
  the logger, but it means backend shared-context resolution is not active.

## Production-Friendly Notes

- Keep `base_namespace` stable for a deployment.
- Use deterministic IDs for important entities (`activity_id`, `message_id`, `state_id`) when traceability matters.
- Introduce shared context only when you need cross-robot event alignment; do not turn it on implicitly without a use
  case.
- Avoid destructive graph reset (`/ttl/delete_all`) in normal runtime pipelines.

## Next

- [API Reference](api-reference.md)
- [Publish Your First Log](../guides/publish-your-first-log.md)
- [Shared Context Workflow](../guides/shared-context-workflow.md)
