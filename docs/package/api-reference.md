# `semantic_log_generator` API Reference

This page is the formal reference for the package API. It is written for implementation work: you should be able to
scan the page, find the right method quickly, understand the accepted argument shapes, and avoid common misuse.

!!! tip "Start here if you are integrating the library"
    Read [Use `semantic_log_generator`](usage.md) first if you want a runnable flow. Use this page when you need exact
    method behavior, argument contracts, or the right object shape for a specific call.

## API Map

| You need to... | Go to |
|---|---|
| create logs in memory | [`SemanticSEGBLogger`](#semanticsegblogger) |
| publish Turtle to backend | [`SEGBPublisher`](#segbpublisher) |
| resolve shared events through backend | [`HTTPSharedContextResolver`](#httpsharedcontextresolver) |
| understand enum/data types used in signatures | [Signature Types](#signature-types-used-in-this-page) |

!!! note "Recommended mental model"
    The package has three layers:

    1. `SemanticSEGBLogger`: create RDF resources and relations in memory.
    2. `SEGBPublisher`: send Turtle or graphs to the backend.
    3. `HTTPSharedContextResolver`: ask the backend to align shared events across robots.

## Abstraction Level

`semantic_log_generator` is designed as a Python-first API, not as a thin RDF triple writer.

For the common path:

- use `ActivityKind` instead of choosing ontology classes manually
- use logger methods such as `register_human()`, `log_message()`, and `log_robot_state()` instead of constructing RDF
  entities yourself
- treat explicit ontology terms as an advanced escape hatch, not as the default integration path

### What The Abstraction Covers

In the common path, you usually do not need to know the exact ontology classes behind each method call.

Examples:

- `register_human("maria")` adds the expected human/person typing for you
- `log_activity(activity_kind=ActivityKind.DECISION)` adds the base activity typing plus the default ontology class for
  that kind
- `log_message("Hello")` creates a `schema:Message` and provenance links without requiring you to write triples
- `log_robot_state(...)` expands a Python snapshot into RDF entities and `schema:PropertyValue` nodes

This is the intended developer experience: Python-first inputs, RDF output.

<a id="activitykind-default-classifier"></a>
### `ActivityKind` As The Default Activity Classifier

`ActivityKind` is the main built-in abstraction used by `log_activity(...)`. It gives you a stable Python vocabulary
for the activity categories the package supports by default.

You can pass either:

- an enum member such as `ActivityKind.RESPONSE`
- the equivalent string such as `"response"`

| `ActivityKind` | Intended meaning | Default RDF type(s) added by the logger |
|---|---|---|
| `LISTENING` | the robot or system listens to an input | `oro:ListeningEvent` |
| `DECISION` | a decision or internal choice is made | `oro:DecisionMakingAction` |
| `RESPONSE` | the system produces a reply or external response | `oro:ResponseAction` |
| `EMOTION_RECOGNITION` | an emotion-recognition step runs | `oro:EmotionRecognitionEvent` |
| `EMOTION_ANALYSIS` | an emotion-analysis step runs | `onyx:EmotionAnalysis` |
| `HUMAN_DETECTION` | a human-detection step runs | `oro:DetectedHumanEvent` |
| `ML_RUN` | a generic ML execution step runs | `mls:Run` |

All activities also receive the generic activity typing added by the logger for interoperability.

### When You Still Need Explicit Ontology Terms

The package does abstract ontology details for ordinary integrations, but not completely. You may still need explicit
ontology terms when:

- you want a more specific class than the default one for an activity
- you want to tag a message with a particular semantic type such as `oro:InitialMessage`
- you want to refer to an external ontology resource directly
- you need custom RDF typing beyond the built-in abstractions

Rule of thumb: start with `ActivityKind` and the built-in logger methods. Reach for explicit RDF terms only when the
default typing is not specific enough for your graph model.

<a id="signature-types-used-in-this-page"></a>
## Signature Types Used In This Page

These types appear repeatedly in method signatures. Understanding them first removes most of the ambiguity in the rest
of the API.

### `RDFTermLike`

`RDFTermLike = str | URIRef`

!!! info "Practical rule"
    If you already have a URI returned by the logger, pass it as is. If you are writing a value manually, prefer a
    prefixed term such as `oro:Human` or an absolute URI. Use local identifiers like `"maria"` or `"message_1"` only
    when you want the resource to live under `base_namespace`.

In practice, the logger accepts four useful forms:

| Form | Example | What the logger does |
|---|---|---|
| local identifier | `"maria"` | resolves inside `base_namespace` |
| prefixed term | `"oro:Human"` | resolves using bound prefixes |
| absolute URI | `"https://example.org/humans/maria"` | uses that URI directly |
| `rdflib.URIRef` | `URIRef("https://example.org/humans/maria")` | uses it directly |

**Typical use**

```python
human_uri = logger.register_human("maria", first_name="Maria")
logger.log_activity(performer=human_uri, activity_kind=ActivityKind.DECISION)
logger.log_activity(extra_types=["oro:ListeningEvent"], activity_kind=ActivityKind.LISTENING)
```

### `ModelUsage`

`ModelUsage` is the structured way to describe how one model was used inside an activity. Use it when you need more
than a plain model link.

| Field | Type | Meaning |
|---|---|---|
| `model` | `RDFTermLike` | model resource used by the activity |
| `parameters` | `Mapping[str, Any]` | runtime parameters such as temperature or thresholds |
| `implementation` | `RDFTermLike \| None` | optional implementation resource |
| `software_label` | `str \| None` | human-readable software/runtime name |
| `software_version` | `str \| None` | version of the runtime/tooling |

```python
from semantic_log_generator import ModelUsage

usage = ModelUsage(
    model=model_uri,
    parameters={"temperature": 0.2, "top_p": 0.9},
    implementation="dialogue_impl_v1",
    software_label="ollama",
    software_version="0.6.0",
)
```

`ModelUsage` is consumed by `log_activity(model_usages=[...])`.

### `EmotionScore`

`EmotionScore` represents one emotion prediction:

```python
EmotionScore(category=EmotionCategory.SADNESS, intensity=0.82, confidence=0.91)
```

It is consumed by `log_emotion_annotation(emotions=[...])`.

### `RobotStateSnapshot`

`RobotStateSnapshot` is the input object for `log_robot_state(...)`. It collects operational state in Python-first
form before the logger expands it into RDF entities and `schema:PropertyValue` nodes.

<a id="semanticsegblogger"></a>
## SemanticSEGBLogger

High-level facade to build semantic logs as RDF triples.

### Constructor

```python
SemanticSEGBLogger(
    *,
    base_namespace: str,
    robot_id: str,
    robot_name: str | None = None,
    default_language: str = "en",
    graph: Graph | None = None,
    namespace_prefix: str = "robotlog",
    compact_resource_ids: bool = False,
    shared_event_policy: SharedEventPolicy | None = None,
    shared_event_resolver: SharedEventResolver | None = None,
    emit_prov_redundant: bool = True,
    strict_result_typing: bool = False,
)
```

| Parameter | Type | Meaning | Typical choice |
|---|---|---|---|
| `base_namespace` | `str` | base URI for resources created by this logger | deployment-specific stable URI |
| `robot_id` | `str` | logical robot identifier | `"ari1"` |
| `robot_name` | `str \| None` | human-readable robot label | `"ARI"` |
| `default_language` | `str` | default language tag for text literals | `"en"` |
| `graph` | `Graph \| None` | existing graph to append into | omit unless combining multiple loggers |
| `namespace_prefix` | `str` | RDF prefix label for `base_namespace` | `"ari"` or `"tiago"` |
| `compact_resource_ids` | `bool` | shorter local identifiers in generated URIs | `True` for cleaner TTL |
| `shared_event_policy` | `SharedEventPolicy \| None` | default shared-event namespace and time bucket | omit unless tuning shared-event behavior |
| `shared_event_resolver` | `SharedEventResolver \| None` | external resolver callable for shared events | set only for cross-robot alignment |
| `emit_prov_redundant` | `bool` | emit PROV equivalents of SEGB properties | keep `True` unless you know why not |
| `strict_result_typing` | `bool` | suppress explicit `prov:Activity` on `segb:Result` nodes | keep `False` for backend compatibility |

**Raises**

- `ValueError` if `base_namespace` is empty.
- `ValueError` if `namespace_prefix` is empty or invalid.

**Minimal example**

```python
logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
    namespace_prefix="demo",
)
```

### Quick Method Guide

| Method | Use it when... | Returns |
|---|---|---|
| `register_human` | you need a human actor URI and typing | `URIRef` |
| `register_robot` | you need to override or enrich robot agent data | `URIRef` |
| `log_activity` | you need a causal/temporal step in the trace | `URIRef` |
| `log_message` | you need a `schema:Message` with sender/provenance | `URIRef` |
| `log_observation` | you need a generic entity observation | `URIRef` |
| `log_emotion_annotation` | you need emotion-analysis output | `URIRef` |
| `log_robot_state` | you need telemetry/operational state | `URIRef` |
| `get_shared_event_uri` | you need a canonical shared event, local or remote | `URIRef` |
| `serialize` | you want RDF text output | `str` |
| `publish` | you already have a publisher object | `dict[str, Any]` |

### Agent and Utility Methods

#### `register_human(human_id, *, first_name=None, homepage=None) -> URIRef`

Registers a human with RDF types `prov:Person`, `foaf:Person`, and `oro:Human`.

```python
human_uri = logger.register_human("maria", first_name="Maria")
```

#### `register_robot(*, robot_uri=None, robot_name=None, owner=None) -> URIRef`

Registers or enriches the robot agent with types `prov:Agent` and `oro:Robot`.

Use `owner` only if you explicitly want the RDF link `oro:belongsTo`.

#### `resolve_term(value) -> URIRef`

Normalizes an `RDFTermLike` into `URIRef`.

Use it when you need to inspect or reuse the exact URI the logger will produce.

#### `resource_uri(kind, resource_id=None) -> URIRef`

Builds one URI in the logger namespace for a given resource kind such as `activity`, `message`, `human`, or `state`.

<a id="log_activity"></a>
## log_activity

`log_activity(...) -> URIRef` is the central method in the package. It creates the step that later ties together who
did what, when, using which inputs/models, and with which outputs.

!!! tip "What to think about before calling `log_activity`"
    Most calls answer four questions:

    1. What kind of step is this? Use `activity_kind`.
    2. Who performed it and when? Use `performer`, `started_at`, and `ended_at`.
    3. What caused it and what did it use? Use the `triggered_by_*`, `used_*`, and `model_usages` arguments.
    4. What did it produce? Use `produced_entity_results` and `produced_activity_results`.

```python
log_activity(
    *,
    activity_id: str | None = None,
    activity_kind: ActivityKind | str,
    extra_types: Sequence[RDFTermLike] | None = None,
    label: str | None = None,
    related_shared_events: Sequence[RDFTermLike] | None = None,
    performer: RDFTermLike | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    triggered_by_activity: RDFTermLike | None = None,
    triggered_by_entity: RDFTermLike | None = None,
    triggered_by_entities: Sequence[RDFTermLike] | None = None,
    intermediate_activities: Sequence[RDFTermLike] | None = None,
    used_entities: Sequence[RDFTermLike] | None = None,
    used_models: Sequence[RDFTermLike] | None = None,
    model_usages: Sequence[ModelUsage] | None = None,
    produced_entity_results: Sequence[RDFTermLike] | None = None,
    produced_activity_results: Sequence[RDFTermLike] | None = None,
)
```

### Core Parameters

| Parameter | Use it for | Example |
|---|---|---|
| `activity_id` | stable identifier if you do not want random URIs | `"listen_1"` |
| `activity_kind` | high-level category mapped to ontology classes | `ActivityKind.LISTENING` |
| `extra_types` | extra RDF classes beyond the default kind mapping | `["oro:ListeningEvent"]` |
| `label` | human-readable label for the activity | `"ARI listens to Maria"` |
| `performer` | override default performer; if omitted, the logger robot is used | `human_uri` or `"https://..."` |

### Shared Context, Time, and Causality

| Parameter | Use it for | Example |
|---|---|---|
| `related_shared_events` | link activity to canonical shared event(s) | `[shared_event_uri]` |
| `started_at` / `ended_at` | execution timestamps | `datetime.now(timezone.utc)` |
| `triggered_by_activity` | one upstream activity caused this one | `previous_activity_uri` |
| `triggered_by_entity` | one entity caused this activity | `message_uri` |
| `triggered_by_entities` | several triggering entities | `[obs1_uri, obs2_uri]` |
| `intermediate_activities` | link sub-steps that influenced this one | `[asr_uri, nlu_uri]` |

### Inputs and Model Provenance

| Parameter | Use it for | Example |
|---|---|---|
| `used_entities` | explicit inputs used by the activity | `[message_uri]` |
| `used_models` | simple model links without parameter details | `[model_uri]` |
| `model_usages` | structured model usage with parameters/software metadata | `[ModelUsage(...)]` |

### Outputs

| Parameter | Use it for | Example |
|---|---|---|
| `produced_entity_results` | entities produced by this activity | `[message_uri, annotation_uri]` |
| `produced_activity_results` | downstream activities produced as result | `[followup_activity_uri]` |

### What `activity_kind` Accepts

`activity_kind` can be either:

- an `ActivityKind` enum member
- a string matching one of the supported values

Supported values:

- `listening`
- `decision`
- `response`
- `emotion_recognition`
- `emotion_analysis`
- `human_detection`
- `ml_run`

### Choosing `ActivityKind`

Use `ActivityKind` for the default classification of an activity. That is the stable, library-level contract exposed to
normal users.

| Value | Use it when... | Default RDF type |
|---|---|---|
| `LISTENING` | the system listens or captures an input | `oro:ListeningEvent` |
| `DECISION` | the system decides what to do | `oro:DecisionMakingAction` |
| `RESPONSE` | the system emits a response or outward action | `oro:ResponseAction` |
| `EMOTION_RECOGNITION` | a recognition step detects emotional signals | `oro:EmotionRecognitionEvent` |
| `EMOTION_ANALYSIS` | an analysis step produces emotion interpretation | `onyx:EmotionAnalysis` |
| `HUMAN_DETECTION` | a detection step identifies a human | `oro:DetectedHumanEvent` |
| `ML_RUN` | a generic ML execution is the main event | `mls:Run` |

Use `extra_types` only when the default mapping is not specific enough for your graph model.

### What `RDFTermLike` Looks Like Inside `log_activity`

All parameters typed as `RDFTermLike` or `Sequence[RDFTermLike]` accept the same shapes:

```python
logger.log_activity(
    activity_kind=ActivityKind.DECISION,
    performer=human_uri,                         # URIRef returned by logger
    triggered_by_entity="message_1",            # local id in base_namespace
    used_models=["https://example.org/model"],  # absolute URI
    extra_types=["oro:DecisionMakingAction"],   # prefixed term
)
```

### What `ModelUsage` Looks Like Inside `log_activity`

Use `model_usages` when you need more than just `used_models`.

!!! note "When to use `used_models` vs `model_usages`"
    Use `used_models` when you only need to link the model resource. Use `model_usages` when you need parameter values,
    implementation information, or software/runtime versioning.

```python
from semantic_log_generator import ModelUsage

decision_uri = logger.log_activity(
    activity_id="reply_1",
    activity_kind=ActivityKind.DECISION,
    model_usages=[
        ModelUsage(
            model=model_uri,
            parameters={"temperature": 0.2, "top_p": 0.9},
            implementation="dialogue_impl_v1",
            software_label="ollama",
            software_version="0.6.0",
        )
    ],
)
```

This adds:

- model link to the activity
- implementation resource if needed
- software metadata if provided
- parameter resources and values

### Minimal Example

```python
from datetime import datetime, timezone

listen_uri = logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
    started_at=datetime.now(timezone.utc),
)
```

### Rich Example

```python
decision_uri = logger.log_activity(
    activity_id="decision_1",
    activity_kind=ActivityKind.DECISION,
    label="Generate spoken reply",
    triggered_by_entity=message_uri,
    used_entities=[message_uri],
    related_shared_events=[shared_event_uri],
    model_usages=[
        ModelUsage(
            model=model_uri,
            parameters={"temperature": 0.2},
            software_label="ollama",
            software_version="0.6.0",
        )
    ],
)
```

### Returns

- `URIRef` for the created activity.

### Raises

- `ValueError` if `activity_kind` is missing or invalid.
- `ValueError` if the same `activity_id` is reused with different `started_at` or `ended_at`.

## Entity Methods

### `log_message`

```python
log_message(
    text: str,
    *,
    message_id: str | None = None,
    language: str | None = None,
    message_types: Sequence[RDFTermLike] | None = None,
    generated_by_activity: RDFTermLike | None = None,
    previous_message: RDFTermLike | None = None,
    sender: RDFTermLike | None = None,
) -> URIRef
```

Use this for human utterances and robot replies.

| Parameter | Meaning | Example |
|---|---|---|
| `text` | message content | `"Hello robot"` |
| `message_id` | stable identifier | `"msg_1"` |
| `language` | literal language tag | `"en"` |
| `message_types` | extra RDF types for the message | `[ORO.InitialMessage]` |
| `generated_by_activity` | provenance link to activity | `listen_uri` |
| `previous_message` | conversational derivation | `previous_msg_uri` |
| `sender` | actor who sent the message | `human_uri` or `logger.robot_uri` |

**Important**

- If `message_types` contains `oro:InitialMessage`, `language` is mandatory.

**Example**

```python
reply_uri = logger.log_message(
    "I am here to help.",
    message_id="reply_1",
    generated_by_activity=decision_uri,
    sender=logger.robot_uri,
)
```

### `log_observation`

```python
log_observation(
    *,
    observation_id: str | None = None,
    label: str | None = None,
    observation_types: Sequence[RDFTermLike] | None = None,
    generated_by_activity: RDFTermLike | None = None,
    related_shared_event: RDFTermLike | None = None,
    confidence: float | None = None,
    mark_as_result: bool = False,
) -> URIRef
```

Use this for non-message observed entities such as face snapshots, detections, or generic evidence nodes.

**Important**

- `confidence` requires `related_shared_event`.

### `log_emotion_annotation`

```python
log_emotion_annotation(
    *,
    source_activity: RDFTermLike,
    targets: Sequence[RDFTermLike],
    emotions: Sequence[EmotionScore],
    annotation_id: str | None = None,
    emotion_model: RDFTermLike = EMOML.big6,
) -> URIRef
```

Use this when an activity produced emotion-analysis output.

**Example**

```python
logger.log_emotion_annotation(
    source_activity=emotion_activity_uri,
    targets=[human_uri],
    emotions=[EmotionScore(category=EmotionCategory.SADNESS, intensity=0.84, confidence=0.92)],
)
```

### `log_robot_state`

```python
log_robot_state(
    snapshot: RobotStateSnapshot,
    *,
    state_id: str | None = None,
    source_activity: RDFTermLike | None = None,
) -> URIRef
```

Use this for telemetry and operational state snapshots.

**Example**

```python
state_uri = logger.log_robot_state(
    RobotStateSnapshot(
        battery_level=0.73,
        cpu_load=0.38,
        autonomy_mode="semi_auto",
        location="room_a",
    )
)
```

## Shared-Event Methods

### `get_shared_event_uri`

```python
get_shared_event_uri(
    *,
    event_kind: str,
    observed_at: datetime,
    subject: RDFTermLike | None = None,
    text: str | None = None,
    modality: str | None = None,
    shared_event_namespace: str | None = None,
    event_types: Sequence[RDFTermLike] | None = None,
    event_id: str | None = None,
    time_bucket_seconds: int | None = None,
    resolver: SharedEventResolver | None = None,
    policy: SharedEventPolicy | None = None,
) -> URIRef
```

Use this when several observations may refer to the same real-world event. If a resolver is configured, it asks the
backend first; otherwise it falls back to deterministic local resolution.

### `resolve_shared_event`

Forces local deterministic shared-event creation. Use it when you explicitly do not want backend resolution.

### `link_observation_to_shared_event`

Adds `prov:specializationOf` between an observation entity and a shared event. Use `confidence` to attach
`shared_event_confidence`.

### `link_activity_to_shared_event`

Adds `schema:about` between activity and shared event.

## Serialization and Publication Helpers

### `merge_turtle(ttl_content) -> None`

Parses Turtle and merges it into the current graph.

### `serialize(*, format="turtle") -> str`

Serializes the graph into RDF text. Use `"turtle"` unless you need another RDF format for tooling.

### `publish(publisher, *, user=None) -> dict[str, Any]`

Delegates to `publisher.publish_graph(...)`. Use this only if you already manage publisher lifecycle elsewhere.

<a id="segbpublisher"></a>
## SEGBPublisher

HTTP publisher for backend endpoints such as `/ttl` and `/ttl/delete_all`.

### Constructor

```python
SEGBPublisher(
    *,
    base_url: str,
    token: str | None = None,
    default_user: str | None = None,
    timeout_seconds: float = 20.0,
    verify_tls: bool = True,
    queue_file: str | None = None,
)
```

| Parameter | Meaning | Typical choice |
|---|---|---|
| `base_url` | backend base URL | `http://localhost:5000` |
| `token` | JWT when auth is enabled | `os.getenv("SEGB_API_TOKEN")` |
| `default_user` | user field sent to backend | robot/runtime name |
| `timeout_seconds` | HTTP timeout | `20.0` |
| `verify_tls` | TLS verification | `True` |
| `queue_file` | optional local retry queue path | `~/.cache/segb/publish.queue` |

### Methods

#### `publish_turtle(ttl_content, *, user=None) -> dict[str, Any]`

Posts raw Turtle to `/ttl`.

**Raises**

- `ValueError` if `ttl_content` is empty.
- `RuntimeError` for backend HTTP errors.
- `requests.RequestException` for network failures.

#### `publish_graph(graph, *, user=None) -> dict[str, Any]`

Serializes an `rdflib.Graph` to Turtle and posts it to `/ttl`.

#### `delete_all_ttls(*, user=None) -> dict[str, Any]`

Calls `/ttl/delete_all`. Use for demos and controlled resets, not for normal runtime publishing.

!!! warning "Impact"
    `delete_all_ttls()` removes the current backend graph. In production or in environments where historical analysis
    matters, it should not be part of the normal publication path.

#### `flush_queue() -> list[dict[str, Any]]`

Retries queued payloads from `queue_file` and keeps only the ones that still fail.

<a id="httpsharedcontextresolver"></a>
## HTTPSharedContextResolver

Callable resolver for backend shared-context resolution.

### Constructor

```python
HTTPSharedContextResolver(
    *,
    base_url: str,
    token: str | None = None,
    timeout_seconds: float = 5.0,
    verify_tls: bool = True,
    raise_on_error: bool = False,
    endpoint_path: str = "/shared-context/resolve",
    session: requests.Session | None = None,
)
```

### Behavior

- On success: returns `shared_context_uri` as `str`
- On failure with `raise_on_error=False`: returns `None`
- On failure with `raise_on_error=True`: raises the underlying error

### `__call__(request: SharedEventRequest) -> str | None`

Use it indirectly by passing it into `SemanticSEGBLogger(shared_event_resolver=...)`.

### `close() -> None`

Closes the internal HTTP session.

## build_http_shared_context_resolver_from_env

```python
build_http_shared_context_resolver_from_env(
    *,
    env: Mapping[str, str] | None = None,
) -> HTTPSharedContextResolver | None
```

Builds a resolver from environment variables:

- `SEGB_API_URL`
- `SEGB_API_TOKEN`
- `SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS`
- `SEGB_SHARED_CONTEXT_VERIFY_TLS`
- `SEGB_SHARED_CONTEXT_RAISE_ON_ERROR`

Returns `None` if `SEGB_API_URL` is not set.

**Example**

```python
from semantic_log_generator import SemanticSEGBLogger, build_http_shared_context_resolver_from_env

resolver = build_http_shared_context_resolver_from_env()

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    shared_event_resolver=resolver,
)
```

## Core Types

### `ActivityKind`

Enum used by `log_activity`. Values:

- `LISTENING`
- `DECISION`
- `RESPONSE`
- `EMOTION_RECOGNITION`
- `EMOTION_ANALYSIS`
- `HUMAN_DETECTION`
- `ML_RUN`

This is the main activity-classification abstraction for normal users. For the default RDF mapping behind each value,
see [`ActivityKind` As The Default Activity Classifier](#activitykind-default-classifier).

### `EmotionCategory`

Enum for EmotionML big6 categories. Helper methods:

- `EmotionCategory.coerce(value)`
- `EmotionCategory.from_expression(expression)`

### `EmotionScore`

```python
EmotionScore(
    category: EmotionCategory | RDFTermLike,
    intensity: float,
    confidence: float | None = None,
)
```

### `ModelUsage`

```python
ModelUsage(
    model: RDFTermLike,
    parameters: Mapping[str, Any] = {},
    implementation: RDFTermLike | None = None,
    software_label: str | None = None,
    software_version: str | None = None,
)
```

### `RobotStateSnapshot`

```python
RobotStateSnapshot(
    timestamp: datetime | None = None,
    battery_level: float | None = None,
    autonomy_mode: str | None = None,
    mission_phase: str | None = None,
    cpu_load: float | None = None,
    memory_load: float | None = None,
    network_status: str | None = None,
    location: RDFTermLike | None = None,
    note: str | None = None,
    custom: Mapping[str, Any] = {},
)
```

### `SharedEventPolicy`

```python
SharedEventPolicy(namespace: str | None = None, time_bucket_seconds: int = 1)
```

### `SharedEventRequest`

```python
SharedEventRequest(
    event_kind: str,
    observed_at: datetime,
    subject: RDFTermLike | None = None,
    text: str | None = None,
    modality: str | None = None,
    shared_event_namespace: str | None = None,
    event_types: tuple[RDFTermLike, ...] = (),
    event_id: str | None = None,
    time_bucket_seconds: int = 1,
)
```
