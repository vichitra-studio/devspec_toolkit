"""``p2_id_collisions``: an id that two nodes define is renamed once; the migration renames only REAL collisions.

``graph.dups`` of the graph over the spec folder lists every id defined more than once.  The rule per pair of kinds is in
``migration/maps/legacy_ref_fields.yaml`` (``collisions``): a 14 task criterion that reuses a 04 criterion id becomes
``tc-...``; the 09 copy of a milestone id 14 also defines becomes ``milestone-...``; any other pair keeps the earlier
definition and gives the later one the id E704 suggests.  ``trace.rename.rename_node`` refuses an id defined twice (E770),
so this script edits the renamed definition itself (its id field, found by the graph's ``file`` and ``jq_path``), writes no
alias (it would collide with the kept id) and records the rename in its result for the runner's id invariant.

A reference to the old id is rewritten only where the HOLDER FIELD fixes the kind it points at (the table ``fields`` of the
same file, the ``type`` of a ``{type, id}`` entry through ``typed_types``) and that kind is the renamed one.  A mention that
the field does not fix (an unlisted field, a type that names two kinds, free text such as a plan item's description) is
never rewritten: it is a worklist item, one per holder and field, naming both candidates.  Duplicated ambiguity ids are no
collision to mint around: a copy in the anchor and a copy in a plan is one promoted item (``duplicate-promoted-item`` for a
person); two copies in plans are P4's (nothing here).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import path_steps
from specdev_tools.graph.ids import first_free_id
from specdev_tools.graph.model import Graph, Node
from specdev_tools.migration.context import CAPTURE_REL, file_key
from specdev_tools.migration.maps import LEGACY_STEP_IDS, legacy_ref_fields
from specdev_tools.migration.registry import PHASE_IDS, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import AMBIGUITY, RENAMES_KEY, closed_plan_files
from specdev_tools.migration.worklist import OPEN_ITEM_RULE, WorklistItem, add_items, make_item, missing_items
from specdev_tools.validation.linter_utils import graph_known_ids

SCRIPT = ScriptSpec(id="p2_id_collisions", phase=PHASE_IDS, touches=(*LEGACY_STEP_IDS, "extras"))

ANCHOR_FILE = "16_impl_context.json"
KIND_CITATION = "collided-id-citation"
KIND_PROMOTED = "duplicate-promoted-item"
_TYPED = "type:"

Path = tuple[Any, ...]


@dataclass(frozen=True)
class Rename:
    """One definition that gets a new id."""

    old: str
    new: str
    node: Node
    id_field: str


@dataclass(frozen=True)
class RefEdit:
    """One reference rewritten: the file, the path of the string in it, and the old and new id."""

    file: str
    path: Path
    old: str
    new: str


def _fields_for(rel: str) -> list[dict[str, Any]]:
    """The tables of the step of *rel* (plan files: ``plan``), then the shared ``trace`` table."""
    fields = legacy_ref_fields()["fields"]
    key = "plan" if rel.startswith("impl_context/") else file_key(rel)
    return [fields.get(key) or {}, fields.get("trace") or {}]


def _rule_for(kinds: set[str]) -> dict[str, Any] | None:
    for rule in legacy_ref_fields()["collisions"]:
        if set(rule["kinds"]) == kinds:
            return rule
    return None


def _new_id(old: str, rule: dict[str, Any] | None, taken: set[str]) -> str:
    swap = (rule or {}).get("replace_prefix")
    if swap:
        base = swap["to"] + (old[len(swap["from"]):] if old.startswith(swap["from"]) else old)
    else:
        base = old
    new = first_free_id(base, taken)
    taken.add(new)
    return new


def _scanned(rel: str) -> bool:
    """Step files and plan files are read for references; ``extras``, ``canon`` and ``common`` are not."""
    return file_key(rel)[:1].isdigit()


def _walk(value: Any, path: Path = (), field: str | None = None):
    """Every string of *value* as ``(path, field, text)``; ``field`` is the key the string sits under (``type:<t>`` for the id of a typed entry)."""
    if isinstance(value, dict):
        for key, held in value.items():
            if isinstance(held, str):
                typed = isinstance(value.get("type"), str) and key == "id"
                yield (*path, key), f"{_TYPED}{value['type']}" if typed else key, held
            else:
                yield from _walk(held, (*path, key), key)
    elif isinstance(value, list):
        for index, held in enumerate(value):
            if isinstance(held, str):
                yield (*path, index), field, held
            else:
                yield from _walk(held, (*path, index), field)


def _holder(nodes_by_file: dict[str, list[tuple[Path, Node]]], rel: str, path: Path) -> Node | None:
    best: Node | None = None
    best_len = -1
    for steps, node in nodes_by_file.get(rel, ()):
        if path[: len(steps)] == steps and len(steps) > best_len:
            best, best_len = node, len(steps)
    return best


def _kind_of_field(rel: str, field: str | None, holder_kind: str | None) -> str | None | bool:
    """The kind *field* of the file *rel* fixes: a kind name, ``None`` when it fixes none, ``False`` when it is no reference at all."""
    if field is None:
        return None
    if field.startswith(_TYPED):
        return legacy_ref_fields()["typed_types"].get(field[len(_TYPED):])
    for table in _fields_for(rel):
        if field in (table.get("definitions") or ()) or field in (table.get("not_references") or {}):
            return False
        ref = (table.get("refs") or {}).get(field)
        if isinstance(ref, dict):
            return ref.get(holder_kind)
        if ref is not None:
            return ref
    return None


class _Plan:
    def __init__(self, ctx) -> None:
        self.renames: list[Rename] = []
        self.edits: list[RefEdit] = []
        self.items: dict[str, WorklistItem] = {}
        graph = build_graph(ctx.spec_root, ctx.toolkit_root)
        taken = graph_known_ids(graph)
        for old in sorted(graph.dups):
            self._group(old, graph.dups[old], graph, taken)
        if self.renames:
            self._references(ctx, graph)

    def _group(self, old: str, nodes: list[Node], graph: Graph, taken: set[str]) -> None:
        kinds = {n.kind for n in nodes}
        rule = _rule_for(kinds)
        if kinds == {AMBIGUITY}:
            if rule and rule.get("triage_when_files") and ANCHOR_FILE in {n.file for n in nodes} and len({n.file for n in nodes}) > 1:
                item = make_item("16", KIND_PROMOTED, old, audience="operator", blocking=True,
                                 evidence=f"the open item {old} is in the anchor and in a plan ({', '.join(sorted({n.file for n in nodes}))}): one item promoted from a plan to the anchor",
                                 proposal=f"the run renames the plan's copy to `{old}-2` (the next number not in use if that is taken; the run prints `duplicate id renamed: {old} -> <new id>`), so each copy has its own id: answer the question in the spec, then delete both by id (`specdev json delete --id {old}` and `specdev json delete --id {old}-2`); {OPEN_ITEM_RULE}")
                self.items[item.id] = item
            return
        if rule and rule.get("rename"):
            renamed = [n for n in nodes if n.kind == rule["rename"]]
        else:
            renamed = nodes[1:]
        for node in renamed:
            decl = graph.decls[node.kind]
            self.renames.append(Rename(old, _new_id(old, rule, taken), node, decl.id_field or ""))

    def _references(self, ctx, graph: Graph) -> None:
        by_old: dict[str, list[Rename]] = {}
        for rename in self.renames:
            by_old.setdefault(rename.old, []).append(rename)
        definition_paths = {(n.file, tuple(path_steps(n.jq_path) or ()) + (graph.decls[n.kind].id_field,)) for old in by_old for n in graph.dups[old] if graph.decls.get(n.kind)}
        nodes_by_file: dict[str, list[tuple[Path, Node]]] = {}
        for node in graph.nodes:
            nodes_by_file.setdefault(node.file, []).append((tuple(path_steps(node.jq_path) or ()), node))
        frozen = closed_plan_files(ctx)
        patterns = {old: re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(old)}(?![A-Za-z0-9_-])") for old in by_old}
        for rel in sorted(graph.documents):
            if not _scanned(rel):
                continue
            for path, field, text in _walk(graph.documents[rel]):
                if (rel, path) in definition_paths:
                    continue
                for old, renames in by_old.items():
                    if old not in text or not patterns[old].search(text):
                        continue
                    holder = _holder(nodes_by_file, rel, path)
                    kind = _kind_of_field(rel, field, holder.kind if holder else None) if text == old else None
                    if kind is False:
                        continue
                    if text == old and kind in {r.node.kind for r in renames}:
                        self.edits.append(RefEdit(rel, path, old, next(r.new for r in renames if r.node.kind == kind)))
                    elif text == old and kind:
                        continue  # the field fixes the kind that keeps the id
                    else:
                        self._citation(rel, path, field, text, holder, old, graph, rel in frozen)

    def _citation(self, rel: str, path: Path, field: str | None, text: str, holder: Node | None, old: str, graph: Graph, in_frozen_plan: bool) -> None:
        defs = graph.dups[old]
        described = "; ".join(f"{n.kind} at {n.file} {n.jq_path}" + (f" (now {r.new})" if (r := next((r for r in self.renames if r.node is n), None)) else "") for n in defs)
        about = holder.id if holder else rel
        item = make_item(
            file_key(rel), KIND_CITATION, about, audience="agent", blocking=False, key=f"{old}-{field or 'text'}",
            evidence=f"{rel} {'.'.join(str(p) for p in path)} names `{old}`; {len(defs)} nodes defined it: {described}",
            proposal=(
                "the plan holding this text is closed and frozen: leave the text as it is and resolve the item"
                if in_frozen_plan else f"decide which one the text means; if the renamed one, replace `{old}` with its new id"
            ),
        )
        self.items[item.id] = item


def detect(ctx) -> int:
    """Definitions to rename, references to rewrite, and worklist items not yet listed."""
    plan = _Plan(ctx)
    return len(plan.renames) + len(plan.edits) + len(missing_items(ctx, list(plan.items.values())))


def _set_at(data: Any, path: Path, value: Any) -> None:
    for step in path[:-1]:
        data = data[step]
    data[path[-1]] = value


def _record_renames(ctx, renames: list[Rename]) -> None:
    """Append the renames to the ``renames`` section of the capture (P20); an entry already there is not added twice."""
    if not renames:
        return
    capture = ctx.documents.load(CAPTURE_REL).data
    held = capture.setdefault(RENAMES_KEY, [])
    for rename in renames:
        entry = {"old": rename.old, "new": rename.new, "kind": rename.node.kind, "file": rename.node.file}
        if entry not in held:
            held.append(entry)


def apply(ctx) -> ScriptResult:
    """Rename the later definitions, rewrite the references their field fixes, list the rest, record the renames in the capture."""
    plan = _Plan(ctx)
    _record_renames(ctx, plan.renames)
    for rename in plan.renames:
        steps = tuple(path_steps(rename.node.jq_path) or ()) + (rename.id_field,)
        _set_at(ctx.documents.load(rename.node.file).data, steps, rename.new)
    for edit in plan.edits:
        _set_at(ctx.documents.load(edit.file).data, edit.path, edit.new)
    listed = add_items(ctx, list(plan.items.values()))
    residue = tuple(f"{r.old} -> {r.new} ({r.node.kind}, {r.node.file} {r.node.jq_path})" for r in plan.renames)
    return ScriptResult(
        edits=len(plan.renames) + len(plan.edits) + listed,
        worklist_items=listed,
        residue=residue,
        renames=tuple((r.old, r.new) for r in plan.renames),
    )


def _aliases(document: Any) -> list[tuple[Path, str]]:
    return [(path, text) for path, field, text in _walk(document) if field == "aliases"]


def verify(before, after) -> list[Problem]:
    """A rename writes no alias: no file gained an entry in an ``aliases`` list (it would collide with the kept id)."""
    problems: list[Problem] = []
    for rel, document in sorted(after.documents.items()):
        if _scanned(rel) and set(_aliases(document)) - set(_aliases(before.documents.get(rel))):
            problems.append(Problem(f"{rel}: the rename wrote an alias", rel))
    return problems
