"""``p3_convert``: the 1.1.1 fields that become a declared 1.2.0 field or shape (phase 3), and the judgement they leave.

One row of ``migration/maps/v1_2_0.yaml`` per field (script ``p3_convert``); the row's ``convert.type`` says how:

* ``refs``: a field holding ids of one kind (``goal_id``, ``success_metric_refs``, a connection's ``from``) becomes the link
  field the registry declares for (holder kind, target kind);
* ``typed``: a list of ``{type, id, note}`` entries (``trace``, ``targets``, ``target_ids``, ``mitigations``) becomes links
  when the entry's type, the kind the id really has and ONE declared link field of the holder agree; every other entry is a
  worklist item (never a silent drop) and the old note goes;
* ``rename``, ``value``, ``out-of-scope``, ``rule-scope``, ``environment-config``, ``defaults``: the one-to-one cases;
* ``schedules`` (step 09 ``deliverables``) and ``spec-ref`` (open plans): judgement, one worklist item per case.

The link field of a (holder kind, target kind) pair comes from the kind registry, leaving out the verbs that accept any
kind (``replaces``, ``removes``, ``about``): "exactly one declared field" or the case is a worklist item.  Where a node
needs ``scope`` and has none it gets ``in`` (kinds whose contract names ``scope``); every node left with ``later`` or
``out`` and no ``scope_reason`` gets a ``scope-reason`` item (no reason is invented).  The source field of a converted row
is removed with the conversion; what could not be converted is in the worklist item's evidence.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import path_steps
from specdev_tools.graph.model import LIFECYCLES, Node
from specdev_tools.graph.names import ABOUT, CONNECTS_TO, DERIVES_FROM
from specdev_tools.migration.maps import legacy_ref_fields, shape_rows
from specdev_tools.migration.registry import PHASE_SHAPES, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.scripts.v1_2_0.p1_capture import CAPTURE_REL, capture_renames
from specdev_tools.migration.scripts.v1_2_0.p2_plan_milestone_key import step_file
from specdev_tools.migration.scripts.v1_2_0.p3_remove import STEPS, closed_plan_files, row_step
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items
from specdev_tools.migration.writer import WriterError

SCRIPT = ScriptSpec(
    id="p3_convert",
    phase=PHASE_SHAPES,
    requires=("p2_action_ids", "p2_anchor_rows", "p2_id_collisions", "p2_id_mint", "p2_plan_milestone_key"),
    touches=(*STEPS, "extras"),
)

KIND_TRACE_LINK = "trace-link"
KIND_LEGACY_REF = "legacy-ref"
KIND_SCOPE_REASON = "scope-reason"
KIND_SCHEDULES = "schedules"
KIND_SPEC_REF = "spec-ref-realises"
KIND_ENV_KEY = "environment-key"
KIND_EXTERNAL = "connection-external"
KIND_OUT_OF_SCOPE = "out-of-scope-entry"
SCOPE_IN, SCOPE_LATER, SCOPE_OUT = "in", "later", "out"
_WILDCARD_VERBS = frozenset({"replaces", "removes", ABOUT})
_CONFIG_KEY = re.compile(r"^[a-z][a-z0-9_-]*$")
_NODE_EXTRAS = frozenset({"lifecycle", "aliases"})
_PRIORITY_WONT = "wont-have"


@dataclass
class _Plan:
    """What one pass over the files did: edits made, worklist items found."""

    edits: int = 0
    items: dict[str, WorklistItem] = field(default_factory=dict)

    def item(self, item: WorklistItem) -> None:
        self.items.setdefault(item.id, item)


def _list_of(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _holder_kinds(ctx) -> dict[tuple[str, str], str]:
    """``{(step, collection path): kind}`` for every declared collection (``.milestones.tasks``)."""
    found: dict[tuple[str, str], str] = {}

    def walk(step: str, parent: str, decls) -> None:
        for decl in decls:
            path = parent + decl.array_path.replace("{}", "").replace("[]", "")
            found[(step, path)] = decl.kind
            walk(step, path, decl.nested)

    for file_decl in ctx.kind_registry().files:
        walk(file_decl.step, "", file_decl.kinds)
    return found


def _row_holder(kinds: dict[tuple[str, str], str], row: dict[str, Any]) -> str | None:
    collection = "." + ".".join(seg.replace("[]", "").replace("{}", "") for seg in row["path"].split(".")[:-1])
    return kinds.get((row_step(row), collection))


class _Pass:
    """One conversion pass over a graph and the document data (live when *write*, else private copies)."""

    def __init__(self, ctx, write: bool) -> None:
        self.ctx, self.write = ctx, write
        self.plan = _Plan()
        self.graph = build_graph(ctx.spec_root, ctx.toolkit_root)
        self.registry = ctx.kind_registry()
        self.kinds = _holder_kinds(ctx)
        self.docs: dict[str, Any] = {}
        self.kind_of: dict[str, str] = {}
        self.entries: list[tuple[Node, dict[str, Any]]] = []
        self.closed = closed_plan_files(ctx)
        for node in self.graph.nodes:
            item = self._item_of(node)
            if item is not None:
                self.entries.append((node, item))
                self.kind_of.setdefault(node.id, node.kind)
        self.external = {n.id for n, i in self.entries if n.kind == "component" and i.get("type") == "external"}

    def data(self, rel: str) -> Any:
        if rel not in self.docs:
            held = self.ctx.documents.load(rel).data
            self.docs[rel] = held if self.write else copy.deepcopy(held)
        return self.docs[rel]

    def _item_of(self, node: Node) -> dict[str, Any] | None:
        if node.step == "seed" or node.file.startswith(("/", "..")):
            return None
        steps = path_steps(node.jq_path)
        try:
            current: Any = self.data(node.file)
            for step in steps or ():
                current = current[step]
        except (KeyError, IndexError, TypeError, OSError, WriterError):
            return None
        return current if isinstance(current, dict) and steps else None

    def holders(self, row: dict[str, Any]) -> list[tuple[Node, dict[str, Any]]]:
        kind = _row_holder(self.kinds, row)
        step = row_step(row)
        return [(n, i) for n, i in self.entries if n.kind == kind and n.step == step]

    def link_field(self, holder_kind: str, target_kind: str) -> str | None:
        """The ONE link field *holder_kind* declares for *target_kind* (verbs that take any kind left out), else ``None``."""
        decl = self.graph.decls.get(holder_kind)
        every = set(self.registry.kind_names)
        fields = [
            link.field
            for link in (decl.links if decl else ())
            if link.field not in _WILDCARD_VERBS and set(link.kinds) != every and link.accepts(target_kind)
        ]
        return fields[0] if len(fields) == 1 else None

    def accepts(self, holder_kind: str, field_name: str, target_kind: str) -> bool:
        decl = self.graph.decls.get(holder_kind)
        return any(link.field == field_name and link.accepts(target_kind) for link in (decl.links if decl else ()))

    def add_links(self, item: dict[str, Any], field_name: str, ids: list[str]) -> None:
        held = item.get(field_name)
        current = list(held) if isinstance(held, list) else []
        new = [i for i in dict.fromkeys(ids) if i not in current]
        if new:
            item[field_name] = current + new
            self.plan.edits += 1

    def drop(self, item: dict[str, Any], *names: str) -> None:
        for name in names:
            if name in item:
                del item[name]
                self.plan.edits += 1

    def worklist(self, node: Node, kind: str, key: str, evidence: str, proposal: str = "", *, blocking: bool = False) -> None:
        self.plan.item(make_item(node.step or "", kind, node.id, audience="agent", blocking=blocking, key=key, evidence=evidence, proposal=proposal))

    # --- rows ------------------------------------------------------------------------------------------------------

    def run(self) -> _Plan:
        handlers = {
            "refs": self._refs, "typed": self._typed, "rename": self._rename, "value": self._value,
            "out-of-scope": self._out_of_scope, "rule-scope": self._rule_scope, "environment-config": self._environment_config,
            "schedules": self._schedules, "spec-ref": self._spec_ref, "defaults": lambda row: None,
        }
        for row in shape_rows(SCRIPT.id):
            handlers[row["convert"]["type"]](row)
        self._defaults()
        self._scope_reasons()
        return self.plan

    def _values(self, item: dict[str, Any], names: list[str]) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for name in names:
            held = item.get(name)
            for value in held if isinstance(held, list) else [held]:
                if isinstance(value, str) and value:
                    found.append((name, value))
        return found

    def _refs(self, row: dict[str, Any]) -> None:
        spec = row["convert"]
        for node, item in self.holders(row):
            names = [n for n in spec["fields"] if n in item]
            if not names:
                continue
            target_field = spec.get("to") or self.link_field(node.kind, spec["target"])
            good: list[str] = []
            for name, value in self._values(item, names):
                real = self.kind_of.get(value)
                if target_field is None or real != spec["target"]:
                    why = "no node has this id" if real is None else f"it is a {real}, the field names a {spec['target']}"
                    self.worklist(node, KIND_LEGACY_REF, f"{name}-{value}", f"{name} `{value}`: {why}", "decide which node it meant, or drop it")
                elif value in self.external and target_field == CONNECTS_TO:
                    self.worklist(node, KIND_EXTERNAL, f"{name}-{value}", f"{name} `{value}` is an external component: the third-party pass replaces it",
                                  "after the third-party node exists, `connects_to` it")
                else:
                    good.append(value)
            if target_field:
                self.add_links(item, target_field, good)
            self.drop(item, *names)

    def _typed(self, row: dict[str, Any]) -> None:
        spec = row["convert"]
        types = legacy_ref_fields()["typed_types"]
        for node, item in self.holders(row):
            entries = item.get(spec["field"])
            if spec["field"] not in item:
                continue
            for entry in entries if isinstance(entries, list) else []:
                self._typed_entry(node, item, row, entry, types)
            self.drop(item, spec["field"])

    def _typed_entry(self, node: Node, item: dict[str, Any], row: dict[str, Any], entry: Any, types: dict[str, Any]) -> None:
        spec = row["convert"]
        kind = spec.get("item_kind", KIND_TRACE_LINK)
        ident = entry.get("id") if isinstance(entry, dict) else None
        stated = types.get(str(entry.get("type"))) if isinstance(entry, dict) else None
        real = self.kind_of.get(ident) if isinstance(ident, str) else None
        field_name = spec.get("to") or (self.link_field(node.kind, real) if real else None)
        text = f"{spec['field']} entry {entry!r}"
        if not isinstance(ident, str) or real is None:
            self.worklist(node, kind, f"{spec['field']}-{ident}", f"{text}: no node has this id", "drop it or point it at the node it meant")
        elif stated is None or stated != real:
            self.worklist(node, kind, f"{spec['field']}-{ident}", f"{text}: the entry's type fixes {stated or 'no kind'}, the id is a {real}", "decide which it is")
        elif field_name is None or not self.accepts(node.kind, field_name, real):
            self.worklist(node, kind, f"{spec['field']}-{ident}", f"{text}: a {node.kind} has no single link field for a {real}", self._no_field_proposal(node, real, ident))
        else:
            self.add_links(item, field_name, [ident])

    def _no_field_proposal(self, node: Node, real: str, ident: str) -> str:
        if real == "fr" and node.kind == "fixture":
            criteria = [n.id for n in self.graph.nodes if n.kind == "criterion" and n.parent == ident]
            if criteria:
                return f"`verifies` takes criteria, not an FR: use the criteria of {ident}: {', '.join(criteria)}"
        return "link it by hand with the field that fits, or drop it"

    def _rename(self, row: dict[str, Any]) -> None:
        spec = row["convert"]
        for node, item in self.holders(row):
            if spec["field"] not in item:
                continue
            held = item[spec["field"]]
            values = [v for v in (held if isinstance(held, list) else [held]) if isinstance(v, str)]
            good: list[str] = []
            for value in values:
                kind = self.kind_of.get(value)
                if kind is None or self.accepts(node.kind, spec["to"], kind):
                    good.append(value)
                else:
                    self.worklist(node, KIND_LEGACY_REF, f"{spec['field']}-{value}", f"{spec['field']} `{value}` is a {kind}, {spec['to']} does not take one", "link it by hand or drop it")
            self.drop(item, spec["field"])
            self.add_links(item, spec["to"], good)

    def _value(self, row: dict[str, Any]) -> None:
        spec = row["convert"]
        for node, item in self.holders(row):
            if item.get(spec["field"]) != spec["old"]:
                continue
            if spec["field"] == "priority":
                self.drop(item, "priority")
                item["scope"] = spec["scope"]
            else:
                item[spec["field"]] = spec["new"]
            self.plan.edits += 1

    def _out_of_scope(self, row: dict[str, Any]) -> None:
        name = step_file(self.ctx, row_step(row))
        if name is None:
            return
        document = self.data(name)
        entries = document.get("out_of_scope")
        if "out_of_scope" not in document:
            return
        for entry in entries if isinstance(entries, list) else []:
            self._out_entry(name, entry)
        del document["out_of_scope"]
        self.plan.edits += 1

    def _out_entry(self, name: str, entry: Any) -> None:
        target = next((v for k, v in entry.items() if k.endswith("_id") and isinstance(v, str)), None) if isinstance(entry, dict) else None
        found = next(((n, i) for n, i in self.entries if n.id == target), None) if target else None
        if found is None:
            self.plan.item(make_item(name[:2], KIND_OUT_OF_SCOPE, name, audience="agent", blocking=False, key=str(target or entry)[:40],
                                     evidence=f"out_of_scope entry {entry!r} names no node", proposal="set `scope: out` and a scope_reason on the node it meant"))
            return
        node, item = found
        item["scope"] = SCOPE_OUT
        reason = entry.get("rationale")
        if isinstance(reason, str) and reason.strip():
            item["scope_reason"] = reason
        self.plan.edits += 1

    def _rule_scope(self, row: dict[str, Any]) -> None:
        for node, item in self.holders(row):
            held = item.get("scope")
            if not isinstance(held, dict):
                continue
            ids = [v for name in ("components", "apis") for v in _list_of(held.get(name))]
            good = [i for i in ids if self.kind_of.get(i) and self.accepts(node.kind, "constrains", self.kind_of[i])]
            for ident in ids:
                if ident not in good:
                    self.worklist(node, KIND_LEGACY_REF, f"scope-{ident}", f"scope names `{ident}`, which is no node a rule can constrain", "drop it or link it by hand")
            self.add_links(item, "constrains", good)
            item["scope"] = SCOPE_IN
            self.plan.edits += 1

    def _environment_config(self, row: dict[str, Any]) -> None:
        for node, item in ((n, i) for n, i in self.entries if n.kind == "environment"):
            decl = self.graph.decls.get(node.kind)
            known = set(decl.contract if decl else ()) | {link.field for link in (decl.links if decl else ())} | _NODE_EXTRAS
            moved: dict[str, Any] = {}
            for key in [k for k in item if k not in known]:
                if _CONFIG_KEY.match(key):
                    moved[key] = item.pop(key)
                else:
                    self.worklist(node, KIND_ENV_KEY, key, f"environment key `{key}` is no node field and is not a valid config key", "rename it, then put it under config")
            lifecycle = item.get("lifecycle")
            if lifecycle is not None and lifecycle not in LIFECYCLES:
                moved["lifecycle"] = item.pop("lifecycle")
            if moved:
                existing: dict[str, Any] = item["config"] if isinstance(item.get("config"), dict) else {}
                item["config"] = {**moved, **existing}
                self.plan.edits += 1

    def _schedules(self, row: dict[str, Any]) -> None:
        name = step_file(self.ctx, row_step(row))
        if name is None:
            return
        proposals = schedule_proposals(self.ctx, self.graph, self.kind_of)
        for node, item in self.entries:
            if node.file != name or node.kind != "design-milestone":
                continue
            if item.get("schedules"):
                self.drop(item, "deliverables")
                continue
            candidates = proposals.get(node.id, [])
            self.worklist(node, KIND_SCHEDULES, "schedules", f"{node.id} schedules nothing yet: `schedules` is required and the old `deliverables` are free text (in capture.json, milestone_links)",
                          f"schedule: {', '.join(candidates)}" if candidates else "no candidate: the paired 14 milestone names none", blocking=True)
            self.drop(item, "deliverables")

    def _spec_ref(self, row: dict[str, Any]) -> None:
        for rel in sorted(rel for rel in {n.file for n, _ in self.entries if n.kind == "plan-item"} if rel not in self.closed):
            for node, item in self.entries:
                if node.file == rel and node.kind == "plan-item" and isinstance(item.get("spec_ref"), dict):
                    task = item["spec_ref"].get("id")
                    criteria = [n.id for n in self.graph.nodes if n.kind == "task-criterion" and n.parent == task]
                    self.worklist(node, KIND_SPEC_REF, "spec-ref", f"spec_ref names task `{task}`; the item must `realises` task criteria",
                                  f"realises: {', '.join(criteria)}" if criteria else "the task has no criteria: add one first", blocking=True)

    def _defaults(self) -> None:
        for node, item in self.entries:
            decl = self.graph.decls.get(node.kind)
            if decl and "scope" in decl.contract and "scope" not in item and node.step not in (None, "16"):
                item["scope"] = SCOPE_IN
                self.plan.edits += 1

    def _scope_reasons(self) -> None:
        for node, item in self.entries:
            if item.get("scope") in (SCOPE_LATER, SCOPE_OUT) and not item.get("scope_reason"):
                self.worklist(node, KIND_SCOPE_REASON, "", f"{node.id} has scope `{item['scope']}` and no scope_reason; the old data gave none",
                              "write why, from the seed or the charter; no reason is invented here", blocking=True)


def schedule_proposals(ctx, graph, kind_of: dict[str, str]) -> dict[str, list[str]]:
    """``{09 milestone id (now): obligation ids it could schedule}``: the typed ``deliverables`` of the milestone and the FRs of the paired 14 milestones.

    Read from ``capture.json`` (``milestone_links``): the 09 rows are keyed by the id the milestone had when the capture
    was made, the 14 rows name their 09 milestones in ``legacy_source_milestones`` by the same old ids; ``capture_renames``
    maps an old 09 id to its id now.  Only ids of a kind the registry lets a 09 milestone schedule are proposed.
    """
    renames = capture_renames(ctx).get("design-milestone", {})
    decl = graph.decls.get("design-milestone")
    allowed = {k for link in (decl.links if decl else ()) if link.field == "schedules" for k in link.kinds}
    rows = ctx.documents.load(CAPTURE_REL).data.get("milestone_links") or []
    paired: dict[str, list[str]] = {}
    for row in rows:
        if row.get("step") == "14":
            for old in row.get("legacy_source_milestones") or []:
                paired.setdefault(old, []).extend(row.get("legacy_fr_refs") or [])
    found: dict[str, list[str]] = {}
    for row in rows:
        if row.get("step") != "09":
            continue
        old = str(row["milestone"])
        ids = [e.get("id") for e in row.get("legacy_deliverables") or [] if isinstance(e, dict)] + paired.get(old, [])
        unique = list(dict.fromkeys(i for i in ids if isinstance(i, str) and kind_of.get(i) in allowed))
        found[renames.get(old, old)] = unique
    return found


def _run(ctx, write: bool) -> tuple[_Plan, list[WorklistItem]]:
    plan = _Pass(ctx, write).run()
    return plan, list(plan.items.values())


def detect(ctx) -> int:
    """Edits still to make, plus worklist items not yet listed."""
    plan, items = _run(ctx, write=False)
    return plan.edits + len(missing_items(ctx, items))


def apply(ctx) -> ScriptResult:
    """Convert the rows' fields and list what needs a person."""
    plan, items = _run(ctx, write=True)
    listed = add_items(ctx, items)
    return ScriptResult(edits=plan.edits + listed, worklist_items=listed)


def verify(before, after) -> list[Problem]:
    """The root ``out_of_scope`` lists are gone (steps 05 and 08 converted them, ``p2_id_mint`` step 00)."""
    return [
        Problem(f"{rel}: out_of_scope is still at the top of the file", rel)
        for rel, document in sorted(after.documents.items())
        if isinstance(document, dict) and rel[:2].isdigit() and "out_of_scope" in document
    ]
