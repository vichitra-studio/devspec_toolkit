"""``p2_anchor_rows``: an anchor row is a status record ABOUT its milestone, with an id of its own (design 3.1).

A 1.1.1 row (``plan.milestone_index[]`` of ``16_impl_context.json``) is named by the 14 milestone id it carries as
``milestone_id``.  A 1.2.0 row has its own id (``anchor_id``, minted by the one minter, ``anchor-<milestone id>``: it
never reuses the milestone's id) and a one-element ``about`` link to the 14 milestone.  ``status``, ``summary`` and
``checklist_id_prefix`` stay; ``context_path`` and ``fr_refs`` stay too and go with the removed fields (P3, from the
capture, which holds both).  Runs after ``p2_plan_milestone_key``, which reads ``context_path`` and ``milestone_id``.
"""

from __future__ import annotations

from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import mint_slug, suggest_prefix
from specdev_tools.graph.names import ABOUT
from specdev_tools.migration.registry import PHASE_IDS, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import anchor_rows
from specdev_tools.validation.linter_utils import graph_known_ids

SCRIPT = ScriptSpec(id="p2_anchor_rows", phase=PHASE_IDS, requires=("p2_plan_milestone_key", "p2_id_mint"), touches=("16",))

LEGACY_FIELD = "milestone_id"
ID_FIELD = "anchor_id"
ARRAY_PATH = ".plan.milestone_index"


def _legacy_rows(ctx) -> list[dict[str, Any]]:
    return [row for row in anchor_rows(ctx) if isinstance(row.get(LEGACY_FIELD), str) and ABOUT not in row]


def _row_kind(ctx) -> str:
    """The kind the registry declares for ``plan.milestone_index`` (its id prefix is the one the minter suggests)."""
    for file_decl in ctx.kind_registry().files:
        for decl in file_decl.kinds:
            if file_decl.step == "16" and decl.array_path == ARRAY_PATH:
                return decl.kind
    raise ValueError(f"the kind registry declares no kind at {ARRAY_PATH}")


def _convert(ctx, rows: list[dict[str, Any]], *, write: bool) -> int:
    kind = _row_kind(ctx)
    taken = set(graph_known_ids(build_graph(ctx.spec_root, ctx.toolkit_root)))
    for row in rows:
        milestone = row[LEGACY_FIELD]
        new_id = row.get(ID_FIELD) if isinstance(row.get(ID_FIELD), str) else mint_slug(milestone, taken, prefix=suggest_prefix(kind))
        taken.add(new_id)
        if write:
            held = list(row.items())
            row.clear()
            row[ID_FIELD] = new_id
            row[ABOUT] = [milestone]
            row.update((key, value) for key, value in held if key not in (LEGACY_FIELD, ID_FIELD))
    return len(rows)


def detect(ctx) -> int:
    """How many rows still name their milestone by ``milestone_id``."""
    return len(_legacy_rows(ctx))


def apply(ctx) -> ScriptResult:
    """Give each legacy row an ``anchor_id`` and an ``about``; the rest of the row keeps its order."""
    return ScriptResult(edits=_convert(ctx, _legacy_rows(ctx), write=True))


def verify(before, after) -> list[Problem]:
    """No row has both a ``milestone_id`` and an ``about``, and no row id equals the milestone it is about."""
    problems: list[Problem] = []
    document = after.documents.get("16_impl_context.json")
    rows = ((document or {}).get("plan") or {}).get("milestone_index") if isinstance(document, dict) else None
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and ABOUT in row:
            if LEGACY_FIELD in row:
                problems.append(Problem(f"the anchor row about {row[ABOUT]} still has a milestone_id", "16_impl_context.json"))
            if row.get(ID_FIELD) in row[ABOUT]:
                problems.append(Problem(f"the anchor row {row.get(ID_FIELD)} reuses the id of its milestone", "16_impl_context.json"))
    return problems
