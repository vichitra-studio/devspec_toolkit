"""Plan discovery and the freeze of a closed plan: which 16a plan file belongs to which milestone, and whether it changed.

A plan names its milestone in one file-level key, ``milestone``. Discovery scans ``<spec_root>/impl_context/*.json``
for that key. This is the place the 1.2.0 shape maps a milestone to its plan file; one reader still builds a plan path
from 1.1.1 data (``cli.py`` ``milestone-state``, by name).

These readers read the file-level key and the raw bytes only and never validate a plan against the plan schema, so a
plan that still carries fields the schema no longer has reads without error.  The batch id is the stem of the plan file
(``ms_<batch>_plan.json``); it is not derivable from the milestone id.

A plan is frozen when the anchor row of its milestone is ``done``.  ``plan_hash`` is the snapshot a close stores;
``frozen_plan_drift`` compares the plan with it.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..core.errors import FindingError, make_error, refusal
from ..core.loaders import read_json_object
from ..core.step_paths import PLAN_DIR_NAME

MILESTONE_KEY = "milestone"
HASH_PREFIX = "sha256:"
_BATCH_OF_FILE = re.compile(r"^ms_(.+)_plan\.json$")
_NO_KEY = "run `specdev align` (the plan has no `milestone` key)"


def find_plan(spec_root: str | Path, milestone_id: str) -> Path | None:
    """Return the plan file whose file-level ``milestone`` key equals *milestone_id*, or ``None``.

    Scans ``<spec_root>/impl_context/*.json`` in name order and returns the first match. A file that cannot be
    read, is not a JSON object, has no ``milestone`` key or holds a non-string one is skipped (a plan written
    before the key existed is such a file). Never raises: a missing directory gives ``None``.
    """
    for path in _plan_files(spec_root):
        if milestone_key(path) == milestone_id:
            return path
    return None


def require_plan(spec_root: str | Path, milestone_id: str) -> Path:
    """The plan file of *milestone_id*; the wrapper every lifecycle command calls where ``find_plan`` would return ``None``.

    Raises:
        FindingError: E803 with subcode ``MILESTONE_KEY_MISSING`` when no plan file carries a ``milestone`` key (a
            host before the migration), or ``MILESTONE_NOT_FOUND`` when plans carry it and none names *milestone_id*.
    """
    found = find_plan(spec_root, milestone_id)
    if found is not None:
        return found
    if not any(milestone_key(path) for path in _plan_files(spec_root)):
        raise FindingError(make_error(
            "E803", f"no plan names milestone {milestone_id}: {_NO_KEY}", subcode="MILESTONE_KEY_MISSING", node_id=milestone_id
        ))
    raise FindingError(make_error(
        "E803",
        f"no plan names milestone {milestone_id} in its `milestone` key; give the id of a milestone that has a plan in {PLAN_DIR_NAME}/",
        subcode="MILESTONE_NOT_FOUND",
        node_id=milestone_id,
    ))


def milestone_of_batch(spec_root: str | Path, batch_id: str) -> str:
    """The milestone id in the ``milestone`` key of the plan file ``impl_context/ms_<batch_id>_plan.json``.

    Raises:
        FindingError: E803 with subcode ``MILESTONE_KEY_MISSING`` when the file has no string ``milestone`` key,
            ``MILESTONE_NOT_FOUND`` when there is no such file.
    """
    path = Path(spec_root) / PLAN_DIR_NAME / f"ms_{batch_id}_plan.json"
    if not path.is_file():
        raise FindingError(make_error(
            "E803", f"there is no plan file {PLAN_DIR_NAME}/{path.name}; give the stem of a plan file as the batch id", subcode="MILESTONE_NOT_FOUND"
        ))
    key = milestone_key(path)
    if key is None:
        raise FindingError(make_error(
            "E803", f"{PLAN_DIR_NAME}/{path.name} has no `milestone` key: {_NO_KEY}", subcode="MILESTONE_KEY_MISSING"
        ))
    return key


def batch_of_milestone(spec_root: str | Path, milestone_id: str) -> str:
    """The batch id (``<batch>`` of ``ms_<batch>_plan.json``) of the plan of *milestone_id*.

    Raises:
        FindingError: E803 as ``require_plan``.
    """
    path = require_plan(spec_root, milestone_id)
    match = _BATCH_OF_FILE.match(path.name)
    return match.group(1) if match else path.stem


def plan_hash(plan_path: str | Path) -> str:
    """``sha256:<hex>`` of the canonical JSON of the plan file (sorted keys, no insignificant whitespace).

    Not a lock hash: the snapshot a close record and a recorded migration store.

    Raises:
        FindingError: E520 when the file cannot be read or is not JSON.
    """
    try:
        with open(plan_path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise refusal("E520", f"{plan_path} cannot be read as JSON ({error}); repair the file") from None
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stored_plan_hash(close: object) -> str | None:
    """The hash a plan must still have: the ``hash_after`` of the last migration of the ``close`` record, else its ``plan_hash``; ``None`` when it stores none."""
    if not isinstance(close, dict):
        return None
    migrations = close.get("migrations")
    if isinstance(migrations, list) and migrations and isinstance(migrations[-1], dict):
        return migrations[-1].get("hash_after")
    value = close.get("plan_hash")
    return value if isinstance(value, str) else None


def _plan_files(spec_root: str | Path) -> list[Path]:
    return sorted((Path(spec_root) / PLAN_DIR_NAME).glob("*.json"))


def milestone_key(path: Path) -> str | None:
    """The file-level ``milestone`` of the JSON file at *path*; ``None`` when absent, mistyped or unreadable."""
    value = (read_json_object(path) or {}).get(MILESTONE_KEY)
    return value if isinstance(value, str) else None
