"""Lineage and impact of a node: the closures behind ``specdev trace --up`` and ``--down``.

``--up`` follows the node's outgoing links (what it derives from, assumes, relies on) and, by default, the
containment edge from a child to its parent.  ``--down`` follows the reverse index (what points at it) and the
containment edge from a parent to its children.  The two walks are separate, so a node reached upward is never
expanded downward: siblings that share an ancestor are not part of the answer.  Records are collected apart from the
other nodes and are never walked through; a node whose lifecycle is ``not_applicable`` is neither shown nor walked.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.kinds import RECORD_ROLE
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node

Direction = Literal["up", "down"]
BOTH_DIRECTIONS: tuple[Direction, ...] = ("up", "down")
_NO_STEP_RANK = 10**6


class UnknownTraceTargetError(Exception):
    """The id to trace is not a node of the graph; the E706 finding is in ``error``."""

    def __init__(self, error: SpecError) -> None:
        super().__init__(error.message)
        self.error = error


@dataclass(frozen=True)
class TraceOptions:
    """How far and along what a walk goes.

    ``depth`` counts edges from the entry (``None`` = no limit); ``kinds`` keeps only nodes of those kinds in the
    answer (the walk still passes through other kinds); ``verbs`` limits the link fields followed (empty = all);
    ``containment`` follows the parent / child edge.
    """

    depth: int | None = None
    kinds: frozenset[str] = frozenset()
    verbs: frozenset[str] = frozenset()
    containment: bool = True


@dataclass(frozen=True)
class TraceSide:
    """One direction of a trace: the nodes reached (ordered by step, then id) and the records reached, apart."""

    direction: Direction
    nodes: tuple[Node, ...]
    records: tuple[Node, ...]

    @property
    def size(self) -> int:
        """Number of nodes and records reached."""
        return len(self.nodes) + len(self.records)


@dataclass(frozen=True)
class TraceResult:
    """The trace of ``entry``; a side that was not asked for is ``None``.

    ``reached`` holds the entry and every node and record either side reached, once each, ordered by step then id.
    """

    entry: Node
    up: TraceSide | None
    down: TraceSide | None
    reached: tuple[Node, ...]


def _step_rank(graph: Graph, node: Node) -> tuple[int, str, str]:
    """Order of *node* in the waterfall: step rank (unknown steps last), step name, id."""
    rank = graph.shape.step_ranks.get(node.step, _NO_STEP_RANK) if node.step is not None else _NO_STEP_RANK
    return rank, node.step or "", node.id


def _neighbour_ids(graph: Graph, node: Node, direction: Direction, options: TraceOptions) -> list[str]:
    """Ids one edge away from *node* in *direction*: link targets or sources, then the containment edge."""
    verbs = options.verbs
    if direction == "up":
        ids = [link.target for link in graph.outgoing.get(node.id, ()) if not verbs or link.field in verbs]
        if options.containment and node.parent is not None:
            ids.append(node.parent)
        return ids
    ids = [link.source for link in graph.incoming.get(node.id, ()) if not verbs or link.field in verbs]
    if options.containment:
        ids.extend(node.children)
    return ids


def _walk(graph: Graph, entry: Node, direction: Direction, options: TraceOptions) -> list[Node]:
    """Breadth-first closure from *entry* in *direction*, entry excluded; records are returned but not expanded."""
    seen = {entry.id}
    reached: list[Node] = []
    queue: deque[tuple[Node, int]] = deque([(entry, 0)])
    while queue:
        node, distance = queue.popleft()
        if options.depth is not None and distance >= options.depth:
            continue
        for neighbour_id in _neighbour_ids(graph, node, direction, options):
            neighbour = graph.by_id.get(neighbour_id)
            if neighbour is None or neighbour_id in seen or neighbour.lifecycle == NOT_APPLICABLE:
                continue
            seen.add(neighbour_id)
            reached.append(neighbour)
            if neighbour.role != RECORD_ROLE:
                queue.append((neighbour, distance + 1))
    return reached


def _side(graph: Graph, entry: Node, direction: Direction, options: TraceOptions) -> TraceSide:
    reached = [node for node in _walk(graph, entry, direction, options) if not options.kinds or node.kind in options.kinds]
    ordered = sorted(reached, key=lambda node: _step_rank(graph, node))
    return TraceSide(
        direction,
        tuple(node for node in ordered if node.role != RECORD_ROLE),
        tuple(node for node in ordered if node.role == RECORD_ROLE),
    )


def trace_node(
    graph: Graph,
    node_id: str,
    directions: Iterable[Direction] = BOTH_DIRECTIONS,
    options: TraceOptions = TraceOptions(),
) -> TraceResult:
    """The trace of *node_id* in each of *directions* (default both).

    The entry itself may have any lifecycle.  Raises ``UnknownTraceTargetError`` (E706) when no node has that id.
    """
    entry = graph.by_id.get(node_id)
    if entry is None:
        raise UnknownTraceTargetError(make_error("E706", f"no node has the id {node_id!r}"))
    wanted = set(directions)
    up = _side(graph, entry, "up", options) if "up" in wanted else None
    down = _side(graph, entry, "down", options) if "down" in wanted else None
    found = {entry.id: entry}
    for side in (up, down):
        if side is not None:
            found.update((node.id, node) for node in (*side.nodes, *side.records))
    return TraceResult(entry, up, down, tuple(sorted(found.values(), key=lambda node: _step_rank(graph, node))))


def group_by_kind(nodes: Iterable[Node]) -> dict[str, list[Node]]:
    """*nodes* grouped by kind, kinds in order of first appearance, nodes in the order given."""
    groups: dict[str, list[Node]] = {}
    for node in nodes:
        groups.setdefault(node.kind, []).append(node)
    return groups


def _node_line(node: Node) -> str:
    step = node.step if node.step is not None else "-"
    return f"    {node.id}  {node.kind}  {step}  {node.lifecycle}  {node.label}".rstrip()


def _render_side(side: TraceSide) -> list[str]:
    lines = [f"{side.direction} ({side.size})"]
    if side.size == 0:
        return [*lines, "  none"]
    for kind, nodes in group_by_kind(side.nodes).items():
        lines.append(f"  {kind} ({len(nodes)})")
        lines.extend(_node_line(node) for node in nodes)
    if side.records:
        lines.append(f"  records ({len(side.records)})")
        lines.extend(_node_line(node) for node in side.records)
    return lines


def render_text(result: TraceResult) -> str:
    """The trace as text: the entry, then each side with its nodes grouped by kind and its records apart."""
    lines = [f"trace of {result.entry.id}", _node_line(result.entry).strip()]
    for side in (result.up, result.down):
        if side is not None:
            lines.extend(["", *_render_side(side)])
    return "\n".join(lines)


def _node_to_dict(node: Node) -> dict[str, Any]:
    return {"id": node.id, "kind": node.kind, "step": node.step, "lifecycle": node.lifecycle, "label": node.label}


def _side_to_dict(side: TraceSide) -> dict[str, Any]:
    return {
        "count": side.size,
        "groups": {kind: [_node_to_dict(node) for node in nodes] for kind, nodes in group_by_kind(side.nodes).items()},
        "records": [_node_to_dict(node) for node in side.records],
    }


def result_to_dict(result: TraceResult) -> dict[str, Any]:
    """The trace as a JSON-ready dict: ``entry`` and, for each side asked for, ``up`` / ``down``."""
    document: dict[str, Any] = {"entry": _node_to_dict(result.entry)}
    for side in (result.up, result.down):
        if side is not None:
            document[side.direction] = _side_to_dict(side)
    return document
