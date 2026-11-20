"""Plan discovery: which 16a plan file belongs to which milestone.

A plan names its milestone in one file-level key, ``milestone``. Discovery scans ``<spec_root>/impl_context/*.json``
for that key. This is the place the 1.2.0 shape maps a milestone to its plan file; two readers still build a plan path
from 1.1.1 data (``cli.py`` ``milestone-state`` by name, ``traceability_closure._load_milestone_plans_from_anchor`` by
``context_path``).
"""
from __future__ import annotations

from pathlib import Path

from ..core.loaders import read_json_object
from ..core.step_paths import PLAN_DIR_NAME

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
    value = (read_json_object(path) or {}).get(MILESTONE_KEY)
    return value if isinstance(value, str) else None
