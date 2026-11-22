"""``p2_id_mint``: an id for every item that had none ("every node has an id", design 3.1).

Which collections hold nodes, which field is the id and which text field a plain string becomes all come from the 1.2.0
kind registry (``ctx.kind_registry()``: the ``x-node`` of the schemas), never from a table of this script.  For every
registered collection of a step file the script finds the entries that have no id: a string (a charter risk, an 02a gate or
secret, a stakeholder need, ...) becomes ``{<id field>: <id>, <first contract field>: <string>}``; an object gets its id
field, first.  A gate keeps its own kebab name as its id; every other id is minted ONCE by the build's one minter
(``graph.ids.mint_slug`` with the prefix ``graph.ids.suggest_prefix`` suggests, free among every id of the spec and every
id minted so far) and is never derived again: an item that has an id is not touched, so a rerun mints nothing.

Two legacy lists have another NAME than the collection they become and are read here: step 00 ``in_scope`` and
``out_of_scope`` (one ``scope_items`` list, ``scope`` ``in`` or ``out`` from the source list) and step 10 ``pr_rules``
(``rules``).  An ``out`` scope item needs a ``scope_reason`` the migration must not invent: one worklist item each.  A
gate string that is not a kebab name is minted a slug and the text goes to the worklist (a gate object has no text field).
Nothing else of an item changes here (links such as ``derives_from``, ``scope`` of the other obligations and the removed
fields are the work of later phases).
"""

from __future__ import annotations

import copy
import re
from typing import Any

from specdev_tools.core.ambiguity_items import ANCHOR_STEP
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import first_free_id, suggest_prefix
from specdev_tools.graph.kinds import KindDecl
from specdev_tools.migration.maps import LEGACY_STEP_IDS
from specdev_tools.migration.minting import mint_id
from specdev_tools.migration.registry import PHASE_IDS, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.worklist import add_items, make_item, missing_items
from specdev_tools.validation.linter_utils import graph_known_ids

# Step 16 (the anchor file) is left out on purpose: its only collections are nested (``plan.ambiguities``,
# ``plan.milestone_index``), which ``_run`` does not reach, and an anchor row gets its id from its milestone in
# ``p2_anchor_rows``, never from this script's label rule.
STEPS = tuple(step for step in LEGACY_STEP_IDS if step != ANCHOR_STEP)
SCRIPT = ScriptSpec(id="p2_id_mint", phase=PHASE_IDS, requires=("p2_id_collisions",), touches=(*STEPS, "extras"))

# Legacy list name -> (collection it becomes, fields every converted item gets), per step file.
LEGACY_LISTS: dict[str, tuple[tuple[str, str, dict[str, str]], ...]] = {
    "00": (("in_scope", "scope_items", {"scope": "in"}), ("out_of_scope", "scope_items", {"scope": "out"})),
    "10": (("pr_rules", "rules", {}),),
}
GATE_KIND = "gate"
SCOPE_OUT = "out"
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KIND_SCOPE_REASON = "scope-reason"
KIND_GATE_TEXT = "gate-text"

# What names an object that has no text of its own: the fields that read as its name, per kind (first non-empty wins).
_NAME_FIELDS = {"stakeholder": ("role",), "api-error": ("code", "message"), "connection": ("from", "to"), "scaffold-row": ("method", "path")}


def _label(kind: str, entry: dict[str, Any]) -> str:
    """The text a new id is made from: the kind's name fields, else the first of the usual label fields."""
    fields = _NAME_FIELDS.get(kind) or ("title", "name", "text", "description", "summary")
    parts = [str(entry[f]) for f in fields if isinstance(entry.get(f), str) and entry[f]]
    return " ".join(parts if kind in ("connection", "scaffold-row") else parts[:1])


def _with_id_first(entry: dict[str, Any], id_field: str, new_id: str) -> None:
    held = list(entry.items())
    entry.clear()
    entry[id_field] = new_id
    entry.update(held)


class _Minter:
    """One pass over the step files: converts and mints on the data it is given, counts, and lists the worklist items."""

    def __init__(self, ctx, taken: set[str]) -> None:
        self.ctx, self.taken = ctx, taken
        self.count = 0
        self.items: list = []
        self.renames: list[str] = []

    def new_id(self, decl: KindDecl, text: str) -> str:
        minted = mint_id(text, self.taken, prefix=suggest_prefix(decl.kind))
        self.taken.add(minted)
        return minted

    def convert_string(self, decl: KindDecl, text: str, step: str, extra: dict[str, str]) -> dict[str, Any]:
        assert decl.id_field is not None
        if decl.kind == GATE_KIND:
            kebab = bool(KEBAB.match(text))
            gate_id = first_free_id(text, self.taken) if kebab else self.new_id(decl, text)
            self.taken.add(gate_id)
            if not kebab:
                self.items.append(make_item(step, KIND_GATE_TEXT, gate_id, audience="agent", blocking=False,
                                            evidence=f"the gate was the text {text!r}, which is not a kebab name; a gate object has no text field",
                                            proposal=f"name the gate {gate_id} as you see fit; keep the original wording in a note"))
            return {decl.id_field: gate_id}
        text_field = decl.contract[0] if decl.contract else "text"
        return {decl.id_field: self.new_id(decl, text), text_field: text, **extra}

    def array(self, decl: KindDecl, entries: list[Any], step: str) -> None:
        if decl.map_keyed or decl.id_field is None:
            return
        for index, entry in enumerate(entries):
            if isinstance(entry, str):
                entry = entries[index] = self.convert_string(decl, entry, step, {})
                self.count += 1
            elif isinstance(entry, dict) and not isinstance(entry.get(decl.id_field), str):
                label = _label(decl.kind, entry)
                if label:
                    _with_id_first(entry, decl.id_field, self.new_id(decl, label))
                    self.count += 1
            if isinstance(entry, dict):
                self.nested(decl, entry, step)

    def nested(self, decl: KindDecl, entry: dict[str, Any], step: str) -> None:
        for child in decl.nested:
            name = child.array_path.lstrip(".")
            if isinstance(entry.get(name), list):
                self.array(child, entry[name], step)

    def legacy_lists(self, step: str, data: dict[str, Any], decls: dict[str, KindDecl]) -> None:
        for old, new, extra in LEGACY_LISTS.get(step, ()):
            values = data.get(old)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                continue
            decl = decls[new]
            target = data.get(new) if isinstance(data.get(new), list) else None
            if target is None:
                held = list(data.items())
                data.clear()
                for key, value in held:
                    if key == old:
                        data[new] = target = []
                    data[key] = value
            for text in values:
                target.append(self.convert_string(decl, text, step, extra))
                self.count += 1
                if extra.get("scope") == SCOPE_OUT:
                    self.items.append(make_item(step, KIND_SCOPE_REASON, target[-1][decl.id_field], audience="agent", blocking=True,
                                                evidence=f"{target[-1][decl.id_field]} was listed in out_of_scope; scope `out` needs a scope_reason and the old list gave none",
                                                proposal="write why the item is out of scope, from the seed or the charter; no reason is invented here"))
            del data[old]
            self.count += 0 if values else 1


def _run(ctx, *, write: bool) -> _Minter:
    taken = set(graph_known_ids(build_graph(ctx.spec_root, ctx.toolkit_root)))
    minter = _Minter(ctx, taken)
    for file_decl in ctx.kind_registry().files:
        if file_decl.is_glob or file_decl.step not in STEPS:
            continue
        try:
            document = ctx.documents.load(file_decl.pattern)
        except FileNotFoundError:
            continue
        data = document.data if write else copy.deepcopy(document.data)
        if not isinstance(data, dict):
            continue
        decls = {decl.array_path.lstrip("."): decl for decl in file_decl.kinds}
        minter.legacy_lists(file_decl.step, data, decls)
        for decl in file_decl.kinds:
            name = decl.array_path.lstrip(".")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and isinstance(data.get(name), list):
                minter.array(decl, data[name], file_decl.step)
    return minter


def detect(ctx) -> int:
    """Items to convert or mint, plus worklist items not yet listed."""
    minter = _run(ctx, write=False)
    return minter.count + len(missing_items(ctx, minter.items))


def apply(ctx) -> ScriptResult:
    """Convert and mint on the loaded documents (the runner writes them) and list what needs a person."""
    minter = _run(ctx, write=True)
    listed = add_items(ctx, minter.items)
    return ScriptResult(edits=minter.count + listed, worklist_items=listed)


def verify(before, after) -> list[Problem]:
    """The legacy list names are gone from step 00 and 10."""
    problems: list[Problem] = []
    for step, lists in LEGACY_LISTS.items():
        for rel, document in after.documents.items():
            if rel.startswith(f"{step}_") and isinstance(document, dict):
                for old, _new, _extra in lists:
                    if isinstance(document.get(old), list) and all(isinstance(v, str) for v in document[old]):
                        problems.append(Problem(f"{rel} still holds the legacy list {old}", rel))
    return problems
