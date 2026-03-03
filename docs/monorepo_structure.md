# Monorepo Structure

This repository contains both the centralized SEGB stack and a ROS2 workspace used by robot simulation/runtime.

## 1) Centralized Stack (Main source of truth)

- `apps/backend`: FastAPI API, services, Virtuoso adapter, OpenAPI metadata.
- `apps/frontend`: Vue UI (`segb-ui`) and frontend Docker packaging.
- `packages/semantic_log_generator`: reusable Python package for semantic RDF logging.
- `examples`: simulations, mocks, notebooks, sample outputs.
- `tests`: unit + integration suites for backend/logger/simulation flows.
- `docs`: deployment and architecture documentation.

## 2) ROS2 Workspace (Robot runtime track)

- `ros4hri-exchange/ws/src`: ROS2 packages (`emotion_mirror`, `basic_say`, `sample_skill_msgs`).
- `ros4hri-exchange/semantic_log_generator`: ROS-side copy used for workspace compatibility.

If you are working only on centralized SEGB services/UI, you usually do not need to modify ROS workspace code.

## 3) Generated Artifacts (Do not treat as source)

These directories are build/runtime outputs and should not be edited manually:

- `ros4hri-exchange/{build,install,log}`
- `ros4hri-exchange/ws/{build,install,log}`
- `**/build`, `**/dist`, `**/*.egg-info`

## 4) Typical First-Day Navigation

1. Start with `README.md` for full-stack quick start.
2. Read `docs/deployment_centralized.md` for runtime/deployment behavior.
3. Inspect `apps/backend/src` and `apps/frontend/segb-ui/src` for implementation details.
4. Use `examples/simulations` and `tests/` to understand expected flows.
