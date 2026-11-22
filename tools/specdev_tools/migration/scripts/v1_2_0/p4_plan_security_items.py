"""``p4_plan_security_items``: ``plan.security.spec_mutations`` and ``new_fixtures`` become open items (DOC "ambiguity items").

A 1.1.1 plan could list, under ``plan.security``, the spec changes it found it needed (``spec_mutations``) and the fixtures it
needed that did not exist (``new_fixtures``).  1.2.0 has no such fields: what a plan finds that the spec lacks is an open
item.  ``p3_remove`` removed the fields after ``capture.json`` kept them (sections ``plan_security``); this script reads the
capture, one entry at a time.  In an OPEN plan each entry becomes an open item in the plan's ``plan.ambiguities`` (``about``
the plan's milestone, or the task a mutation's ``ref`` names); in a legacy-closed plan the entry is an informational worklist
item (``blocking: false``) and the plan is not changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from specdev_tools.migration.context import CAPTURE_REL
from specdev_tools.graph.build import build_graph
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import LEGACY, PLAN_HOLDER_STEP, about_allowed, add_open_item, array_at, closed_plan_files, ensure_array, has_open_item, plan_milestones
from specdev_tools.migration.worklist import OPEN_ITEM_RULE, WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_plan_security_items", phase=PHASE_CONTENT, requires=("p3_remove", "p4_ambiguities"), touches=("16", "extras"))

KIND_FROZEN = "plan-security-item"
PLAN_ITEMS = ".plan.ambiguities"


@dataclass(frozen=True)
class _Entry:
    """One captured entry: the plan file and milestone, the text of its open item, what it is about, and the label its id is minted from."""

    rel: str
    milestone: str
    description: str
    about: str
    label: str


def _mutation_text(entry: Any) -> tuple[str, str, str]:
    """The sentence of one ``spec_mutations`` entry, the type and the id its ``ref`` names (``""`` when it names none)."""
    if not isinstance(entry, dict):
        return f"Spec change the plan asked for: {entry}", "", ""
    ref: dict[str, Any] = entry["ref"] if isinstance(entry.get("ref"), dict) else {}
    target = f" ({ref.get('type', 'node')} {ref['id']})" if ref.get("id") else ""
    reason = f" Reason: {str(entry['reason']).rstrip('.')}." if entry.get("reason") else ""
    return f"Spec change the plan asked for{target}: {str(entry.get('change', entry)).rstrip('.')}.{reason}", str(ref.get("type", "")), str(ref.get("id", ""))


def _entries(ctx) -> list[_Entry]:
    milestones = plan_milestones(ctx)
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    found = []
    for row in ctx.documents.load(CAPTURE_REL).data.get("plan_security") or []:
        rel = row["file"]
        milestone: str = milestones.get(rel) or rel
        for index, entry in enumerate(row.get(LEGACY + "spec_mutations") or [], start=1):
            text, ref_type, ref_id = _mutation_text(entry)
            about = ref_id if ref_type == "task" and about_allowed(graph, PLAN_HOLDER_STEP, ref_id) else milestone
            found.append(_Entry(rel, milestone, text, about, f"{milestone} mutation {index}"))
        for index, entry in enumerate(row.get(LEGACY + "new_fixtures") or [], start=1):
            found.append(_Entry(rel, milestone, f"Fixture the plan asked for that does not exist yet: {entry}", milestone, f"{milestone} fixture {index}"))
    return found


def _frozen_items(entries: list[_Entry], frozen: set[str]) -> list[WorklistItem]:
    return [
        make_item(
            PLAN_HOLDER_STEP, KIND_FROZEN, e.milestone, audience="operator", blocking=False, key=e.label,
            evidence=f"{e.description} (from {e.rel}, a closed plan: the plan is not changed)",
            proposal=f"raise it again in the right artifact after the migration, or drop it; {OPEN_ITEM_RULE}",
        )
        for e in entries
        if e.rel in frozen
    ]


def _is_new(ctx, entry: _Entry) -> bool:
    plan = ctx.documents.load(entry.rel).data
    return not has_open_item(array_at(plan, PLAN_ITEMS) or [], entry.description, [entry.about])


def _split(ctx) -> tuple[list[_Entry], list[_Entry], set[str]]:
    frozen = closed_plan_files(ctx)
    entries = _entries(ctx)
    return [e for e in entries if e.rel not in frozen and _is_new(ctx, e)], entries, frozen


def detect(ctx) -> int:
    """Open items still to add to open plans, plus informational items not yet listed."""
    pending, entries, frozen = _split(ctx)
    return len(pending) + len(missing_items(ctx, _frozen_items(entries, frozen)))


def apply(ctx) -> ScriptResult:
    """Add one open item per entry of an open plan; list one informational item per entry of a closed plan."""
    pending, entries, frozen = _split(ctx)
    taken = set(build_graph(ctx.spec_root, ctx.toolkit_root).by_id)
    added = sum(add_open_item(ensure_array(ctx.documents.load(e.rel).data, PLAN_ITEMS), e.description, [e.about], taken, e.label) for e in pending)
    listed = add_items(ctx, _frozen_items(entries, frozen))
    residue = (f"plan security entries: {len(entries)}; open items added to open plans: {added}; informational items for closed plans: {listed}",)
    return ScriptResult(edits=added + listed, worklist_items=listed, residue=residue)


def _without_items(document: dict[str, Any]) -> dict[str, Any]:
    plan = {k: v for k, v in (document.get("plan") or {}).items() if k != "ambiguities"}
    return {**document, "plan": plan}


def verify(before, after) -> list[Problem]:
    """A plan file changed only in its ``plan.ambiguities``."""
    return [
        Problem(f"{rel} changed beyond plan.ambiguities", rel)
        for rel, document in sorted(after.documents.items())
        if rel.startswith("impl_context/") and isinstance(document, dict) and isinstance(before.documents.get(rel), dict)
        and _without_items(document) != _without_items(before.documents[rel])
    ]
