"""Plan discovery: which 16a plan file belongs to which milestone.

A plan names its milestone in one file-level key, ``milestone``. Discovery scans ``<spec_root>/impl_context/*.json``
for that key. This is the only place a milestone is mapped to its plan file.
"""
from __future__ import annotations

import json
from pathlib import Path

PLAN_DIR_NAME = "impl_context"
MILESTONE_KEY = "milestone"


def find_plan(spec_root: str | Path, milestone_id: str) -> Path | None:
    """Return the plan file whose file-level ``milestone`` key equals *milestone_id*, or ``None``.

    Scans ``<spec_root>/impl_context/*.json`` in name order and returns the first match. A file that cannot be
    read, is not a JSON object, has no ``milestone`` key or holds a non-string one is skipped (a plan written
    before the key existed is such a file). Never raises: a missing directory gives ``None``.
    """
    for path in sorted((Path(spec_root) / PLAN_DIR_NAME).glob("*.json")):
        if _milestone_key(path) == milestone_id:
            return path
    return None


def _milestone_key(path: Path) -> str | None:
    """The file-level ``milestone`` of the JSON file at *path*; ``None`` when absent, mistyped or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get(MILESTONE_KEY) if isinstance(data, dict) else None
    return value if isinstance(value, str) else None
