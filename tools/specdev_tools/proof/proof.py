"""Proof of an obligation at a gate: what the verifiers the spec declares for it have shown, at which stage.

``proof(graph, ctx, obligation_id, cap)`` answers for one node; ``proof_errors(graph, ctx, scope, cap)`` turns the answers
of a set of nodes into the findings a gate prints.  The routing follows the design: criteria, APIs, invariants and NFRs are
proven by the fixtures (and jobs) that verify them; environments, gates and secrets by the jobs that realise them; a rule by
its enforcer (a job, a listed command or a person's attestation); a threat or an edge case when all its mitigations are; a
functional requirement when all its criteria are; a charter item or capability when everything derived from it is; a task
criterion by its own ``verified_by`` verifier; an obligation that names verifiers in its own ``verified_by`` (one of an
extension) by those too.  Every verifier must be satisfied: the spec declared them all.

A verifier is satisfied at a gate when each of its bindings whose stage is at or below the gate's cap has valid, passing
evidence (``validity``).  A manual fixture and a rule enforced by ``review`` have no binding by design: a valid
attestation record satisfies them.  Nothing here writes a file.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from specdev_tools.core.cli_commands import known_cli_commands
from specdev_tools.core.errors import FindingError, SpecError, make_error, refusal
from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.host_kinds import NAMED_IN_LINK, verifier_naming
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import (
    API_ERROR, DERIVES_FROM, FIXTURE, FR, JOB, MANUAL_MODE, MITIGATED_BY, OBLIGATION_ROLES, REALISES, REFINES, REVIEW_ENFORCER, RULE, TASK_CRITERION,
    VERIFIED_BY, VERIFIER_ROLE, VERIFIES, link_targets,
)
from specdev_tools.graph.ownership import OwnerContext, load_owner_context, owner_for
from specdev_tools.graph.stages import (
    CI_STAGE, DEFAULT_STAGE, STAGES, UnknownStageForEnvironment, bindings_of, is_retired_binding, is_retired_verifier, required_stage, stage_at_least, stage_rank,
)
from specdev_tools.proof.validity import (
    GUARD_NOT_MATCHED, NO_EVIDENCE, NONZERO_EXIT, STAGE_TOO_LOW, STALE_HASH, STALE_TP_VERSION, STALE_TREE, ProofContext, Validity,
    attestation_valid, covers, effective_stage, evidence_for, evidence_valid, same_run,
)
from specdev_tools.trace.coverage import exemption
from specdev_tools.trace.history import contained, containers_of
from specdev_tools.verify.bind import proved_ids
from specdev_tools.verify.records import Binding, Evidence, attestations_about, binding_of

PROVEN = "proven"
PENDING_STAGE = "pending-stage"
UNPROVEN = "unproven"
UNBOUND = "unbound"
NO_VERIFIER = "no-verifier"
NOT_REQUIRED = "not-required"
"""Every verifier of the node is out of play, retired, or (close mode) bound only above the close gate: nothing is asked of it at this gate."""
REASON_UNBOUND = "UNBOUND"
REASON_NO_VERIFIER = "NO_VERIFIER"
STAGE_UNKNOWN = "E334"
OBLIGATION_NOT_PROVEN = "E348"
VERIFIER_NO_VALID_EVIDENCE = "E347"
CLOSE_IGNORED_STAGES = STAGES[STAGES.index(CI_STAGE) + 1:]
"""The stages above ``ci``: the close gate ignores a binding at one of them."""
COARSE_STEPS = ("00", "01")
_CAUSE = {
    NONZERO_EXIT: "the commands failed",
    GUARD_NOT_MATCHED: "the output did not match the guard",
    STALE_TREE: "the code changed since the run",
    STALE_HASH: "the binding, its verifier or a node it proves changed since the run",
    STALE_TP_VERSION: "the run did not record the pinned version of a third party",
    STAGE_TOO_LOW: "the run was at a lower stage than the binding",
    NO_EVIDENCE: "no run has written evidence for it",
}
_FIX_FIRST = (NONZERO_EXIT, GUARD_NOT_MATCHED)
_WAY_OUT = {
    STALE_TP_VERSION: "check the pins with `specdev third-party check` and fix what it names, then run",
}
"""What to do before the run, for a cause the run may not clear: a run records the version the repository declares, so it records the old one until the repository says the pin; when the pins already match, the check names nothing and the run is all that is left."""


@dataclass(frozen=True)
class Shortfall:
    """Why one verifier does not satisfy an obligation: its ``verifier``, its ``binding`` and that binding's ``stage`` (``None`` for a verifier with none) and the ``reason`` (an evidence reason, ``UNBOUND`` or ``NO_VERIFIER``)."""

    verifier: str
    binding: str | None
    reason: str
    stage: str | None = None


@dataclass(frozen=True)
class ProofResult:
    """The proof of one obligation: its ``status`` (``PROVEN``, ``PENDING_STAGE``, ``UNPROVEN``, ``UNBOUND``, ``NO_VERIFIER`` or ``NOT_REQUIRED``) and, for the statuses that fail, what fell short."""

    obligation: str
    status: str
    shortfalls: tuple[Shortfall, ...] = ()


@dataclass(frozen=True)
class _Outcome:
    """How one verifier stands: a status of ``ProofResult`` and the shortfalls when it fails."""

    status: str
    shortfalls: tuple[Shortfall, ...] = ()


_PRECEDENCE = (UNPROVEN, UNBOUND, NO_VERIFIER, PENDING_STAGE)


def _combine(obligation: str, outcomes: Sequence[_Outcome]) -> ProofResult:
    """One result from the outcomes of all the verifiers: failures first (``_PRECEDENCE``), then proven, then not required.

    A shortfall two outcomes share (one binding reached by two mitigations of the node) is listed once.
    """
    if not outcomes:
        return ProofResult(obligation, NO_VERIFIER, (Shortfall(obligation, None, REASON_NO_VERIFIER),))
    for status in _PRECEDENCE:
        matching = [outcome for outcome in outcomes if outcome.status == status]
        if matching:
            return ProofResult(obligation, status, tuple(dict.fromkeys(shortfall for outcome in matching for shortfall in outcome.shortfalls)))
    return ProofResult(obligation, PROVEN if any(outcome.status == PROVEN for outcome in outcomes) else NOT_REQUIRED)


def is_attested_by_person(node: Node, graph: Graph) -> bool:
    """Whether *node* is satisfied by a person's attestation and not by a run: a fixture with ``mode: manual``, or a rule enforced by ``review``."""
    item = item_of(graph, node) or {}
    if node.kind == FIXTURE:
        return item.get("mode") == MANUAL_MODE
    return node.kind == RULE and item.get("enforcer") == REVIEW_ENFORCER


def _needed_stage(graph: Graph, obligation: Node | None, verifier: Node) -> str:
    """The stage the obligation needs proof at, as far as a stored binding can be held to it.

    Raises:
        FindingError: E334 when the stage cannot be told (an environment that is not a stage, or an NFR with a stage that is not one): such a node is not proven.
    """
    if obligation is None:
        return DEFAULT_STAGE
    try:
        return required_stage(obligation, graph, verifier if verifier.kind == JOB else None)
    except UnknownStageForEnvironment as exc:
        raise refusal(STAGE_UNKNOWN, f"environment '{exc.environment}' is not a stage; name it dev, ci, staging or prod") from exc
    except ValueError as exc:
        raise refusal(STAGE_UNKNOWN, str(exc)) from exc


class _Prover:
    """One run of ``proof``: the graph, the context, the gate and the evidence of runs not stored."""

    def __init__(self, graph: Graph, ctx: ProofContext, cap: str, treat_ci_as_dev: bool, transient: Iterable[Evidence]) -> None:
        stage_rank(cap)
        self.graph, self.ctx, self.cap, self.treat_ci_as_dev = graph, ctx, cap, treat_ci_as_dev
        self.transient = {evidence.evidence_id: evidence for evidence in transient}
        self._commands: frozenset[str] | None = None

    # --- bindings and evidence -------------------------------------------------------------------------------------

    def _evidence(self, binding: Binding) -> list[Evidence]:
        stored = {evidence.evidence_id: evidence for evidence in evidence_for(binding, self.ctx)}
        stored.update({key: evidence for key, evidence in self.transient.items() if binding.id in evidence.about})
        return list(stored.values())

    def _satisfied(self, binding: Binding) -> Validity:
        """Whether a run of *binding*, or of another binding of the same verifier with the same commands and guard, proves it now."""
        verifier = self.graph.by_id[binding.verifier]
        siblings = [binding_of(node, self.graph) for node in bindings_of(verifier, self.graph)]
        candidates = [evidence for sibling in siblings if same_run(binding, sibling) for evidence in self._evidence(sibling) if covers(evidence, binding, self.graph)]
        verdicts = [(evidence, evidence_valid(evidence, binding, self.graph, self.ctx, treat_ci_as_dev=self.treat_ci_as_dev)) for evidence in candidates]
        for _evidence, verdict in verdicts:
            if verdict.valid:
                return verdict
        if not verdicts:
            return Validity(False, NO_EVIDENCE)
        best = max(verdicts, key=lambda pair: stage_rank(pair[0].stage))
        return best[1]

    def _names(self, binding: Binding, verifier: Node, obligation: Node | None) -> bool:
        """Whether *binding* is a binding for *obligation*: it proves it, a node it contains or a node that contains it; any binding when there is no obligation."""
        if obligation is None or obligation.id == binding.verifier:
            return True
        related = contained(self.graph, obligation.id) | set(containers_of(self.graph, obligation))
        return bool(set(proved_ids(binding, self.graph)) & related)

    def _bindings_for(self, verifier: Node, obligation: Node | None) -> list[Binding]:
        needed = _needed_stage(self.graph, obligation, verifier)
        bindings = (binding_of(node, self.graph) for node in bindings_of(verifier, self.graph) if not is_retired_binding(node, self.graph))
        return [b for b in bindings if self._names(b, verifier, obligation) and stage_at_least(b.stage, needed)]

    # --- one verifier ----------------------------------------------------------------------------------------------

    def _ignored_in_close(self, binding: Binding) -> bool:
        return self.treat_ci_as_dev and binding.stage in CLOSE_IGNORED_STAGES

    def _attested(self, verifier: Node, obligation: Node | None) -> _Outcome:
        needed = _needed_stage(self.graph, obligation, verifier) if obligation is not None and obligation.kind != RULE else DEFAULT_STAGE
        if not stage_at_least(self.cap, needed):
            return _Outcome(PENDING_STAGE)
        reason = NO_EVIDENCE
        for attestation in attestations_about(self.graph, verifier.id):
            verdict = attestation_valid(attestation, verifier.id, self.graph, self.ctx)
            if verdict.valid and stage_at_least(attestation.stage, needed):
                return _Outcome(PROVEN)
            reason = verdict.reason or STAGE_TOO_LOW
        return _Outcome(UNPROVEN, (Shortfall(verifier.id, None, reason),))

    def verifier_outcome(self, verifier: Node, obligation: Node | None) -> _Outcome:
        """How *verifier* stands for *obligation* (any when ``None``) at this gate."""
        bindings = self._bindings_for(verifier, obligation)
        if not bindings and is_attested_by_person(verifier, self.graph) and not bindings_of(verifier, self.graph):
            return self._attested(verifier, obligation)
        if not bindings:
            return _Outcome(UNBOUND, (Shortfall(verifier.id, None, REASON_UNBOUND),))
        considered = [binding for binding in bindings if not self._ignored_in_close(binding)]
        if not considered:
            return _Outcome(NOT_REQUIRED)
        due = [binding for binding in considered if stage_at_least(self.cap, effective_stage(binding.stage, self.treat_ci_as_dev))]
        if not due:
            return _Outcome(PENDING_STAGE)
        for binding in due:
            verdict = self._satisfied(binding)
            if not verdict.valid:
                return _Outcome(UNPROVEN, (Shortfall(verifier.id, binding.id, verdict.reason or NO_EVIDENCE, binding.stage),))
        return _Outcome(PROVEN)

    # --- obligations -----------------------------------------------------------------------------------------------

    def _verifiers_of(self, node: Node) -> list[Node]:
        """The in-play verifiers of *node*: those that name it in ``verifies`` or ``realises``, then those it names in its own ``verified_by``."""
        naming = [self.graph.by_id.get(link.source) for link in self.graph.incoming.get(node.id, ()) if link.field in (VERIFIES, REALISES)]
        named = [self.graph.by_id.get(name) for name in link_targets(self.graph, node, VERIFIED_BY)]
        found = {source.id: source for source in (*naming, *named) if source is not None and source.role == VERIFIER_ROLE}
        return [verifier for verifier in found.values() if exemption(verifier) is None]

    def _in_play_verifiers(self, node: Node) -> tuple[list[Node], bool]:
        """The verifiers of *node* that are in play and not retired, and whether it has any at all."""
        everyone = self._verifiers_of(node)
        return [verifier for verifier in everyone if not is_retired_verifier(verifier, self.graph)], bool(everyone)

    def _known_commands(self) -> frozenset[str]:
        if self._commands is None:
            self._commands = known_cli_commands(resolve_effective_toolkit_root(None))
        return self._commands

    def _rule(self, node: Node) -> list[_Outcome]:
        item = item_of(self.graph, node) or {}
        command = item.get("cli_command")
        if isinstance(command, str):
            if command not in self._known_commands():
                return []
            return [self.verifier_outcome(node, node)] if bindings_of(node, self.graph) else [_Outcome(PROVEN)]
        if item.get("enforcer") == REVIEW_ENFORCER:
            return [self.verifier_outcome(node, node)]
        return self._by_verifiers(node)

    def _by_verifiers(self, node: Node) -> list[_Outcome]:
        verifiers, any_verifier = self._in_play_verifiers(node)
        if any_verifier and not verifiers:
            return [_Outcome(NOT_REQUIRED)]
        return [self.verifier_outcome(verifier, node) for verifier in verifiers]

    @staticmethod
    def _as_outcome(result: ProofResult) -> _Outcome:
        return _Outcome(result.status, result.shortfalls)

    def _derived(self, nodes: Iterable[Node], visiting: frozenset[str]) -> list[_Outcome]:
        """The outcomes of the nodes a coarse item or a container rests on: the proof of each of them that is an obligation and in play (one that nothing verifies fails the whole)."""
        outcomes: list[_Outcome] = []
        for node in nodes:
            if node.role not in OBLIGATION_ROLES or exemption(node) is not None or node.id in visiting:
                continue
            outcomes.append(self._as_outcome(self._prove(node, visiting | {node.id})))
        return outcomes

    def _task_criterion(self, node: Node) -> list[_Outcome]:
        verifiers = [self.graph.by_id[name] for name in link_targets(self.graph, node, VERIFIED_BY) if name in self.graph.by_id]
        verifiers = [verifier for verifier in verifiers if verifier.role == VERIFIER_ROLE and exemption(verifier) is None and not is_retired_verifier(verifier, self.graph)]
        refined = [self.graph.by_id[name] for name in link_targets(self.graph, node, REFINES) if name in self.graph.by_id]
        return [self.verifier_outcome(verifier, obligation) for verifier in verifiers for obligation in (refined or [None])]

    def _mitigated(self, node: Node, visiting: frozenset[str]) -> list[_Outcome]:
        outcomes: list[_Outcome] = []
        for name in link_targets(self.graph, node, MITIGATED_BY):
            mitigation = self.graph.by_id.get(name)
            if mitigation is None or name in visiting:
                continue
            if mitigation.role == VERIFIER_ROLE:
                outcomes.append(self.verifier_outcome(mitigation, None))
            else:
                outcomes.append(self._as_outcome(self._prove(mitigation, visiting | {name})))
        return outcomes

    def _outcomes(self, node: Node, visiting: frozenset[str]) -> list[_Outcome]:
        if node.kind == TASK_CRITERION:
            return self._task_criterion(node)
        if node.role == VERIFIER_ROLE:
            return [self.verifier_outcome(node, None)]
        if node.kind == API_ERROR and node.parent in self.graph.by_id:
            return self._derived([self.graph.by_id[node.parent]], visiting)
        if link_targets(self.graph, node, MITIGATED_BY):
            return self._mitigated(node, visiting)
        direct = self._rule(node) if node.kind == RULE else self._by_verifiers(node)
        if direct or self._verifiers_of(node):
            return direct
        if node.step in COARSE_STEPS:
            sources = (self.graph.by_id.get(link.source) for link in self.graph.incoming.get(node.id, ()) if link.field == DERIVES_FROM)
            return self._derived((source for source in sources if source is not None), visiting)
        if node.kind == FR:
            return self._derived((self.graph.by_id[child] for child in self.graph.children.get(node.id, ())), visiting)
        return []

    def _prove(self, node: Node, visiting: frozenset[str]) -> ProofResult:
        return _combine(node.id, self._outcomes(node, visiting))

    def prove(self, obligation_id: str) -> ProofResult:
        node = self.graph.find(obligation_id)
        if node is None:
            raise KeyError(obligation_id)
        return self._prove(node, frozenset({node.id}))


def proof(
    graph: Graph, ctx: ProofContext, obligation_id: str, cap: str, *, treat_ci_as_dev: bool = False, transient_evidence: Sequence[Evidence] | None = None,
) -> ProofResult:
    """The proof of the node *obligation_id* at the gate whose highest stage is *cap* (``dev`` at close, ``ci`` at merge and release CI, ``staging`` at the production-deploy gate, ``prod`` at the next release).

    ``PROVEN``: every verifier is satisfied at stages up to *cap*.  ``PENDING_STAGE``: a verifier's bindings are all above
    *cap*.  ``UNPROVEN``: a binding has no valid passing evidence (``shortfalls`` give the reason).  ``UNBOUND``: a verifier
    has no binding for it.  ``NO_VERIFIER``: nothing verifies it (a task criterion with no ``verified_by`` too).  ``NOT_REQUIRED``:
    every verifier is out of play or retired, or ignored at this gate.

    With *treat_ci_as_dev* (the close gate) a ``ci`` binding counts as ``dev`` and a ``staging`` or ``prod`` binding is ignored.
    *transient_evidence* is the evidence of runs made with ``record=False``: it counts for this call like stored evidence
    and replaces the stored file of the same id.

    Raises:
        KeyError: no node has the id *obligation_id*.
        ValueError: *cap* is not a stage.
        FindingError: E334 when the stage a verifier of the node needs cannot be told.
        GitViewError: E708 when git fails.
        FindingError: E520 when the host declarations cannot be read.
    """
    return _Prover(graph, ctx, cap, treat_ci_as_dev, transient_evidence or ()).prove(obligation_id)


def verifier_proof(
    graph: Graph, ctx: ProofContext, verifier_id: str, cap: str, *, treat_ci_as_dev: bool = False, transient_evidence: Sequence[Evidence] | None = None,
) -> ProofResult:
    """Whether the verifier *verifier_id* (a fixture, a job or a rule) is satisfied at *cap*, whatever it proves: the keywords and the statuses of ``proof``.

    ``UNBOUND``: it has no binding (and is not a manual fixture or a review rule); ``UNPROVEN``: a binding at or below *cap* has no
    valid passing evidence (``NO_EVIDENCE`` when no run wrote a file, ``STALE_TREE`` when the evidence is on another code tree,
    ``STAGE_TOO_LOW`` when it is at a lower stage); ``PENDING_STAGE``: every binding is above *cap*; ``NOT_REQUIRED``: every
    binding is retired, or ignored by the close gate.

    Raises:
        KeyError: no node has the id *verifier_id*.
        ValueError: *cap* is not a stage.
        GitViewError: E708 when git fails.
        FindingError: E520 when the host declarations cannot be read.
    """
    prover = _Prover(graph, ctx, cap, treat_ci_as_dev, transient_evidence or ())
    node = graph.find(verifier_id)
    if node is None:
        raise KeyError(verifier_id)
    outcome = _Outcome(NOT_REQUIRED) if is_retired_verifier(node, graph) else prover.verifier_outcome(node, None)
    return _combine(node.id, [outcome])


def _advice(shortfall: Shortfall) -> str:
    if shortfall.reason == REASON_UNBOUND:
        return f"bind it with `specdev verify bind {shortfall.verifier} --command \"<command>\" --guard \"<regex>\"`"
    if shortfall.binding is None:
        return f"a person attests it: run `specdev verify attest {shortfall.verifier}`"
    command = f"`specdev verify run {shortfall.binding} --stage {shortfall.stage}`"
    first = _WAY_OUT.get(shortfall.reason, "fix it, then run" if shortfall.reason in _FIX_FIRST else "run")
    return f"{_CAUSE[shortfall.reason]}; {first} {command}"


def _way_to_a_verifier(graph: Graph, lacking: Node | None) -> str:
    """What gives the node *lacking* a verifier: a fixture or a job that verifies it, or, for an obligation of an extension, its own ``verified_by``."""
    naming = verifier_naming(graph, lacking) if lacking is not None else None
    if naming is None:
        return "add a fixture or a job that verifies it"
    if naming == NAMED_IN_LINK:
        return f"name a fixture or a job in verified_by of {lacking.id}"
    return (
        f"the kind {lacking.kind} declares no verified_by link; declare one to a fixture or a job in the schema of its extension, "
        f"then name the verifier in verified_by of {lacking.id}"
    )


def _finding(graph: Graph, node: Node, shortfall: Shortfall, owners: OwnerContext) -> SpecError:
    if shortfall.reason == REASON_NO_VERIFIER:
        lacking = f"{node.kind} {node.id}" + ("" if shortfall.verifier == node.id else f": {shortfall.verifier}")
        code, message = OBLIGATION_NOT_PROVEN, f"{lacking} has no verifier to prove it: {_way_to_a_verifier(graph, graph.find(shortfall.verifier))}"
    elif shortfall.reason == REASON_UNBOUND:
        code, message = OBLIGATION_NOT_PROVEN, f"{node.kind} {node.id}: its verifier {shortfall.verifier} has no binding; {_advice(shortfall)}"
    else:
        what = f"binding {shortfall.binding}" if shortfall.binding else f"verifier {shortfall.verifier}"
        code, message = VERIFIER_NO_VALID_EVIDENCE, f"{node.kind} {node.id}: {what} has no valid evidence ({shortfall.reason}): {_advice(shortfall)}"
    return make_error(
        code, message, file=node.file, jq_path=node.jq_path or None, node_id=node.id, subcode=shortfall.reason, owner=owner_for(code, node, owners),
    )


def _stage_finding(node: Node, error: SpecError, owners: OwnerContext) -> SpecError:
    """The E334 the proof of *node* raised (its stage cannot be told), as a finding about *node*."""
    return make_error(
        error.code, f"{node.kind} {node.id}: {error.message}", file=node.file, jq_path=node.jq_path or None, node_id=node.id, owner=owner_for(error.code, node, owners),
    )


def proof_errors(
    graph: Graph, ctx: ProofContext, scope: Collection[str], cap: str, *, treat_ci_as_dev: bool = False, transient_evidence: Sequence[Evidence] | None = None,
) -> list[SpecError]:
    """The findings of the gate that checks the nodes *scope* at *cap* (the keywords as ``proof``): E347 for each binding with no valid evidence, E348 for a verifier with no binding or a node with no verifier.

    A node that is proven, pending a higher stage or not required gives nothing.  An id of *scope* that names no node is
    skipped.  A node whose stage cannot be told (an environment that is not a stage) gives E334 instead.  The owner of a finding is the one the ownership table gives for the node (its step).  Findings come in the order of *scope*.
    """
    owners = load_owner_context(resolve_effective_toolkit_root(None))
    prover = _Prover(graph, ctx, cap, treat_ci_as_dev, transient_evidence or ())
    findings: list[SpecError] = []
    for obligation_id in scope:
        node = graph.find(obligation_id)
        if node is None:
            continue
        try:
            findings.extend(_finding(graph, node, shortfall, owners) for shortfall in prover.prove(node.id).shortfalls)
        except FindingError as exc:
            if exc.error.code != STAGE_UNKNOWN:
                raise
            findings.append(_stage_finding(node, exc.error, owners))
    return findings
