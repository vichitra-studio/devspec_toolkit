"""The two milestone numbers of step 14 as graph checks (``milestone-numbers``): E566 and E567.

E566: an in-play FR that no task criterion reaches.  The reach is the walk of ``graph_checks.built.walk_derivations``
along the verbs a ``built`` derivation follows (``refines``, ``realises``, ``derives_from``, ``mitigated_by``), with no
hash and no milestone state, started from the FR and from each node it contains (ruling R17, as for E567): an FR is
planned when some task criterion refines it, an acceptance criterion of it, or a node derived from either.

E567: a node a design milestone ``schedules`` that no task criterion refines, for a design milestone some roadmap
milestone computes; one finding for each pair of ``graph_checks.design_milestones.unrefined_scheduled``.

Both read the graph only, so they run under ``spec-check`` and the step gate and not under ``validate`` of one file.
"""
from __future__ import annotations

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.model import Node
from specdev_tools.trace.history import contained
from specdev_tools.validation.graph_checks.built import walk_derivations
from specdev_tools.validation.graph_checks.context import GraphCheckContext, Mode
from specdev_tools.validation.graph_checks.design_milestones import unrefined_scheduled
from specdev_tools.validation.graph_checks.names import DERIVES_FROM, FR, MITIGATED_BY, REALISES, REFINES, TASK_CRITERION

UNCOVERED_FR_MILESTONE = "E566"
INCOMPLETE_MILESTONE_DECOMPOSITION = "E567"
BUILT_VERBS = (REFINES, REALISES, DERIVES_FROM, MITIGATED_BY)
"""The verbs a derivation from an FR to a task criterion follows."""


def _reached_by_a_task_criterion(ctx: GraphCheckContext, fr: Node) -> bool:
    """Whether a task criterion is reached from *fr* or from a node it contains (ruling R17: a criterion that refines an acceptance criterion of the FR refines the FR), through the built verbs."""
    inside = sorted((ctx.graph.by_id[i] for i in contained(ctx.graph, fr.id) if i in ctx.graph.by_id), key=ctx.graph.shape.order_key)
    return any(
        reached.kind == TASK_CRITERION for start in inside if ctx.in_play(start) for reached in walk_derivations(ctx, start, BUILT_VERBS)
    )


def check_milestone_numbers(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E566 for each in-play FR no task criterion reaches, then E567 for each scheduled node a computed design milestone leaves unrefined."""
    findings: list[SpecError] = []
    for fr in ctx.in_play_nodes():
        if fr.kind != FR:
            continue
        if not _reached_by_a_task_criterion(ctx, fr):
            findings.append(ctx.finding(
                UNCOVERED_FR_MILESTONE, fr,
                f"{fr.kind} {fr.id} is in scope but no task criterion reaches it: add a task criterion that refines it, one of its acceptance criteria "
                "or a node derived from it, or set its scope to later or out with a scope_reason",
            ))
    for design, scheduled in unrefined_scheduled(ctx):
        findings.append(ctx.finding(
            INCOMPLETE_MILESTONE_DECOMPOSITION, design,
            f"{scheduled.kind} {scheduled.id} is scheduled by {design.id} but no task criterion refines it: add a task criterion that refines it "
            f"or a node it contains, or remove it from the schedules of {design.id}",
            target=scheduled.id,
        ))
    return findings
