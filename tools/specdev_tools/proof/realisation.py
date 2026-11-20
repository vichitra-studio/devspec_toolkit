"""Realisation status: what became of the thing a closed milestone's task criterion refined.

A milestone is closed when its anchor row says ``done``.  Each ``refines`` link of a criterion of it has a lock entry with the
content hash the target had when the link was accepted.  Compared with the target now, a link is ``current`` (same hash),
``outdated`` (the target changed, or its id names something else now), ``superseded`` (outdated, and another closed milestone's
criterion refines the current version) or ``removed`` (no node has the id any more).  A removed link never becomes superseded.
The status is computed from the lock, not from lifecycle: a ``not_applicable`` criterion keeps its history.

``unresolved_realisations`` lists what a release has to answer for: an outdated link needs a change milestone, a removed one a
closed milestone with a criterion that ``removes`` the target or a node that contained it.  The release gate (M9) raises
E343 and E344 from this list; nothing here raises.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.queries import milestone_of
from specdev_tools.trace.hashing import compute_all, content_hash
from specdev_tools.trace.history import contained, done_milestones
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation.graph_checks.names import REFINES, REMOVES, TASK_CRITERION, link_targets

CURRENT = "current"
OUTDATED = "outdated"
SUPERSEDED = "superseded"
REMOVED = "removed"
REALISATION_OUTDATED = "E343"
REALISATION_REMOVED = "E344"


@dataclass(frozen=True)
class Realisation:
    """One ``refines`` link of a task criterion of a closed milestone and what became of its target.

    ``target`` is the id as the link wrote it; ``current_hash`` is ``None`` for a removed target; ``superseded_by`` is the closed
    milestone that refines the current version of an outdated target; ``containers`` are the ids that enclosed the target when
    the link was accepted (current ids, nearest first), as the lock entry recorded them.
    """

    milestone: str
    criterion: str
    target: str
    state: str
    recorded_hash: str
    current_hash: str | None
    superseded_by: str | None
    containers: tuple[str, ...]


@dataclass(frozen=True)
class UnresolvedRealisation:
    """A target that a release has to answer for: ``code`` is ``E343`` for ``kind`` ``outdated``, ``E344`` for ``removed``.

    ``existing_milestone`` is the milestone that already carries the answer but is not closed (a change milestone whose criterion
    refines the current version, or a removal milestone), or ``None`` when no milestone does.
    """

    code: str
    kind: str
    milestone: str
    target: str
    current_hash: str | None
    existing_milestone: str | None


def _closed_criteria(graph: Graph) -> list[tuple[str, Node]]:
    """``(closed milestone id, task criterion)`` for each criterion the closed milestones contain, a milestone's criteria in graph order."""
    pairs: list[tuple[str, Node]] = []
    for milestone in sorted(done_milestones(graph)):
        inside = contained(graph, milestone)
        criteria = sorted((graph.by_id[i] for i in inside if graph.by_id[i].kind == TASK_CRITERION), key=graph.shape.order_key)
        pairs.extend((milestone, criterion) for criterion in criteria)
    return pairs


def _current_hash(graph: Graph, hashes: Mapping[str, tuple[str, str]], node_id: str, seed_texts: Mapping[str, str]) -> str:
    """The content hash of *node_id* now; a ``not_applicable`` node has none in *hashes* and is hashed on its own."""
    return hashes[node_id][0] if node_id in hashes else content_hash(node_id, graph, seed_texts)


@dataclass(frozen=True)
class _Link:
    """A ``refines`` link of a closed criterion with its lock entry: the hash recorded and the hash of the target now (``None`` when no node has the id)."""

    milestone: str
    criterion: str
    target: str
    recorded: str
    now: str | None
    containers: tuple[str, ...]


def _links(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> list[_Link]:
    hashes = compute_all(graph, seed_texts)
    links: list[_Link] = []
    for milestone, criterion in _closed_criteria(graph):
        for link in criterion.links:
            entry = lock.get(criterion.id, REFINES, link.target) if link.field == REFINES else None
            if entry is None:
                continue
            target = graph.find(link.target)
            now = _current_hash(graph, hashes, target.id, seed_texts) if target is not None else None
            links.append(_Link(milestone, criterion.id, link.target, entry.content_hash, now, tuple(graph.canonical_id(name) for name in entry.target_containers)))
    return links


def _realisation(graph: Graph, link: _Link, refined_now: Mapping[str, set[str]]) -> Realisation:
    if link.now is None:
        return Realisation(link.milestone, link.criterion, link.target, REMOVED, link.recorded, None, None, link.containers)
    if link.now == link.recorded:
        return Realisation(link.milestone, link.criterion, link.target, CURRENT, link.recorded, link.now, None, link.containers)
    others = sorted(refined_now.get(graph.canonical_id(link.target), set()) - {link.milestone})
    state, by = (SUPERSEDED, others[0]) if others else (OUTDATED, None)
    return Realisation(link.milestone, link.criterion, link.target, state, link.recorded, link.now, by, link.containers)


def realisation_status(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> list[Realisation]:
    """One ``Realisation`` for each ``refines`` link, with a lock entry, of a task criterion of a closed milestone, in milestone, criterion and link order.

    A link with no lock entry has no recorded hash to compare and is left out.  Targets and containers are resolved through
    aliases, so a renamed target is still ``current``.
    """
    links = _links(graph, lock, seed_texts)
    refined_now: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if link.now is not None and link.recorded == link.now:
            refined_now[graph.canonical_id(link.target)].add(link.milestone)
    return [_realisation(graph, link, refined_now) for link in links]


def _open_refiner(graph: Graph, lock: Lock, closed: set[str], target: str, current: str) -> str | None:
    """The milestone, not closed, whose task criterion refines the current version of *target* (its lock entry holds *current*), else ``None``."""
    for criterion in graph.by_kind.get(TASK_CRITERION, ()):
        milestone = milestone_of(graph, criterion)
        if milestone is None or milestone in closed:
            continue
        for link in criterion.links:
            entry = lock.get(criterion.id, REFINES, link.target) if link.field == REFINES else None
            if entry is not None and graph.canonical_id(link.target) == target and entry.content_hash == current:
                return milestone
    return None


def _removal_criteria(graph: Graph, wanted: set[str]) -> list[Node]:
    """The task criteria whose ``removes`` names one of *wanted* (current ids or ids as written), in graph order."""
    return [criterion for criterion in graph.by_kind.get(TASK_CRITERION, ()) if wanted & set(link_targets(graph, criterion, REMOVES))]


def unresolved_realisations(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> list[UnresolvedRealisation]:
    """What each closed milestone's links still owe, one entry for each (milestone, target): ``outdated`` with no closed milestone that refines the current version, ``removed`` with no closed milestone whose criterion ``removes`` the target or a node that contained it.

    Removal is matched through the containers the lock entry recorded, so a criterion that refined ``ac-x`` is answered by a
    closed criterion that ``removes`` ``fr-x`` (the FR that contained it), with no history walk.  A milestone that carries the
    answer but is not closed is named in ``existing_milestone``.  Entries are in the order of ``realisation_status``.
    """
    closed = done_milestones(graph)
    found: dict[tuple[str, str], UnresolvedRealisation] = {}
    for row in realisation_status(graph, lock, seed_texts):
        key = (row.milestone, graph.canonical_id(row.target))
        if row.state == OUTDATED and key not in found:
            existing = _open_refiner(graph, lock, closed, key[1], row.current_hash or "")
            found[key] = UnresolvedRealisation(REALISATION_OUTDATED, OUTDATED, row.milestone, row.target, row.current_hash, existing)
        elif row.state == REMOVED and key not in found:
            matches = _removal_criteria(graph, {row.target, key[1], *row.containers})
            milestones = [milestone_of(graph, criterion) for criterion in matches]
            if not any(milestone in closed for milestone in milestones):
                found[key] = UnresolvedRealisation(REALISATION_REMOVED, REMOVED, row.milestone, row.target, None, next((m for m in milestones if m), None))
    return list(found.values())
