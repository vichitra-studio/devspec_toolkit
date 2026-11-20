"""The removal rules of step 14 as one graph check (``removal-rules``): E341 and E342.

A removal criterion is a task criterion with ``removes``; a removal fixture is a fixture with ``removes``.  The fixture proves
that the removed behaviour is gone, so it justifies itself through ``removes`` and needs no ``verifies``.

**E341.**  The ``removes`` of a criterion must equal the ``removes`` of each removal fixture in its ``verified_by``, and each id a
removal fixture removes must be removed by a criterion that lists the fixture in ``verified_by``.

**E342.**  A live criterion or fixture whose ``removes`` names an id that a node has now: the removed thing is still in the spec.

Closed work is history.  A criterion of a closed milestone is never checked; a removal fixture whose every criterion is closed
is closed with them (it may be deleted after the close, and an id removed long ago may be used again); the closed criteria still
count as the cover of a fixture that is still in the spec.
"""
from __future__ import annotations

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import FIXTURE, REMOVES, TASK_CRITERION, VERIFIED_BY, link_targets

from .context import GraphCheckContext, Mode

REMOVAL_FIXTURE_MISMATCH = "E341"
REMOVES_TARGET_PRESENT = "E342"


def _removed(graph: Graph, node: Node) -> set[str]:
    return set(link_targets(graph, node, REMOVES))


def _listed(ids: set[str]) -> str:
    return ", ".join(sorted(ids))


def _naming(graph: Graph, fixture: Node) -> list[Node]:
    """The task criteria that list *fixture* in ``verified_by``, in graph order."""
    return [criterion for criterion in graph.by_kind.get(TASK_CRITERION, ()) if fixture.id in link_targets(graph, criterion, VERIFIED_BY)]


def _frozen(naming: list[Node], historical: set[str]) -> bool:
    """A removal fixture is closed work when some criterion lists it and every one that does is closed."""
    return bool(naming) and all(criterion.id in historical for criterion in naming)


def _mismatches(ctx: GraphCheckContext, criterion: Node) -> list[SpecError]:
    """E341 for each removal fixture in ``verified_by`` of the live removal criterion *criterion* whose ``removes`` differ from its own."""
    own = _removed(ctx.graph, criterion)
    findings: list[SpecError] = []
    for name in link_targets(ctx.graph, criterion, VERIFIED_BY):
        fixture = ctx.graph.by_id.get(name)
        if fixture is None or fixture.kind != FIXTURE or not (theirs := _removed(ctx.graph, fixture)) or theirs == own:
            continue
        findings.append(ctx.finding(
            REMOVAL_FIXTURE_MISMATCH, criterion,
            f"task criterion {criterion.id} removes {_listed(own)} but its removal fixture {fixture.id} removes {_listed(theirs)}: "
            f"make the removes of {criterion.id} and {fixture.id} the same list",
            target=link_target(VERIFIED_BY, name),
        ))
    return findings


def _uncovered(ctx: GraphCheckContext, fixture: Node, naming: list[Node]) -> list[SpecError]:
    """E341 when *fixture* removes an id that no criterion listing it removes."""
    covered = {removed for criterion in naming for removed in _removed(ctx.graph, criterion)}
    missing = _removed(ctx.graph, fixture) - covered
    if not missing:
        return []
    return [ctx.finding(
        REMOVAL_FIXTURE_MISMATCH, fixture,
        f"removal fixture {fixture.id} removes {_listed(missing)} but no task criterion that lists it in verified_by removes "
        f"{'it' if len(missing) == 1 else 'them'}: add a task criterion with those ids in removes and {fixture.id} in verified_by",
    )]


def _present(ctx: GraphCheckContext, node: Node) -> list[SpecError]:
    """E342 for each id *node* removes that a node has now."""
    findings: list[SpecError] = []
    for removed in sorted(_removed(ctx.graph, node)):
        if ctx.graph.find(removed) is None:
            continue
        findings.append(ctx.finding(
            REMOVES_TARGET_PRESENT, node,
            f"{node.kind} {node.id} removes {removed}, which is still in the spec: delete {removed}, or take it out of removes",
            target=link_target(REMOVES, removed),
        ))
    return findings


def check_removal_rules(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E341 and E342 for the live removal criteria and removal fixtures: criteria first, then fixtures, each in step then id order."""
    historical = ctx.historical
    live = ctx.in_play_nodes()
    criteria = [node for node in live if node.kind == TASK_CRITERION and node.id not in historical and _removed(ctx.graph, node)]
    fixtures = [node for node in live if node.kind == FIXTURE and _removed(ctx.graph, node)]
    findings: list[SpecError] = []
    for criterion in criteria:
        findings.extend(_mismatches(ctx, criterion))
        findings.extend(_present(ctx, criterion))
    for fixture in fixtures:
        naming = _naming(ctx.graph, fixture)
        if not _frozen(naming, historical):
            findings.extend(_uncovered(ctx, fixture, naming))
            findings.extend(_present(ctx, fixture))
    return findings
