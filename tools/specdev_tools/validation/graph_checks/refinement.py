"""The refinement check (E745): the verifier of a task criterion must verify the obligation the criterion refines.

A verifier ``V`` of a criterion covers an obligation ``O`` when ``V`` names ``O``, a container of ``O`` or a node
``O`` contains in ``verifies`` (or in the ``extra_verifiers`` seam), when ``V`` is a job that ``realises`` ``O``, or
when ``V`` is the rule ``O`` itself (an enforcer covers the rule it enforces).  Criteria of closed milestones are
history and are skipped.
"""
from __future__ import annotations

from typing import Any

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.model import Graph, Node
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext

from .codes import VERIFIER_DOES_NOT_VERIFY_REFINED
from .context import GRAPH_NOT_BUILT, GraphCheckContext, Mode

TASK_CRITERION = "task-criterion"
REFINES = "refines"
VERIFIED_BY = "verified_by"
VERIFIES = "verifies"
REALISES = "realises"
RULE = "rule"
JOB = "job"


def link_targets(graph: Graph, node: Node, field: str) -> list[str]:
    """The ids of the nodes *node* links to through *field*, written as ids and resolved by alias to the current id, in link order; a target no node has is kept as written."""
    return [graph.canonical_id(link.target) for link in node.links if link.field == field]


def _ancestors(graph: Graph, node: Node) -> set[str]:
    found: set[str] = set()
    parent = graph.by_id.get(node.parent) if node.parent else None
    while parent is not None and parent.id not in found:
        found.add(parent.id)
        parent = graph.by_id.get(parent.parent) if parent.parent else None
    return found


def _descendants(graph: Graph, node_id: str) -> set[str]:
    found: set[str] = set()
    pending = list(graph.children.get(node_id, ()))
    while pending:
        child = pending.pop()
        if child not in found:
            found.add(child)
            pending.extend(graph.children.get(child, ()))
    return found


def _named_by(ctx: GraphCheckContext, verifier: Node) -> set[str]:
    return set(link_targets(ctx.graph, verifier, VERIFIES)) | {ctx.graph.canonical_id(name) for name in ctx.extra_verifiers(verifier)}


def covers(ctx: GraphCheckContext, verifier: Node, obligation: Node) -> bool:
    """Whether *verifier* covers *obligation*: it is the rule *obligation* itself, it is a job that realises it, or what it verifies is the obligation, a container of it or something it contains."""
    if verifier.kind == RULE:
        return verifier.id == obligation.id
    if verifier.kind == JOB and obligation.id in link_targets(ctx.graph, verifier, REALISES):
        return True
    named = _named_by(ctx, verifier)
    related = {obligation.id} | _ancestors(ctx.graph, obligation) | _descendants(ctx.graph, obligation.id)
    return bool(named & related)


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
    historical = historical_node_ids(ctx.graph)
    findings: list[SpecError] = []
    for criterion in ctx.in_play_nodes():
        if criterion.kind != TASK_CRITERION or criterion.id in historical:
            continue
        for target, obligation in _refined_unverified(ctx, criterion):
            message = (
                f"task criterion {criterion.id} refines {obligation.id} but none of its verifiers ({_listed(ctx.graph, criterion)}) "
                f"verifies {obligation.id}, a node that contains it or a node it contains; add a verifier that does"
            )
            findings.append(ctx.finding(VERIFIER_DOES_NOT_VERIFY_REFINED, criterion, message, target=link_target(REFINES, target)))
    return findings


def _listed(graph: Graph, criterion: Node) -> str:
    return ", ".join(link_targets(graph, criterion, VERIFIED_BY)) or "none listed"


def run_refinement(ctx: CheckContext) -> dict[str, Any]:
    """The registered function: E745 findings of ``check_refinement`` at merge, or a skip when no graph could be built."""
    gctx = GraphCheckContext.from_registry(ctx)
    if gctx is None:
        return check_registry.skip(GRAPH_NOT_BUILT)
    return check_registry.check_result(check_refinement(gctx, "merge"))
