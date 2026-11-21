"""Which plan file names a milestone: the one reader of the file-level ``milestone`` key of the files in ``impl_context/``.

Lives in ``core`` because ``trace`` (``step create 16a`` refuses a second plan for a milestone) and ``lifecycle`` (every
command that starts from a milestone id) both ask it and ``trace`` may not import ``lifecycle``.  It reads the key only,
never validates a plan, so a plan that still carries retired fields reads without error.
"""
from __future__ import annotations

from pathlib import Path

from .loaders import read_json_object
from .step_paths import PLAN_DIR_NAME, PLAN_FILE_GLOB

MILESTONE_KEY = "milestone"


def plan_files(spec_root: str | Path) -> list[Path]:
    """Every plan file (``PLAN_FILE_GLOB``) of ``<spec_root>/impl_context/``, in name order; empty when the folder is missing.

    Any other file of the folder is no plan, whatever it holds.
    """
    return sorted((Path(spec_root) / PLAN_DIR_NAME).glob(PLAN_FILE_GLOB))


def milestone_key(path: Path) -> str | None:
    """The file-level ``milestone`` of the JSON file at *path*; ``None`` when absent, mistyped or unreadable."""
    value = (read_json_object(path) or {}).get(MILESTONE_KEY)
    return value if isinstance(value, str) else None


def find_plan(spec_root: str | Path, milestone_id: str) -> Path | None:
    """Return the plan file whose file-level ``milestone`` key equals *milestone_id*, or ``None``.

    Scans ``plan_files`` in name order and returns the first match. A file that cannot be
    read, is not a JSON object, has no ``milestone`` key or holds a non-string one is skipped (a plan written
    before the key existed is such a file). Never raises: a missing directory gives ``None``.
    """
    for path in plan_files(spec_root):
        if milestone_key(path) == milestone_id:
            return path
    return None
