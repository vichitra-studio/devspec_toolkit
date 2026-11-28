"""``p4_ambiguities``: the 1.1.1 ambiguity items of the anchor and the plans, resolved ones deleted, the rest converted or triaged (CD-10, CD-11).

Three arrays held legacy items (``severity``, ``status``, ``impact``): the anchor's ``plan.ambiguities`` (step 16), a plan's
``plan.ambiguities`` (16a) and its ``execution.emergent_ambiguities`` (16b).  1.2.0 has one open-item shape (``id``,
``description``, ``about``; an item exists or is deleted).  This script, in the order of the legacy-item rules:

1. deletes every ``resolved`` item (history is git; the count is printed).  The rule is M6a's (``core.ambiguity_items.is_open``,
   ``iter_ambiguity_items`` reads them); the deletion goes through the format-preserving writer, so a plan written at another indent keeps it;
2. removes a non-resolved item of a legacy-closed plan and lists it as an informational worklist item (``blocking: false``,
   ``about`` the plan's milestone), so a frozen plan keeps no open item;
3. converts a non-resolved item of the anchor or an open plan to the unified shape when its ``impact`` names exactly one
   node that ``about`` may name (one of an earlier step: a plan item of the same plan does not qualify); otherwise it leaves the
   item as it is and lists a worklist item for the operator (the script never guesses what an item is about; the old ``impact``
   stays readable in ``capture.json``).

The id of an item is unique across the spec (E704): of two items with one id the later one gets the next free ``-2``,
``-3`` name and the rename is recorded in the capture's ``renames`` section (kind ``ambiguity-item``).  There is no bound on the number of items (the plan-size warning covers volume).
Closed plans change only by the removal of their open items; every other legacy field of a closed plan stays history.

``spec_reads.add_open_item`` is the one writer of a NEW unified item into an array; ``p4_plan_security_items`` calls it.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.ambiguity_items import ANCHOR_STEP, AmbiguityItem, is_open, iter_ambiguity_items
from specdev_tools.migration.context import CAPTURE_REL
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import first_free_id
from specdev_tools.graph.model import Graph
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import AMBIGUITY, PLAN_HOLDER_STEP, RENAMES_KEY, about_allowed, array_at, capture_renames, closed_plan_files, ensure_array, plan_milestones
from specdev_tools.migration.worklist import OPEN_ITEM_RULE, WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_ambiguities", phase=PHASE_CONTENT, requires=("p3_remove",), touches=("16", "extras"))

KIND_FROZEN_ITEM = "legacy-open-item"
KIND_ABOUT = "ambiguity-about"
_LEGACY_STEPS = frozenset({ANCHOR_STEP, "16a", "16b"})
_ITEM_FIELDS = ("id", "description", "about", "decision", "proposed_assumption")
_LOCATION_TAG = {"16": "anchor", "16a": "plan", "16b": "emergent"}


@dataclass(frozen=True)
class Planned:
    """What the script does with one legacy item: ``delete`` (resolved), ``freeze`` (remove, list), ``convert`` or ``keep``; ``new_id`` differs from ``item.id`` for a renamed duplicate."""

    action: str
    rel: str
    location: str
    index: int
    item: AmbiguityItem
    new_id: str
    about: tuple[str, ...]
    milestone: str | None


def _flat_renames(ctx) -> dict[str, str]:
    return {old: new for by_kind in capture_renames(ctx).values() for old, new in by_kind.items()}


def _legacy_entries(ctx) -> list[tuple[AmbiguityItem, int]]:
    """Every legacy item of the three locations in file order, with its index in its array (counted over every entry, converted ones included, so a rerun finds the right one)."""
    seen: Counter[tuple[str, str]] = Counter()
    entries = []
    for item in iter_ambiguity_items(ctx.spec_root):
        key = (item.artifact_path, item.location)
        index = seen[key]
        seen[key] += 1
        if item.step in _LEGACY_STEPS and item.shape == "legacy":
            entries.append((item, index))
    return entries


def _about_of(raw: dict[str, Any], graph: Graph, holder_step: str, renames: dict[str, str]) -> tuple[str, ...]:
    impact = raw.get("impact")
    if isinstance(impact, list) and len(impact) == 1 and isinstance(impact[0], str):
        name = renames.get(impact[0], impact[0])
        if about_allowed(graph, holder_step, name):
            return (name,)
    return ()


def _holder_step(item: AmbiguityItem) -> str:
    """The step the graph gives an open item: the anchor's is ``16``, every item of a plan file is ``16a``."""
    return ANCHOR_STEP if item.step == ANCHOR_STEP else PLAN_HOLDER_STEP


def _plan(ctx) -> list[Planned]:
    """Decide every legacy item of the three locations, in file order (the ids a rename must avoid are those of every other node)."""
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    entries = _legacy_entries(ctx)
    legacy_ids = Counter(item.id for item, _ in entries)
    taken = {node_id for node_id, count in Counter(node.id for node in graph.nodes).items() if count > legacy_ids[node_id]}
    renames = _flat_renames(ctx)
    frozen = closed_plan_files(ctx)
    milestones = plan_milestones(ctx)
    planned: list[Planned] = []
    for item, index in entries:
        rel = os.path.relpath(item.artifact_path, ctx.spec_root).replace(os.sep, "/")
        milestone = milestones.get(rel)
        if not is_open(item):
            planned.append(Planned("delete", rel, item.location, index, item, item.id, (), milestone))
            continue
        if rel in frozen:
            planned.append(Planned("freeze", rel, item.location, index, item, item.id, (), milestone))
            continue
        new_id = first_free_id(item.id, taken) if item.id in taken else item.id
        taken.add(new_id)
        about = _about_of(item.raw, graph, _holder_step(item), renames)
        convertible = bool(about) and bool(item.description)
        planned.append(Planned("convert" if convertible else "keep", rel, item.location, index, item, new_id, about, milestone))
    return planned


def _legacy_text(raw: dict[str, Any]) -> str:
    parts = [f"{name} {raw[name]}" for name in ("severity", "status", "source", "impact", "mitigation", "decision", "proposed_assumption") if raw.get(name) not in (None, "", [])]
    return f"{raw.get('description', '(no description)')} | " + "; ".join(parts) if parts else str(raw.get("description", ""))


def _worklist(plans: list[Planned]) -> list[WorklistItem]:
    items = []
    for plan in plans:
        tag = _LOCATION_TAG[plan.item.step]
        if plan.action == "freeze":
            about = plan.milestone or plan.rel
            items.append(make_item(
                plan.item.step, KIND_FROZEN_ITEM, about, audience="operator", blocking=False, key=f"{tag}-{plan.item.id}",
                evidence=f"{plan.item.id} in the closed plan {plan.rel}: {_legacy_text(plan.item.raw)}",
                proposal=f"raise it again in the right artifact after the migration, or drop it; the item was removed from the closed plan (the capture and git hold it); {OPEN_ITEM_RULE}",
            ))
        elif plan.action == "keep":
            items.append(make_item(
                plan.item.step, KIND_ABOUT, plan.new_id, audience="operator", blocking=True, key=f"{tag}-{plan.rel}",
                evidence=f"{plan.new_id} in {plan.rel}: {_legacy_text(plan.item.raw)}; its impact does not name exactly one node of an earlier step (or it has no description)",
                proposal=f"rewrite the item as {{id, description, about: [node ids]}} and delete the old fields (about must name the nodes it concerns); that repairs its shape (E520) and nothing more: {OPEN_ITEM_RULE}",
            ))
    return items


def _edits(plans: list[Planned]) -> int:
    return sum(1 for p in plans if p.action in ("delete", "freeze", "convert") or p.new_id != p.item.id)


def detect(ctx) -> int:
    """Items to delete, remove, convert or rename, and worklist items not yet listed."""
    plans = _plan(ctx)
    return _edits(plans) + len(missing_items(ctx, _worklist(plans)))


def _converted(raw: dict[str, Any], new_id: str, about: tuple[str, ...]) -> dict[str, Any]:
    fresh = {"id": new_id, "description": raw["description"], "about": list(about)}
    fresh.update({name: raw[name] for name in ("decision", "proposed_assumption") if isinstance(raw.get(name), str) and raw[name].strip()})
    return fresh


def _rewrite(ctx, plans: list[Planned]) -> None:
    removals: dict[tuple[str, str], list[int]] = {}
    for plan in plans:
        array = ensure_array(ctx.documents.load(plan.rel).data, plan.location)
        if plan.action in ("delete", "freeze"):
            removals.setdefault((plan.rel, plan.location), []).append(plan.index)
        elif plan.action == "convert":
            array[plan.index] = _converted(plan.item.raw, plan.new_id, plan.about)
        elif plan.new_id != plan.item.id:
            array[plan.index] = {**plan.item.raw, "id": plan.new_id}
    for (rel, location), indices in removals.items():
        array = ensure_array(ctx.documents.load(rel).data, location)
        for index in sorted(indices, reverse=True):
            del array[index]


def _record_renames(ctx, plans: list[Planned]) -> None:
    """Append each renamed duplicate to the capture's ``renames`` section (as ``p2_id_collisions`` does), so the old id stays readable; an entry already there is not added twice."""
    held = None
    for plan in plans:
        if plan.new_id != plan.item.id:
            held = ctx.documents.load(CAPTURE_REL).data.setdefault(RENAMES_KEY, []) if held is None else held
            entry = {"old": plan.item.id, "new": plan.new_id, "kind": AMBIGUITY, "file": plan.rel}
            if entry not in held:
                held.append(entry)


def apply(ctx) -> ScriptResult:
    """Delete the resolved items, remove, convert and rename the rest, and list what needs a person."""
    plans = _plan(ctx)
    _rewrite(ctx, plans)
    _record_renames(ctx, plans)
    listed = add_items(ctx, _worklist(plans))
    deleted = [p for p in plans if p.action == "delete"]
    removed = [p for p in plans if p.action == "freeze"]
    renames = tuple((p.item.id, p.new_id) for p in plans if p.new_id != p.item.id)
    residue = (
        f"resolved items deleted: {len(deleted)} in {len({p.rel for p in deleted})} file(s)",
        f"open items removed from closed plans and listed: {len(removed)}",
        f"open items converted to the unified shape: {sum(1 for p in plans if p.action == 'convert')}",
        f"open items left for the operator (impact names no single node of an earlier step): {sum(1 for p in plans if p.action == 'keep')}",
        *(f"duplicate id renamed: {old} -> {new}" for old, new in renames),
    )
    return ScriptResult(edits=_edits(plans) + listed, worklist_items=listed, residue=residue, renames=renames, deleted_ids=tuple(p.item.id for p in deleted + removed))


def verify(before, after) -> list[Problem]:
    """No resolved legacy item is left in a plan or the anchor."""
    problems = []
    for rel, document in sorted(after.documents.items()):
        if not isinstance(document, dict):
            continue
        for location in (".plan.ambiguities", ".execution.emergent_ambiguities"):
            for entry in array_at(document, location) or ():
                if isinstance(entry, dict) and entry.get("status") == "resolved":
                    problems.append(Problem(f"{rel}: a resolved item {entry.get('id')} is left", rel))
    return problems
