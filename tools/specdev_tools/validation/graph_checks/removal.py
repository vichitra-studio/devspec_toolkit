"""The clause of the advice "remove it": how many nodes link the node, and the command that lists them.

A link left pointing at a removed node is E700 and a required list left empty is E520, so advice to remove a node (a seed, a fixture, a job) says how many nodes link it.  What else removing takes is said once, as a loop, in the catalogue (``docs/developers/error-codes.md``, "Removing a node").
"""
from __future__ import annotations

from specdev_tools.graph.model import Graph
from specdev_tools.graph.trace import TraceOptions, trace_node


def links_clause(graph: Graph, node_id: str) -> str:
    """``(N nodes: specdev trace <id> --down --depth 1 lists them)``; ``""`` when no node links *node_id*.

    The count is the size of that command's answer (``trace_node``, one edge down): the one definition of who links a node.
    """
    count = trace_node(graph, node_id, ("down",), TraceOptions(depth=1)).down.size  # type: ignore[union-attr]
    if not count:
        return ""
    return f"({count} node{'' if count == 1 else 's'}: specdev trace {node_id} --down --depth 1 lists {'it' if count == 1 else 'them'})"
