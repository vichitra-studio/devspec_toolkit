"""The cross-cutting obligation check (E744): a task an obligation reaches must carry a criterion that refines it.

A cross-cutting obligation is an in-play obligation with a ``constrains`` link (an invariant or an NFR).  Its reach
is the set of capabilities and components it constrains; a task is bound by it when something the task refines leads
to the same capability or component.  Tasks of closed milestones are history and are skipped.
"""
from __future__ import annotations

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.model import Graph, Node

from .codes import CROSS_CUTTING_NOT_REFINED
from .context import GraphCheckContext, Mode
from .names import API, COMPONENT, DERIVES_FROM, REFINES, link_targets

CONSTRAINS = "constrains"
TASK = "task"
CAPABILITY = "capability"
FR = "fr"
CRITERION = "criterion"
PROVIDED_BY = "provided_by"


def _linked(graph: Graph, node: Node, field: str, *kinds: str) -> list[Node]:
    found = (graph.by_id.get(target) for target in link_targets(graph, node, field))
    return [target for target in found if target is not None and target.kind in kinds]


def lineage(graph: Graph, node: Node) -> set[str]:
    """The ids of the capabilities and components *node* leads to, walking upward; empty for a kind that leads to none.

    An FR gives its capabilities, a criterion those of its FR, an API its ``provided_by`` components and those of its
    FR, an API error those of the criterion it derives from, a component itself, a connection its source component, and
    an invariant or NFR the lineage of everything it constrains.
    """
    kind = node.kind
    if kind in (CAPABILITY, COMPONENT):
        return {node.id}
    if kind == FR:
        return {target.id for target in _linked(graph, node, DERIVES_FROM, CAPABILITY)}
    if kind == CRITERION:
        return _lineage_of(graph, [graph.by_id[node.parent]] if node.parent in graph.by_id else [])
    if kind == API:
        return _lineage_of(graph, _linked(graph, node, DERIVES_FROM, FR)) | {target.id for target in _linked(graph, node, PROVIDED_BY, COMPONENT)}
    if kind == "api-error":
        return _lineage_of(graph, _linked(graph, node, DERIVES_FROM, CRITERION))
    if kind == "connection":
        return {target.id for target in _linked(graph, node, DERIVES_FROM, COMPONENT)}
    if _constrains(node):
        return _lineage_of(graph, [graph.by_id[target] for target in link_targets(graph, node, CONSTRAINS) if target in graph.by_id])
    return set()


def _lineage_of(graph: Graph, nodes: list[Node]) -> set[str]:
    return set().union(*(lineage(graph, node) for node in nodes)) if nodes else set()


def _constrains(node: Node) -> bool:
    return any(link.field == CONSTRAINS for link in node.links)


def _refined(ctx: GraphCheckContext, task: Node) -> list[str]:
    """The ids the in-play criteria of *task* refine."""
    criteria = (ctx.graph.by_id[child] for child in task.children if child in ctx.graph.by_id)
    return [target for criterion in criteria if ctx.in_play(criterion) for target in link_targets(ctx.graph, criterion, REFINES)]


def _task_reach(ctx: GraphCheckContext, refined: list[str]) -> set[str]:
    return _lineage_of(ctx.graph, [ctx.graph.by_id[target] for target in refined if target in ctx.graph.by_id])


def check_cross_cutting(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E744 for each in-play task of an open milestone that an in-play cross-cutting obligation reaches and no criterion of the task refines.

    The finding carries the task as ``node_id`` and ``refines->O`` as ``target``.
    """
    obligations = [(node, lineage(ctx.graph, node)) for node in ctx.in_play_nodes() if _constrains(node)]
    historical = ctx.historical
    findings: list[SpecError] = []
    for task in ctx.in_play_nodes():
        if task.kind != TASK or task.id in historical:
            continue
        refined = _refined(ctx, task)
        reach = _task_reach(ctx, refined)
        for obligation, obligation_reach in obligations:
            shared = reach & obligation_reach
            if shared and obligation.id not in refined:
                message = (
                    f"task {task.id} falls under {obligation.id} through {', '.join(sorted(shared))} "
                    f"but no criterion of the task refines it; add a task criterion that refines {obligation.id}"
                )
                findings.append(ctx.finding(CROSS_CUTTING_NOT_REFINED, task, message, target=link_target(REFINES, obligation.id)))
    return findings
