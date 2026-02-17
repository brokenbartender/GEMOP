from __future__ import annotations

import os
from pathlib import Path


def get_repo_root() -> Path:
    """
    Resolve the repository root.

    Priority:
    1) GEMINI_OP_REPO_ROOT (set by start.ps1 and other launchers)
    2) this file's location (repo/scripts/repo_paths.py -> parents[1])
    """
    env = os.environ.get("GEMINI_OP_REPO_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]

