"""The milestone commands: ``start`` and ``defer`` (and resume), ``close``, and the pieces the status view and the sign-off share.

A milestone is a roadmap milestone (``ms-...``), never a batch id: every command here takes the id the anchor row is about.
A batch id (the stem of ``impl_context/ms_<batch>_plan.json``) is refused with the way to find the milestone id.

The anchor row's ``status``, ``deferral_reason`` and ``close`` are written by ``anchor_store.write_row_state`` only.  The
write lock is not re-entrant, so each command checks under the lock (on a graph built under it: no other write is running)
and writes after the check; the row is replaced in one write.

The close gate needs two checks of ``validation`` (open items, scaffold rows), which this package may not import.  The command
layer passes a ``ProviderFactory`` (``lifecycle/commands.py``) that builds them from the graph and the lock of the run.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..core.errors import FindingError, SpecError, make_error
from ..graph.gitview import read_seed_texts
from ..graph.model import Graph
from ..graph.names import ROADMAP_MILESTONE
from ..proof.built_evidence import bind_proof_seams
from ..proof.validity import ProofContext
from ..trace.lockfile import Lock
from ..trace.writing import locked_graph
from ..verify.records import records_folder
from . import anchor_store, chain, close_gate, executed, plans
from .close_gate import GateReport, OpenItemsProvider, ScaffoldProvider
from .records import now_utc

DEFER_REASON_MAX = 300
NO_LOCK_NOTE = "no trace lock: suspect check skipped"
ProviderFactory = Callable[[Graph, Lock | None], tuple[OpenItemsProvider, ScaffoldProvider]]
"""Builds the open-item and scaffold checks of the close gate for the graph and the lock of one run (they live in ``validation``)."""
MILESTONE_STATE_HINT = "specdev milestone-state --batch-id {batch}"


class MilestoneRefusal(FindingError):
    """A command refusal with the findings behind it: ``error`` is the one E80x finding, ``details`` the owner-tagged findings it rests on."""

    def __init__(self, error: SpecError, details: tuple[SpecError, ...] = ()) -> None:
        super().__init__(error)
        self.details = details


@dataclass(frozen=True)
class StartResult:
    """What ``milestone start`` did: the status before, whether it was a resume (from ``deferred``) or a no-op (already ``in_progress``), and the notes."""

    milestone: str
    previous: str
    resumed: bool = False
    noop: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeferResult:
    """What ``milestone defer`` did: the status before and the reason written."""

    milestone: str
    previous: str
    reason: str


@dataclass(frozen=True)
class CloseResult:
    """What ``milestone close`` did: the gate's report, whether the row was written (``closed``), the close record written and the tree of the sign-off it rests on."""

    milestone: str
    report: GateReport
    closed: bool
    check_only: bool
    record: dict[str, Any] | None = None
    signoff_tree: str | None = None
    tree: str | None = None


def gate_context(spec_root: str, git_root: str) -> ProofContext:
    """The proof context of a run on *spec_root* (absolute) in the host *git_root*; the proof seams are bound first."""
    bind_proof_seams()
    return ProofContext(git_root, spec_root, evidence_dir=records_folder(spec_root))


def run_gate(graph: Graph, ctx: ProofContext, lock: Lock | None, milestone_id: str, providers: ProviderFactory) -> GateReport:
    """The close gate on *graph* for *milestone_id*, with the checks *providers* builds (nothing is written)."""
    open_items, scaffold = providers(graph, lock)
    return close_gate.check_close_gate(graph, ctx, lock, milestone_id, open_items=open_items, scaffold=scaffold)


def _refuse(code: str, message: str, subcode: str | None = None, node_id: str | None = None) -> FindingError:
    return FindingError(make_error(code, message, subcode=subcode, node_id=node_id))


def milestone_id_of(graph: Graph, spec_root: str, given: str) -> str:
    """The canonical id of the milestone *given*; a batch id is refused (E803) with the way to find the milestone id.

    A batch id is the stem of a plan file (``ms_<batch>_plan.json``); an id that names a roadmap milestone is never taken for one.
    """
    node = graph.find(given)
    if node is not None and node.kind == ROADMAP_MILESTONE:
        return node.id
    plan = os.path.join(spec_root, "impl_context", f"ms_{given}_plan.json")
    if os.path.isfile(plan):
        raise _refuse(
            "E803",
            f"{given} is a batch id (the plan file impl_context/ms_{given}_plan.json), not a milestone id (ms-...); "
            f"`{MILESTONE_STATE_HINT.format(batch=given)}` prints the milestone of that plan under `milestone`",
            "MILESTONE_NOT_FOUND",
        )
    return given


def refuse_not_in_progress(milestone_id: str, status: str, what: str) -> FindingError:
    """The E801 for *what* (``closed``, ``signed off``) a milestone that is not ``in_progress``: the way out is ``start`` unless it is done already."""
    way = "a closed milestone stays closed" if status == "done" else f"`specdev milestone start {milestone_id}` first"
    return _refuse("E801", f"milestone {milestone_id} is {status}; only an in_progress milestone is {what} ({way})", node_id=milestone_id)


def require_row(spec_root: str, milestone_id: str) -> anchor_store.AnchorRow:
    """The anchor row of *milestone_id*.

    Raises:
        FindingError: E800 (``ANCHOR_ROW_MISSING``) when the anchor file has no row about it; E801 for an unknown status.
    """
    row = anchor_store.read_row(spec_root, milestone_id)
    if row is None:
        raise _refuse(
            "E800",
            f"{anchor_store.ANCHOR_FILE} has no anchor row about {milestone_id}; the anchor row of a milestone is written with step 16 "
            "(`specdev step create 16`), and a milestone id looks like ms-account-recovery",
            "ANCHOR_ROW_MISSING", milestone_id,
        )
    return row


def _suspects_on_chain(graph: Graph, ctx: ProofContext, lock: Lock, milestone_id: str) -> list[SpecError]:
    return chain.suspect_links_on_chain(graph, lock, read_seed_texts(graph, ctx.git_root), chain.milestone_chain(graph, milestone_id))


def start_milestone(spec_root: str, repo_root: str, git_root: str, given: str) -> StartResult:
    """Start (or resume) the milestone *given*: its row becomes ``in_progress`` and loses its ``deferral_reason``.

    ``in_progress`` is a no-op.  Refused with E800: ``ANCHOR_ROW_MISSING``; ``STATUS_NOT_STARTABLE`` for ``done``;
    ``PENDING_REPLAY_ON_CHAIN`` when a suspect link is on the milestone's chain (links elsewhere do not block; no trace lock means
    the check is skipped and the result says so).  E803 when no plan names the milestone, or *given* is a batch id.
    """
    with locked_graph(spec_root, repo_root, "milestone start") as graph:
        milestone_id = milestone_id_of(graph, spec_root, given)
        row = require_row(spec_root, milestone_id)
        if row.status == "in_progress":
            return StartResult(milestone_id, row.status, noop=True)
        if row.status == "done":
            raise _refuse("E800", f"milestone {milestone_id} is done; a closed milestone is not started again", "STATUS_NOT_STARTABLE", milestone_id)
        plans.require_plan(spec_root, milestone_id)
        lock = executed.lock_if_present(spec_root)
        notes: tuple[str, ...] = (NO_LOCK_NOTE,) if lock is None else ()
        found = [] if lock is None else _suspects_on_chain(graph, gate_context(spec_root, git_root), lock, milestone_id)
        if found:
            shown = "; ".join(f"{error.node_id} {error.target}" for error in found[:3]) + (" ..." if len(found) > 3 else "")
            raise MilestoneRefusal(
                make_error(
                    "E800",
                    f"milestone {milestone_id} cannot start: {len(found)} suspect link(s) on its chain ({shown}); replay the steps `specdev stale` lists, then start again",
                    subcode="PENDING_REPLAY_ON_CHAIN", node_id=milestone_id,
                ),
                tuple(found),
            )
    anchor_store.write_row_state(spec_root, milestone_id, "in_progress", repo_root=repo_root)
    return StartResult(milestone_id, row.status, resumed=row.status == "deferred", notes=notes)


def defer_milestone(spec_root: str, repo_root: str, given: str, reason: str | None) -> DeferResult:
    """Defer the milestone *given* with *reason* (1 to 300 characters): from ``pending`` or ``in_progress``; no task, plan item or open item is touched.

    Refused: E802 for no reason, a blank one or one over 300 characters; E801 for a status that is neither (``deferred`` or ``done``).
    """
    text = (reason or "").strip()
    if not text or len(text) > DEFER_REASON_MAX:
        said = "no reason was given" if not text else f"the reason is {len(text)} characters; at most {DEFER_REASON_MAX}"
        raise _refuse("E802", f"a milestone is deferred with a reason ({said}); give `--reason \"<why it waits>\"`, at most {DEFER_REASON_MAX} characters")
    with locked_graph(spec_root, repo_root, "milestone defer") as graph:
        milestone_id = milestone_id_of(graph, spec_root, given)
        row = require_row(spec_root, milestone_id)
        if row.status not in ("pending", "in_progress"):
            raise _refuse("E801", f"milestone {milestone_id} is {row.status}; only a pending or in_progress milestone is deferred", node_id=milestone_id)
    anchor_store.write_row_state(spec_root, milestone_id, "deferred", deferral_reason=text, repo_root=repo_root)
    return DeferResult(milestone_id, row.status, text)


def close_milestone(spec_root: str, repo_root: str, git_root: str, given: str, providers: ProviderFactory, *, check_only: bool = False) -> CloseResult:
    """Run the close gate for the milestone *given* and, when it passes and *check_only* is not set, close it in one write.

    The row must be ``in_progress`` (E801).  A gate that finds errors writes nothing and the result carries them.  A pass writes
    ``status: done`` and the close record (``signed_off_by`` the email of the latest sign-off's git author, ``signoff`` its id,
    ``tree``, ``plan_hash``, ``closed_at``, ``migrations: []``) in the one write of ``anchor_store.write_row_state``; the plan file
    is not rewritten and is frozen from then on.
    """
    with locked_graph(spec_root, repo_root, "milestone close") as graph:
        milestone_id = milestone_id_of(graph, spec_root, given)
        row = require_row(spec_root, milestone_id)
        if row.status != "in_progress":
            raise refuse_not_in_progress(milestone_id, row.status, "closed")
        ctx = gate_context(spec_root, git_root)
        report = run_gate(graph, ctx, executed.lock_if_present(spec_root), milestone_id, providers)
        signed = close_gate.latest_signoff(spec_root, milestone_id)
        tree = ctx.code_tree
        plan = plans.require_plan(spec_root, milestone_id)
        plan_hash = plans.plan_hash(plan)
    if not report.passed or check_only or signed is None:
        return CloseResult(milestone_id, report, closed=False, check_only=check_only, signoff_tree=signed.tree if signed else None, tree=tree)
    record: dict[str, Any] = {
        "signed_off_by": signed.git_author.get("email", ""), "signoff": signed.signoff_id, "tree": tree,
        "plan_hash": plan_hash, "closed_at": now_utc(), "migrations": [],
    }
    anchor_store.write_row_state(spec_root, milestone_id, "done", close=record, repo_root=repo_root)
    return CloseResult(milestone_id, report, closed=True, check_only=False, record=record, signoff_tree=signed.tree, tree=tree)
