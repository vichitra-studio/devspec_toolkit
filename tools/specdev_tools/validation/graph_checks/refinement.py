"""The refinement check (E745): the verifier of a task criterion must verify the obligation the criterion refines.

A verifier ``V`` of a criterion covers an obligation ``O`` when ``V`` names ``O``, a container of ``O`` or a node
``O`` contains in ``verifies`` (or in the ``extra_verifiers`` seam), when ``V`` is a job that ``realises`` ``O``, when
``O`` lists ``V`` in its own ``verified_by`` (an obligation of an extension names what proves it), or when ``V`` is the
rule ``O`` itself (an enforcer covers the rule it enforces).  A node that lists ``mitigated_by`` (a threat, an edge
case) is proven through its mitigations: ``V`` also covers it when ``V`` is one of them or covers one.
Criteria of closed milestones are history and are skipped.
"""
from __future__ import annotations

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.host_kinds import NAMED_IN_LINK, verifier_naming
from specdev_tools.graph.model import Graph, Node
from specdev_tools.trace.history import contained

from .codes import VERIFIER_DOES_NOT_VERIFY_REFINED
from .context import GraphCheckContext, Mode
from specdev_tools.graph.names import JOB, MITIGATED_BY, REALISES, REFINES, RULE, TASK_CRITERION, VERIFIED_BY, VERIFIES, link_targets


def _ancestors(graph: Graph, node: Node) -> set[str]:
    found: set[str] = set()
    parent = graph.by_id.get(node.parent) if node.parent else None
    while parent is not None and parent.id not in found:
        found.add(parent.id)
        parent = graph.by_id.get(parent.parent) if parent.parent else None
    return found


def _named_by(ctx: GraphCheckContext, verifier: Node) -> set[str]:
    return set(link_targets(ctx.graph, verifier, VERIFIES)) | {ctx.graph.canonical_id(name) for name in ctx.extra_verifiers(verifier)}


def mitigations(graph: Graph, node: Node) -> list[Node]:
    """The nodes *node* lists in ``mitigated_by``, in link order; empty for a kind without the field."""
    return [graph.by_id[target] for target in link_targets(graph, node, MITIGATED_BY) if target in graph.by_id]


def _covers_directly(ctx: GraphCheckContext, verifier: Node, obligation: Node) -> bool:
    if verifier.kind == RULE:
        return verifier.id == obligation.id
    if verifier.kind == JOB and obligation.id in link_targets(ctx.graph, verifier, REALISES):
        return True
    if verifier.id in link_targets(ctx.graph, obligation, VERIFIED_BY):
        return True
    named = _named_by(ctx, verifier)
    related = contained(ctx.graph, obligation.id) | _ancestors(ctx.graph, obligation)
    return bool(named & related)


def covers(ctx: GraphCheckContext, verifier: Node, obligation: Node) -> bool:
    """Whether *verifier* covers *obligation*: it is the rule *obligation* itself, it is a job that realises it, *obligation* lists it in its own ``verified_by``, or what it verifies is the obligation, a container of it or something it contains; for an obligation with ``mitigated_by``, it is one of the mitigations or covers one (a threat is covered when ANY ONE of them is)."""
    if _covers_directly(ctx, verifier, obligation):
        return True
    return any(verifier.id == mitigation.id or _covers_directly(ctx, verifier, mitigation) for mitigation in mitigations(ctx.graph, obligation))


def covering_verifiers(ctx: GraphCheckContext, criterion: Node, obligation: Node) -> list[Node]:
    """The in-play verifiers listed in ``verified_by`` of *criterion* that cover *obligation*, in link order (see ``covers``); empty when none does."""
    verifiers = (ctx.graph.by_id.get(verifier_id) for verifier_id in link_targets(ctx.graph, criterion, VERIFIED_BY))
    return [verifier for verifier in verifiers if verifier is not None and ctx.in_play(verifier) and covers(ctx, verifier, obligation)]


def _refined_unverified(ctx: GraphCheckContext, criterion: Node) -> list[tuple[str, Node]]:
    """The links of *criterion* to refined obligations no verifier of it covers, as ``(link target as written, obligation)``; a target no node has is the dangling check's."""
    missing: list[tuple[str, Node]] = []
    for link in criterion.links:
        obligation = ctx.graph.find(link.target) if link.field == REFINES else None
        if obligation is not None and not covering_verifiers(ctx, criterion, obligation):
            missing.append((link.target, obligation))
    return missing


def check_refinement(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E745 for each in-play task criterion of an open milestone and each obligation it refines that none of its ``verified_by`` verifiers covers.

    The finding carries the criterion as ``node_id`` and ``refines->O`` as ``target``, so each pair counts apart.
    """
    historical = ctx.historical
    findings: list[SpecError] = []
    for criterion in ctx.in_play_nodes():
        if criterion.kind != TASK_CRITERION or criterion.id in historical:
            continue
        for target, obligation in _refined_unverified(ctx, criterion):
            findings.append(ctx.finding(VERIFIER_DOES_NOT_VERIFY_REFINED, criterion, _message(ctx.graph, criterion, obligation), target=link_target(REFINES, target)))
    return findings


def _message(graph: Graph, criterion: Node, obligation: Node) -> str:
    """The text of E745, with the way out that works for *obligation*: a verifier that verifies it, or, for an obligation of an extension, its own ``verified_by``."""
    start = f"task criterion {criterion.id} refines {obligation.id} but "
    naming = verifier_naming(graph, obligation)
    if naming is None:
        return (
            f"{start}none of its verifiers ({_listed(graph, criterion)}) "
            f"verifies {obligation.id}, a node that contains it or a node it contains (for a threat or an edge case: one of its mitigations or a verifier of one); add a verifier that does"
        )
    if naming == NAMED_IN_LINK:
        return (
            f"{start}none of its verifiers ({_listed(graph, criterion)}) is named in verified_by of {obligation.id}; list in verified_by of {criterion.id} "
            f"a verifier that {obligation.id} names ({_listed(graph, obligation)}), or add a verifier of {criterion.id} to verified_by of {obligation.id}"
        )
    return (
        f"{start}no verifier can prove a {obligation.kind}: the kind declares no verified_by link; declare a verified_by link to a fixture or a job "
        f"on the kind {obligation.kind} in the schema of its extension, then name a verifier of {criterion.id} in verified_by of {obligation.id}"
    )


def _listed(graph: Graph, holder: Node) -> str:
    return ", ".join(link_targets(graph, holder, VERIFIED_BY)) or "none listed"
