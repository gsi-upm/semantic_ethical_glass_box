"""Bootstrap helpers for simulation scripts.

These helpers keep `python -m ...` as the preferred execution mode while still
allowing direct script execution in development.
"""

from __future__ import annotations

import sys
from pathlib import Path


def configure_pythonpath() -> None:
    """Injects local project paths when simulations are launched as plain scripts."""
    project_root = Path(__file__).resolve().parents[2]
    candidate_paths = (
        project_root,
        project_root / "packages/semantic_log_generator/src",
        project_root / "apps/backend/src",
    )
    for path in candidate_paths:
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)
