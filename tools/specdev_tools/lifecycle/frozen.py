"""Frozen plans: whether a milestone's plan is frozen, whether it drifted, and the ``frozen-plans`` check.

The module above ``plans`` (which knows plan files) and ``anchor_store`` (which knows the anchor rows): the questions
here need both.

A plan is frozen when the anchor row of its milestone is ``done``; it may change after that only through a recorded
migration of the close.  The check compares each closed plan with the hash its close record stores (E827).  It reports;
it blocks nothing (``json patch`` does not refuse a closed plan).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import FindingError, SpecError, make_error
from ..core.step_paths import PLAN_DIR_NAME
from . import anchor_store, plans


def is_frozen(spec_root: str | Path, milestone_id: str) -> bool:
    """Whether the plan of *milestone_id* is frozen: the status of its anchor row is ``done``.

    Raises:
        FindingError: E801 (``STATUS_UNKNOWN``) when the row's status is not one of the four values.
    """
    row = anchor_store.read_row(spec_root, milestone_id)
    return row is not None and row.status == "done"


def is_frozen_path(spec_root: str | Path, plan_path: Path) -> bool:
    """``is_frozen`` for the plan file *plan_path*, from its ``milestone`` key; a file with no usable key is not frozen.

    The provider ``check_open_items`` takes is ``Callable[[Path], bool]``: pass ``functools.partial(is_frozen_path, spec_root)``.
    """
    milestone_id = plans.milestone_key(plan_path)
    return milestone_id is not None and is_frozen(spec_root, milestone_id)


def frozen_plan_drift(spec_root: str | Path, milestone_id: str) -> str | None:
    """``None`` when the closed plan of *milestone_id* still has the stored hash, else the message that says it changed (E827).

    Compares ``plan_hash`` of the plan now with the last ``close.migrations[].hash_after``, else ``close.plan_hash``.
    ``None`` as well when the milestone is not ``done``, stores no hash (a legacy close without one) or has no plan.

    Raises:
        FindingError: E801 (``STATUS_UNKNOWN``) for a row with an unknown status; E520 when the plan cannot be read.
    """
    row = anchor_store.read_row(spec_root, milestone_id)
    stored = plans.stored_plan_hash(row.close) if row is not None and row.status == "done" else None
    plan = plans.find_plan(spec_root, milestone_id)
    if stored is None or plan is None:
        return None
    current = plans.plan_hash(plan)
    if current == stored:
        return None
    return (
        f"plan {PLAN_DIR_NAME}/{plan.name} changed after milestone {milestone_id} was closed "
        f"(its hash is {current[:19]}, the close record holds {stored[:19]}); restore the plan to its closed text"
    )


@dataclass(frozen=True)
class FrozenPlansReport:
    """What the check found: the milestones that are ``done``, how many of them store a hash to compare, and the findings."""

    closed: int
    compared: int
    errors: tuple[SpecError, ...]


def _drift_finding(spec_root: str, milestone_id: str) -> SpecError | None:
    """The E827 finding for *milestone_id*, or ``None`` when its plan is as closed; E801 and E520 refusals come back as findings."""
    try:
        message = frozen_plan_drift(spec_root, milestone_id)
    except FindingError as error:
        return error.error
    if message is None:
        return None
    plan = plans.find_plan(spec_root, milestone_id)
    file = os.path.join(PLAN_DIR_NAME, plan.name) if plan else None
    return make_error("E827", message, file=file, node_id=milestone_id)


def check_frozen_plans(spec_root: str) -> FrozenPlansReport:
    """Compare the plan of every ``done`` milestone of the anchor with the hash its close record stores."""
    try:
        states = anchor_store.read_statuses(spec_root)
    except FindingError as error:
        return FrozenPlansReport(0, 0, (error.error,))
    closed = {milestone: state for milestone, state in states.items() if state.status == "done"}
    findings = [_drift_finding(spec_root, milestone) for milestone, state in closed.items() if plans.stored_plan_hash(state.close)]
    errors = tuple(finding for finding in findings if finding is not None)
    return FrozenPlansReport(len(closed), len(findings), errors)
