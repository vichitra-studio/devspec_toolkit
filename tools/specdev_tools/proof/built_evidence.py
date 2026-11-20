"""The proof package's share of the graph checks: three seams of the check context and the evidence branches of "built".

``bind_proof_seams`` binds ``retired_bindings``, ``record_users`` and ``pin_matches`` of ``validation.graph_checks.context``
(``cli.py`` calls it when it builds the parser, which every command does, and ``validation/spec_check.py`` calls it where
it registers the checks, which a caller that runs the checks in process reaches).  ``extra_verifiers`` keeps its default, the empty set: a job's ``verifies`` link is
stored in step 12 and the checks read it themselves.

``built_at_cap(ctx, cap)`` is ``compute_built`` with the evidence branches registered for a gate whose highest stage is
*cap*; the plain ``compute_built`` leaves the evidence kinds ``PENDING_EVIDENCE``.  The branches (DOC 5.3):

- an environment, a gate or a secret is built when the job that realises it is proven (``proof``);
- a step-10 rule is built when a job that realises it is proven, or when its ``cli_command`` is in the command list
  (``proof`` holds both); a rule enforced by ``review`` is left to the default branch (M8);
- a threat or an edge case is built when it has a mitigation, every obligation that mitigates it is built and every fixture
  that mitigates it is proven; zero mitigations is not built;
- an NFR keeps the default branch (a closed milestone refines it), and is ``RELIEVED`` when that makes it built and its
  proof waits only for a stage above *cap*.

A context with no host root, or a host whose code tree cannot be read, leaves every one of these ``PENDING_EVIDENCE``, as
before this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from specdev_tools.core.errors import FindingError
from specdev_tools.core.host_declarations import HostDeclarationsError, load_host_declarations
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.gitview import GitViewError
from specdev_tools.graph.model import Graph, Node
from specdev_tools.proof.proof import NOT_REQUIRED, PENDING_STAGE, PROVEN, REASON_NO_VERIFIER, REASON_UNBOUND, ProofResult, proof, verifier_proof
from specdev_tools.graph.stages import STAGES, binding_stage, bindings_of, is_retired_binding, retired_binding_ids, stage_at_least, stage_rank
from specdev_tools.proof.validity import ProofContext
from specdev_tools.thirdparty.check import check_pins
from specdev_tools.validation.graph_checks.built import (
    EVIDENCE_KINDS, PIN_MISMATCH, PIN_OK, BuiltComputation, BuiltResult, BuiltState, combine, compute_built,
    register_built_provider,
)
from specdev_tools.validation.graph_checks.context import PIN_UNKNOWN, GraphCheckContext, bind_seams
from specdev_tools.graph.names import ABOUT, BINDING_KIND, NFR, OBLIGATION_ROLES, REALISES, REVIEW_ENFORCER, RULE, THIRD_PARTY, VERIFIER_ROLE, VERIFIES
from specdev_tools.validation.graph_checks.refinement import mitigations
from specdev_tools.verify.records import EVIDENCE_KIND, records_folder

THREAT_KINDS = frozenset({"threat", "edge-case"})
_PROOF_KEY = "proof-context"
_PINS_KEY = "pin-results"
_RECORD_LINKS = {BINDING_KIND: VERIFIES, EVIDENCE_KIND: ABOUT}
"""For each kind of record, the link field through which it names a verifier."""
_NO_HOST = "no host repository to read evidence from"


# --- the seams ----------------------------------------------------------------------------------------------------------


def retired_bindings(ctx: GraphCheckContext, verifier: Node) -> set[str]:
    """The seam ``Seams.retired_bindings``: the bindings of *verifier* when it has some and all are retired, else empty."""
    return retired_binding_ids(verifier, ctx.graph)


def record_users(ctx: GraphCheckContext, verifier: Node) -> set[str]:
    """The seam ``Seams.record_users``: the ids of the verification records that ``verifies`` *verifier* and of the evidence records whose ``about`` names it (an old name resolves to it)."""
    found: set[str] = set()
    for link in ctx.graph.incoming.get(verifier.id, ()):
        holder = ctx.graph.by_id.get(link.source)
        if holder is not None and _RECORD_LINKS.get(holder.kind) == link.field:
            found.add(holder.id)
    return found


def pin_matches(ctx: GraphCheckContext, third_party: Node) -> str:
    """The seam ``Seams.pin_matches``: ``OK`` when every source the host declares for *third_party* reads its pin, ``MISMATCH`` when one differs or cannot be read, ``UNKNOWN`` when it has no declared source, when the context has no host root or when the declarations file cannot be read."""
    return _pin_results(ctx).get(third_party.id, PIN_UNKNOWN)


def _pin_results(ctx: GraphCheckContext) -> dict[str, str]:
    """``OK`` or ``MISMATCH`` for each third party with a declared source, read once for the context."""
    if _PINS_KEY not in ctx.memo:
        ctx.memo[_PINS_KEY] = _read_pins(ctx)
    return ctx.memo[_PINS_KEY]


def _read_pins(ctx: GraphCheckContext) -> dict[str, str]:
    if ctx.git_root is None or ctx.spec_root is None:
        return {}
    try:
        declarations = load_host_declarations(ctx.spec_root)
    except HostDeclarationsError:
        return {}
    wrong = {finding.node_id for finding in check_pins(ctx.graph, declarations, ctx.git_root)}
    sourced = (ctx.graph.by_id.get(ctx.graph.canonical_id(name)) for name in declarations.pin_sources)
    return {node.id: PIN_MISMATCH if node.id in wrong else PIN_OK for node in sourced if node is not None and node.kind == THIRD_PARTY}


@cache
def bind_proof_seams() -> None:
    """Bind the three seams to their implementations for every context built afterwards; the first call binds, a later one does nothing."""
    bind_seams(retired_bindings=retired_bindings, record_users=record_users, pin_matches=pin_matches)


# --- the evidence branches ----------------------------------------------------------------------------------------------


def proof_context(ctx: GraphCheckContext) -> ProofContext | None:
    """The proof context of the host of *ctx* (its code tree and hashes are read when first asked), built once for *ctx*; ``None`` for a context with no host root."""
    if ctx.git_root is None or ctx.spec_root is None:
        return None
    if _PROOF_KEY not in ctx.memo:
        ctx.memo[_PROOF_KEY] = ProofContext(ctx.git_root, ctx.spec_root, records_folder(ctx.spec_root))
    return ctx.memo[_PROOF_KEY]


def _waits_for(graph: Graph, node: Node, cap: str) -> str:
    """The lowest stage above *cap* at which a live binding of *node*, or of a verifier that ``verifies`` or ``realises`` it, is made; the stage after *cap* when none is found."""
    sources = (graph.by_id.get(link.source) for link in graph.incoming.get(node.id, ()) if link.field in (VERIFIES, REALISES))
    verifiers = [node, *(source for source in sources if source is not None and source.role == VERIFIER_ROLE)]
    stages = [
        binding_stage(record, graph) for verifier in verifiers for record in bindings_of(verifier, graph) if not is_retired_binding(record, graph)
    ]
    above = [stage for stage in stages if not stage_at_least(cap, stage)]
    return min(above, key=stage_rank) if above else STAGES[min(stage_rank(cap) + 1, len(STAGES) - 1)]


def _unproven_reason(result: ProofResult) -> str:
    """Why *result* (an ``UNPROVEN``, ``UNBOUND`` or ``NO_VERIFIER`` proof) is not built, in a few words."""
    shortfall = result.shortfalls[0] if result.shortfalls else None
    if shortfall is None or shortfall.reason == REASON_NO_VERIFIER:
        return "no verifier proves it"
    if shortfall.reason == REASON_UNBOUND:
        return f"its verifier {shortfall.verifier} has no binding"
    return f"{shortfall.binding or shortfall.verifier} has no valid evidence ({shortfall.reason})"


def _relieved(graph: Graph, node: Node, cap: str, reason: str) -> BuiltResult:
    return BuiltResult(BuiltState.RELIEVED, reason, waits_for=_waits_for(graph, node, cap))


def _from_proof(graph: Graph, node: Node, result: ProofResult, cap: str) -> BuiltResult:
    """The built state the proof *result* of *node* gives: proven (or nothing asked) is built, a proof that waits for a stage above *cap* is relieved, anything else is not built."""
    if result.status == PROVEN:
        return BuiltResult(BuiltState.BUILT, f"proven at stage {cap}")
    if result.status == NOT_REQUIRED:
        return BuiltResult(BuiltState.BUILT, "nothing is asked of its verifiers at this gate")
    if result.status == PENDING_STAGE:
        return _relieved(graph, node, cap, "its proof waits for a later stage")
    return BuiltResult(BuiltState.NOT_BUILT, _unproven_reason(result))


@dataclass(frozen=True)
class _EvidenceBranches:
    """The evidence branches for the gate whose highest stage is ``cap``: ``claims`` says which nodes they decide, calling the instance decides one."""

    graph: Graph
    cap: str

    def claims(self, node: Node) -> bool:
        """Whether the branches decide *node*: an obligation of an evidence kind, except a rule enforced by ``review``, and an NFR."""
        if node.role not in OBLIGATION_ROLES:
            return False
        if node.kind == RULE:
            return (item_of(self.graph, node) or {}).get("enforcer") != REVIEW_ENFORCER
        return node.kind in EVIDENCE_KINDS or node.kind == NFR

    def __call__(self, computation: BuiltComputation, node: Node) -> BuiltResult:
        """The state of *node* from its proof; a proof that cannot be made (E334: the stage cannot be told) is not built, with the finding's message as the reason."""
        if node.kind == NFR:
            return self._nfr(computation, node)
        host = proof_context(computation.ctx)
        if host is None:
            return BuiltResult(BuiltState.PENDING_EVIDENCE, _NO_HOST)
        try:
            if node.kind in THREAT_KINDS:
                return self._threat(computation, node, host)
            return _from_proof(self.graph, node, proof(self.graph, host, node.id, self.cap), self.cap)
        except GitViewError as exc:
            return BuiltResult(BuiltState.PENDING_EVIDENCE, f"the code tree cannot be read: {exc}")
        except FindingError as exc:
            return BuiltResult(BuiltState.NOT_BUILT, exc.error.message)

    def _nfr(self, computation: BuiltComputation, node: Node) -> BuiltResult:
        """The default state; relieved when that is built and the proof of the NFR waits only for a stage above the cap (an unreadable host leaves the default)."""
        default = computation.by_default(node)
        host = proof_context(computation.ctx)
        if default.state is not BuiltState.BUILT or host is None:
            return default
        try:
            result = proof(self.graph, host, node.id, self.cap)
        except GitViewError:
            return default
        except FindingError as exc:
            return BuiltResult(BuiltState.NOT_BUILT, exc.error.message)
        return _relieved(self.graph, node, self.cap, default.reason + "; its proof waits for a later stage") if result.status == PENDING_STAGE else default

    def _threat(self, computation: BuiltComputation, node: Node, host: ProofContext) -> BuiltResult:
        """Built when every in-play mitigation is (a fixture by its proof, any other obligation by the engine) and there is at least one; relieved when a mitigation is."""
        members = [(mitigation.id, self._mitigation(computation, mitigation, host)) for mitigation in mitigations(self.graph, node) if computation.ctx.in_play(mitigation)]
        if not members:
            return BuiltResult(BuiltState.NOT_BUILT, "it has no mitigation in play")
        decided = combine(members, "mitigation")
        waiting = [result for _id, result in members if result.state is BuiltState.RELIEVED]
        if decided.state is BuiltState.BUILT and waiting:
            return BuiltResult(BuiltState.RELIEVED, "a mitigation waits for a later stage", decided.via, min((r.waits_for for r in waiting if r.waits_for), key=stage_rank, default=None))
        return decided

    def _mitigation(self, computation: BuiltComputation, mitigation: Node, host: ProofContext) -> BuiltResult:
        if mitigation.role != VERIFIER_ROLE:
            return computation.result_of(mitigation)
        return _from_proof(self.graph, mitigation, verifier_proof(self.graph, host, mitigation.id, self.cap), self.cap)


def built_at_cap(ctx: GraphCheckContext, cap: str, node_id: str | None = None) -> dict[str, BuiltResult]:
    """``compute_built(ctx, node_id)`` with the evidence branches of the gate whose highest stage is *cap* (``ci`` at the release gate, ``staging`` at the production-deploy gate).

    The branches are registered for the call and removed after it, whatever happens.

    Raises:
        ValueError: *cap* is not a stage.
        KeyError: *node_id* names no node of the graph.
        FindingError: E520 when the host declarations cannot be read.
    """
    stage_rank(cap)
    branches = _EvidenceBranches(ctx.graph, cap)
    restore = register_built_provider(branches.claims, branches)
    try:
        return compute_built(ctx, node_id)
    finally:
        restore()


def built_state(ctx: GraphCheckContext, node: Node, cap: str) -> BuiltResult:
    """The built state of *node* at *cap*: ``BUILT``, ``RELIEVED`` (``waits_for`` names the stage) or ``NOT_BUILT`` (see ``built_at_cap``)."""
    return built_at_cap(ctx, cap, node.id)[node.id]


def relieved_nodes(ctx: GraphCheckContext, cap: str) -> list[Node]:
    """The nodes that are ``RELIEVED`` at *cap*, in listing order: what the production-deploy gate and the next-release check must re-check (see ``built_at_cap``)."""
    found = (ctx.graph.by_id[node_id] for node_id, result in built_at_cap(ctx, cap).items() if result.state is BuiltState.RELIEVED)
    return list(found)

