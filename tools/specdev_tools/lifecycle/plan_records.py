"""``specdev plan record``: write execution records into a plan, prune the orphans, write at-deploy records; and the ``plan-records`` check.

An execution record states that one action of one plan item was carried out, failed or is blocked.  It is appended to
``execution.records[]`` of the plan file that holds the item.  A record is a record-role node: its ``about`` link must
resolve, and it has no lock entry.  Which items count as executed is computed from the records and the proof of the item's
verifiers (``executed.py``); nothing is stored on the item.

An action that names a verifier gets no record (E822): its proof is the evidence of ``verify run``.  The plan of a closed
milestone is frozen (E820).  An at-deploy record is a file of its own, ``extras/verification/dep-<NNNN>.json``, so it works
on a closed milestone and leaves the plan as it is.

The ``plan-records`` check reports W825 (a record is stale) and W826 (an item realises only deferred or wont_do tasks).
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.errors import FindingError, SpecError, make_error, refusal
from ..core.json_utils import check_edit, delete_text, insert_text, json_write_atomic, nearest_ids
from ..graph.contract import item_of
from ..graph.model import Graph, Node
from ..graph.names import AT_DEPLOY_RECORD, EXECUTION_RECORD, PLAN_ITEM
from ..trace.lockfile import Lock
from ..trace.records import orphan_records
from ..trace.writing import locked_graph
from ..verify.code_tree import code_tree_for_host
from ..verify.records import records_folder, write_at_deploy
from . import executed, frozen, plans
from .records import git_author, mint_id, now_utc

ADDRESS = re.compile(r"^(?P<item>[^/\s]+)/(?P<action>\S+)$")
RECORDS_PATH = ".execution.records"
NEAREST = 3


@dataclass(frozen=True)
class Address:
    """The address of an action: the plan item id and the action id, written ``<item>/<action>``."""

    item: str
    action: str

    def __str__(self) -> str:
        return f"{self.item}/{self.action}"


def parse_address(text: str) -> Address | None:
    """The ``Address`` written as ``<plan item id>/<action id>``; ``None`` when *text* is not of that form."""
    matched = ADDRESS.match(text)
    return Address(matched["item"], matched["action"]) if matched else None


@dataclass(frozen=True)
class RecordResult:
    """What ``plan record`` wrote: the record, the plan file it went into and the size of that file before and after.

    ``notes`` are lines the command prints beside the result (the action's command is close to a binding's, but not equal).
    """

    record: dict[str, Any]
    plan: str
    bytes_before: int
    bytes_after: int
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeployResult:
    """What ``plan record --at-deploy`` wrote: the record and the record file; the plan is not touched."""

    record: dict[str, Any]
    file: str


@dataclass(frozen=True)
class PruneResult:
    """What ``plan record --prune`` removed from the plan of a milestone, and the size of the plan before and after."""

    plan: str
    removed: tuple[str, ...]
    bytes_before: int
    bytes_after: int


@dataclass(frozen=True)
class _Target:
    """A plan item and one of its actions, as the plan holds them."""

    item: Node
    action: Mapping[str, Any]
    action_id: str


def refuse_if_frozen(spec_root: str, milestone: str | None, plan_file: str) -> None:
    """Raise E820 when *milestone*, the one the plan file *plan_file* names, is closed; a plan with no milestone is never frozen.

    Raises:
        FindingError: E820 for a closed milestone; E801 for an anchor row with an unknown status.
    """
    if milestone is not None and frozen.is_frozen(spec_root, milestone):
        raise refusal(
            "E820",
            f"plan {plan_file} belongs to milestone {milestone}, which is closed: a closed plan is frozen and changes only "
            "through a recorded migration, so no record can be written to it or removed from it",
        )


def _unknown_item(graph: Graph, item_id: str) -> FindingError:
    known = [node.id for node in graph.by_kind.get(PLAN_ITEM, ())]
    nearest = ", ".join(entry["id"] for entry in nearest_ids(item_id, known, NEAREST))
    hint = f"the nearest plan items are {nearest}" if nearest else "no plan holds an item"
    return refusal("E821", f"no plan item {item_id}; {hint}")


def _plan_item(graph: Graph, item_id: str) -> Node:
    node = graph.find(item_id)
    if node is None or node.kind != PLAN_ITEM:
        raise _unknown_item(graph, item_id)
    return node


def _action_of(graph: Graph, item: Node, action_id: str) -> Mapping[str, Any]:
    actions = executed.actions_of(item_of(graph, item) or {})
    ids = [name for action in actions if isinstance(name := action.get("id"), str)]
    found = [action for action in actions if action.get("id") == action_id]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise refusal("E821", f"{item.id} has {len(found)} actions with the id {action_id}; give each action its own id")
    if not ids:
        raise refusal(
            "E821",
            f"{item.id} has no action {action_id}: its actions carry no id; give the first one with "
            f"`specdev json patch --id {item.id} '.implementation.actions[0].id' '\"a01\"'`, and so on for the others",
        )
    raise refusal("E821", f"{item.id} has no action {action_id}; its actions are {', '.join(ids)}")


def _resolve(graph: Graph, address: Address) -> _Target:
    item = _plan_item(graph, address.item)
    return _Target(item, _action_of(graph, item, address.action), address.action)


def _refuse_naming(graph: Graph, target: _Target) -> None:
    named = executed.naming_bindings(graph, target.item, target.action)
    if named:
        first = named[0]
        raise refusal(
            "E822",
            f"action {target.action_id} of {target.item.id} names a verifier: its command is a command of binding {first.binding} "
            f"(verifier {first.verifier}, stage {first.stage}), so its proof is the evidence of `specdev verify run {first.binding}`, not a record",
        )


def _close_command_note(graph: Graph, target: _Target) -> tuple[str, ...]:
    """The note for an action whose command is not a binding's command although the item has bindings: it is recorded as a plain action."""
    command = target.action.get("command")
    bindings = executed.item_bindings(graph, target.item)
    if not isinstance(command, str) or not bindings:
        return ()
    ids = ", ".join(named.binding for named in bindings)
    return (
        f"note: the command of this action is not a command of {ids} (compared after trimming and collapsing whitespace), "
        "so it does not name a verifier and is recorded as a plain action",
    )


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_text(path: str, content: str, new_content: str, repo_root: str) -> None:
    """Replace the plan file *path* with *new_content* after the differential schema check: it adds no violation to *content*."""
    check_edit(path, content, new_content, repo_root)
    json_write_atomic(path, new_content)


def _record_of(graph: Graph, spec_root: str, target: _Target, outcome: str, note: str | None, git_root: str) -> dict[str, Any]:
    lock = executed.lock_if_present(spec_root)
    taken = [node.id for node in graph.by_kind.get(EXECUTION_RECORD, ())]
    record: dict[str, Any] = {
        "record_id": mint_id("rec", taken),
        "about": [target.item.id],
        "action": target.action_id,
        "outcome": outcome,
    }
    if note:
        record["note"] = note
    record.update(
        realises_hash=executed.realises_hash(lock, target.item.id) if lock is not None else None,
        recorded_at=now_utc(),
        git_author=git_author(git_root).as_record(),
    )
    return record


def record_action(spec_root: str, repo_root: str, git_root: str, address: Address, outcome: str, note: str | None = None) -> RecordResult:
    """Append an execution record for *address* with *outcome* (``done``, ``failed`` or ``blocked``) to the plan holding the item.

    Takes the write lock of *spec_root*.  The record gets the next ``rec-`` id, the git author, the time and the hash of
    what the item realises now (``None`` when there is no trace lock).  No lock entry is written.

    Raises:
        FindingError: E821 for an unknown item, or an unknown or ambiguous action; E820 for a closed milestone; E822 for an
            action that names a verifier; E767 when git names no author; E769 when another write holds the lock.
        JsonUtilsError: the record would add a schema violation to the plan.
    """
    with locked_graph(spec_root, repo_root, "plan record") as graph:
        item = _plan_item(graph, address.item)
        refuse_if_frozen(spec_root, item.milestone, item.file)
        target = _Target(item, _action_of(graph, item, address.action), address.action)
        _refuse_naming(graph, target)
        record = _record_of(graph, spec_root, target, outcome, note, git_root)
        path = os.path.join(spec_root, item.file)
        content, before = _read(path), os.path.getsize(path)
        _write_text(path, content, insert_text(content, RECORDS_PATH, json.dumps(record), create=True), repo_root)
        return RecordResult(record, item.file, before, os.path.getsize(path), _close_command_note(graph, target))


def record_at_deploy(spec_root: str, repo_root: str, git_root: str, address: Address, env: str, outcome: str, tag: str | None = None) -> DeployResult:
    """Write the at-deploy record of the action *address* at *env* (``staging`` or ``prod``) as ``extras/verification/dep-<NNNN>.json``.

    The action must be marked ``at_deploy`` for *env*.  The plan is not written, so this works for a closed milestone.  The
    author is the git author, or ``ci`` with an empty email when git names none.

    Raises:
        FindingError: E821 for an unknown item or action, or an action not marked ``at_deploy`` for *env*; E803 when the plan
            has no ``milestone`` key; E774 when the record would break its schema; E769 when another write holds the lock.
    """
    with locked_graph(spec_root, repo_root, "plan record --at-deploy") as graph:
        target = _resolve(graph, address)
        marked = executed.at_deploy_of(target.action)
        if env not in marked:
            now = f"marked at_deploy for {', '.join(marked)}" if marked else "not marked at_deploy"
            raise refusal("E821", f"action {address.action} of {address.item} is {now}, not for {env}; an at-deploy record names a stage its action is marked for")
        if target.item.milestone is None:
            raise FindingError(make_error(
                "E803", f"plan {target.item.file} has no `milestone` key: run `specdev align`", subcode="MILESTONE_KEY_MISSING", node_id=target.item.id,
            ))
        record: dict[str, Any] = {
            "deploy_id": mint_id("dep", [node.id for node in graph.by_kind.get(AT_DEPLOY_RECORD, ())]),
            "about": [target.item.id],
            "milestone": target.item.milestone,
            "action": address.action,
            "env": env,
            **({"tag": tag} if tag else {}),
            "tree": code_tree_for_host(git_root, spec_root),
            "outcome": outcome,
            "recorded_at": now_utc(),
            "git_author": git_author(git_root, ci_fallback=True).as_record(),
        }
        name = write_at_deploy(records_folder(spec_root), repo_root, record)
        return DeployResult(record, os.path.join(os.path.relpath(records_folder(spec_root), spec_root), name))


def _orphans(graph: Graph, plan_file: str) -> list[str]:
    """The ids of the execution records of *plan_file* whose item is gone, or whose action is gone from an item that is not."""
    ids = [node.id for node in orphan_records(graph) if node.kind == EXECUTION_RECORD and node.file == plan_file]
    for record in executed.execution_records(graph):
        if record.file != plan_file or record.record_id in ids:
            continue
        item = graph.find(record.item)
        content = item_of(graph, item) if item is not None else None
        if item is not None and item.kind == PLAN_ITEM and record.action not in {action.get("id") for action in executed.actions_of(content or {})}:
            ids.append(record.record_id)
    return ids


def prune_records(spec_root: str, repo_root: str, milestone_id: str) -> PruneResult:
    """Remove from the plan of *milestone_id* the execution records whose item or action no longer exists; nothing else changes.

    Raises:
        FindingError: E803 when no plan names the milestone; E820 for a closed milestone; E769 when another write holds the lock.
    """
    plan = plans.require_plan(spec_root, milestone_id)
    rel = os.path.relpath(plan, spec_root)
    with locked_graph(spec_root, repo_root, "plan record --prune") as graph:
        refuse_if_frozen(spec_root, milestone_id, rel)
        orphans = _orphans(graph, rel)
        before = os.path.getsize(plan)
        if orphans:
            content = _read(str(plan))
            chosen = " or ".join(f'.record_id == "{record_id}"' for record_id in orphans)
            _write_text(str(plan), content, delete_text(content, f".execution.records[] | select({chosen})"), repo_root)
        return PruneResult(rel, tuple(orphans), before, os.path.getsize(plan))


def _frozen_milestones(spec_root: str, milestones: set[str | None]) -> tuple[set[str], list[SpecError]]:
    """The milestones of *milestones* that are closed, and an E801 finding for each whose anchor row has an unknown status."""
    closed: set[str] = set()
    findings: list[SpecError] = []
    for milestone in sorted(m for m in milestones if m is not None):
        try:
            if frozen.is_frozen(spec_root, milestone):
                closed.add(milestone)
        except FindingError as error:
            findings.append(error.error)
    return closed, findings


def check_plan_records(graph: Graph, lock: Lock | None, spec_root: str) -> list[SpecError]:
    """The findings of the ``plan-records`` check: W825 for an action whose latest record is stale, W826 for an item that realises only deferred or wont_do tasks.

    Neither is reported for the plan of a closed milestone.  W825 needs the trace lock (*lock*); with ``None`` it is not
    evaluated.  An anchor row with an unknown status comes back as its E801 finding, once.
    """
    items = list(graph.by_kind.get(PLAN_ITEM, ()))
    closed, findings = _frozen_milestones(spec_root, {item.milestone for item in items})
    records = executed.execution_records(graph)
    latest = {(record.item, record.action): record for record in records}
    for (item_id, action_id), record in latest.items():
        node = graph.find(item_id)
        if node is not None and executed.is_stale(record, lock, frozen_plan=node.milestone in closed):
            findings.append(make_error(
                "W825",
                f"execution record {record.record_id} (action {action_id} of {item_id}) is stale: what the item realises changed since it was written; "
                f"carry the action out again and run `specdev plan record {item_id}/{action_id} --outcome done`",
                file=record.file, node_id=record.record_id,
            ))
    for item in items:
        if item.milestone not in closed and executed.realises_only_excluded(graph, item):
            findings.append(make_error(
                "W826",
                f"plan item {item.id} realises only criteria of tasks that are deferred or wont_do, so the close gate ignores it; drop it when 16a re-plans",
                file=item.file, jq_path=item.jq_path or None, node_id=item.id,
            ))
    return findings
