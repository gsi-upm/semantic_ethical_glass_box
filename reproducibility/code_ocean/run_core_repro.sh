#!/usr/bin/env bash
set -euo pipefail

mkdir -p results

# Keep imports explicit so the run is independent from local editable installs.
export PYTHONPATH="packages/semantic_log_generator/src:apps/backend/src:${PYTHONPATH:-}"

python -m unittest \
  examples.simulations.tests.integration.test_ros2_mock_use_case_03_shared_context_auto_match \
  examples.simulations.tests.integration.test_ros2_mock_use_case_05_ttl_validate_insert \
  2>&1 | tee results/unittest_uc03_uc05.txt

{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "python_version=$(python --version 2>&1)"
  echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
} > results/run_metadata.txt

echo "Reproducible core run completed. Artifacts:"
echo "- results/unittest_uc03_uc05.txt"
echo "- results/run_metadata.txt"

