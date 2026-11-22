"""``p3_remove``: the fields 1.2.0 removed, taken out of the 1.1.1 files (phase 3).

One row of ``migration/maps/v1_2_0.yaml`` per field (script ``p3_remove``: dispositions ``remove`` and ``capture-then-remove``).
A ``capture-then-remove`` row names the section of ``capture.json`` that holds the value (``p1_capture`` wrote it first);
a ``remove`` row is a field nothing replaces and no later pack reads.  The path of a row (``milestones[].tasks[].status``)
is walked in every file of the row's step; ``[]`` is each object of a list and ``{}`` each value of a map.

Plan files: the row says ``closed_plans``.  A legacy-closed plan (the rule of ``spec_reads.closed_milestones``,
ruling P13) loses only the rows marked ``strip`` (the stored computed names, E768) and keeps the rest as history; an open
plan gets every row.  Stored ``content_hash`` / ``chain_stamp`` (``COMPUTED_VIEWS``) go from every file.  The retired
files of the map (step 13a, ``extras/trace_matrix.json``) are deleted.  Row counts go to the report as residue lines.
"""

from __future__ import annotations

import copy
import os
from typing import Any

from specdev_tools.migration.maps import LEGACY_STEP_IDS, shape_map, shape_rows
from specdev_tools.migration.registry import PHASE_SHAPES, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import closed_plan_files, files_of_row, last_key, parents_at, plan_rels, step_json_names
from specdev_tools.trace.computed_fields import COMPUTED_VIEWS

SCRIPT = ScriptSpec(
    id="p3_remove",
    phase=PHASE_SHAPES,
    requires=("p2_action_ids", "p2_anchor_rows", "p2_id_collisions", "p3_convert", "p3_ordering"),
    touches=(*LEGACY_STEP_IDS, "extras"),
)

# Names stored on any node that the toolkit computes (every ``COMPUTED_VIEWS`` row that is not limited to some kinds).
_EVERYWHERE = tuple(name for view in COMPUTED_VIEWS if view.scope is None for name in view.names)


def _strip_everywhere(value: Any, names: tuple[str, ...]) -> int:
    removed = 0
    if isinstance(value, dict):
        for name in names:
            if name in value:
                del value[name]
                removed += 1
        removed += sum(_strip_everywhere(held, names) for held in value.values())
    elif isinstance(value, list):
        removed += sum(_strip_everywhere(held, names) for held in value)
    return removed


def _retired_paths(ctx) -> list[str]:
    found: list[str] = []
    for entry in shape_map()["retired_files"]:
        if "path" in entry:
            if os.path.isfile(os.path.join(ctx.spec_root, entry["path"])):
                found.append(entry["path"])
        else:
            found.extend(name for step, name in step_json_names(ctx.spec_root) if step == entry["step"])
    return found


def _used_canonical_ids(value: Any) -> set[str]:
    """The ``cn:`` ids a file refers to through ``*_ref`` objects (what the canonical-integrity drift check counts as used)."""
    used: set[str] = set()
    if isinstance(value, dict):
        for key, held in value.items():
            if key.endswith("_ref") and isinstance(held, dict) and isinstance(held.get("id"), str) and held["id"].startswith("cn:"):
                used.add(held["id"])
            used |= _used_canonical_ids(held)
    elif isinstance(value, list):
        for held in value:
            used |= _used_canonical_ids(held)
    return used


def _prune_canonical_refs(data: dict[str, Any]) -> int:
    """Drop the ``canonical_refs_used`` entries that no ``*_ref`` of the file names any more; returns how many."""
    declared = data.get("canonical_refs_used")
    if not isinstance(declared, list):
        return 0
    used = _used_canonical_ids({k: v for k, v in data.items() if k != "canonical_refs_used"})
    kept = [e for e in declared if not (isinstance(e, dict) and isinstance(e.get("id"), str) and e["id"].startswith("cn:") and e["id"] not in used)]
    removed = len(declared) - len(kept)
    if removed:
        declared[:] = kept
    return removed


class _Work:
    """The removals of one run over the files of the map; works on the live data when *write*, else on private copies."""

    def __init__(self, ctx, write: bool) -> None:
        self.ctx, self.write = ctx, write
        self.docs: dict[str, Any] = {}
        self.counts: dict[str, int] = {}
        self.changed: set[str] = set()

    def data(self, rel: str) -> Any:
        if rel not in self.docs:
            held = self.ctx.documents.load(rel).data
            self.docs[rel] = held if self.write else copy.deepcopy(held)
        return self.docs[rel]

    def rows(self, rows: list[dict[str, Any]]) -> None:
        closed_rels = closed_plan_files(self.ctx)
        for row in rows:
            key = last_key(row["path"])
            for rel in files_of_row(self.ctx, row, closed_rels):
                for holder in list(parents_at(self.data(rel), row["path"])):
                    if key in holder:
                        del holder[key]
                        self.counts[row["id"]] = self.counts.get(row["id"], 0) + 1
                        self.changed.add(rel)

    def computed(self) -> int:
        removed = 0
        for rel in _step_files(self.ctx):
            count = _strip_everywhere(self.data(rel), _EVERYWHERE)
            removed += count
            if count:
                self.changed.add(rel)
        return removed

    def prune(self) -> int:
        return sum(_prune_canonical_refs(self.data(rel)) for rel in sorted(self.changed) if isinstance(self.data(rel), dict))


def _step_files(ctx) -> list[str]:
    retired = set(_retired_paths(ctx))
    names = [name for _step, name in step_json_names(ctx.spec_root) if name not in retired]
    return names + plan_rels(ctx)


def _run(ctx, write: bool) -> tuple[_Work, int, int]:
    work = _Work(ctx, write)
    work.rows(shape_rows(SCRIPT.id))
    computed = work.computed()
    return work, computed, work.prune()


def detect(ctx) -> int:
    """Keys still to remove, stale ``canonical_refs_used`` entries, and retired files still present."""
    work, computed, pruned = _run(ctx, write=False)
    return sum(work.counts.values()) + computed + pruned + len(_retired_paths(ctx))


def apply(ctx) -> ScriptResult:
    """Remove the rows' keys and the stored computed names, prune the canonical refs they leave unused, delete the retired files."""
    work, computed, pruned = _run(ctx, write=True)
    retired = _retired_paths(ctx)
    for rel in retired:
        os.remove(os.path.join(ctx.spec_root, rel))
    residue = tuple(f"{row_id}: {count} removed" for row_id, count in sorted(work.counts.items()))
    if computed:
        residue += (f"stored computed names ({', '.join(_EVERYWHERE)}): {computed} removed",)
    if pruned:
        residue += (f"canonical_refs_used: {pruned} entries no longer named by a *_ref removed",)
    residue += tuple(f"{rel}: file deleted" for rel in retired)
    return ScriptResult(edits=sum(work.counts.values()) + computed + pruned + len(retired), residue=residue)


def verify(before, after) -> list[Problem]:
    """The retired files are gone, no ``*_refs_ingested`` is left, and no file gained a key."""
    problems: list[Problem] = []
    for rel in sorted(after.documents):
        document = after.documents[rel]
        if not isinstance(document, dict):
            continue
        if any(name in document for name in ("spec_refs_ingested", "seed_refs_ingested")):
            problems.append(Problem(f"{rel}: a *_refs_ingested key is left", rel))
        old = before.documents.get(rel)
        if isinstance(old, dict) and set(document) - set(old):
            problems.append(Problem(f"{rel}: gained the key {sorted(set(document) - set(old))}", rel))
    return problems
