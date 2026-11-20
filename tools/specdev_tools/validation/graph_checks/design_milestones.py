"""The step-09 milestones that nothing computes (the release-time check of S-036): read at release (M9); nothing here raises an error."""
from __future__ import annotations

from specdev_tools.graph.model import Node

from .context import GraphCheckContext
from .names import REFINES, TASK_CRITERION, link_targets

DESIGN_MILESTONE = "design-milestone"
SCHEDULES = "schedules"


def unrealised_design_milestones(ctx: GraphCheckContext) -> list[Node]:
    """The in-play step-09 milestones that no step-14 milestone computes: no task criterion refines anything they schedule."""
    graph = ctx.graph
    refined = {
        target
        for criterion in graph.by_kind.get(TASK_CRITERION, ())
        if ctx.in_play(criterion)
        for target in link_targets(graph, criterion, REFINES)
    }
    return [
        milestone for milestone in ctx.in_play_nodes()
        if milestone.kind == DESIGN_MILESTONE and not refined.intersection(link_targets(graph, milestone, SCHEDULES))
    ]
