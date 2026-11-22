"""The release gate: whether the code tree checked out is fit to be tagged as a release.

``run_release_gate`` is a state check of the checkout (no history walk; the one git lookup is the previous release tag).  It
reads ONE ``CheckContext`` (so one graph and one lock) and ONE ``ProofContext``, and runs, in this order:

1. the static state: every registered ``spec-check`` check (errors in every step: an unlinked legacy criterion and an unscheduled
   in-scope obligation are E566, E567 and E740 there, so they block a release through this step), the merge-mode open-items and
   pin checks (nothing is run), the step-15 scaffold rows of every API (E746, release mode) and the unrealised design milestones (E928);
2. every closed milestone has a sign-off record (E913, the close gate's E814 text);
3. every in-scope obligation is built at ``ci`` (E914); an obligation that waits only for staging or production proof is relieved
   and listed in the result;
4. the dev and CI proof stands for this code tree (E347 / E348, re-emitted from ``proof_errors``);
5. every outdated or removed realisation has its change milestone closed (E343 / E344, built here from ``unresolved_realisations``);
6. every rule enforced by review is attested (E830, from ``review_rule_attested``);
7. obligations of scope ``later`` or ``out`` are listed (W933), a stage whose environment is retired is skipped (W936);
8. the next-release check (``release.previous``: E920, W937, W938).

A step that raises a ``FindingError`` is reported as that step's finding and the other steps still run.  Every fact keeps the
code of the milestone that defined it; the gate mints none of its own for them.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.graph.model import Node
from specdev_tools.graph.names import ENVIRONMENT, OBLIGATION_ROLES, ROW_DONE, RULE
from specdev_tools.graph.ownership import CLOSE_OWNER, RELEASE_OWNER
from specdev_tools.graph.stages import CI_STAGE, STAGES
from specdev_tools.lifecycle import anchor_store
from specdev_tools.lifecycle.attest import review_rule_attested
from specdev_tools.lifecycle.close_gate import verify_close_record
from specdev_tools.proof.built_evidence import bind_proof_seams, built_at_cap, proof_context
from specdev_tools.proof.proof import is_attested_by_person, proof_errors
from specdev_tools.proof.realisation import unresolved_realisations
from specdev_tools.release.previous import NextReleaseResult, PreviousRelease, check_next_release
from specdev_tools.trace.coverage import PARKED_SCOPES
from specdev_tools.validation import spec_check
from specdev_tools.validation.check_registry import CheckContext, run_registered_checks
from specdev_tools.validation.graph_checks.built import SATISFIED, BuiltState
from specdev_tools.validation.graph_checks.context import GraphCheckContext, Mode
from specdev_tools.validation.graph_checks.design_milestones import unrealised_design_milestones
from specdev_tools.validation.graph_checks.scaffold import scaffold_scan
from specdev_tools.validation.merge_gate import MERGE_OPEN_ITEMS, MERGE_PINS, open_items_check, pins_check

_SCOPE_OUT = PARKED_SCOPES[-1]
_RELEASE_MODE: Mode = "release"
_NO_GRAPH = "no spec graph could be built, so the release checks that read the graph did not run; correct the errors above"


class RelievedNode(NamedTuple):
    """A node that is built but for the proof of a later stage: what the production-deploy gate and the next-release check re-check."""

    node_id: str
    waits_for: str


@dataclass(frozen=True)
class ReleaseGateResult:
    """What the release gate found: ``errors`` block the release; ``warnings`` and ``listed`` (W933: obligations of scope ``later`` or ``out``) do not.

    ``relieved`` is the set of nodes that wait only for proof at staging or production; ``notes`` say what a step could not check;
    ``previous`` is the release the next-release check looked at (``None`` for a first release).
    """

    errors: tuple[SpecError, ...]
    warnings: tuple[SpecError, ...]
    listed: tuple[SpecError, ...]
    relieved: tuple[RelievedNode, ...]
    notes: tuple[str, ...]
    previous: PreviousRelease | None

    @property
    def passed(self) -> bool:
        """Whether nothing blocks the release."""
        return not self.errors


@dataclass
class _Run:
    """What the steps of one run collect."""

    errors: list[SpecError]
    warnings: list[SpecError]
    listed: list[SpecError]
    relieved: list[RelievedNode]
    notes: list[str]
    previous: PreviousRelease | None = None

    def add(self, findings: list[SpecError]) -> None:
        """File each finding as a warning (a W code) or an error."""
        for finding in findings:
            (self.warnings if finding.code.startswith("W") else self.errors).append(finding)

    def step(self, step: Callable[[], list[SpecError] | None]) -> None:
        """Run *step*; its findings are filed, a ``FindingError`` it raises is filed as its one finding."""
        try:
            self.add(step() or [])
        except FindingError as exc:
            self.add([exc.error])


def _scope(gctx: GraphCheckContext) -> list[Node]:
    """The obligations in play: the release scope."""
    return [node for node in gctx.in_play_nodes() if node.role in OBLIGATION_ROLES]


def _static_state(ctx: CheckContext, run: _Run) -> list[SpecError]:
    if not ctx.quiet:
        spec_check.warn_ignored_promotions()
    checks = run_registered_checks(ctx)
    checks[MERGE_OPEN_ITEMS] = open_items_check(ctx)
    checks[MERGE_PINS] = pins_check(ctx)
    return list(dict.fromkeys(spec_check.check_findings(checks)))


def _unsigned(gctx: GraphCheckContext) -> list[SpecError]:
    """E913 for each closed milestone whose close record names no sign-off (the close gate's E814 text)."""
    spec_root = gctx.spec_root or ""
    found: list[SpecError] = []
    for milestone, state in anchor_store.read_statuses(spec_root).items():
        row = anchor_store.read_row(spec_root, milestone) if state.status == ROW_DONE else None
        found += [make_error("E913", error.message, node_id=milestone, owner=CLOSE_OWNER) for error in (verify_close_record(row) if row is not None else ())]
    return found


def _not_built(gctx: GraphCheckContext, scope: list[Node], run: _Run) -> list[SpecError]:
    """E914 for each obligation of *scope* that is not built at ``ci``; the relieved ones go to ``run.relieved``."""
    built = built_at_cap(gctx, CI_STAGE)
    found: list[SpecError] = []
    for node in scope:
        result = built[node.id]
        if result.state is BuiltState.RELIEVED:
            run.relieved.append(RelievedNode(node.id, result.waits_for or ""))
        elif result.state not in SATISFIED:
            found.append(gctx.finding("E914", node, f"{node.kind} {node.id} is an obligation of this release and is not built ({result.reason}); build and prove it, or set its scope to later or out with a scope_reason"))
    return found


def _realisations(gctx: GraphCheckContext, run: _Run) -> list[SpecError]:
    """E343 / E344 for each realisation that is outdated or removed and whose change milestone is not closed."""
    if gctx.lock is None:
        run.notes.append("no trace lock: outdated and removed realisations were not checked")
        return []
    found: list[SpecError] = []
    for entry in unresolved_realisations(gctx.graph, gctx.lock, gctx.seed_texts):
        what = "changed" if entry.code == "E343" else "is removed"
        way = f"close its change milestone {entry.existing_milestone}" if entry.existing_milestone else "carry the change in a milestone and close it"
        found.append(make_error(entry.code, f"milestone {entry.milestone} realised {entry.target}, which {what} since; {way}", node_id=entry.target, owner=RELEASE_OWNER))
    return found


def _unattested(gctx: GraphCheckContext) -> list[SpecError]:
    """E830 for each rule enforced by review that has no valid attestation."""
    proof = proof_context(gctx)
    rules = [node for node in gctx.in_play_nodes() if node.kind == RULE and is_attested_by_person(node, gctx.graph)]
    return [finding for node in rules for finding in review_rule_attested(node.id, gctx.graph, proof)] if proof is not None else []


def _listed(gctx: GraphCheckContext) -> list[SpecError]:
    """W933 for each obligation of scope ``later`` or ``out`` (not part of this release, not blocking)."""
    parked = [node for node in gctx.graph.gated_nodes() if node.role in OBLIGATION_ROLES and node.scope in PARKED_SCOPES]
    return [gctx.finding("W933", node, f"{node.kind} {node.id} is scope {node.scope} and not part of this release; listed, not blocking") for node in parked]


def _skipped_stages(gctx: GraphCheckContext) -> list[SpecError]:
    """W936 for each stage whose environment is retired (scope out): its proof is not asked for."""
    retired = [node for node in gctx.graph.gated_nodes() if node.kind == ENVIRONMENT and node.id in STAGES and node.scope == _SCOPE_OUT]
    return [gctx.finding("W936", node, f"stage {node.id} is skipped: its environment is retired (scope out)") for node in retired]


def _graph_steps(gctx: GraphCheckContext, run: _Run) -> None:
    scope = _scope(gctx)
    proof = proof_context(gctx)

    def scaffold() -> list[SpecError]:
        scan = scaffold_scan(gctx, None, _RELEASE_MODE)
        run.notes.extend(scan.notes)
        if scan.skip_reason is not None:
            run.notes.append(f"scaffold rows were not checked: {scan.skip_reason}")
        return scan.findings

    run.step(scaffold)
    run.step(lambda: [gctx.finding("E928", node, f"design milestone {node.id} is realised by no roadmap milestone; schedule it into one, or set its scope to later or out with a scope_reason") for node in unrealised_design_milestones(gctx)])
    run.step(lambda: _unsigned(gctx))
    run.step(lambda: _not_built(gctx, scope, run))
    run.step(lambda: proof_errors(gctx.graph, proof, [node.id for node in scope], CI_STAGE) if proof is not None else [])
    run.step(lambda: _realisations(gctx, run))
    run.step(lambda: _unattested(gctx))
    run.listed.extend(_listed(gctx))
    run.add(_skipped_stages(gctx))


def _next_release(ctx: CheckContext, run: _Run) -> list[SpecError]:
    result: NextReleaseResult = check_next_release(ctx.project_root, ctx.effective_spec_root, ctx.repo_root)
    run.previous = result.previous
    return [*result.errors, *result.warnings]


def run_release_gate(
    repo_root: str, spec_dir: str, git_root: str | None = None, spec_root: str | None = None, project_canon_dir: str | None = None,
) -> ReleaseGateResult:
    """The release gate on the checkout (see the module text).

    *repo_root* is the toolkit, *spec_dir* the spec folder, *git_root* the host repository (default: the folder that holds the spec
    folder) and *spec_root* the spec folder the project canon lives in when it is not *spec_dir*; *project_canon_dir* is the project canon folder the command discovers (``spec-check`` passes the same).  The previous release is looked up
    from HEAD.  Nothing is written and no bound command runs.
    """
    bind_proof_seams()
    ctx = CheckContext(repo_root=repo_root, spec_dir=spec_dir, git_root=git_root, spec_root=spec_root, project_canon_dir=project_canon_dir)
    run = _Run([], [], [], [], [])
    run.step(lambda: _static_state(ctx, run))
    gctx: GraphCheckContext | None = None
    try:
        gctx = GraphCheckContext.from_registry(ctx)
    except FindingError as exc:
        run.add([exc.error])
    if gctx is None:
        run.add([make_error("E520", _NO_GRAPH, owner=RELEASE_OWNER)])
    else:
        _graph_steps(gctx, run)
    run.step(lambda: _next_release(ctx, run))
    return ReleaseGateResult(tuple(run.errors), tuple(run.warnings), tuple(run.listed), tuple(run.relieved), tuple(run.notes), run.previous)
