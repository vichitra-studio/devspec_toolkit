"""The executed reading of a plan item: which of its actions are carried out, and what an at-deploy action still owes.

A plan item is executed when every action that is not marked ``at_deploy`` is satisfied:

* an action that names a verifier at stage ``dev`` or ``ci`` is satisfied by valid passing evidence for that verifier on the
  current code tree (the close mode of ``proof.verifier_proof``);
* an action that names a verifier at stage ``staging`` or ``prod`` is left to the release gate and holds nothing up here (its
  proof is an evidence record of ``verify run`` at that stage, so no record could satisfy it);
* any other action needs a record whose latest entry has outcome ``done`` and is not stale.

An action *names a verifier* when its ``command`` equals, after trimming and collapsing whitespace, a command of a binding
(a verification record) of a verifier that a criterion the item ``realises`` lists in ``verified_by``.  It is computed on
read; nothing is stored on the action.  A record is *stale* when the hash of the criteria its item realises, taken from the
trace lock, differs from the one the record stored; staleness is computed, never stored, and is not evaluated for the plan of
a closed milestone or when there is no trace lock.

Nothing here writes a file.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..core.loaders import read_json_object
from ..core.plan_files import find_plan
from ..graph.contract import item_of
from ..graph.model import Graph, Node, collapse_whitespace
from ..graph.names import ABOUT, EXECUTION_RECORD, PAUSED_DISPOSITIONS, PLAN_ITEM, REALISES, VERIFIED_BY, link_targets
from ..graph.queries import task_disposition, task_of
from ..graph.stages import is_retired_binding, bindings_of
from ..proof.proof import CLOSE_IGNORED_STAGES, PROVEN, verifier_proof
from ..proof.validity import ProofContext
from ..trace.hashing import HASH_PREFIX
from ..trace.lockfile import Lock, lock_path, read_lock
from ..verify.records import Binding, binding_of, deploy_records
from . import frozen

CLOSE_CAP = "dev"
DONE = "done"

AT_DEPLOY = "at-deploy"
LATER_STAGE = "later-stage"
PROVEN_BY_EVIDENCE = "proven"
NEEDS_EVIDENCE = "needs-evidence"
RECORDED = "recorded"
NO_RECORD = "no-record"
STALE = "stale"
NOT_DONE = "not-done"
SATISFIED = frozenset({AT_DEPLOY, LATER_STAGE, PROVEN_BY_EVIDENCE, RECORDED})
"""The states of an action that hold the item up: every other state is something the item still owes."""


@dataclass(frozen=True)
class NamedBinding:
    """A binding whose command an action repeats: the binding, its verifier and the binding's stage."""

    binding: str
    verifier: str
    stage: str


@dataclass(frozen=True)
class ExecutionRecord:
    """An execution record as the graph holds it: its id, the item and action it is about, the outcome and the stored realises hash."""

    record_id: str
    item: str
    action: str
    outcome: str
    realises_hash: str | None
    file: str


@dataclass(frozen=True)
class ActionReading:
    """How one action stands: its id (``None`` when it has none), its ``state`` and one line saying why."""

    action: str | None
    state: str
    detail: str

    @property
    def satisfied(self) -> bool:
        """Whether the action holds the item up no longer."""
        return self.state in SATISFIED


@dataclass(frozen=True)
class ItemReading:
    """The executed reading of one plan item: one ``ActionReading`` per action, in plan order."""

    item: str
    actions: tuple[ActionReading, ...]

    @property
    def executed(self) -> bool:
        """Whether every action is satisfied (an item with no action is executed)."""
        return all(action.satisfied for action in self.actions)

    @property
    def owed(self) -> tuple[ActionReading, ...]:
        """The actions that still hold the item up."""
        return tuple(action for action in self.actions if not action.satisfied)


def actions_of(item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The actions of the plan item *item* (a parsed checklist entry), as the mappings they are; none when the shape is not there."""
    implementation = item.get("implementation")
    actions = implementation.get("actions") if isinstance(implementation, Mapping) else None
    return [action for action in actions if isinstance(action, Mapping)] if isinstance(actions, list) else []


def at_deploy_of(action: Mapping[str, Any]) -> tuple[str, ...]:
    """The stages the action is marked ``at_deploy`` for; empty when it is not."""
    stages = action.get("at_deploy")
    return tuple(stage for stage in stages if isinstance(stage, str)) if isinstance(stages, list) else ()


def at_deploy_state(action: Mapping[str, Any]) -> str:
    """How the action is marked, for a refusal: ``marked at_deploy for staging, prod`` or ``not marked at_deploy``."""
    marked = at_deploy_of(action)
    return f"marked at_deploy for {', '.join(marked)}" if marked else "not marked at_deploy"


def plan_item_node(graph: Graph, item_id: str) -> Node | None:
    """The plan item *item_id* (an alias resolves to the current id); ``None`` when no node has the id or it is not a plan item.

    The one lookup of "which plan item is this" for ``plan record`` and ``verify attest``; each builds its own refusal.
    """
    node = graph.find(item_id)
    return node if node is not None and node.kind == PLAN_ITEM else None


def actions_with_id(graph: Graph, item: Node, action_id: str) -> list[Mapping[str, Any]]:
    """The actions of *item* whose ``id`` is *action_id*: one for an address that names an action, none or several otherwise."""
    return [action for action in actions_of(item_of(graph, item) or {}) if action.get("id") == action_id]


def _criterion_bindings(graph: Graph, criterion: str) -> list[NamedBinding]:
    """The bindings of the verifiers the task criterion *criterion* lists in ``verified_by``, retired ones left out."""
    node = graph.find(criterion)
    verifiers = [graph.find(name) for name in link_targets(graph, node, VERIFIED_BY)] if node is not None else []
    named: list[NamedBinding] = []
    for verifier in (found for found in verifiers if found is not None):
        for record in bindings_of(verifier, graph):
            if not is_retired_binding(record, graph):
                binding = binding_of(record, graph)
                named.append(NamedBinding(binding.id, verifier.id, binding.stage))
    return named


def item_bindings(graph: Graph, item: Node) -> list[NamedBinding]:
    """The bindings of every verifier that a criterion *item* realises lists in ``verified_by``, retired ones left out, in link order, each once."""
    found: dict[str, NamedBinding] = {}
    for criterion in link_targets(graph, item, REALISES):
        for named in _criterion_bindings(graph, criterion):
            found.setdefault(named.binding, named)
    return list(found.values())


def _commands(graph: Graph, bindings: Iterable[NamedBinding]) -> dict[str, list[NamedBinding]]:
    """The normalised commands of *bindings*, each with the bindings that carry it."""
    by_command: dict[str, list[NamedBinding]] = {}
    for named in bindings:
        node = graph.find(named.binding)
        stored: Binding | None = binding_of(node, graph) if node is not None else None
        for command in stored.commands if stored is not None else ():
            by_command.setdefault(collapse_whitespace(command), []).append(named)
    return by_command


def naming_bindings(graph: Graph, item: Node, action: Mapping[str, Any]) -> list[NamedBinding]:
    """The bindings *action* of the plan item *item* names: those with a command equal to the action's ``command`` after trimming and collapsing whitespace.

    Empty for an action with no ``command``, and for a command that is not repeated exactly (another quoting, other arguments).
    """
    command = action.get("command")
    if not isinstance(command, str) or not command.strip():
        return []
    return _commands(graph, item_bindings(graph, item)).get(collapse_whitespace(command), [])


def realises_hash(lock: Lock, item_id: str) -> str:
    """``sha256:<hex>`` of the sorted ``(target, content hash)`` pairs of the lock entries whose source is the plan item *item_id* and whose field is ``realises``."""
    pairs = sorted([entry.target, entry.content_hash] for entry in lock.entries if entry.source == item_id and entry.field == REALISES)
    return HASH_PREFIX + hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode("utf-8")).hexdigest()


def lock_if_present(spec_root: str) -> Lock | None:
    """The trace lock of *spec_root*, or ``None`` when the folder has no lock file (every host before the graph model).

    Raises:
        LockError: E760 when the lock file exists and cannot be read.
    """
    return read_lock(spec_root) if os.path.isfile(lock_path(spec_root)) else None


def execution_records(graph: Graph) -> list[ExecutionRecord]:
    """Every execution record of *graph*, in graph order (the order they were appended in a plan file)."""
    records: list[ExecutionRecord] = []
    for node in graph.by_kind.get(EXECUTION_RECORD, ()):
        content = item_of(graph, node) or {}
        targets = link_targets(graph, node, ABOUT)
        action, outcome, stored = content.get("action"), content.get("outcome"), content.get("realises_hash")
        if targets and isinstance(action, str) and isinstance(outcome, str):
            records.append(ExecutionRecord(node.id, targets[0], action, outcome, stored if isinstance(stored, str) else None, node.file))
    return records


def is_stale(record: ExecutionRecord, lock: Lock | None, *, frozen_plan: bool) -> bool:
    """Whether *record* is stale: its stored hash differs from the hash of what its item realises now.

    Never stale for the plan of a closed milestone (*frozen_plan*), with no lock, or when the record stored no hash.
    """
    if lock is None or frozen_plan or record.realises_hash is None:
        return False
    return record.realises_hash != realises_hash(lock, record.item)


def plan_is_frozen(spec_root: str, item: Node) -> bool:
    """Whether the plan holding the plan item *item* belongs to a closed milestone.

    Raises:
        FindingError: E801 for an anchor row with an unknown status.
    """
    return item.milestone is not None and frozen.is_frozen(spec_root, item.milestone)


def latest_record(records: Sequence[ExecutionRecord], item_id: str, action_id: str) -> ExecutionRecord | None:
    """The last of *records* that is about *action_id* of *item_id*: the latest entry for that action wins."""
    about_action = [record for record in records if record.item == item_id and record.action == action_id]
    return about_action[-1] if about_action else None


def _recorded_state(record: ExecutionRecord | None, stale: bool) -> ActionReading:
    if record is None:
        return ActionReading(None, NO_RECORD, "no record: run `specdev plan record` for it")
    if stale:
        return ActionReading(None, STALE, f"{record.record_id} is stale: what the item realises changed since; carry the action out again and record it")
    if record.outcome != DONE:
        return ActionReading(None, NOT_DONE, f"{record.record_id} says {record.outcome}")
    return ActionReading(None, RECORDED, f"{record.record_id} says done")


def _verifier_state(named: NamedBinding, graph: Graph, ctx: ProofContext) -> ActionReading:
    if named.stage in CLOSE_IGNORED_STAGES:
        return ActionReading(None, LATER_STAGE, f"binding {named.binding} is at stage {named.stage}: proof owed at that stage, held by the release gate")
    status = verifier_proof(graph, ctx, named.verifier, CLOSE_CAP, treat_ci_as_dev=True).status
    if status == PROVEN:
        return ActionReading(None, PROVEN_BY_EVIDENCE, f"binding {named.binding} has valid passing evidence")
    return ActionReading(None, NEEDS_EVIDENCE, f"binding {named.binding} has no valid passing evidence ({status}): run `specdev verify run {named.binding}`")


def _reading_of(action: Mapping[str, Any], item: Node, graph: Graph, ctx: ProofContext, records: Sequence[ExecutionRecord], lock: Lock | None, frozen_plan: bool) -> ActionReading:
    action_id = action.get("id") if isinstance(action.get("id"), str) else None
    if at_deploy_of(action):
        reading = ActionReading(None, AT_DEPLOY, f"marked at_deploy for {', '.join(at_deploy_of(action))}: proof is a deploy record, not held up here")
    elif named := naming_bindings(graph, item, action):
        reading = _verifier_state(named[0], graph, ctx)
    else:
        record = latest_record(records, item.id, action_id) if action_id else None
        reading = _recorded_state(record, record is not None and is_stale(record, lock, frozen_plan=frozen_plan))
    return ActionReading(action_id, reading.state, reading.detail)


def item_reading(graph: Graph, ctx: ProofContext, item_id: str, lock: Lock | None) -> ItemReading:
    """The executed reading of the plan item *item_id*: where each of its actions stands.

    *lock* is the trace lock (``lock_if_present``; ``None`` skips staleness).  The reading of an action that names a
    verifier is the close mode of ``verifier_proof``.

    Raises:
        KeyError: no plan item has the id *item_id*.
        FindingError: E801 for an anchor row with an unknown status; E520 when the host declarations cannot be read.
        GitViewError: E708 when git fails.
    """
    item = graph.find(item_id)
    content = item_of(graph, item) if item is not None else None
    if item is None or item.kind != PLAN_ITEM or content is None:
        raise KeyError(item_id)
    records = execution_records(graph)
    frozen_plan = plan_is_frozen(ctx.spec_root, item)
    return ItemReading(item.id, tuple(_reading_of(action, item, graph, ctx, records, lock, frozen_plan) for action in actions_of(content)))


def realises_only_excluded(graph: Graph, item: Node) -> bool:
    """Whether *item* realises criteria and every one of them belongs to a roadmap task that is deferred or wont_do."""
    criteria = link_targets(graph, item, REALISES)
    if not criteria:
        return False
    dispositions = []
    for criterion in criteria:
        task = task_of(graph, criterion)
        dispositions.append(task_disposition(graph, task)[0] if task is not None else None)
    return all(value in PAUSED_DISPOSITIONS for value in dispositions)


def at_deploy_recorded(spec_dir: str, item_id: str, action_id: str, env: str) -> bool:
    """Whether a deploy job recorded the ``at_deploy`` action *action_id* of *item_id* at *env* as done: the latest ``dep-`` record for that triple has outcome ``done``.

    Reads only the ``dep-`` records of ``extras/verification/``; a record finds its milestone by its own ``milestone`` field,
    so no plan is read.
    """
    outcomes = [
        record.get("outcome")
        for record in deploy_records(spec_dir)
        if record.get("about") == [item_id] and record.get("action") == action_id and record.get("env") == env
    ]
    return bool(outcomes) and outcomes[-1] == DONE


def at_deploy_required(spec_dir: str, milestone_ids: Iterable[str]) -> list[tuple[str, str, str]]:
    """The ``(item id, action id, env)`` triples the plans of *milestone_ids* mark ``at_deploy``, in plan order; a milestone with no plan gives none.

    An action with no id cannot be addressed and is left out.
    """
    triples: list[tuple[str, str, str]] = []
    for milestone in milestone_ids:
        plan = find_plan(spec_dir, milestone)
        document = read_json_object(plan) if plan is not None else None
        checklist = ((document or {}).get("plan") or {}).get("spec_alignment", {}).get("checklist")
        for item in checklist if isinstance(checklist, list) else ():
            for action in actions_of(item) if isinstance(item, Mapping) else ():
                if isinstance(item.get("id"), str) and isinstance(action.get("id"), str):
                    triples.extend((item["id"], action["id"], env) for env in at_deploy_of(action))
    return triples
