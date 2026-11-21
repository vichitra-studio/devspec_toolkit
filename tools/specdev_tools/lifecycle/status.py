"""``specdev status``: where the work stands, in sections, and the sign-off and close view of one milestone.

``status`` reads and writes nothing and is not a gate: it lists what is owed and exits 0 (it exits 1 only when it cannot read
what it needs: the trace lock, the host declarations, an anchor row with an unknown status).  Each section is a function that
is registered under a name, ``register_status_section(name, fn)``; this module registers the sections below.  The two release
sections, ``MERGE_RELEASE_SECTION`` and ``PRODUCTION_SECTION``, are registered here as placeholders that print "release gate not
installed"; ``release.status_sections.install()``, which ``cli.build_parser`` calls (this package does not import ``release``),
replaces them in their places with the merge-check and release-gate findings and the production verification of the previous
release.  A section function gets a ``StatusContext`` and returns a ``Section``.

``milestone_view`` is the view of one milestone that ``status --milestone`` and ``milestone sign-off`` print: the code tree,
the proof of each criterion, the manual share, what is deferred or won't-do, what is open, and the close gate as a dry run (not for a ``done`` row: a closed
milestone stays closed; a plan changed after the close is ``spec-check``'s to report, E827, and code that moved on is not reported).
Every question about several nodes is asked node by node: a node whose stage cannot be told (E334) is reported as that and the
others are still answered.
"""
from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.ambiguity_items import PLAN_ITEM_STEPS, AmbiguityItem, is_open, read_ambiguity_items
from ..core.errors import FindingError, SpecError
from ..core.plan_files import find_plan
from ..core.step_order import load_step_order
from ..graph.gitview import read_seed_texts
from ..graph.model import Graph, Node
from ..graph.names import FIXTURE, ROW_DONE, ROW_IN_PROGRESS, RULE, VERIFIED_BY, link_targets
from ..graph.ownership import CLOSE_OWNER
from ..graph.stages import STAGES
from ..proof.proof import PROVEN, STAGE_UNKNOWN, UNPROVEN, is_attested_by_person, proof, verifier_proof
from ..proof.realisation import unresolved_realisations
from ..proof.validity import ProofContext
from ..trace import replay, step_ready
from ..trace.lockfile import Lock
from ..verify.code_tree import submodule_warnings
from ..verify.records import signoff_records
from . import anchor_store, close_gate, executed, plans
from .frozen import is_frozen_path
from .milestone import ProviderFactory, gate_context, require_row, run_gate

RELEASE_NOT_INSTALLED = "release gate not installed"
MERGE_RELEASE_SECTION = "merge_release_gates"
PRODUCTION_SECTION = "production_verification"
_TRINITY_STEPS = frozenset({"16a", "16b", "16c"})


@dataclass(frozen=True)
class StatusContext:
    """What a section reads: the graph, the roots, the trace lock (``None`` when the folder has none), the proof context and the close-gate checks."""

    graph: Graph
    spec_root: str
    repo_root: str
    git_root: str
    lock: Lock | None
    ctx: ProofContext
    providers: ProviderFactory

    @property
    def seed_texts(self) -> dict[str, str]:
        return read_seed_texts(self.graph, self.git_root)


@dataclass(frozen=True)
class Section:
    """One section of the report: its ``name`` (the stable JSON key), ``title``, the printed ``lines`` and the ``data`` the JSON carries."""

    name: str
    title: str
    lines: tuple[str, ...]
    data: Any


SectionFn = Callable[[StatusContext], Section]
SECTIONS: dict[str, SectionFn] = {}
"""The registered sections in the order they print; registering a name again replaces its function and keeps its place."""


def register_status_section(name: str, fn: SectionFn) -> None:
    """Register the section *name*: ``fn(context)`` returns its ``Section``.  A name that is registered already is replaced in place."""
    SECTIONS[name] = fn


def _in_progress(ctx: StatusContext) -> list[str]:
    return [milestone for milestone, state in anchor_store.read_statuses(ctx.spec_root).items() if state.status == ROW_IN_PROGRESS]


def _review_verdict(spec_root: str, milestone_id: str) -> str | None:
    plan = find_plan(spec_root, milestone_id)
    return close_gate.review_verdict(plan) if plan is not None else None


# --- the sections -----------------------------------------------------------------------------------------------------

def _pending_replay(sc: StatusContext) -> Section:
    title = "Pending replay by step"
    if sc.lock is None:
        return Section("pending_replay", title, ("no trace lock: the pending replay was not computed",), None)
    steps = replay.compute_replay(sc.graph, sc.lock, sc.seed_texts).steps
    data = [{"step": step.step, "suspect_links": step.link_count, "coverage_gaps": len(step.coverage_gaps)} for step in steps]
    lines = tuple(f"step {step.step or replay.NO_STEP_LABEL}: {step.link_count} suspect link(s), {len(step.coverage_gaps)} coverage gap(s)" for step in steps)
    return Section("pending_replay", title, (*lines, "`specdev stale` lists the links") if lines else ("none",), data)


def _live_open_items(spec_root: str, items: Iterable[AmbiguityItem]) -> list[AmbiguityItem]:
    """The open items of *items* left after the ones in the plan of a closed milestone: the test ``spec-check`` uses (``frozen.is_frozen_path``)."""
    return [item for item in items if is_open(item) and not (item.step in PLAN_ITEM_STEPS and is_frozen_path(spec_root, Path(item.artifact_path)))]


def _open_items(sc: StatusContext) -> Section:
    title = "Open items by owner"
    read = read_ambiguity_items(sc.spec_root)
    by_owner: dict[str, list[str]] = defaultdict(list)
    for item in _live_open_items(sc.spec_root, read.items):
        by_owner[f"step:{item.step}"].append(item.id or "(no id)")
    lines = [f"{owner}: {len(ids)} ({', '.join(ids)})" for owner, ids in sorted(by_owner.items())]
    if read.error is not None:
        lines.append(f"the list may be incomplete: {read.error}")
    return Section("open_items", title, tuple(lines) or ("none",), {owner: ids for owner, ids in sorted(by_owner.items())})


def _awaiting_signoff(sc: StatusContext) -> Section:
    waiting = [
        milestone for milestone in _in_progress(sc)
        if _review_verdict(sc.spec_root, milestone) == close_gate.VERIFIED and not signoff_records(sc.spec_root, milestone)
    ]
    lines = tuple(f"{milestone}: reviewed `verified`, no sign-off; `specdev milestone sign-off {milestone}`" for milestone in waiting)
    return Section("awaiting_signoff", "Milestones awaiting sign-off", lines or ("none",), waiting)


def _realisations(sc: StatusContext) -> Section:
    title = "Outdated and removed realisations"
    if sc.lock is None:
        return Section("realisations", title, ("no trace lock: realisations were not computed",), None)
    owed = unresolved_realisations(sc.graph, sc.lock, sc.seed_texts)
    lines = tuple(
        f"{entry.code} {entry.kind}: {entry.milestone} realised {entry.target}; "
        + (f"change milestone {entry.existing_milestone} (not closed)" if entry.existing_milestone else "no milestone carries the change yet")
        for entry in owed
    )
    data = [{"code": e.code, "kind": e.kind, "milestone": e.milestone, "target": e.target, "change_milestone": e.existing_milestone} for e in owed]
    return Section("realisations", title, lines or ("none",), data)


def _next_step(sc: StatusContext) -> Section:
    title = "Next step that may start"
    present = step_ready.present_steps(sc.graph, sc.spec_root)
    pending = [step for step in load_step_order(sc.repo_root).get("steps", []) if step not in present and step not in _TRINITY_STEPS]
    if not pending:
        return Section("next_step", title, ("every step has a spec file",), None)
    step = pending[0]
    plan = replay.compute_replay(sc.graph, sc.lock if sc.lock is not None else Lock(), sc.seed_texts)
    readiness = step_ready.check_ready(sc.graph, plan, step, step_ready.required_spec_inputs(sc.repo_root, step), present)
    if readiness.ready:
        return Section("next_step", title, (f"step {step} may start",), {"step": step, "ready": True})
    return Section("next_step", title, (f"step {step} is not ready: {step_ready.first_clause(readiness)}",), {"step": step, "ready": False})


def _gate_owned(sc: StatusContext) -> Section:
    title = "Gate-owned errors by owner"
    by_owner: dict[str, list[str]] = defaultdict(list)
    notes: list[str] = []
    for milestone in _in_progress(sc):
        try:
            report = run_gate(sc.graph, sc.ctx, sc.lock, milestone, sc.providers)
        except FindingError as error:
            if error.error.code != "E803":
                raise
            notes.append(f"{milestone}: the close gate was not run ({error.error.message})")
            continue
        for found in report.errors:
            by_owner[found.owner or CLOSE_OWNER].append(f"{milestone}: {found.render()}")
    warnings = [error.render() for error in submodule_warnings(sc.git_root)]
    lines = [line for owner, found in sorted(by_owner.items()) for line in (f"{owner} ({len(found)}):", *(f"  {text}" for text in found))]
    lines.extend([*notes, *warnings])
    data = {"errors": {owner: found for owner, found in sorted(by_owner.items())}, "warnings": warnings, "notes": notes}
    return Section("gate_owned_errors", title, tuple(lines) or ("none for the milestones in progress",), data)


def _release_not_installed(name: str, title: str) -> SectionFn:
    return lambda _sc: Section(name, title, (RELEASE_NOT_INSTALLED,), None)


register_status_section("pending_replay", _pending_replay)
register_status_section("open_items", _open_items)
register_status_section("awaiting_signoff", _awaiting_signoff)
register_status_section("realisations", _realisations)
register_status_section("next_step", _next_step)
register_status_section("gate_owned_errors", _gate_owned)
register_status_section(MERGE_RELEASE_SECTION, _release_not_installed(MERGE_RELEASE_SECTION, "Merge-check and release-gate errors"))
register_status_section(PRODUCTION_SECTION, _release_not_installed(PRODUCTION_SECTION, "Production verification"))


def build_status(sc: StatusContext) -> list[Section]:
    """Every registered section, in order."""
    return [fn(sc) for fn in SECTIONS.values()]


def status_text(sections: list[Section]) -> str:
    """The report as printed: each section a title and its lines."""
    return "\n\n".join("\n".join([section.title, *(f"  {text}" for text in section.lines)]) for section in sections)


def status_dict(sections: list[Section]) -> dict[str, Any]:
    """The report as JSON: ``{"command": "status", "sections": {<name>: {"title", "lines", "data"}}}``."""
    return {"command": "status", "sections": {s.name: {"title": s.title, "lines": list(s.lines), "data": s.data} for s in sections}}


# --- the view of one milestone ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CriterionLine:
    """A criterion in play: its task and its close-mode proof status (``stage-unknown`` when its stage cannot be told)."""

    criterion: str
    task: str
    status: str


@dataclass(frozen=True)
class ManualLine:
    """A node a person attests (a manual fixture or a rule enforced by review) and whether it is attested now."""

    node: str
    kind: str
    attested: bool


@dataclass(frozen=True)
class MilestoneView:
    """What the person who signs a milestone off is shown; also the ``listed`` of the sign-off record."""

    milestone: str
    status: str
    plan_file: str
    tree: str
    signoffs: tuple[str, ...]
    criteria: tuple[CriterionLine, ...]
    manual: tuple[ManualLine, ...]
    paused: tuple[close_gate.PausedTask, ...]
    paused_items: tuple[str, ...]
    open_items: tuple[str, ...]
    items_not_executed: tuple[str, ...]
    proof_owed_later: tuple[str, ...]
    report: close_gate.GateReport | None
    warnings: tuple[str, ...]

    @property
    def manual_attested(self) -> int:
        return sum(1 for line in self.manual if line.attested)


def _criterion_status(graph: Graph, ctx: ProofContext, node: Node) -> str:
    answer = close_gate.proof_of(graph, ctx, node)
    return STAGE_UNKNOWN if isinstance(answer, SpecError) else answer.status


def _owed_later(graph: Graph, ctx: ProofContext, node: Node) -> bool:
    """Whether the criterion *node* has a binding at ``staging`` or ``prod`` that the proof with the cap ``prod`` does not find proven.

    The close gate ignores those bindings; this asks the proof code as it is (cap ``prod``, no ``treat_ci_as_dev``) and reads
    the stage of the binding each shortfall names.  A criterion that has a failing binding at a lower stage as well may name only
    that one (``proof`` stops at the first binding that fails); the gate and the criterion's line say it is unproven then.
    A stage that cannot be told (E334) is the gate's finding, not an owed proof.
    """
    try:
        answer = proof(graph, ctx, node.id, STAGES[-1])
    except FindingError as error:
        if error.error.code != STAGE_UNKNOWN:
            raise
        return False
    return answer.status == UNPROVEN and any(shortfall.stage in STAGES[STAGES.index("staging"):] for shortfall in answer.shortfalls)


def _manual_lines(graph: Graph, ctx: ProofContext, scope: close_gate.Scope) -> tuple[ManualLine, ...]:
    """The manual fixtures and review rules the criteria in play are verified by, each once, with whether it is attested now."""
    found: dict[str, ManualLine] = {}
    for criterion, _ in scope.criteria:
        for name in link_targets(graph, criterion, VERIFIED_BY):
            node = graph.find(name)
            if node is None or node.id in found or node.kind not in (FIXTURE, RULE) or not is_attested_by_person(node, graph):
                continue
            try:
                attested = verifier_proof(graph, ctx, node.id, "dev", treat_ci_as_dev=True).status == PROVEN
            except FindingError as error:
                if error.error.code != STAGE_UNKNOWN:
                    raise
                attested = False
            found[node.id] = ManualLine(node.id, node.kind, attested)
    return tuple(found.values())


def _not_executed(graph: Graph, ctx: ProofContext, lock: Lock | None, items: list[Node]) -> tuple[str, ...]:
    owed: list[str] = []
    for item in items:
        try:
            if not executed.item_reading(graph, ctx, item.id, lock).executed:
                owed.append(item.id)
        except FindingError as error:
            if error.error.code != STAGE_UNKNOWN:
                raise
            owed.append(item.id)
    return tuple(owed)


def milestone_view(sc: StatusContext, milestone_id: str) -> MilestoneView:
    """The view of *milestone_id* (a canonical roadmap milestone id): the close gate is a dry run (``report`` is ``None`` for a ``done`` row), nothing is written.

    Raises:
        FindingError: E800 when the anchor file has no row about it; E803 when no plan names the milestone; E801 for an unknown status; E520 once for host declarations that cannot be read.
    """
    graph, spec_root = sc.graph, sc.spec_root
    row = require_row(spec_root, milestone_id)
    plan = plans.require_plan(spec_root, milestone_id)
    scope = close_gate.scope_of(graph, milestone_id)
    items = close_gate.plan_items(graph, milestone_id)
    in_scope = close_gate.in_scope_items(graph, items, scope)
    criteria = tuple(CriterionLine(node.id, task, _criterion_status(graph, sc.ctx, node)) for node, task in scope.criteria)
    report = None if row.status == ROW_DONE else run_gate(graph, sc.ctx, sc.lock, milestone_id, sc.providers)
    realised_only_paused = tuple(w.node_id for w in report.warnings if w.node_id) if report is not None else ()
    plan_path = os.path.abspath(plan)
    open_items = tuple(item.id or "(no id)" for item in _live_open_items(spec_root, read_ambiguity_items(spec_root).items) if os.path.abspath(item.artifact_path) == plan_path)
    return MilestoneView(
        milestone=milestone_id,
        status=row.status,
        plan_file=os.path.relpath(plan, spec_root),
        tree=sc.ctx.code_tree,
        signoffs=tuple(f"{r.signoff_id} (tree {r.tree})" for r in signoff_records(spec_root, milestone_id)),
        criteria=criteria,
        manual=_manual_lines(graph, sc.ctx, scope),
        paused=scope.paused,
        paused_items=realised_only_paused,
        open_items=open_items,
        items_not_executed=_not_executed(graph, sc.ctx, sc.lock, in_scope),
        proof_owed_later=tuple(node.id for node, _ in scope.criteria if _owed_later(graph, sc.ctx, node)),
        report=report,
        warnings=tuple(error.render() for error in submodule_warnings(sc.git_root)),
    )


def view_text(view: MilestoneView) -> str:
    """The view as printed."""
    out = [f"milestone {view.milestone}: {view.status}", f"plan: {view.plan_file}", f"code tree: {view.tree}"]
    out.append("sign-offs: " + (", ".join(view.signoffs) if view.signoffs else "none"))
    out.append(f"criteria in play ({len(view.criteria)}):")
    out.extend(f"  {line.criterion} (task {line.task}): {line.status}" for line in view.criteria)
    out.append(f"manual share: {len(view.manual)} node(s) a person attests, {view.manual_attested} attested")
    out.extend(f"  {line.node} ({line.kind}): " + ("attested" if line.attested else f"not attested; `specdev verify attest {line.node}`") for line in view.manual)
    out.append(f"deferred and won't-do tasks ({len(view.paused)}):")
    out.extend(f"  {task.task_id} {task.disposition}: {task.reason or '(no reason)'}" for task in view.paused)
    if view.paused_items:
        out.append(f"plan items that realise only excluded tasks (W826): {', '.join(view.paused_items)}")
    out.append(f"open items: {len(view.open_items)}" + (f" ({', '.join(view.open_items)})" if view.open_items else ""))
    out.append(f"plan items not executed: {len(view.items_not_executed)}" + (f" ({', '.join(view.items_not_executed)})" if view.items_not_executed else ""))
    out.append("proof owed at staging or prod: " + (", ".join(view.proof_owed_later) if view.proof_owed_later else "none"))
    out.extend(view.warnings)
    if view.report is not None:
        out.append(f"close gate (dry run): {'passes' if view.report.passed else f'{len(view.report.errors)} error(s)'}")
        out.extend(f"  {error.render()}" for error in view.report.errors)
        out.extend(f"  note: {note}" for note in view.report.notes)
    return "\n".join(out)


def view_dict(view: MilestoneView) -> dict[str, Any]:
    """The view as JSON (stable keys)."""
    return {
        "command": "status --milestone", "milestone": view.milestone, "status": view.status, "plan": view.plan_file, "tree": view.tree,
        "signoffs": list(view.signoffs),
        "criteria": [{"criterion": c.criterion, "task": c.task, "proof": c.status} for c in view.criteria],
        "manual": {"count": len(view.manual), "attested": view.manual_attested, "nodes": [{"node": m.node, "kind": m.kind, "attested": m.attested} for m in view.manual]},
        "paused_tasks": [{"task": t.task_id, "disposition": t.disposition, "reason": t.reason} for t in view.paused],
        "paused_items": list(view.paused_items), "open_items": list(view.open_items), "items_not_executed": list(view.items_not_executed),
        "proof_owed_later": list(view.proof_owed_later), "warnings": list(view.warnings),
        "close_gate": None if view.report is None else {"passes": view.report.passed, "errors": [{"code": e.code, "owner": e.owner, "message": e.message, "node": e.node_id} for e in view.report.errors], "notes": list(view.report.notes)},
    }


def status_context(spec_root: str, repo_root: str, git_root: str, lock: Lock | None, graph: Graph, providers: ProviderFactory) -> StatusContext:
    """The context of a run on *graph* (the proof seams are bound; the proof context reads the code tree when first asked)."""
    return StatusContext(graph, spec_root, repo_root, git_root, lock, gate_context(spec_root, git_root), providers)
