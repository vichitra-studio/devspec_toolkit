"""The ``graph`` check of ``spec-check``: build the graph of a spec folder, then check its ids, its aliases and its links."""
from __future__ import annotations

from specdev_tools.core.errors import SpecError, link_target, make_error
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.kinds import KindRegistryError
from specdev_tools.graph.model import Graph, Link, Node, article
from specdev_tools.graph.ownership import step_owner
from specdev_tools.graph.resolve import NULL_HOOKS, resolve_graph
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import Lock
from specdev_tools.trace.suspects import LockHook

REPLACES_FIELD = "replaces"


def _node_finding(code: str, node: Node, message: str, *, link: Link | None = None) -> SpecError:
    """A finding about *node*; with *link*, also about that link (``target`` is ``<field>-><target as written>``)."""
    return make_error(
        code, message, file=node.file, jq_path=node.jq_path or None, owner=step_owner(node), node_id=node.id,
        target=link_target(link.field, link.target) if link else None,
    )


def check_alias_space(graph: Graph) -> list[SpecError]:
    """E771 for every alias that equals the id of a node or an alias another node lists.

    Aliases share the id space of the nodes, whatever a node's lifecycle.  Each offending alias is reported once, owned
    by the step of the node that lists it (for an alias two nodes list, the later node in build order).
    """
    listed: dict[str, Node] = {}
    errors: list[SpecError] = []
    for node in graph.live_nodes():
        for alias in dict.fromkeys(node.aliases):
            other = listed.setdefault(alias, node)
            if alias in graph.by_id:
                problem = f"is the id of {article(graph.by_id[alias].kind)} {graph.by_id[alias].kind}"
            elif other.id != node.id:
                problem = f"is also an alias of '{other.id}'"
            else:
                continue
            errors.append(_node_finding("E771", node, f"{node.id}: alias '{alias}' {problem}; give the node a different alias"))
    return errors


def check_replaces(graph: Graph) -> list[SpecError]:
    """E772 for every ``replaces`` link that names a node that is still in the spec (by its id or one of its aliases).

    The link names an id that was deleted; the git history of the spec is not read.  Owned by the holder's step.
    """
    errors: list[SpecError] = []
    for holder in graph.live_nodes():
        for link in holder.links:
            target = graph.find(link.target) if link.field == REPLACES_FIELD else None
            if target is not None:
                message = f"{holder.id}, field {link.field}, target '{link.target}': '{target.id}' is still in the spec; delete it or drop the link"
                errors.append(_node_finding("E772", holder, message, link=link))
    return errors


def run_graph_check(
    spec_root: str, repo_root: str, *, graph: Graph | None = None, lock: Lock | None = None
) -> list[SpecError]:
    """E704 for duplicate ids, E771 for an alias that is not free, E772 for a ``replaces`` of a live node, then E700-E703 for links, over the spec folder *spec_root*.

    With *lock* (the trace lock of the folder) the one resolver run also reports E761 for a link with no lock entry and
    W720 for a new link to a deprecated node; ``None`` leaves both out (a lock that could not be read).

    A file the builder cannot read (invalid JSON, a root that is not an object) adds nothing here: ``validate_file``
    already reports it.  *graph* is a graph already built from *spec_root* and *repo_root* (no ``files``/``steps``
    narrowing); when ``None`` the check builds it.  A missing or unreadable ``tools/entry_key_registry.json`` (or step order) gives that one E520.
    """
    if graph is None:
        try:
            graph = build_graph(spec_root, repo_root)
        except KindRegistryError as exc:
            return [exc.error]
    hooks = NULL_HOOKS if lock is None else LockHook(graph, lock)
    return [*check_unique_ids(graph), *check_alias_space(graph), *check_replaces(graph), *resolve_graph(graph, hooks=hooks, historical=historical_node_ids(graph))]
