"""Plan discovery and the freeze of a closed plan: which 16a plan file belongs to which milestone, and whether it changed.

A plan names its milestone in one file-level key, ``milestone``. Discovery (``find_plan``, ``milestone_key``) is
``core/plan_files.py``, shared with ``step create 16a``; the commands here build on it. This is the place the 1.2.0
shape maps a milestone to its plan file; one reader still builds a plan path
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
from pathlib import Path

from ..core.errors import FindingError, make_error, refusal
from ..core.plan_files import find_plan, milestone_key, plan_files
from ..core.step_paths import PLAN_DIR_NAME
from ..trace.hashing import HASH_PREFIX

_NO_KEY = "run `specdev align` (the plan has no `milestone` key)"


def require_plan(spec_root: str | Path, milestone_id: str) -> Path:
    """The plan file of *milestone_id*; the wrapper every lifecycle command calls where ``find_plan`` would return ``None``.

    Raises:
        FindingError: E803 with subcode ``MILESTONE_KEY_MISSING`` when no plan file carries a ``milestone`` key (a
            host before the migration), or ``MILESTONE_NOT_FOUND`` when plans carry it and none names *milestone_id*.
    """
    found = find_plan(spec_root, milestone_id)
    if found is not None:
        return found
    if not any(milestone_key(path) for path in plan_files(spec_root)):
        raise FindingError(make_error(
            "E803", f"no plan names milestone {milestone_id}: {_NO_KEY}", subcode="MILESTONE_KEY_MISSING", node_id=milestone_id
        ))
    raise FindingError(make_error(
        "E803",
        f"no plan names milestone {milestone_id} in its `milestone` key; give the id of a milestone that has a plan in {PLAN_DIR_NAME}/",
        subcode="MILESTONE_NOT_FOUND",
        node_id=milestone_id,
    ))


def plan_hash(plan_path: str | Path) -> str:
    """``sha256:<hex>`` of the canonical JSON of the plan file (sorted keys, no insignificant whitespace).

    Not a lock hash: the snapshot a close record and a recorded migration store.  It is not ``trace.hashing``'s digest
    (a list of values) and not ``executed.realises_hash`` (sorted pairs): the three recipes differ and a closed milestone's
    stored ``plan_hash`` is compared byte for byte, so only the ``sha256:`` prefix is shared.

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
