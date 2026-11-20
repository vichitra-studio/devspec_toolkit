"""The step-09 milestones that a step-14 milestone computes, and those that nothing computes (the release-time check of S-036): read at release (M9) and by E567 (M6c); nothing here raises an error."""
from __future__ import annotations

from specdev_tools.graph.model import Node
from specdev_tools.trace.history import contained

from .context import GraphCheckContext
from .names import DESIGN_MILESTONE, REFINES, ROADMAP_MILESTONE, SCHEDULES, TASK_CRITERION, link_targets


def _milestone_of(ctx: GraphCheckContext, criterion: Node) -> Node | None:
    """The roadmap milestone above *criterion* (criterion, task, milestone), or ``None``."""
    node: Node | None = criterion
    while node is not None:
        if node.kind == ROADMAP_MILESTONE:
            return node
        node = ctx.graph.by_id.get(node.parent) if node.parent else None
    return None


def matching_milestones(ctx: GraphCheckContext) -> list[tuple[Node, Node]]:
    """The pairs ``(design milestone, roadmap milestone)`` where the step-14 milestone computes the step-09 one.

    The design (S-036) computes the step-09 milestones of a step-14 milestone as those that ``schedules`` the
    obligations its task criteria refine.  A scheduled node counts as refined when an in-play task criterion refines it
    or a node it contains (ruling R17; ``trace.history.contained`` is the one containment walk), so a milestone that
    schedules an FR is computed by the criteria that refine one of the FR's criteria.  The design milestone is in play
    (a design milestone out of play is in no pair); the roadmap milestone is the one above the criterion and need not be
    in play.  Ordered as ``ctx.in_play_nodes()`` is (design milestone, then roadmap milestone, in the order of the
    first criterion); a design milestone with no pair is not computed by any step-14 milestone.
    """
    graph = ctx.graph
    refined_by: dict[str, list[Node]] = {}
    for criterion in graph.by_kind.get(TASK_CRITERION, ()):
        milestone = _milestone_of(ctx, criterion) if ctx.in_play(criterion) else None
        if milestone is not None:
            for target in link_targets(graph, criterion, REFINES):
                refined_by.setdefault(target, []).append(milestone)
    order = {node.id: rank for rank, node in enumerate(ctx.in_play_nodes())}
    pairs: list[tuple[Node, Node]] = []
    for design in ctx.in_play_nodes():
        if design.kind != DESIGN_MILESTONE:
            continue
        found: dict[str, Node] = {}
        for scheduled in link_targets(graph, design, SCHEDULES):
            for inside in contained(graph, scheduled):
                for milestone in refined_by.get(inside, ()):
                    found.setdefault(milestone.id, milestone)
        pairs.extend((design, found[key]) for key in sorted(found, key=lambda i: (order.get(i, len(order)), i)))
    return pairs


def unrealised_design_milestones(ctx: GraphCheckContext) -> list[Node]:
    """The in-play step-09 milestones that no step-14 milestone computes: in no pair of ``matching_milestones``."""
    computed = {design.id for design, _ in matching_milestones(ctx)}
    return [milestone for milestone in ctx.in_play_nodes() if milestone.kind == DESIGN_MILESTONE and milestone.id not in computed]
