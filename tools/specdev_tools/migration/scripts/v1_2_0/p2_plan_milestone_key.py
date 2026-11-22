"""``p2_plan_milestone_key``: every plan file names its milestone in a file-level ``milestone`` key (CD-10).

A 1.1.1 plan is found from its anchor row (``context_path``) and carries no key; 1.2.0 finds the plan the other way
(``core.plan_files.find_plan`` reads the key).  The key is the 14 milestone id of the anchor row that names the plan
file, set in every plan file, closed or open, and nothing else of the plan changes: no plan file is renamed.  A plan
file that no anchor row names, or whose key disagrees with the row, is a worklist item (the script never guesses).

This module also holds the two readers the action-id script shares: which plan file belongs to which milestone and
which milestones are legacy-closed (the rule of the legacy close: 14 status ``done``, anchor status ``done`` or a
close record, or a plan review verdict ``verified``).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from specdev_tools.core.plan_files import MILESTONE_KEY, plan_files
from specdev_tools.core.step_paths import PLAN_DIR_NAME, STEP_JSON_RE
from specdev_tools.graph.names import ROW_DONE
from specdev_tools.lifecycle.anchor_store import is_legacy_close
from specdev_tools.migration.registry import PHASE_IDS, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.worklist import add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p2_plan_milestone_key", phase=PHASE_IDS, touches=("16", "extras"))

ANCHOR_STEP = "16"
ROADMAP_STEP = "14"
VERDICT_VERIFIED = "verified"
KIND_NO_ROW = "plan-without-row"
KIND_KEY_MISMATCH = "plan-milestone-mismatch"


def step_file(ctx, step: str) -> str | None:
    """The file name of *step* in the spec folder (``None`` when the host has none)."""
    for name in sorted(os.listdir(ctx.spec_root)):
        match = STEP_JSON_RE.match(name)
        if match and match.group(1) == step:
            return name
    return None


def step_data(ctx, step: str) -> dict[str, Any]:
    """The data of the file of *step* (``{}`` when the host has none)."""
    name = step_file(ctx, step)
    data = ctx.documents.load(name).data if name else None
    return data if isinstance(data, dict) else {}


def anchor_rows(ctx) -> Iterator[dict[str, Any]]:
    """The objects of the anchor's ``plan.milestone_index`` (legacy or converted)."""
    rows = (step_data(ctx, ANCHOR_STEP).get("plan") or {}).get("milestone_index")
    return (row for row in rows if isinstance(row, dict)) if isinstance(rows, list) else iter(())


def row_milestone(row: dict[str, Any]) -> str | None:
    """The 14 milestone id of an anchor row: the legacy ``milestone_id``, or the one id of ``about``."""
    legacy = row.get("milestone_id")
    if isinstance(legacy, str):
        return legacy
    about = row.get("about")
    return about[0] if isinstance(about, list) and len(about) == 1 and isinstance(about[0], str) else None


def plan_rel_of_row(row: dict[str, Any]) -> str | None:
    """The plan file a legacy row names, as a path relative to the spec folder (``impl_context/<file>``)."""
    path = row.get("context_path")
    if not isinstance(path, str) or not path:
        return None
    return f"{PLAN_DIR_NAME}/{path.replace(chr(92), '/').rsplit('/', 1)[-1]}"


def plan_rels(ctx) -> list[str]:
    """Every plan file, relative to the spec folder, in name order."""
    return [f"{PLAN_DIR_NAME}/{path.name}" for path in plan_files(ctx.spec_root)]


def plan_milestones(ctx) -> dict[str, str]:
    """``{plan file: milestone id}``: the plan's own key when it has one, else the anchor row that names the file."""
    named = {rel: row_milestone(row) for row in anchor_rows(ctx) if (rel := plan_rel_of_row(row))}
    found: dict[str, str] = {}
    for rel in plan_rels(ctx):
        key = ctx.documents.load(rel).data.get(MILESTONE_KEY)
        milestone = key if isinstance(key, str) else named.get(rel)
        if milestone:
            found[rel] = milestone
    return found


def closed_milestones(ctx) -> set[str]:
    """The 14 milestones that are legacy-closed now: 14 or the anchor says ``done`` (or holds a close), or the plan's verdict is ``verified``."""
    closed = {
        m["milestone_id"]
        for m in step_data(ctx, ROADMAP_STEP).get("milestones", [])
        if isinstance(m, dict) and m.get("status") == ROW_DONE and isinstance(m.get("milestone_id"), str)
    }
    for row in anchor_rows(ctx):
        milestone = row_milestone(row)
        if milestone and (row.get("status") == ROW_DONE or is_legacy_close(row.get("close"))):
            closed.add(milestone)
    for rel, milestone in plan_milestones(ctx).items():
        verdict = (ctx.documents.load(rel).data.get("review") or {}).get("verdict")
        if verdict == VERDICT_VERIFIED:
            closed.add(milestone)
    return closed


def insert_key(data: dict[str, Any], name: str, value: Any, *, after: str | None = None) -> None:
    """Add *name* to *data* in place, right after the key *after* (first when *after* is absent), keeping the other keys in order."""
    rest = list(data.items())
    data.clear()
    placed = False
    if after is None or after not in dict(rest):
        data[name], placed = value, True
    for key, held in rest:
        data[key] = held
        if key == after and not placed:
            data[name], placed = value, True


def _plan(ctx) -> tuple[list[tuple[str, str]], list]:
    """The keys to set as ``(plan file, milestone id)``, and the worklist items for the plans it cannot decide."""
    named: dict[str, str] = {}
    for row in anchor_rows(ctx):
        rel, milestone = plan_rel_of_row(row), row_milestone(row)
        if rel and milestone:
            named.setdefault(rel, milestone)
    sets: list[tuple[str, str]] = []
    items = []
    for rel in plan_rels(ctx):
        key = ctx.documents.load(rel).data.get(MILESTONE_KEY)
        wanted = named.get(rel)
        if wanted is None and not isinstance(key, str):
            items.append(make_item(
                "16", KIND_NO_ROW, rel, audience="operator", blocking=True,
                evidence=f"no anchor row names {rel} in its context_path, so the milestone of the plan is not known",
                proposal=f"set `milestone` in {rel} to the id of the roadmap milestone the plan is for",
            ))
        elif isinstance(key, str) and wanted is not None and key != wanted:
            items.append(make_item(
                "16", KIND_KEY_MISMATCH, rel, audience="operator", blocking=True,
                evidence=f"{rel} has milestone {key!r}; the anchor row that names it is for {wanted!r}",
                proposal="keep the key of the plan or the row, whichever is right; the script changed neither",
            ))
        elif not isinstance(key, str) and wanted is not None:
            sets.append((rel, wanted))
    return sets, items


def detect(ctx) -> int:
    """Keys to set plus worklist items not yet listed."""
    sets, items = _plan(ctx)
    return len(sets) + len(missing_items(ctx, items))


def apply(ctx) -> ScriptResult:
    """Put ``milestone`` right after ``id`` in each plan file that has no key; list the plans it cannot decide."""
    sets, items = _plan(ctx)
    for rel, milestone in sets:
        data = ctx.documents.load(rel).data
        insert_key(data, MILESTONE_KEY, milestone, after="id")
    listed = add_items(ctx, items)
    return ScriptResult(edits=len(sets) + listed, worklist_items=listed, residue=tuple(f"{rel}: milestone {milestone}" for rel, milestone in sets))


def verify(before, after) -> list[Problem]:
    """Every plan file that gained a ``milestone`` kept all its other top-level keys and its file name."""
    problems: list[Problem] = []
    for rel, document in sorted(after.documents.items()):
        old = before.documents.get(rel)
        if rel.startswith(f"{PLAN_DIR_NAME}/") and isinstance(old, dict) and isinstance(document, dict):
            if {k: v for k, v in document.items() if k != MILESTONE_KEY} != {k: v for k, v in old.items() if k != MILESTONE_KEY}:
                problems.append(Problem(f"{rel} changed beyond its milestone key", rel))
    removed = sorted(rel for rel in before.documents if rel.startswith(f"{PLAN_DIR_NAME}/") and rel not in after.documents)
    return problems + [Problem(f"plan file {rel} disappeared (a plan is never renamed)", rel) for rel in removed]
