# Install `semantic_log_generator`

## Objective

Install `semantic_log_generator` in a Python environment used by robot or simulation runtimes.

## Prerequisites

- Python `>=3.10,<3.13`
- `pip`

## Steps

### 1) Choose installation source

PyPI (when available):

```bash
python -m pip install semantic-log-generator
```

TestPyPI channel:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "semantic-log-generator>=1.0.0,<2.0.0"
```

GitHub monorepo subdirectory:

```bash
python -m pip install "git+https://github.com/<owner>/<repo>.git@<tag_or_commit>#subdirectory=packages/semantic_log_generator"
```

### 2) Validate installation

```bash
python -c "from semantic_log_generator import SemanticSEGBLogger; print('ok')"
```

Expected: `ok`.

## Validation

Confirm package import and runtime dependencies are available.

Main runtime dependencies:

- `rdflib`
- `requests`

## Troubleshooting

- `ModuleNotFoundError`: confirm you are using the intended Python interpreter.
- Dependency resolution issues in TestPyPI flow: keep `--extra-index-url https://pypi.org/simple`.
- Network errors: verify internet/proxy configuration.

## Next

- API usage patterns: [Usage](usage.md)
- End-to-end deployment: [Centralized Deployment](../deployment/centralized.md)
