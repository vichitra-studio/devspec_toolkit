"""``p2_plan_milestone_key``: every plan file names its milestone in a file-level ``milestone`` key (CD-10).

A 1.1.1 plan is found from its anchor row (``context_path``) and carries no key; 1.2.0 finds the plan the other way
(``core.plan_files.find_plan`` reads the key).  The key is the 14 milestone id of the anchor row that names the plan
file, set in every plan file, closed or open, and nothing else of the plan changes: no plan file is renamed.  A plan
file that no anchor row names, or whose key disagrees with the row, is a worklist item (the script never guesses).

The readers this script and others share (which plan file belongs to which milestone, which milestones are legacy-closed:
14 status ``done``, anchor status ``done`` or a close record, or a plan review verdict ``verified``; read from
``capture.json``, ruling P23) are in ``migration/spec_reads.py``.
"""

from __future__ import annotations

from specdev_tools.core.plan_files import MILESTONE_KEY
from specdev_tools.core.step_paths import PLAN_DIR_NAME
from specdev_tools.migration.registry import PHASE_IDS, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import anchor_rows, insert_key, plan_rel_of_row, plan_rels, row_milestone
from specdev_tools.migration.worklist import add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p2_plan_milestone_key", phase=PHASE_IDS, touches=("16", "extras"))

KIND_NO_ROW = "plan-without-row"
KIND_KEY_MISMATCH = "plan-milestone-mismatch"


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
