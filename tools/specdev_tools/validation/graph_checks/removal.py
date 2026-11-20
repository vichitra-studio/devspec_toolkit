"""What removing a node takes, as a clause for the advice "remove it": the nodes that still link to it, in which steps, and which of them would be left with an empty required list.

A link left pointing at a removed node is E700, and a required list left empty is E520, so advice to remove a node (a seed, a fixture, a job) names the links that go with it.
"""
from __future__ import annotations

from specdev_tools.graph.model import Graph, Link


def _left_empty(graph: Graph, link: Link, node_id: str) -> bool:
    """Whether the list of *link* (a required one) holds no node but *node_id*: removing the node would leave it empty."""
    holder = graph.by_id.get(link.source)
    if holder is None or not link.decl.required:
        return False
    return {graph.canonical_id(other.target) for other in holder.links if other.field == link.field} == {node_id}


def links_clause(graph: Graph, node_id: str) -> str:
    """``(N nodes, in steps a, b; K of them hold no other entry and need one first)`` for the nodes that link to *node_id* (any node, any field, in play or not); ``""`` when none does.

    A holder needs another entry first when a required link list of it holds no node but *node_id*.  Steps are in the order of every listing.
    """
    links = graph.incoming.get(node_id, ())
    holders = {link.source: graph.by_id.get(link.source) for link in links}
    if not holders:
        return ""
    steps = sorted({holder.step for holder in holders.values() if holder is not None and holder.step is not None}, key=graph.shape.step_key)
    emptied = {link.source for link in links if _left_empty(graph, link, node_id)}
    count = len(holders)
    head = f"{count} node{'' if count == 1 else 's'}" + (f", in step{'' if len(steps) == 1 else 's'} {', '.join(steps)}" if steps else "")
    if not emptied:
        return f"({head})"
    if count == 1:
        return f"({head}; it holds no other entry and needs one first)"
    if len(emptied) == 1:
        return f"({head}; 1 of them holds no other entry and needs one first)"
    return f"({head}; {len(emptied)} of them hold no other entry and need one first)"
