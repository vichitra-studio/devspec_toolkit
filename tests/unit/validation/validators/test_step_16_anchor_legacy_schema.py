"""W608 ANCHOR_LEGACY_SCHEMA after the migration (WI-M10-14b): its two sites, read against the anchor row phase 2 leaves.

The anchor validator reads a ``milestone_index`` row by ``about`` (else ``anchor_id``, else the old ``milestone_id``), so a
migrated row and an unmigrated one both find their plan.  W608 fires at two sites: a plan file with no file-level
``milestone`` key (the shape ``p2_plan_milestone_key`` fixes) and an anchor file that still declares the plan schema.  Both are
pinned here as they are.  The second is kept as a warning: no migration script rewrites a pre-split anchor, so W608 is the only
signal such a host gets, and its entry in ``docs/developers/error-codes.md`` (W608, case 1) gives the steps to migrate by hand.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.validation.validate import validate_file
from unit.lifecycle._support import ANCHOR, PLAN, example_spec, load, toolkit_root


def _anchor_errors(spec: Path) -> list[SpecError]:
    return validate_file(toolkit_root(), str(spec / ANCHOR), spec_root=str(spec))


def _codes(errors: list[SpecError]) -> list[str]:
    return [error.code for error in errors]


def test_a_plan_file_with_no_milestone_key_still_gives_w608(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    plan: dict[str, Any] = load(spec, PLAN)
    del plan["milestone"]
    (spec / PLAN).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    w608 = [error for error in _anchor_errors(spec) if error.code == "W608"]
    assert len(w608) == 1
    assert "has no file-level 'milestone' key" in w608[0].message and "the pre-1.2.0 plan shape" in w608[0].message


def test_the_migrated_anchor_row_and_plan_give_no_w608(tmp_path: Path) -> None:
    """A row with ``anchor_id`` and ``about`` (no ``milestone_id``) and a plan with its ``milestone`` key: the shape the migration leaves."""
    spec = example_spec(tmp_path)
    rows = load(spec, ANCHOR)["plan"]["milestone_index"]
    assert rows and all("anchor_id" in row and "about" in row and "milestone_id" not in row for row in rows)
    assert "W608" not in _codes(_anchor_errors(spec))


def test_the_pre_split_anchor_branch_still_gives_w608(tmp_path: Path) -> None:
    """An anchor file that declares ``vc:16-impl-context`` still gets W608 (no migration script rewrites it; ``docs/developers/error-codes.md``, W608 case 1)."""
    spec = example_spec(tmp_path)
    anchor: dict[str, Any] = load(spec, ANCHOR)
    anchor["$schema"] = "vc:16-impl-context"
    (spec / ANCHOR).write_text(json.dumps(anchor, indent=2) + "\n", encoding="utf-8")
    messages = [error.message for error in _anchor_errors(spec) if error.code == "W608"]
    assert any("declares $schema='vc:16-impl-context'" in message for message in messages)
