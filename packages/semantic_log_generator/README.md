# `semantic_log_generator`

Python package to generate SEGB-compatible RDF logs locally and optionally publish them to a SEGB backend.

## Compatibility

- Python: 3.10, 3.11, 3.12
- License: Apache-2.0
- Versioning: Semantic Versioning (see [`CHANGELOG.md`](CHANGELOG.md))
- `pip` package name: `semantic-log-generator`
- Python import name: `semantic_log_generator`

## What It Does

- Maps robot runtime facts to RDF triples
- Uses SEGB + PROV + ORO + ONYX + MLS + SOSA vocabularies
- Supports shared-event/shared-context linking across robots
- Publishes TTL payloads to backend `/ttl`
- Emits `schema:provider` links as resources (URI or materialized `schema:Organization`), not literals

## What It Does Not Do

- Sensor acquisition
- ROS transport/orchestration
- Robot decision making
- KG reasoning

## Install

### From PyPI (default)

```bash
python -m pip install semantic-log-generator
```

### From repository checkout (editable)

```bash
python -m pip install -e packages/semantic_log_generator
```

### From GitHub subdirectory

```bash
python -m pip install "git+https://github.com/gsi-upm/semantic_ethical_glass_box.git@<tag_or_commit>#subdirectory=packages/semantic_log_generator"
```

### From TestPyPI (only if a pre-release is published there)

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "semantic-log-generator==<prerelease-version>"
```

## Quick Example

```python
from semantic_log_generator import ActivityKind, SemanticSEGBLogger

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
)

logger.log_activity(
    activity_id="listen_1",
    activity_kind=ActivityKind.LISTENING,
)

print(logger.serialize(format="turtle"))
```

## Main APIs

- `SemanticSEGBLogger`
- `SEGBPublisher`
- `HTTPSharedContextResolver`
- `ActivityKind`, `RobotStateSnapshot`, `EmotionScore`, `ModelUsage`

## Abstraction Level

The library is Python-first by default. In normal usage, you should not need to write ontology terms manually for
common actions such as logging an activity, a message, a human actor, or a robot state snapshot.

Use:

- `ActivityKind` to classify activities
- logger methods to create typed RDF resources
- explicit ontology terms only when you need custom typing beyond the defaults

## Local-Only vs Backend-Backed Use

You can use `SemanticSEGBLogger` without running the rest of SEGB. Backend endpoints are required only for these
features:

- `SEGBPublisher`: `POST /ttl`
- backend verification flows in the docs: usually `GET /events`
- shared-context resolution: `POST /shared-context/resolve`

Safest deployment path: keep the package and the SEGB backend on the same repository release or tag.

## Shared Context (Cross-Robot)

`SemanticSEGBLogger` does not auto-read environment variables and does not call
`POST /shared-context/resolve` unless you pass a resolver explicitly.

To enable backend shared-context resolution, create a resolver and inject it:

```python
from semantic_log_generator import SemanticSEGBLogger, build_http_shared_context_resolver_from_env

robot_id = "r1"
base_namespace = f"https://example.org/segb/robots/{robot_id}/"
resolver = build_http_shared_context_resolver_from_env()
logger = SemanticSEGBLogger(
    base_namespace=base_namespace,
    robot_id=robot_id,
    shared_event_resolver=resolver,
)
```

Environment variables for `build_http_shared_context_resolver_from_env()`:

- General SEGB API configuration (recommended):
  - `SEGB_API_URL`
  - `SEGB_API_TOKEN` (only when backend auth is enabled)
- Optional:
  - `SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS` (must be `> 0`, default `5.0`)
  - `SEGB_SHARED_CONTEXT_VERIFY_TLS` (`true`/`false`, default `true`)
  - `SEGB_SHARED_CONTEXT_RAISE_ON_ERROR` (`true`/`false`, default `false`)

### Shared Event RDF Shape

- Shared events are serialized as `schema:Event` and `prov:Entity`.
- `event_kind` and `modality` are still used for resolver/fingerprint logic, but are not emitted as `schema:eventType`/`schema:measurementTechnique`.
- When `modality` is provided, the logger emits a `sosa:Observation` linked to the shared event with:
  - `sosa:hasFeatureOfInterest` (the shared event)
  - `sosa:usedProcedure` (procedure resource labelled with modality, e.g. `speech`)
  - `sosa:resultTime`
  - `sosa:hasSimpleResult` (when text is available)
- Observation-to-shared-event confidence is emitted as `schema:additionalProperty` (`schema:PropertyValue` with `schema:propertyID="shared_event_confidence"`).

### Robot State RDF Shape

- Robot state snapshots are emitted as entities with `schema:PropertyValue` nodes.
- State properties are linked with `schema:additionalProperty`.
- State location is linked with `prov:atLocation`.

## Related Docs

- Package overview: [`docs/package/index.md`](https://semantic-ethical-black-box-segb.readthedocs.io/en/stable/package/)
- Installation guide: [`docs/package/installation.md`](https://semantic-ethical-black-box-segb.readthedocs.io/en/stable/package/installation/)
- API reference: [`docs/package/api-reference.md`](https://semantic-ethical-black-box-segb.readthedocs.io/en/stable/package/api-reference/)
- Usage guide: [`docs/package/usage.md`](https://semantic-ethical-black-box-segb.readthedocs.io/en/stable/package/usage/)

## Tests

Package-specific tests are in `packages/semantic_log_generator/tests/unit`.

```bash
PYTHONPATH=packages/semantic_log_generator/src python -m unittest discover -s packages/semantic_log_generator/tests/unit -p 'test_*.py'
```
