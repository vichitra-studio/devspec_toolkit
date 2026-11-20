"""The step-09 milestones that a step-14 milestone computes, and those that nothing computes (the release-time check of S-036): read at release (M9) and by E567 (M6c); nothing here raises an error."""
from __future__ import annotations

from typing import NamedTuple

from specdev_tools.graph.model import Node
from specdev_tools.graph.queries import milestone_of
from specdev_tools.trace.history import contained

from .context import GraphCheckContext
from .names import DESIGN_MILESTONE, REFINES, ROADMAP_MILESTONE, SCHEDULES, TASK_CRITERION, link_targets
from .use_table import Use, use_pairs


class _Index(NamedTuple):
    """What the in-play task criteria refine: for each refined id, the roadmap milestones (in order of the listing, no repeats) that hold a criterion refining it."""

    refined_by: dict[str, list[Node]]
    order: dict[str, int]


def _index(ctx: GraphCheckContext) -> _Index:
    """The one index ``matching_milestones`` and ``unrefined_scheduled`` read: the in-play task criteria that sit under a roadmap milestone, by the id each refines."""
    graph = ctx.graph
    refined_by: dict[str, list[Node]] = {}
    for criterion in graph.by_kind.get(TASK_CRITERION, ()):
        if not ctx.in_play(criterion):
            continue
        milestone = graph.by_id.get(milestone_of(graph, criterion) or "")
        if milestone is None or milestone.kind != ROADMAP_MILESTONE:
            continue
        for target in link_targets(graph, criterion, REFINES):
            refined_by.setdefault(target, []).append(milestone)
    return _Index(refined_by, {node.id: rank for rank, node in enumerate(ctx.in_play_nodes())})


def _matching(ctx: GraphCheckContext, index: _Index) -> list[tuple[Node, Node]]:
    graph = ctx.graph
    pairs: list[tuple[Node, Node]] = []
    for design in ctx.in_play_nodes():
        if design.kind != DESIGN_MILESTONE:
            continue
        found: dict[str, Node] = {}
        for scheduled in link_targets(graph, design, SCHEDULES):
            for inside in contained(graph, scheduled):
                for milestone in index.refined_by.get(inside, ()):
                    found.setdefault(milestone.id, milestone)
        pairs.extend((design, found[key]) for key in sorted(found, key=lambda i: (index.order.get(i, len(index.order)), i)))
    return pairs


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
    return _matching(ctx, _index(ctx))


def unrefined_scheduled(ctx: GraphCheckContext) -> list[tuple[Node, Node]]:
    """The pairs ``(design milestone, scheduled node)`` that a design milestone computed by some roadmap milestone leaves unrefined (the finding of E567).

    For each in-play design milestone that is in a pair of ``matching_milestones``, each node it ``schedules`` that
    (a) is in play (``scope`` later or out, or lifecycle ``not_applicable``, is not planned; a deprecated node is in
    play) and of a kind a task criterion can refine (the use table: a ``refines`` use by a task criterion; a scheduled
    risk, component or environment is never here, ruling R18, as nothing could clear a finding on it) and (b) that no
    in-play task criterion under a roadmap milestone refines, itself or through a node it contains (ruling R17).  A
    design milestone in no pair gives nothing (it is ``unrealised``).  Ordered as ``matching_milestones`` is by design
    milestone, then in the order of its ``schedules`` links; a node scheduled twice is given once.
    """
    graph = ctx.graph
    index = _index(ctx)
    refinable: dict[str, bool] = {}
    result: list[tuple[Node, Node]] = []
    for design in dict.fromkeys(design for design, _ in _matching(ctx, index)):
        for target in dict.fromkeys(link_targets(graph, design, SCHEDULES)):
            scheduled = graph.by_id.get(target)
            if scheduled is None or not ctx.in_play(scheduled):
                continue
            if scheduled.kind not in refinable:
                refinable[scheduled.kind] = Use(TASK_CRITERION, REFINES) in use_pairs(scheduled.kind, graph.decls)
            if refinable[scheduled.kind] and not any(inside in index.refined_by for inside in contained(graph, scheduled.id)):
                result.append((design, scheduled))
    return result


def unrealised_design_milestones(ctx: GraphCheckContext) -> list[Node]:
    """The in-play step-09 milestones that no step-14 milestone computes: in no pair of ``matching_milestones``."""
    computed = {design.id for design, _ in matching_milestones(ctx)}
    return [milestone for milestone in ctx.in_play_nodes() if milestone.kind == DESIGN_MILESTONE and milestone.id not in computed]
