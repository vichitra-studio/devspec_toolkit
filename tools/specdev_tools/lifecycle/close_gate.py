"""The close gate: whether a milestone may be closed, answered as a list of findings and nothing written.

``check_close_gate`` runs the seven checks of the design's close row, in this order, and reports every finding of every check
(a first failure does not hide the others):

1. every task criterion in play has a plan item that ``realises`` it (E810) and is proven (E811);
2. every plan item that realises a criterion in play is executed (E812);
3. the review block of the plan says ``verified`` (E813);
4. the plan holds no open item (E632);
5. no suspect link (E763) and no link without a lock entry (E761) is on the milestone's chain;
6. the scaffold rows of the APIs the criteria refine are tracked files (E746);
7. a sign-off record exists for the milestone (E814).

A task whose ``disposition`` is ``deferred`` or ``wont_do`` and a criterion whose lifecycle is ``not_applicable`` are out of
play; the deferred tasks are listed with their reason.  A plan item that realises only criteria out of play is ignored and
reported as W826.  A milestone whose close record is a legacy close (``signed_off_by`` ``legacy-migration``) is not re-checked.

"Proven" is the close mode of ``proof.proof`` (cap ``dev``, ``ci`` counted as ``dev``, staging and production bindings
ignored); "executed" is ``lifecycle.executed``.  Both are called, never re-implemented.  The open-item and the scaffold
checks live in ``validation``, which this package may not import: the caller passes them in (``open_items``, ``scaffold``).

``verify_close_record`` is the existence check the release gate runs on the close record of an anchor row.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from ..core.errors import FindingError, SpecError, make_error
from ..core.loaders import read_json_object
from ..core.step_paths import PLAN_DIR_NAME
from ..graph.gitview import read_seed_texts
from ..graph.model import NOT_APPLICABLE, Graph, Node
from ..graph.names import API, PLAN_ITEM, PAUSED_DISPOSITIONS, REALISES, ROW_DONE, TASK, TASK_CRITERION, link_targets
from ..graph.ownership import CLOSE_OWNER
from ..graph.queries import milestone_of, task_disposition
from ..graph.trace import trace_node
from ..proof.proof import NOT_REQUIRED, PENDING_STAGE, PROVEN, STAGE_UNKNOWN, ProofResult, proof, proof_errors
from ..proof.validity import ProofContext
from ..trace.lockfile import Lock
from ..verify.records import signoff_records
from . import anchor_store, chain, executed, plan_records, plans

VERIFIED = "verified"
_PASSING = frozenset({PROVEN, PENDING_STAGE, NOT_REQUIRED})
"""The close-mode statuses that do not stop a close.  A binding never gives ``PENDING_STAGE`` here (the close mode ignores staging and
prod bindings: ``NOT_REQUIRED``); a person's attestation of an obligation that needs a stage above ``dev`` can, so the status stays."""


class ScaffoldReading(Protocol):
    """What the scaffold scan of ``validation.graph_checks.scaffold`` reports: ``findings``, ``notes`` and ``skip_reason`` (``None`` when it ran)."""

    @property
    def findings(self) -> list[SpecError]: ...

    @property
    def notes(self) -> list[str]: ...

    @property
    def skip_reason(self) -> str | None: ...


OpenItemsProvider = Callable[[Path], list[SpecError]]
"""The open-item findings of a plan file at the close gate (``validation.open_items.check_open_items`` at its ``close`` gate, given the plan path)."""
ScaffoldProvider = Callable[[Collection[str]], ScaffoldReading]
"""The scaffold scan at close for a set of API ids (``validation.graph_checks.scaffold.scaffold_scan(ctx, api_ids, "close")``)."""


@dataclass(frozen=True)
class PausedTask:
    """A task of the milestone that the gate leaves out: its id, ``deferred`` or ``wont_do`` and the reason it gave."""

    task_id: str
    disposition: str
    reason: str


@dataclass(frozen=True)
class GateReport:
    """The answer of the close gate: the ``errors`` that stop the close, ``warnings`` (W826), the ``paused`` tasks left out and ``notes`` (what could not be checked).

    A milestone whose close record is a legacy close is not checked: the report is clean and its ``notes`` say so.
    """

    milestone_id: str
    errors: tuple[SpecError, ...] = ()
    warnings: tuple[SpecError, ...] = ()
    paused: tuple[PausedTask, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Whether the milestone may be closed: no error."""
        return not self.errors


@dataclass(frozen=True)
class Scope:
    """What the gate judges: the criteria in play with the task each belongs to, and the tasks it leaves out."""

    criteria: tuple[tuple[Node, str], ...]
    paused: tuple[PausedTask, ...]


def _finding(code: str, message: str, node: Node | None = None, **fields: Any) -> SpecError:
    """A gate finding: *code* and *message* about *node* (its file, place and id), owned by the close gate."""
    if node is not None:
        fields = {"file": node.file, "jq_path": node.jq_path or None, "node_id": node.id, **fields}
    return make_error(code, message, owner=CLOSE_OWNER, **fields)


def _stage_finding(node: Node, error: SpecError) -> SpecError:
    """The E334 a proof raised for *node* (its stage cannot be told), as a finding about *node*."""
    return _finding(error.code, f"{node.kind} {node.id}: {error.message}", node)


def scope_of(graph: Graph, milestone_id: str) -> Scope:
    """The criteria of the milestone's tasks that are in play, and the tasks left out because they are deferred or wont_do (with their reason)."""
    criteria: list[tuple[Node, str]] = []
    paused: list[PausedTask] = []
    for task in graph.by_kind.get(TASK, ()):
        if task.lifecycle == NOT_APPLICABLE or milestone_of(graph, task) != milestone_id:
            continue
        value, reason = task_disposition(graph, task)
        if value in PAUSED_DISPOSITIONS:
            paused.append(PausedTask(task.id, value, reason))
            continue
        for child in task.children:
            node = graph.by_id.get(child)
            if node is not None and node.kind == TASK_CRITERION and node.lifecycle != NOT_APPLICABLE:
                criteria.append((node, task.id))
    return Scope(tuple(criteria), tuple(paused))


def plan_items(graph: Graph, milestone_id: str) -> list[Node]:
    """The plan items of the plan that names *milestone_id*, in graph order."""
    return [node for node in graph.by_kind.get(PLAN_ITEM, ()) if node.lifecycle != NOT_APPLICABLE and node.milestone is not None and graph.canonical_id(node.milestone) == milestone_id]


def _realised(graph: Graph, items: list[Node]) -> dict[str, list[Node]]:
    """``{criterion id: the plan items that realise it}``."""
    found: dict[str, list[Node]] = {}
    for item in items:
        for criterion in link_targets(graph, item, REALISES):
            found.setdefault(criterion, []).append(item)
    return found


def _unrealised_findings(scope: Scope, realised: Mapping[str, list[Node]], plan_file: str) -> list[SpecError]:
    """E810 for each criterion in play that no plan item realises."""
    return [
        _finding(
            "E810",
            f"task criterion {node.id} (task {task}) has no plan item that realises it; add a plan item with `realises: [\"{node.id}\"]` to {plan_file}, or mark the criterion not_applicable",
            node,
        )
        for node, task in scope.criteria
        if node.id not in realised
    ]


def proof_of(graph: Graph, ctx: ProofContext, node: Node) -> ProofResult | SpecError:
    """The close-mode proof of the criterion *node*, or its E334 finding when the stage of one of its verifiers cannot be told."""
    try:
        return proof(graph, ctx, node.id, executed.CLOSE_CAP, treat_ci_as_dev=True)
    except FindingError as error:
        if error.error.code != STAGE_UNKNOWN:
            raise
        return _stage_finding(node, error.error)


def _unproven_finding(graph: Graph, ctx: ProofContext, node: Node, result: ProofResult) -> SpecError:
    """E811 for the criterion *node*: what ``proof_errors`` says each verifier lacks (its messages name the node and a way out)."""
    lacking = "; ".join(error.message for error in proof_errors(graph, ctx, [node.id], executed.CLOSE_CAP, treat_ci_as_dev=True))
    return _finding("E811", lacking or f"task criterion {node.id} is not proven at the close gate ({result.status})", node)


def _proof_findings(graph: Graph, ctx: ProofContext, scope: Scope) -> list[SpecError]:
    """E811 for each criterion in play that is not proven, E334 for one whose stage cannot be told; every criterion is asked."""
    findings: list[SpecError] = []
    for node, _ in scope.criteria:
        answer = proof_of(graph, ctx, node)
        if isinstance(answer, SpecError):
            findings.append(answer)
        elif answer.status not in _PASSING:
            findings.append(_unproven_finding(graph, ctx, node, answer))
    return findings


def in_scope_items(graph: Graph, items: list[Node], scope: Scope) -> list[Node]:
    """The plan items that realise at least one criterion in play."""
    wanted = {node.id for node, _ in scope.criteria}
    return [item for item in items if wanted.intersection(link_targets(graph, item, REALISES))]


def _not_executed_finding(item: Node, reading: executed.ItemReading) -> SpecError:
    owed = "; ".join(f"action {action.action or '(no id)'}: {action.detail}" for action in reading.owed)
    return _finding("E812", f"plan item {item.id} is not executed ({owed})", item)


def _execution_findings(graph: Graph, ctx: ProofContext, lock: Lock | None, items: list[Node]) -> list[SpecError]:
    """E812 for each of *items* that is not executed (E334 for one whose stage cannot be told); every item is asked."""
    findings: list[SpecError] = []
    for item in items:
        try:
            reading = executed.item_reading(graph, ctx, item.id, lock)
        except FindingError as error:
            if error.error.code != STAGE_UNKNOWN:
                raise
            findings.append(_stage_finding(item, error.error))
            continue
        if not reading.executed:
            findings.append(_not_executed_finding(item, reading))
    return findings


def review_verdict(plan: Path) -> str | None:
    """The ``review.verdict`` of the plan file *plan*; ``None`` when the plan has no review block or no string verdict.

    The one reader of a plan's verdict: the gate (E813) and the ``awaiting_signoff`` section of ``status`` both call it.
    """
    review = (read_json_object(plan) or {}).get("review")
    verdict = review.get("verdict") if isinstance(review, Mapping) else None
    return verdict if isinstance(verdict, str) else None


def _review_findings(plan: Path, milestone_id: str, plan_file: str) -> list[SpecError]:
    """E813 when the ``review`` block of the plan is missing or its verdict is not ``verified``."""
    verdict = review_verdict(plan)
    if verdict == VERIFIED:
        return []
    said = f"the verdict is {verdict}" if verdict is not None else "no review is recorded"
    return [_finding(
        "E813",
        f"{plan_file}: {said}, and the close needs `verified`; run the 16c review, then `specdev review record {milestone_id} --verdict verified --findings-file <file>`",
        file=plan_file, node_id=milestone_id,
    )]


def _owned(findings: list[SpecError]) -> list[SpecError]:
    """*findings* of another check, reported by the close gate under its owner."""
    return [replace(error, owner=CLOSE_OWNER) for error in findings]


def _suspect_findings(graph: Graph, ctx: ProofContext, lock: Lock | None, milestone_id: str) -> tuple[list[SpecError], list[str]]:
    """The E761 (a link never attested) and E763 findings on the milestone's chain (owned by the close gate) and a note when the check could not run (no trace lock)."""
    if lock is None:
        return [], ["no trace lock: the suspect-link check was skipped"]
    milestone = chain.milestone_chain(graph, milestone_id)
    suspect = chain.suspect_links_on_chain(graph, lock, read_seed_texts(graph, ctx.git_root), milestone)
    return _owned([*chain.missing_entry_links_on_chain(graph, lock, milestone), *suspect]), []


def _apis_of(graph: Graph, scope: Scope) -> list[str]:
    """The APIs the criteria in play reach upward through their links, each once."""
    found: dict[str, None] = {}
    for node, _ in scope.criteria:
        for reached in trace_node(graph, node.id, ("up",)).reached:
            if reached.kind == API:
                found.setdefault(reached.id)
    return list(found)


def _scaffold_findings(graph: Graph, scope: Scope, scaffold: ScaffoldProvider) -> tuple[list[SpecError], list[str]]:
    """The findings of the scaffold scan for the APIs of the criteria in play, and the notes saying what it could not check."""
    apis = _apis_of(graph, scope)
    if not apis:
        return [], []
    scan = scaffold(apis)
    notes = list(scan.notes)
    if scan.skip_reason is not None:
        notes.append(f"scaffold rows were not checked: {scan.skip_reason}")
    return _owned(scan.findings), notes


def _signoff_findings(spec_root: str, milestone_id: str) -> list[SpecError]:
    """E814 when no sign-off record exists for the milestone."""
    if signoff_records(spec_root, milestone_id):
        return []
    return [_finding(
        "E814",
        f"milestone {milestone_id} has no sign-off record; a person signs the milestone off with `specdev milestone sign-off {milestone_id}`",
        node_id=milestone_id,
    )]


def _paused_items_warnings(graph: Graph, lock: Lock | None, spec_root: str, items: list[Node]) -> list[SpecError]:
    """W826 for each of *items* that realises only criteria of deferred or wont_do tasks (the finding of the ``plan-records`` check, kept for this milestone's items)."""
    ids = {item.id for item in items}
    return [error for error in plan_records.check_plan_records(graph, lock, spec_root) if error.code == plan_records.PAUSED_ITEM_WARNING and error.node_id in ids]


def check_close_gate(
    graph: Graph,
    ctx: ProofContext,
    lock: Lock | None,
    milestone_id: str,
    *,
    open_items: OpenItemsProvider,
    scaffold: ScaffoldProvider,
) -> GateReport:
    """Run the close gate for *milestone_id* and report every finding; nothing is written.

    *graph* is the graph of the spec folder of *ctx*, *lock* its trace lock (``executed.lock_if_present``; ``None`` skips the
    suspect check and the staleness of records), *open_items* and *scaffold* the two checks of ``validation`` (see the module
    docstring).  A milestone whose close record is a legacy close gives a clean report without any check.  The findings come
    in the order of the checks: E810 and E811 by criterion, E812 by plan item, E813, E632, E761 and E763, E746, E814; one criterion or
    plan item whose stage cannot be told is one E334 and the others are still answered.

    Raises:
        FindingError: E803 when no plan names the milestone; E801 for an anchor row with an unknown status; E520 when the host
            declarations or a spec file cannot be read (one error, not one per node).
        GitViewError: E708 when git fails.
    """
    spec_root = ctx.spec_root
    milestone_id = graph.canonical_id(milestone_id)
    row = anchor_store.read_row(spec_root, milestone_id)
    if row is not None and anchor_store.is_legacy_close(row.close):
        return GateReport(milestone_id, notes=("legacy close: not re-checked",))
    plan = plans.require_plan(spec_root, milestone_id)
    plan_file = os.path.join(PLAN_DIR_NAME, plan.name)
    scope = scope_of(graph, milestone_id)
    items = plan_items(graph, milestone_id)
    in_scope = in_scope_items(graph, items, scope)
    suspects, suspect_notes = _suspect_findings(graph, ctx, lock, milestone_id)
    scaffold_findings, scaffold_notes = _scaffold_findings(graph, scope, scaffold)
    errors = [
        *_unrealised_findings(scope, _realised(graph, items), plan_file),
        *_proof_findings(graph, ctx, scope),
        *_execution_findings(graph, ctx, lock, in_scope),
        *_review_findings(plan, milestone_id, plan_file),
        *_owned(open_items(plan)),
        *suspects,
        *scaffold_findings,
        *_signoff_findings(spec_root, milestone_id),
    ]
    return GateReport(
        milestone_id,
        errors=tuple(errors),
        warnings=tuple(_paused_items_warnings(graph, lock, spec_root, items)),
        paused=scope.paused,
        notes=tuple([*suspect_notes, *scaffold_notes]),
    )


_REOPEN = (
    f"`specdev milestone close` did not write this row and the milestone commands refuse a done row (E801): set its status back to `in_progress` "
    f"and delete its `close` (`specdev json patch` and `specdev json delete` on {anchor_store.ANCHOR_FILE}), then run `specdev milestone sign-off` and `specdev milestone close`"
)
"""The way out of a ``done`` row that no close record backs, as run on a copy: the row is reopened with the two ``json`` commands, then signed off and closed again."""


def verify_close_record(row: anchor_store.AnchorRow | anchor_store.AnchorState) -> list[SpecError]:
    """E814 findings for an anchor row that is not closed with a close record the release gate can accept; empty when it is.

    A row passes when its status is ``done`` and its ``close`` record is a legacy close (``legacy-migration``) or names the
    person who signed off (``signed_off_by``) and the sign-off record (``signoff``, an id).  An existence check of the
    record's shape only: it does not read the sign-off file or compare any hash, and it returns no record and no marker.
    *row* is a ``read_row`` result or an ``AnchorState`` of ``read_statuses`` (at a git ref too).
    """
    state = row.state if isinstance(row, anchor_store.AnchorRow) else row
    milestone = row.milestone_id if isinstance(row, anchor_store.AnchorRow) else None
    subject = f"milestone {milestone}" if milestone else "a milestone"
    close = state.close
    if state.status != ROW_DONE:
        return [_finding("E814", f"{subject} is not closed with a close record (status {state.status}); close it with `specdev milestone close`", node_id=milestone)]
    if close is None:
        return [_finding("E814", f"{subject} is not closed with a close record (status done, no `close` key); {_REOPEN}", node_id=milestone)]
    if anchor_store.is_legacy_close(close):
        return []
    signoff = close.get("signoff")
    if not state.signed_off_by or not isinstance(signoff, str) or not signoff:
        return [_finding("E814", f"{subject} has a close record that names no sign-off record (signed_off_by {state.signed_off_by!r}, signoff {signoff!r}); {_REOPEN}", node_id=milestone)]
    return []
