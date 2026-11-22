"""``p4_plan_dispositions``: a plan carries no disposition any more (DOC "Plan dispositions").

``plan.status``, ``plan.deferred_reason`` and each checklist item's ``checklist_status``, ``deferred_reason`` and
``wont_do_reason`` are removed (the capture holds them: sections ``milestone_status.plans`` and ``plan_items``).  Only an
OPEN plan is edited: a legacy-closed plan keeps them as history (ruling P13: the map's ``closed_plans`` default).

An item that was not ``active`` in an open plan says that a task may need to be deferred.  The migration does not write
that decision: each such item becomes ONE worklist item (kind ``plan-item-disposition``, audience ``operator``, not
blocking, so no close blocker is added to a milestone in flight) that names the plan file, the item, the old disposition
and its reason, from the capture (ruling P24, M8's S-037(c)).  Nothing is written to the plan's ``plan.ambiguities`` or to
step 14.
"""

from __future__ import annotations

from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.migration.maps import shape_rows
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.scripts.v1_2_0.p1_capture import CAPTURE_REL, LEGACY
from specdev_tools.migration.scripts.v1_2_0.p2_plan_milestone_key import plan_milestones
from specdev_tools.migration.scripts.v1_2_0.p3_remove import closed_plan_files, files_of_row, last_key, parents_at
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_plan_dispositions", phase=PHASE_CONTENT, requires=("p3_remove", "p4_ambiguities"), touches=("16", "extras"))

KIND = "plan-item-disposition"
_ACTIVE = "active"
_REASON_FIELD = {"deferred": "deferred_reason", "wont_do": "wont_do_reason"}
_WORDS = {"deferred": "deferred", "wont_do": "won't do"}


def _removals(ctx) -> list[tuple[dict[str, Any], str, str]]:
    """``(holder, key, row id)`` of every legacy field still in an open plan."""
    closed = closed_plan_files(ctx)
    found = []
    for row in shape_rows(SCRIPT.id):
        key = last_key(row["path"])
        for rel in files_of_row(ctx, row, closed):
            found.extend((holder, key, row["id"]) for holder in parents_at(ctx.documents.load(rel).data, row["path"]) if key in holder)
    return found


def _wanted(ctx) -> list[WorklistItem]:
    """The worklist item each non-active item of an open plan asks for, from the capture."""
    closed = closed_plan_files(ctx)
    milestones = {rel: m for rel, m in plan_milestones(ctx).items() if rel not in closed}
    found = []
    for row in ctx.documents.load(CAPTURE_REL).data.get("plan_items") or []:
        status, milestone = row.get(LEGACY + "checklist_status"), milestones.get(row.get("file"))
        if milestone is None or status in (None, _ACTIVE):
            continue
        reason = row.get(LEGACY + _REASON_FIELD.get(status, "")) or "no reason was recorded"
        evidence = (f"{row['file']}: plan item {row['item']} of milestone {milestone} was {_WORDS.get(status, status)} "
                    f"({status}): {reason.rstrip('.')}.")
        proposal = "Decide whether the task the item realises is deferred or dropped, or whether the item is dropped when 16a re-plans."
        found.append(make_item("16", KIND, row["item"], audience="operator", blocking=False, evidence=evidence, proposal=proposal, key=milestone))
    return found


def detect(ctx) -> int:
    """Legacy fields still in an open plan, plus worklist items still to add."""
    return len(_removals(ctx)) + len(missing_items(ctx, _wanted(ctx)))


def apply(ctx) -> ScriptResult:
    """List the dispositions (from the capture), then remove the legacy fields of the open plans."""
    listed = add_items(ctx, _wanted(ctx))
    counts: dict[str, int] = {}
    for holder, key, row_id in _removals(ctx):
        del holder[key]
        counts[row_id] = counts.get(row_id, 0) + 1
    residue = (f"worklist items for deferred or won't-do plan items: {listed}", *(f"{row_id}: {n} removed" for row_id, n in sorted(counts.items())))
    return ScriptResult(edits=listed + sum(counts.values()), worklist_items=listed, residue=residue)


def verify(before, after) -> list[Problem]:
    """No plan file gained one of the removed keys."""
    keys = {last_key(row["path"]) for row in shape_rows(SCRIPT.id)}
    problems = []
    for rel, document in sorted(after.documents.items()):
        old = before.documents.get(rel)
        if rel.startswith("impl_context/") and isinstance(document, dict) and isinstance(old, dict):
            gained = [key for key in sorted(keys) if key in (document.get("plan") or {}) and key not in (old.get("plan") or {})]
            if gained:
                problems.append(Problem(f"{rel}: gained {gained}", rel))
    return problems
