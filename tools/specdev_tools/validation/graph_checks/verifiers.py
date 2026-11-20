"""The verifier rules: an unused verifier (E742) and an obligation no verifier names (E743).

**Unused (E742).**  A verifier (a fixture or a job) is used when a node that is in play lists it in ``verified_by`` (a
criterion of a closed milestone counts: the fixture is used, not unused), when a record names it (the ``record_users``
seam, empty until M7), or, for a job, when it ``realises`` a node that is in play or ``verifies`` one.  A job reached
only through ``depends_on`` is not used.

**Missing (E743).**  A node that is in play and in scope, of a kind a fixture's ``verifies`` may name (read from the
registry declarations: today criterion, API, invariant and NFR), with no verifier in play that names it.  An NFR may
be verified by a job as well as by a fixture, and the message names both fixes.  Not an obligation of a fixture, and
never reported: an API error (proven with its API), a threat, an edge case, a rule, a node a closed milestone's removal
criterion ``removes``.  The owner is the one the ownership table gives (step 14 for E742, step 08 for E743).

``missing_verifiers`` is the single detector the proof milestone (M7) calls.
"""
from __future__ import annotations

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.model import Graph, Node

from .codes import MISSING_VERIFIER, UNUSED_VERIFIER
from .context import GraphCheckContext, Mode
from .names import FIXTURE, REALISES, REMOVES, VERIFIED_BY, VERIFIER_ROLE, VERIFIES, link_targets
from .removal import links_clause



def _verifiers(ctx: GraphCheckContext) -> list[Node]:
    return [node for node in ctx.in_play_nodes() if node.role == VERIFIER_ROLE]


def _in_play_targets(ctx: GraphCheckContext, node: Node, field: str) -> list[Node]:
    targets = (ctx.graph.by_id.get(target_id) for target_id in link_targets(ctx.graph, node, field))
    return [target for target in targets if target is not None and ctx.in_play(target)]


def _is_used(ctx: GraphCheckContext, verifier: Node) -> bool:
    """Whether a node in play lists *verifier* in ``verified_by``, a record names it, or it ``realises`` or ``verifies`` a node in play."""
    for link in ctx.graph.incoming.get(verifier.id, ()):
        holder = ctx.graph.by_id.get(link.source)
        if link.field == VERIFIED_BY and holder is not None and ctx.in_play(holder):
            return True
    if ctx.record_users(verifier):
        return True
    return verifier.kind != FIXTURE and bool(_in_play_targets(ctx, verifier, REALISES) or _in_play_targets(ctx, verifier, VERIFIES))


def _verifiable_kinds(graph: Graph) -> frozenset[str]:
    """The kinds the ``verifies`` link of a fixture accepts, read from the registry declarations."""
    fixture = graph.decls.get(FIXTURE)
    return frozenset(kind for link in (fixture.links if fixture else ()) if link.field == VERIFIES for kind in link.kinds)


def _verified_ids(ctx: GraphCheckContext) -> set[str]:
    """The ids that a verifier in play names in ``verifies`` or through the ``extra_verifiers`` seam."""
    named: set[str] = set()
    for verifier in _verifiers(ctx):
        named.update(link_targets(ctx.graph, verifier, VERIFIES))
        named.update(ctx.graph.canonical_id(name) for name in ctx.extra_verifiers(verifier))
    return named


def _removed_by_closed_milestone(ctx: GraphCheckContext, node: Node, historical: set[str]) -> bool:
    return any(link.field == REMOVES and link.source in historical for link in ctx.graph.incoming.get(node.id, ()))


def missing_verifiers(ctx: GraphCheckContext) -> list[Node]:
    """The nodes in play and in scope of a kind a fixture can verify that no verifier in play names, in step then id order; empty when the registry declares no fixture."""
    kinds = _verifiable_kinds(ctx.graph)
    if not kinds:
        return []
    verified = _verified_ids(ctx)
    historical = ctx.historical
    return [
        node for node in ctx.in_play_nodes()
        if node.kind in kinds and node.id not in verified and not _removed_by_closed_milestone(ctx, node, historical)
    ]


def _fixes(graph: Graph, kind: str) -> str:
    """The fixes that clear E743 for a node of *kind*: each verifier kind whose ``verifies`` accepts it, with its step.

    A fixture is used only when a task criterion lists it in ``verified_by`` (E742), so its fix says so; a job that
    ``verifies`` a node is used by that.
    """
    options = []
    for decl in graph.decls.values():
        if decl.role == VERIFIER_ROLE and any(link.field == VERIFIES and link.accepts(kind) for link in decl.links):
            steps = graph.shape.kind_steps.get(decl.kind, ())
            where = f"a {decl.kind} at step {'/'.join(steps)}" if steps else f"a {decl.kind}"
            options.append(f"{where} that verifies it" + (" and that a task criterion lists in verified_by" if decl.kind == FIXTURE else ""))
    return ", or ".join(options)


def check_verifier_rules(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E742 for each verifier in play that nothing uses, then E743 for each node a verifier should name and none does; each group in step then id order."""
    unused = [
        ctx.finding(
            UNUSED_VERIFIER, verifier,
            f"{verifier.kind} {verifier.id} is not used: no task criterion lists it in verified_by"
            + ("" if verifier.kind == FIXTURE else ", and it neither realises nor verifies a node")
            + "; list it in a criterion's verified_by, or remove it"
            + (f" and the links to it {clause}" if (clause := links_clause(ctx.graph, verifier.id)) else "")
            + " and run specdev attest --prune",
        )
        for verifier in _verifiers(ctx) if not _is_used(ctx, verifier)
    ]
    missing = [
        ctx.finding(
            MISSING_VERIFIER, node,
            f"{node.kind} {node.id} has no verifier: add {_fixes(ctx.graph, node.kind)}",
        )
        for node in missing_verifiers(ctx)
    ]
    return unused + missing
