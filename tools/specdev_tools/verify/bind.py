"""``verify bind``: plan the verification record that binds a verifier (a fixture, a job or a rule) to commands and a guard.

The plan is pure: it reads the graph and decides the stage, the proved nodes and the record id, or refuses.  The command
holds the write lock, builds the graph under it, plans and writes (``apply_bind``).  A binding covers one verifier;
``proves`` lists the nodes of that verifier it proves, and its stage is the highest stage they need.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from specdev_tools.graph.contract import item_of
from specdev_tools.graph.ids import mint_slug
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node
from specdev_tools.graph.queries import unknown_node_error
from specdev_tools.proof.stages import UnknownStageForEnvironment, binding_required_stage, bindings_of, required_stage
from specdev_tools.verify.guard import GuardError, compile_guard
from specdev_tools.verify.records import BINDING_KIND, BINDING_PREFIX, Binding, binding_of, records_folder, refusal, write_binding

FIXTURE = "fixture"
JOB = "job"
RULE = "rule"
_TARGET_FIELDS = {FIXTURE: ("verifies",), JOB: ("realises", "verifies"), RULE: ()}
_ID_PREFIXES = ("fix-", "job-", "rule-")
_RECORD_ID = re.compile(r"^ver-[a-z0-9]+(?:-[a-z0-9]+)*$")
_MANUAL_MODE = "manual"
EMPTY_GUARD_NOTE = "the guard matches empty output, so it cannot tell a run that printed nothing; prefer a line only a real run prints"


@dataclass(frozen=True)
class BindRequest:
    """What the user gave: the verifier, the commands, the guard, and optionally ``proves``, the stage and the record id."""

    verifier: str
    commands: tuple[str, ...]
    guard: str | None
    proves: tuple[str, ...] = ()
    stage: str | None = None
    record_id: str | None = None


@dataclass(frozen=True)
class BindPlan:
    """The record to write and why: ``reasoning`` is the stage each proved node needs, ``replaced`` whether the record exists."""

    item: dict[str, Any]
    record_id: str
    verifier: str
    stage: str
    proves: tuple[str, ...]
    reasoning: tuple[tuple[str, str], ...]
    replaced: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class BindResult:
    """A written binding: the plan and the name of the record file (in ``extras/verification``)."""

    plan: BindPlan
    file: str


def _verifier_of(graph: Graph, verifier_id: str) -> Node:
    """The node to bind, or the refusal that says why it cannot be bound."""
    node = graph.find(verifier_id)
    if node is None:
        raise unknown_node_error(graph, verifier_id)
    if node.kind not in _TARGET_FIELDS:
        raise refusal("E767", f"'{node.id}' is of kind {node.kind}; a binding verifies a fixture, a job or a rule")
    if node.lifecycle == NOT_APPLICABLE:
        raise refusal("E767", f"'{node.id}' is not_applicable and takes no binding; set it active first or bind another verifier")
    item = item_of(graph, node) or {}
    if node.kind == FIXTURE and item.get("mode") == _MANUAL_MODE:
        raise refusal("E767", f"fixture '{node.id}' is manual and is not run, so it takes no binding; a person attests it")
    return node


def targets_of(verifier: Node, graph: Graph) -> tuple[str, ...]:
    """The ids the verifier can prove, in link order: a fixture's ``verifies``; a job's ``realises`` and the NFRs it ``verifies``; a rule has none."""
    fields = _TARGET_FIELDS[verifier.kind]
    found = dict.fromkeys(graph.canonical_id(link.target) for link in verifier.links if link.field in fields)
    return tuple(found)


def proved_ids(binding: Binding, graph: Graph) -> tuple[str, ...]:
    """The ids *binding* proves: those it states, else every id its verifier can prove (a record that states none, as the worked example's).

    The one reading of an empty ``proves``: the bind check for a second binding (E333), the record lint and the proof read it here.
    """
    verifier = graph.find(binding.verifier)
    return binding.proves or (targets_of(verifier, graph) if verifier is not None else ())


def _proved(request: BindRequest, verifier: Node, graph: Graph) -> tuple[str, ...]:
    """The nodes the binding proves: the request's (each must be a target of the verifier), else every target."""
    targets = targets_of(verifier, graph)
    if not request.proves:
        return targets
    wanted = tuple(dict.fromkeys(graph.canonical_id(node_id) for node_id in request.proves))
    outside = [node_id for node_id in request.proves if graph.canonical_id(node_id) not in targets]
    if outside:
        listed = ", ".join(targets) if targets else "none"
        raise refusal("E331", f"'{', '.join(outside)}' is not proved by '{verifier.id}' (it proves: {listed}); give --proves ids from that list")
    return wanted


def _node_stages(proves: tuple[str, ...], verifier: Node, graph: Graph) -> dict[str, str]:
    """The stage each proved node needs; E334 when an environment among them is not a stage."""
    via_job = verifier if verifier.kind == JOB else None
    try:
        return {node_id: required_stage(node, graph, via_job) for node_id in proves if (node := graph.find(node_id)) is not None}
    except UnknownStageForEnvironment as exc:
        raise refusal("E334", f"environment '{exc.environment}' is not a stage; name it dev, ci, staging or prod") from exc


def _refuse_mixed_stages(verifier: Node, stages: Mapping[str, str]) -> None:
    groups: dict[str, list[str]] = {}
    for node_id, stage in stages.items():
        groups.setdefault(stage, []).append(node_id)
    if len(groups) > 1:
        listed = "; ".join(f"{stage}: {', '.join(ids)}" for stage, ids in groups.items())
        raise refusal("E767", f"'{verifier.id}' proves nodes of different stages ({listed}); one binding per stage: run `verify bind` again with `--proves ...`")


def computed_stage(proves: tuple[str, ...], verifier: Node, graph: Graph) -> str:
    """The highest stage the proved nodes need; a rule that proves nothing needs the stage of the rule itself."""
    if not proves and verifier.kind == RULE:
        return required_stage(verifier, graph)
    return binding_required_stage(proves, graph, verifier if verifier.kind == JOB else None)


def _stage_of(request: BindRequest, proves: tuple[str, ...], stages: Mapping[str, str], verifier: Node, graph: Graph) -> str:
    computed = computed_stage(proves, verifier, graph)
    if request.stage is not None and request.stage != computed:
        needing = [node_id for node_id, stage in stages.items() if stage == computed]
        why = f" ({', '.join(needing)} need{'s' if len(needing) == 1 else ''} it)" if needing else ""
        raise refusal("E330", f"stage '{request.stage}' does not match the stage '{computed}' this binding needs{why}; omit --stage or give --stage {computed}")
    return computed


def _checked_guard(guard: str | None) -> tuple[str, ...]:
    """The notes about a valid *guard*; E332 when it is missing or not a regular expression."""
    try:
        pattern = compile_guard(guard)
    except GuardError as exc:
        raise refusal("E332", str(exc)) from exc
    return (EMPTY_GUARD_NOTE,) if pattern.search("") else ()


def _suffix(verifier: Node) -> str:
    return next((verifier.id.removeprefix(prefix) for prefix in _ID_PREFIXES if verifier.id.startswith(prefix)), verifier.id)


def _own_bindings(verifier: Node, graph: Graph) -> list[Binding]:
    return [binding_of(node, graph) for node in bindings_of(verifier, graph)]


def _owned(existing: Binding | None, stage: str, proves: tuple[str, ...]) -> bool:
    """Whether the existing binding is the one this request updates: the same stage, and the same proved nodes (or none stated)."""
    return existing is not None and existing.stage == stage and (set(existing.proves) == set(proves) or not existing.proves)


def _explicit_id(record_id: str, verifier: Node, graph: Graph) -> str:
    if not _RECORD_ID.match(record_id):
        raise refusal("E767", f"'{record_id}' is not a binding id: ver- followed by a kebab-case name")
    holder = graph.find(record_id)
    if holder is not None and (holder.kind != BINDING_KIND or binding_of(holder, graph).verifier != verifier.id):
        raise refusal("E767", f"'{record_id}' is already the id of a node of kind {holder.kind}; give another --id")
    return record_id


def _record_id(request: BindRequest, verifier: Node, stage: str, proves: tuple[str, ...], graph: Graph) -> str:
    """The id of the record: ``--id``, else ``ver-<verifier suffix>`` (with ``-<stage>`` when that is another binding's), else the first free id."""
    if request.record_id:
        return _explicit_id(request.record_id, verifier, graph)
    own = {binding.id: binding for binding in _own_bindings(verifier, graph)}
    taken = set(graph.by_id) | set(graph.alias_index)
    suffix = _suffix(verifier)
    for candidate in (mint_slug(suffix, (), prefix=BINDING_PREFIX), mint_slug(f"{suffix}-{stage}", (), prefix=BINDING_PREFIX)):
        if candidate not in taken or _owned(own.get(candidate), stage, proves):
            return candidate
    return mint_slug(f"{suffix}-{stage}", taken, prefix=BINDING_PREFIX)


def _refuse_duplicates(verifier: Node, record_id: str, proves: tuple[str, ...], graph: Graph) -> None:
    """E333 when another binding of the verifier already proves one of *proves*."""
    for other in _own_bindings(verifier, graph):
        shared = [node_id for node_id in proves if node_id in proved_ids(other, graph)]
        if other.id != record_id and shared:
            raise refusal("E333", f"'{', '.join(shared)}' is already proved by '{other.id}' for '{verifier.id}'; change that binding with `--id {other.id}` or leave the node out of --proves")


def plan_bind(graph: Graph, request: BindRequest) -> BindPlan:
    """The record ``verify bind`` writes for *request*, or the refusal.

    Raises:
        FindingError: E706 for an unknown verifier; E767 for a verifier that cannot be bound (not a fixture, job or rule,
            ``not_applicable``, a manual fixture), mixed stages without ``--proves``, or a record id that is taken; E331
            for a ``--proves`` id the verifier does not prove; E330 for a ``--stage`` other than the computed one; E332
            for a missing or invalid guard; E333 for a node another binding of the verifier already proves; E334 for an
            environment that is not a stage.
    """
    verifier = _verifier_of(graph, request.verifier)
    proves = _proved(request, verifier, graph)
    stages = _node_stages(proves, verifier, graph)
    if not request.proves:
        _refuse_mixed_stages(verifier, stages)
    stage = _stage_of(request, proves, stages, verifier, graph)
    notes = _checked_guard(request.guard)
    record_id = _record_id(request, verifier, stage, proves, graph)
    _refuse_duplicates(verifier, record_id, proves, graph)
    item: dict[str, Any] = {"verification_id": record_id, "verifies": [verifier.id]}
    if proves:
        item["proves"] = list(proves)
    item.update({"stage": stage, "commands": list(request.commands), "output_guard": request.guard})
    return BindPlan(item, record_id, verifier.id, stage, proves, tuple(stages.items()), record_id in graph.by_id, notes)


def apply_bind(graph: Graph, spec_root: str, repo_root: str, request: BindRequest) -> BindResult:
    """Plan *request* against *graph* and write the record; the caller holds the write lock and built *graph* under it.

    Raises:
        FindingError: as ``plan_bind``, and E774 when the record would break its schema (nothing is written).
    """
    plan = plan_bind(graph, request)
    return BindResult(plan, write_binding(records_folder(spec_root), repo_root, plan.item))
