# Real-World Integration Example (ROS4HRI)

## Objective

Integrate `semantic_log_generator` into an existing ROS4HRI mission controller and optionally publish logs to SEGB.

## Prerequisites

- PAL ROS4HRI tutorial completed through the mission-controller stage (external requirement)
- Running ROS 2 workspace with your mission controller package
- Optional SEGB backend running if you enable publishing
- Optional Ollama server if you enable LLM responses

Note: ROS4HRI container/workspace details are external to this repository.

## Steps

### 1) Start SEGB backend (optional but recommended)

From this repository root:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
curl -s http://localhost:5000/healthz/ready
```

Expected: `{"ready": true, "virtuoso": true}`.

### 2) Install package in robot environment

Inside your ROS container/runtime:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "semantic-log-generator>=1.0.0,<2.0.0"
```

Verify:

```bash
python -c "import semantic_log_generator; print(semantic_log_generator.__version__)"
```

### 3) Add logger to your controller

Use this minimum pattern:

```python
from datetime import datetime, timezone

from semantic_log_generator import ActivityKind, RobotStateSnapshot, SEGBPublisher, SemanticSEGBLogger

self.segb = SemanticSEGBLogger(
    base_namespace="https://gsi.upm.es/segb/robots/demo_robot/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
    namespace_prefix="emotion_mirror",
    compact_resource_ids=True,
)

self.publisher = SEGBPublisher(
    base_url="http://localhost:5000",
    token="<jwt_or_none>",
    default_user="demo_robot",
)
```

### 4) Log one user utterance flow

```python
observed_at = datetime.now(timezone.utc)
shared_event = self.segb.get_shared_event_uri(
    event_kind="human_utterance",
    observed_at=observed_at,
    subject=human_uri,
    text=user_text,
    modality="speech",
)

listen_activity = self.segb.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=observed_at,
    related_shared_events=[shared_event],
)

heard_msg = self.segb.log_message(
    user_text,
    message_id="heard_1",
    generated_by_activity=listen_activity,
    language="en",
)

self.segb.link_observation_to_shared_event(heard_msg, shared_event, confidence=0.95)
```

### 5) Log response and state

```python
response_activity = self.segb.log_activity(
    activity_id="respond_1",
    activity_kind=ActivityKind.RESPONSE,
    started_at=datetime.now(timezone.utc),
    triggered_by_activity=listen_activity,
    triggered_by_entity=heard_msg,
    related_shared_events=[shared_event],
)

self.segb.log_message(
    robot_reply,
    message_id="reply_1",
    generated_by_activity=response_activity,
    previous_message=heard_msg,
)

self.segb.log_robot_state(
    RobotStateSnapshot(
        mission_phase="interactive",
        network_status="online",
        location="location_demo_room",
    ),
    source_activity=response_activity,
)
```

### 6) Publish safely

```python
ttl_text = self.segb.serialize(format="turtle")
self.publisher.publish_turtle(ttl_text, user="demo_robot")
```

### 7) Build and run your ROS package

In your ROS workspace:

```bash
colcon build
source install/setup.bash
ros2 launch <your_package> <your_launch_file>.launch.py
```

## Validation

- Controller runs without import/runtime errors.
- Turtle generation is non-empty.
- If publishing is enabled, `GET /events` returns inserted triples.

## Troubleshooting

- `401/403` when publishing: invalid or missing JWT for enabled auth mode.
- Shared-event mismatch between robots: ensure both use same resolver policy/time window.
- Callback latency with LLM responses: move LLM call out of callback path or use async worker.

## Next

- Package API details: [Usage](usage.md)
- Resolver behavior: [Shared Context Resolution](../backend/shared-context.md)
