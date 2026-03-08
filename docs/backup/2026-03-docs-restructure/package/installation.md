# Install `semantic_log_generator`

## Objective

Install `semantic_log_generator` in a Python environment used by robot or simulation runtimes.

## Prerequisites

- Python `>=3.10,<3.13`
- `pip`
- If you use editable install from source, run commands from repository root (`semantic_ethical_glass_box/`)

## Steps

### 1) Installation

From this repository checkout

```bash
python -m pip install -e packages/semantic_log_generator
```

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

GitHub source:

```bash
python -m pip install "git+https://github.com/gsi-upm/semantic_ethical_glass_box.git@main#subdirectory=packages/semantic_log_generator"
```

### 2) Validation

```bash
python -c "from semantic_log_generator import SemanticSEGBLogger; print('ok')"
```

Expected: `ok`.


## Troubleshooting

- `ModuleNotFoundError`: confirm you are using the intended Python interpreter.
- Dependency resolution issues in TestPyPI flow: keep `--extra-index-url https://pypi.org/simple`.
- Network errors: verify internet/proxy configuration.

## Next

- Continue to Step 3: [Basic Use: Post Your First Log to SEGB](usage.md)
