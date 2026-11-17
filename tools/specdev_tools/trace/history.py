"""Historical nodes: the milestones that are done, what they contain, and the plans written for them.

Work of a closed milestone is history: its links keep their lock entries and their resolver checks, but they take no
part in suspect detection, replay or attest (S-003).  A node is historical when it belongs to a milestone whose anchor
row has status ``done``: the milestone itself, everything it contains (tasks and their criteria) and the nodes of the
plan files that name it.
"""
from __future__ import annotations

from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Graph, Node

ANCHOR_ROW_KIND = "anchor-row"
MILESTONE_KIND = "roadmap-milestone"
ABOUT_FIELD = "about"
DONE_STATUS = "done"
_DEFAULT_STATUS = "pending"


def _anchor_status(graph: Graph, anchor: Node) -> str:
    item = item_of(graph, anchor)
    status = item.get("status") if item is not None else None
    return status if isinstance(status, str) else _DEFAULT_STATUS


def done_milestones(graph: Graph) -> set[str]:
    """Ids of the roadmap milestones that a live anchor row with status ``done`` is about."""
    done: set[str] = set()
    for anchor in graph.gated_nodes():
        if anchor.kind != ANCHOR_ROW_KIND or _anchor_status(graph, anchor) != DONE_STATUS:
            continue
        for link in anchor.links:
            milestone = graph.find(link.target) if link.field == ABOUT_FIELD else None
            if milestone is not None and milestone.kind == MILESTONE_KIND:
                done.add(milestone.id)
    return done


def _contained(graph: Graph, root: str) -> set[str]:
    """*root* and every node below it through containment."""
    found: set[str] = set()
    pending = [root]
    while pending:
        node_id = pending.pop()
        if node_id not in found:
            found.add(node_id)
            pending.extend(graph.children.get(node_id, ()))
    return found


def historical_node_ids(graph: Graph) -> set[str]:
    """Ids of the live nodes that belong to a milestone whose anchor row status is ``done``.

    That is each such milestone, the nodes it contains (tasks, task criteria) and the nodes whose plan file names it
    (``Node.milestone``).  A node whose lifecycle is ``not_applicable`` is left out; so is a milestone whose anchor row
    is missing or has any other status.  Returns an empty set for a graph with no anchor row.
    """
    milestones = done_milestones(graph)
    if not milestones:
        return set()
    historical: set[str] = set()
    for milestone in milestones:
        historical |= _contained(graph, milestone)
    historical |= {node.id for node in graph.nodes if node.milestone in milestones}
    return historical & {node.id for node in graph.gated_nodes()}
