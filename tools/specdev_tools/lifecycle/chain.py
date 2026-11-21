"""The chain of a milestone: the nodes whose change makes the milestone's work suspect, and the suspect links on it.

The close gate and ``milestone start`` ask the same question, "is something I depend on suspect?", and answer it from one
set of nodes.  The chain of a milestone is the milestone, what it contains (its tasks and their criteria), the nodes whose
plan file names it (its plan items and their execution records), and everything those criteria and plan items reach
upward through their links, up to the seeds.  A suspect link is on the chain when its holder or its target is in it, so a
link of another milestone that points at an upstream node this milestone does not reach is not.

Nothing here writes a file.
"""
from __future__ import annotations

from collections.abc import Mapping

from ..core.errors import SpecError
from ..graph.model import Graph
from ..graph.names import TASK_CRITERION
from ..graph.trace import trace_node
from ..trace.history import contained
from ..trace.lockfile import Lock
from ..trace.suspects import check_lock

SUSPECT_CODE = "E763"
_LINK_SEPARATOR = "->"


def milestone_chain(graph: Graph, milestone_id: str) -> frozenset[str]:
    """The ids of the chain of *milestone_id*: itself, what it contains, the nodes its plan file names, and everything those criteria and plan items reach upward.

    A milestone no node knows has the chain of its own id.
    """
    root = graph.canonical_id(milestone_id)
    chain = contained(graph, root)
    chain.update(node.id for node in graph.gated_nodes() if node.milestone is not None and graph.canonical_id(node.milestone) == root)
    starts = [node_id for node_id in chain if _walks_up(graph, node_id)]
    for node_id in starts:
        chain.update(node.id for node in trace_node(graph, node_id, ("up",)).reached)
    return frozenset(chain)


def _walks_up(graph: Graph, node_id: str) -> bool:
    """Whether the upward walk starts at *node_id*: a task criterion, or a node of a plan file (a plan item)."""
    node = graph.by_id.get(node_id)
    return node is not None and (node.kind == TASK_CRITERION or node.milestone is not None)


def on_chain(chain: frozenset[str], graph: Graph, holder: str, target: str) -> bool:
    """Whether a link from *holder* to *target* is on *chain*: either end is in it (an alias of an end counts as the node)."""
    return graph.canonical_id(holder) in chain or graph.canonical_id(target) in chain


def suspect_links_on_chain(graph: Graph, lock: Lock, seed_texts: Mapping[str, str], chain: frozenset[str]) -> list[SpecError]:
    """The E763 findings (``trace.suspects.check_lock``) whose link is on *chain*, in the order the trace-lock check reports them.

    The findings are the ones the ``trace-lock`` check prints, with the owner it gives them: a caller that reports them under
    another owner stamps it.  A finding about a link names it in ``SpecError.target`` as ``<field>-><target>``.
    """
    return [
        error
        for error in check_lock(graph, lock, seed_texts)
        if error.code == SUSPECT_CODE and error.node_id is not None and error.target is not None
        and on_chain(chain, graph, error.node_id, error.target.partition(_LINK_SEPARATOR)[2])
    ]
