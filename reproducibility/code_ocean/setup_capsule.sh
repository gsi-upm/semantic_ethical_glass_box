#!/usr/bin/env bash
set -euo pipefail

# Base environment for reproducible SEGB core execution in Code Ocean.
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e packages/semantic_log_generator
python -m pip install pydantic

