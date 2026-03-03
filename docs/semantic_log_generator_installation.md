# Install `semantic_log_generator`

`semantic_log_generator` is the Python package that creates SEGB-compatible RDF logs and optionally publishes them to the backend.

## Prerequisites

- Python 3.10+
- `pip` (virtualenv recommended)

## Option 1: Install from PyPI (when available)

```bash
python -m pip install semantic-log-generator
```

## Option 2: Install from TestPyPI (current published channel)

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "semantic-log-generator>=1.0.0,<2.0.0"
```

## Option 3: Install from GitHub subdirectory

```bash
python -m pip install "git+https://github.com/<owner>/<repo>.git@<tag_or_commit>#subdirectory=packages/semantic_log_generator"
```

Replace `<owner>/<repo>` with the SEGB monorepo that contains `packages/semantic_log_generator`,
and replace `<tag_or_commit>` with a release tag or commit hash.

## Option 4: Use in a ROS 2 Python package

Typical approach:

1. Install the package in your robot environment (Option 1, 2 or 3).
2. Import it in your ROS 2 node code.
3. Keep your sensing/decision logic in ROS; use this package only to map facts to RDF.

Minimal import test:

```bash
python -c "from semantic_log_generator import SemanticSEGBLogger; print('ok')"
```

## Runtime Dependencies

Main dependencies are:

- `rdflib`
- `requests`

If you publish to backend (`SEGBPublisher`) or use shared-context API resolution (`HTTPSharedContextResolver`), network access to the SEGB API is required.
