# Code Ocean Capsule Guide (SEGB Core)

This folder provides a minimal, reproducible capsule strategy for SEGB when the full software stack is heterogeneous (ROS2 runtime, backend, database, UI, etc.).

The capsule scope is intentionally the **core algorithmic behavior**:

- UC-03 shared-context automatic resolve logic
- UC-05 TTL validation/insert workflow logic (mock API)

These are executed through integration tests that use a fake API client, so no ROS2, Virtuoso, or Docker services are required.

## 1) Freeze a source snapshot

Before creating the capsule, create and push an immutable snapshot:

1. Commit your current state.
2. Create a tag (example: `v0.2.0-repro-core`).
3. Push branch + tag to GitHub.

Use that tag/commit in Code Ocean.

## 2) Create capsule from GitHub

In Code Ocean:

1. Create a new compute capsule.
2. Import this repository from GitHub.
3. Pin the capsule to the tagged commit used above.

## 3) Environment setup command

Run:

```bash
bash reproducibility/code_ocean/setup_capsule.sh
```

## 4) Reproducible run command

Run:

```bash
bash reproducibility/code_ocean/run_core_repro.sh
```

Expected result:

- test output with `Ran 3 tests` and `OK`
- artifacts in `results/`:
  - `unittest_uc03_uc05.txt`
  - `run_metadata.txt`

## 5) What to cite in SoftwareX

Use the capsule link and state scope clearly:

- The capsule reproduces SEGB core semantics and validation behavior (UC-03, UC-05).
- Full heterogeneous deployment (ROS2 runtime, backend+Virtuoso+UI orchestration) is documented in repo docs but is outside this capsule.

