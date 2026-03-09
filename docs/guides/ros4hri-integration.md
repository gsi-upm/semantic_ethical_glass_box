# ROS4HRI Integration

This guide starts from the ROS4HRI Part 3 emotion mirror example and turns it into a SEGB-aware robot flow. The path
is deliberate. First you keep the original behavior so the scenario stays familiar. Then you add a small Ollama-based
reply generator so the robot has a richer dialogue step. Finally, you wrap the meaningful interaction points with
semantic logging and publish them to SEGB.

At the end, one ROS node will do four things in one place: listen to the user, generate a short reply, mirror a facial
expression, and publish a trace that you can inspect later in `/reports` and `/kg-graph`.

## Before You Start

You need the ROS4HRI tutorial completed through Part 3:
<https://ros4hri.github.io/ros4hri-tutorials/interactive-social-robots/#part-3-building-a-simple-social-behaviour>

You also need:

- a working ROS 2 workspace with `emotion_mirror`
- a local checkout of this SEGB repository
- Docker Engine and Docker Compose v2
- Ollama installed locally if you want real LLM replies

For the first run, keep SEGB authentication disabled. That keeps the guide focused on the integration itself and avoids
JWT setup while you are still wiring the robot.

## Step 1: Start SEGB

Before touching the robot code, start the SEGB stack. This gives you a backend ready to receive Turtle payloads and a
UI ready to show the result. Starting SEGB first matters because it shortens the feedback loop: as soon as the robot
publishes something, you can verify it immediately.

From the SEGB repository root:

```bash
cp .env.example .env
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
curl -s http://localhost:5000/healthz/ready
```

You want:

```json
{"ready": true, "virtuoso": true}
```

That response means the backend is up and its storage layer is reachable. If readiness stays `false`, stop here and
check [Centralized Deployment](../operations/centralized-deployment.md). There is no point instrumenting the robot if
the place where it should publish is not ready yet.

## Step 2: Install The Runtime Dependencies

Install `semantic_log_generator` inside the robot runtime itself, using `pip` in the same Python environment that runs
your ROS node. The package does not run inside the SEGB backend. The robot is the component that builds the RDF logs,
so the robot is where `semantic_log_generator` must be installed. If your robot runs in its own container or on its own
computer, run these commands there.

From a local checkout:

```bash
python -m pip install -e /path/to/semantic_ethical_glass_box/packages/semantic_log_generator
python -m pip install ollama
```

The first command installs the SEGB logger package in editable mode so you can integrate it directly from this
repository. The second installs the Python client that your ROS node will use to talk to Ollama.

If you want the dialogue step to use Ollama for real instead of falling back to a fixed sentence, make sure the Ollama
runtime is up and pull the model used in this guide. Start the runtime in one terminal:

```bash
ollama serve
```

Then pull the model in another terminal:

```bash
ollama pull phi4:14b
```

Quick checks:

```bash
python -c "from semantic_log_generator import SemanticSEGBLogger; print('segb ok')"
python -c "from ollama import Client; print('ollama client ok')"
```

If both checks work, the robot runtime has everything it needs to build logs and optionally generate replies through
Ollama.

## Step 3: Start From The Part 3 Mission Controller

This is the plain Part 3 `mission_controller.py` before Ollama and SEGB. Use it as the baseline in your ROS
workspace:

`ws/src/emotion_mirror/emotion_mirror/mission_controller.py`

```python
import json

from hri import HRIListener
from hri_actions_msgs.msg import Intent
from hri_msgs.msg import Expression
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile
from tts_msgs.action import TTS


class MissionController(Node):
    def __init__(self) -> None:
        super().__init__("emotion_mirror")

        self.create_subscription(Intent, "/intents", self.on_intent, 10)
        self.expression_pub = self.create_publisher(Expression, "/robot_face/expression", QoSProfile(depth=10))
        self.hri_listener = HRIListener("mimic_emotion_hrilistener")

        self.tts = ActionClient(self, TTS, "/say")
        self.tts.wait_for_server()

        self._last_expression = ""
        self.create_timer(0.1, self.run)

    def on_intent(self, msg: Intent) -> None:
        try:
            if msg.intent != Intent.RAW_USER_INPUT:
                return

            data = json.loads(msg.data) if msg.data else {}
            text = str(
                data.get("text")
                or data.get("utterance")
                or data.get("message")
                or data.get("object")
                or msg.data
                or ""
            ).strip()
            if not text:
                return

            self._say("I heard you. Could you tell me a bit more so I can help you better?")
        except Exception as error:
            self.get_logger().error(f"on_intent exception (ignored): {type(error).__name__}: {error}")

    def run(self) -> None:
        try:
            faces = list(self.hri_listener.faces.items())
            if not faces:
                return

            _, face = faces[0]
            if not face.expression:
                return

            expression = face.expression.name.lower()
            if expression == self._last_expression:
                return
            self._last_expression = expression

            spoken = f"you look {expression}. Same for me!"
            self._say(spoken)

            out = Expression()
            out.expression = expression
            self.expression_pub.publish(out)
        except Exception as error:
            self.get_logger().error(f"run() exception (ignored): {type(error).__name__}: {error}")

    def _say(self, text: str) -> None:
        goal = TTS.Goal()
        goal.input = text
        self.tts.send_goal_async(goal)
```

This file already has the behavior you care about: it reacts to user input and mirrors observed expressions. That is
exactly why it is a good tutorial starting point. You are not inventing a new robot behavior for SEGB; you are taking a
behavior that already exists and making it explainable afterwards.

## Step 4: Add Ollama Before SEGB

Add Ollama first. That keeps the change easy to reason about. Before SEGB enters the picture, the robot still listens
and speaks exactly as before, but its spoken reply can now come from a local model instead of always being the same
fixed sentence.

Start with the import:

```python
try:
    from ollama import Client as OllamaClient
except Exception:
    OllamaClient = None
```

This keeps the file robust. If Ollama is not installed or not available in the current environment, the node still
starts and can fall back to a fixed reply.

Then add two class constants:

```python
class MissionController(Node):
    OLLAMA_HOST = "http://127.0.0.1:11434"
    OLLAMA_MODEL = "phi4:14b"
```

These constants keep the model configuration in one place instead of scattering it through the callback logic.

Initialize the client in `__init__`, right after `self.tts.wait_for_server()`:

```python
self.ollama = OllamaClient(host=self.OLLAMA_HOST) if OllamaClient else None
```

Now add a helper that asks Ollama for one short spoken reply and falls back cleanly if Ollama is missing or returns an
error:

```python
def _reply(self, text: str, user_name: str) -> tuple[str, str]:
    fallback = "I heard you. Could you tell me a bit more so I can help you better?"
    if not self.ollama:
        return fallback, "fallback"

    system = "You are a friendly social robot. Reply with one short, polite sentence suitable for speech output."
    user = f"User ({user_name}) says: {text}"

    try:
        response = self.ollama.chat(
            model=self.OLLAMA_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        content = ""
        if hasattr(response, "message") and getattr(response.message, "content", None):
            content = str(response.message.content)
        elif isinstance(response, dict):
            content = str(response.get("message", {}).get("content", ""))
        content = " ".join(content.split()).strip()
        return (content[:280] if content else fallback), ("ollama" if content else "fallback-empty")
    except Exception:
        return fallback, "fallback-ollama-error"
```

This helper deliberately returns two values: the reply itself and a small source label. That source label becomes useful
in the next step, because it lets the SEGB logs say whether the reply actually came from Ollama.

Finally, replace the fixed reply inside `on_intent`:

```python
name = str(data.get("name") or data.get("speaker") or data.get("user") or getattr(msg, "source", "") or "human_user")
reply, _reply_source = self._reply(text, name)
self._say(reply)
```

At this point the robot still behaves like the same emotion mirror example, but its dialogue branch is already more
interesting. Only now is it worth adding SEGB around it.

## Step 5: Add SEGB Step By Step

Now add the SEGB part in the robot code. Keep using the same `mission_controller.py` in your robot workspace. The goal
of this section is not to paste a finished file blindly, but to show exactly where each SEGB fragment goes and why it is
there.

This first integration is intentionally small. It does not use shared-event resolution, robot-state snapshots, or
detailed emotion annotations yet. Those features are useful later, but they are not required to learn the basic
pattern: log what the robot perceived, log what the robot said or did next, and publish the graph to SEGB.

### 5.1 Add The SEGB Imports At The Top Of The File

Insert these imports near the top of `mission_controller.py`, after the ROS imports and before the class definition:

```python
import os
import threading
from datetime import datetime, timezone

from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger
from semantic_log_generator.namespaces import ORO
```

Three things happen here. `SemanticSEGBLogger` builds the RDF graph locally inside the robot process. `SEGBPublisher`
sends that graph to the backend over HTTP. `ActivityKind` and `ORO` give you stable vocabulary for the activities and
messages you are about to log.

### 5.2 Add The SEGB Constants Inside `MissionController`

Inside the `MissionController` class, place these constants just below the Ollama constants:

```python
class MissionController(Node):
    OLLAMA_HOST = "http://127.0.0.1:11434"
    OLLAMA_MODEL = "phi4:14b"

    SEGB_BASE_URL = "http://localhost:5000"
    SEGB_BASE_NAMESPACE = "https://example.org/segb/robots/emotion-mirror/v1/"
    SEGB_ROBOT_ID = "emotion_mirror_robot"
    SEGB_ROBOT_NAME = "Emotion Mirror Robot"
    SEGB_DEFAULT_LANGUAGE = "en"
```

These values do two jobs. `SEGB_BASE_URL` tells the robot where the backend lives. The namespace, robot ID, and robot
name tell SEGB how to mint URIs for this robot and how to label them in the graph.

### 5.3 Initialize The Logger And Publisher In `__init__`

In `__init__`, add this block right after `self.ollama = ...` and before `self.create_timer(0.1, self.run)`:

```python
self.segb = SemanticSEGBLogger(
    base_namespace=self.SEGB_BASE_NAMESPACE,
    robot_id=self.SEGB_ROBOT_ID,
    robot_name=self.SEGB_ROBOT_NAME,
    default_language=self.SEGB_DEFAULT_LANGUAGE,
    namespace_prefix="emotion_mirror",
    compact_resource_ids=True,
)
self.chat_model = self.segb.register_ml_model(
    "ollama_dialogue_model",
    label=f"Ollama Dialogue ({self.OLLAMA_MODEL})",
    version="1.0",
    provider="Ollama",
)
self.publisher = SEGBPublisher(
    base_url=self.SEGB_BASE_URL,
    token=os.getenv("SEGB_API_TOKEN"),
    default_user=self.SEGB_ROBOT_ID,
)
```

This is the moment where the robot becomes SEGB-aware. The logger starts a local RDF graph and registers the robot in
it. The publisher is the bridge to the backend. The `chat_model` registration is small but useful: it lets your logs say
that a given response used the Ollama-based dialogue step without forcing you to model a more elaborate pipeline yet.

One logger instance lives for the whole node. That means each callback adds triples to the same in-memory graph. When
you publish, you are sending the graph accumulated so far, not just the very last triple.

### 5.4 Add The SEGB Helper Methods Near The End Of The Class

Add these methods near the end of the class, just before `_say`:

```python
def _human(self, human_hint: str, display_name: str | None = None):
    human_id = "".join(char if char.isalnum() else "_" for char in human_hint.strip().lower()).strip("_")
    human_id = human_id or "human_user"
    return self.segb.register_human(
        human_id,
        first_name=display_name or human_hint.replace("_", " ").title(),
    )

def _publish_segb_safe(self) -> None:
    ttl_text = self.segb.serialize(format="turtle")

    def worker() -> None:
        try:
            self.publisher.publish_turtle(ttl_text)
        except Exception as error:
            self.get_logger().error(f"SEGB publish failed: {type(error).__name__}: {error}")

    threading.Thread(target=worker, daemon=True).start()
```

`_human` turns whatever identifier arrives in the intent payload into a stable human resource. That is important because
the graph becomes much more useful when messages are attributed to an explicit actor instead of being left as anonymous
text. `_publish_segb_safe` keeps the ROS callback responsive by publishing in a background thread instead of waiting for
the HTTP request to finish inline.

### 5.5 Instrument `on_intent`

`on_intent` is the easiest place to start because the structure is already clear. A human says something, the robot
hears it, the robot answers. SEGB just makes those steps explicit.

Inside `on_intent`, keep the existing JSON parsing exactly as it is. Then, right after `if not text: return`, insert
this block:

```python
name = str(
    data.get("name")
    or data.get("speaker")
    or data.get("user")
    or getattr(msg, "source", "")
    or "human_user"
).strip()
now = datetime.now(timezone.utc)
human_uri = self._human(name)

listening = self.segb.log_activity(
    activity_kind=ActivityKind.LISTENING,
    label="Robot listens to a user utterance",
    started_at=now,
    ended_at=now,
)
heard_message = self.segb.log_message(
    text,
    language=self.SEGB_DEFAULT_LANGUAGE,
    message_types=[ORO.InitialMessage],
    generated_by_activity=listening,
    sender=human_uri,
)

reply, reply_source = self._reply(text, name)
self._say(reply)

response = self.segb.log_activity(
    activity_kind=ActivityKind.RESPONSE,
    label="Robot speaks the reply",
    started_at=now,
    ended_at=now,
    triggered_by_activity=listening,
    triggered_by_entity=heard_message,
    used_entities=[heard_message],
    used_models=[self.chat_model] if reply_source == "ollama" else None,
)
self.segb.log_message(
    reply,
    message_types=[ORO.ResponseMessage],
    generated_by_activity=response,
    sender=self.segb.robot_uri,
)
self._publish_segb_safe()
```

Read that snippet in order.

`self._human(name)` turns the raw speaker string into a stable human node. `log_activity(...LISTENING...)` records that
the robot entered a listening phase. `log_message(...)` records what was heard and attributes the message to the human.

Then `_reply(...)` generates the spoken answer exactly as before, but now the answer is wrapped by a response activity.
This tutorial deliberately does not create a separate "decision" activity, because for a first integration that tends to
add complexity without making the graph much easier to understand.

The response activity points back to the input activity and the input message. That one relation is already enough to
capture a simple causal chain: the robot heard something, then the robot answered. When `reply_source == "ollama"`, the
activity also records that the Ollama model was involved.

### 5.6 Instrument `run`

The `run` callback handles the facial-expression branch. Here the robot observes an expression and reacts by mirroring
it. For a first tutorial, that is enough. We do not yet classify the expression into a richer emotion ontology or try to
resolve the face to a specific human identity.

Inside `run`, keep the original face-reading logic. Then, right after `self._last_expression = expression`, insert this
block:

```python
now = datetime.now(timezone.utc)

recognition = self.segb.log_activity(
    activity_kind=ActivityKind.EMOTION_RECOGNITION,
    label="Robot recognizes a facial expression",
    started_at=now,
    ended_at=now,
)
expression_observation = self.segb.log_observation(
    label=f"Observed facial expression: {expression}",
    generated_by_activity=recognition,
)
```

This first block records the perception side of the interaction. The robot recognized an expression, and that activity
generated an observation entity describing what was seen.

Leave the original speaking and expression-publishing lines in place. Then, immediately after
`self.expression_pub.publish(out)`, insert this second block:

```python
response = self.segb.log_activity(
    activity_kind=ActivityKind.RESPONSE,
    label="Robot mirrors the detected facial expression",
    started_at=now,
    ended_at=now,
    triggered_by_activity=recognition,
    triggered_by_entity=expression_observation,
    used_entities=[expression_observation],
)
self.segb.log_message(
    spoken,
    message_types=[ORO.ResponseMessage],
    generated_by_activity=response,
    sender=self.segb.robot_uri,
)
self._publish_segb_safe()
```

This second block records the action side. The robot did not just observe; it reacted. The response activity points back
to the observation that triggered it, and the spoken sentence is logged as the message generated by that response.

That is enough to make the perception-to-action chain visible in SEGB without overloading the tutorial with advanced
modeling choices.

## Step 6: Final Integrated Version

If you want to compare your file against a complete result after all the previous edits, use the version below:

```python
import json
import os
import threading
from datetime import datetime, timezone

from hri import HRIListener
from hri_actions_msgs.msg import Intent
from hri_msgs.msg import Expression
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile
from tts_msgs.action import TTS

try:
    from ollama import Client as OllamaClient
except Exception:
    OllamaClient = None

from semantic_log_generator import ActivityKind, SEGBPublisher, SemanticSEGBLogger
from semantic_log_generator.namespaces import ORO


class MissionController(Node):
    OLLAMA_HOST = "http://127.0.0.1:11434"
    OLLAMA_MODEL = "phi4:14b"

    SEGB_BASE_URL = "http://localhost:5000"
    SEGB_BASE_NAMESPACE = "https://example.org/segb/robots/emotion-mirror/v1/"
    SEGB_ROBOT_ID = "emotion_mirror_robot"
    SEGB_ROBOT_NAME = "Emotion Mirror Robot"
    SEGB_DEFAULT_LANGUAGE = "en"

    def __init__(self) -> None:
        super().__init__("emotion_mirror")

        self.create_subscription(Intent, "/intents", self.on_intent, 10)
        self.expression_pub = self.create_publisher(Expression, "/robot_face/expression", QoSProfile(depth=10))
        self.hri_listener = HRIListener("mimic_emotion_hrilistener")

        self.tts = ActionClient(self, TTS, "/say")
        self.tts.wait_for_server()

        self.ollama = OllamaClient(host=self.OLLAMA_HOST) if OllamaClient else None

        self.segb = SemanticSEGBLogger(
            base_namespace=self.SEGB_BASE_NAMESPACE,
            robot_id=self.SEGB_ROBOT_ID,
            robot_name=self.SEGB_ROBOT_NAME,
            default_language=self.SEGB_DEFAULT_LANGUAGE,
            namespace_prefix="emotion_mirror",
            compact_resource_ids=True,
        )
        self.chat_model = self.segb.register_ml_model(
            "ollama_dialogue_model",
            label=f"Ollama Dialogue ({self.OLLAMA_MODEL})",
            version="1.0",
            provider="Ollama",
        )
        self.publisher = SEGBPublisher(
            base_url=self.SEGB_BASE_URL,
            token=os.getenv("SEGB_API_TOKEN"),
            default_user=self.SEGB_ROBOT_ID,
        )

        self._last_expression = ""
        self.create_timer(0.1, self.run)

    def on_intent(self, msg: Intent) -> None:
        try:
            if msg.intent != Intent.RAW_USER_INPUT:
                return

            data = json.loads(msg.data) if msg.data else {}
            text = str(
                data.get("text")
                or data.get("utterance")
                or data.get("message")
                or data.get("object")
                or msg.data
                or ""
            ).strip()
            if not text:
                return

            name = str(
                data.get("name")
                or data.get("speaker")
                or data.get("user")
                or getattr(msg, "source", "")
                or "human_user"
            ).strip()
            now = datetime.now(timezone.utc)
            human_uri = self._human(name)

            listening = self.segb.log_activity(
                activity_kind=ActivityKind.LISTENING,
                label="Robot listens to a user utterance",
                started_at=now,
                ended_at=now,
            )
            heard_message = self.segb.log_message(
                text,
                language=self.SEGB_DEFAULT_LANGUAGE,
                message_types=[ORO.InitialMessage],
                generated_by_activity=listening,
                sender=human_uri,
            )

            reply, reply_source = self._reply(text, name)
            self._say(reply)

            response = self.segb.log_activity(
                activity_kind=ActivityKind.RESPONSE,
                label="Robot speaks the reply",
                started_at=now,
                ended_at=now,
                triggered_by_activity=listening,
                triggered_by_entity=heard_message,
                used_entities=[heard_message],
                used_models=[self.chat_model] if reply_source == "ollama" else None,
            )
            self.segb.log_message(
                reply,
                message_types=[ORO.ResponseMessage],
                generated_by_activity=response,
                sender=self.segb.robot_uri,
            )
            self._publish_segb_safe()
        except Exception as error:
            self.get_logger().error(f"on_intent exception (ignored): {type(error).__name__}: {error}")

    def run(self) -> None:
        try:
            faces = list(self.hri_listener.faces.items())
            if not faces:
                return

            _, face = faces[0]
            if not face.expression:
                return

            expression = face.expression.name.lower()
            if expression == self._last_expression:
                return
            self._last_expression = expression

            now = datetime.now(timezone.utc)

            recognition = self.segb.log_activity(
                activity_kind=ActivityKind.EMOTION_RECOGNITION,
                label="Robot recognizes a facial expression",
                started_at=now,
                ended_at=now,
            )
            expression_observation = self.segb.log_observation(
                label=f"Observed facial expression: {expression}",
                generated_by_activity=recognition,
            )

            spoken = f"You look {expression}. Same for me!"
            self._say(spoken)

            out = Expression()
            out.expression = expression
            self.expression_pub.publish(out)

            response = self.segb.log_activity(
                activity_kind=ActivityKind.RESPONSE,
                label="Robot mirrors the detected facial expression",
                started_at=now,
                ended_at=now,
                triggered_by_activity=recognition,
                triggered_by_entity=expression_observation,
                used_entities=[expression_observation],
            )
            self.segb.log_message(
                spoken,
                message_types=[ORO.ResponseMessage],
                generated_by_activity=response,
                sender=self.segb.robot_uri,
            )
            self._publish_segb_safe()
        except Exception as error:
            self.get_logger().error(f"run() exception (ignored): {type(error).__name__}: {error}")

    def _reply(self, text: str, user_name: str) -> tuple[str, str]:
        fallback = "I heard you. Could you tell me a bit more so I can help you better?"
        if not self.ollama:
            return fallback, "fallback"

        system = "You are a friendly social robot. Reply with one short, polite sentence suitable for speech output."
        user = f"User ({user_name}) says: {text}"

        try:
            response = self.ollama.chat(
                model=self.OLLAMA_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            content = ""
            if hasattr(response, "message") and getattr(response.message, "content", None):
                content = str(response.message.content)
            elif isinstance(response, dict):
                content = str(response.get("message", {}).get("content", ""))
            content = " ".join(content.split()).strip()
            return (content[:280] if content else fallback), ("ollama" if content else "fallback-empty")
        except Exception:
            return fallback, "fallback-ollama-error"

    def _human(self, human_hint: str, display_name: str | None = None):
        human_id = "".join(char if char.isalnum() else "_" for char in human_hint.strip().lower()).strip("_")
        human_id = human_id or "human_user"
        return self.segb.register_human(
            human_id,
            first_name=display_name or human_hint.replace("_", " ").title(),
        )

    def _publish_segb_safe(self) -> None:
        ttl_text = self.segb.serialize(format="turtle")

        def worker() -> None:
            try:
                self.publisher.publish_turtle(ttl_text)
            except Exception as error:
                self.get_logger().error(f"SEGB publish failed: {type(error).__name__}: {error}")

        threading.Thread(target=worker, daemon=True).start()

    def _say(self, text: str) -> None:
        goal = TTS.Goal()
        goal.input = text
        self.tts.send_goal_async(goal)
```

That full file is only a final check. The tutorial path is still the right way to follow it: add Ollama first, then the
SEGB imports and constants, then the logger and publisher, then the helper methods, then the dialogue instrumentation,
and finally the facial-expression instrumentation.

## Step 7: Run The Robot

From your ROS workspace:

```bash
colcon build
source install/setup.bash
ros2 launch emotion_mirror emotion_mirror.launch.py
```

Interact with the simulator. Speak to the robot so `on_intent` runs, and show expressions so `run()` sees non-empty
face data. If Ollama is available, the dialogue reply will come from the local model. If not, the node still works and
falls back to a fixed sentence.

## Step 8: Verify The Result In SEGB

First check that the backend has data:

```bash
curl -s http://localhost:5000/events | head -n 40
```

Then open:

- `http://localhost:8080/reports`
- `http://localhost:8080/kg-graph`

For this tutorial, the graph view is the most informative place to look first. You should see activities, messages, the
robot resource, and at least one detected expression observation. The reports page may still look lighter than the
report-ready demo dataset, and that is expected: this robot integration logs a meaningful trace, but it does not yet add
all the extra semantic enrichment used by the richer demo dashboards.

What matters at this stage is simpler. You want to confirm that a human utterance leads to a robot response, and that a
detected expression also leads to a robot response. If those chains exist in the graph, the integration is already
working.

## What This Integration Gives You

Without SEGB, the emotion mirror example runs, speaks, and reacts, but it leaves very little behind for later review.
With SEGB, the same interaction becomes inspectable evidence. You can trace what the robot heard, what it answered, what
expression it detected, and which action followed.

That is the practical value of this guide: not changing the robot behavior for its own sake, but making that behavior
explainable after it has happened.

## Next Steps

Once this simpler integration works, the next useful improvements are usually:

1. enrich the face branch with emotion annotations if you need richer emotion semantics
2. add shared-context resolution if several systems must agree on the same interaction event
3. review the result in [Explore the Web UI](explore-the-web-ui.md) and [API and Roles](../reference/api-and-roles.md)
