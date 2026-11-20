"""A small graph builder for the tests of the graph checks that read links and containment (refinement, cross-cutting).

``spec`` takes node rows (``row(...)``), nests each node under its ``parent``, and returns a ``GraphCheckContext`` on
the toolkit's real ownership table.  ``closed_milestone`` adds the anchor row that closes a roadmap milestone.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node, SpecShape
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.graph._synth import ROOT

VERIFIER_KINDS = ("fixture", "job")
PLAN_KINDS = ("task", "task-criterion", "roadmap-milestone", "anchor-row")
ANCHOR_FILE = "anchors.json"
STEP_RANKS = {"04": 0, "08": 1, "14": 2}


def row(
    node_id: str, kind: str, *, parent: str | None = None, lifecycle: str = "active", scope: str | None = None, **links: list[str]
) -> Node:
    """A node *node_id* of *kind*; each keyword is a link field with its target ids; ``children`` is filled by ``spec``."""
    role = "verifier" if kind in VERIFIER_KINDS else "plan" if kind in PLAN_KINDS else "obligation-system"
    made = [Link(node_id, field, target, LinkDecl(field, (), False, False, ())) for field, targets in links.items() for target in targets]
    return Node(node_id, kind, "14" if role == "plan" else "04", role, f"{node_id}.json", ".item", parent, (), lifecycle, scope, tuple(made), node_id)


def closed_milestone(milestone_id: str) -> list[Node]:
    """The milestone *milestone_id* and the anchor row, with status ``done``, that closes it."""
    anchor = replace(row(f"anchor-{milestone_id}", "anchor-row", about=[milestone_id]), file=ANCHOR_FILE, jq_path=".rows[0]")
    return [row(milestone_id, "roadmap-milestone"), anchor]


def spec(*nodes: Node) -> GraphCheckContext:
    """A context on a graph of *nodes* (a node under its ``parent``; containment in both directions), the order given kept."""
    children: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.parent:
            children[node.parent].append(node.id)
    placed = [replace(node, children=tuple(children[node.id])) for node in nodes]
    graph = Graph.from_nodes(placed, shape=SpecShape(step_ranks=STEP_RANKS))
    graph.documents[ANCHOR_FILE] = {"rows": [{"status": "done"}]}
    return GraphCheckContext.from_graph(graph, None, str(ROOT))
