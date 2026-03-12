# Install `semantic_log_generator`

This page is for developers who want to use `semantic_log_generator` in robot runtimes or simulations with minimal
friction.

You do not need Docker, Virtuoso, or the Web UI to install the package and generate Turtle locally. Those are required
only when you want the full SEGB stack running.

## Outcome

After this guide, you will have:

- the package installed in the right Python environment
- a quick import check passing
- a smoke test that confirms the logger can generate Turtle
- the exact distinction between the `pip` package name and the Python import name

## Prerequisites

- Python `3.10`, `3.11`, or `3.12`
- `pip`
- repository root as current directory only when using editable install from this checkout


## Recommended Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

## Installation Options

Use one of the following:

### Option A: From PyPI (default for integrations)

```bash
pip install semantic-log-generator
```

### Option B: From repository source (recommended for contributors)

```bash
python -m pip install packages/semantic_log_generator
```

### Option C: From GitHub subdirectory

```bash
python -m pip install "git+https://github.com/gsi-upm/semantic_ethical_glass_box.git@<tag_or_commit>#subdirectory=packages/semantic_log_generator"
```

### Option D: From TestPyPI (only if a pre-release is published there)

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "semantic-log-generator==<prerelease-version>"
```

## Verify The Install

```bash
python -c "from semantic_log_generator import SemanticSEGBLogger; print('ok')"
```

Expected output: `ok`

If this passes, the package is installed correctly. You still do not need the backend unless you want to publish logs.

## Smoke Test (60 seconds)

```bash
python - <<'PY'
from semantic_log_generator import ActivityKind, SemanticSEGBLogger

logger = SemanticSEGBLogger(
    base_namespace="https://example.org/segb/robots/demo/v1/",
    robot_id="demo_robot",
    robot_name="Demo Robot",
)
logger.log_activity(activity_id="listen_1", activity_kind=ActivityKind.LISTENING)
ttl_text = logger.serialize(format="turtle")
print("Triples:", len(logger.graph))
print("TTL bytes:", len(ttl_text.encode("utf-8")))
PY
```

If this succeeds, your environment is ready for integration.

## Common Problems

- `ModuleNotFoundError`: you installed with one interpreter and executed with another.
- `pip install semantic_log_generator`: wrong package name for `pip`; use `semantic-log-generator`.
- TLS/index issues in TestPyPI installs: keep `--extra-index-url https://pypi.org/simple`.
- Corporate proxy/network restrictions: configure pip proxy/index settings first.

## Next

- [Use `semantic_log_generator`](usage.md)
- [API Reference](api-reference.md)
