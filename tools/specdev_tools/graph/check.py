"""The ``graph`` check of ``spec-check``: build the graph of a spec folder, then check its ids and its links."""
from __future__ import annotations

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.kinds import KindRegistryError
from specdev_tools.graph.model import Graph
from specdev_tools.graph.resolve import resolve_graph


def run_graph_check(spec_root: str, repo_root: str, *, graph: Graph | None = None) -> list[SpecError]:
    """E704 for duplicate ids, then E700-E703 for links, over the spec folder *spec_root*.

    A file the builder cannot read (invalid JSON, a root that is not an object) adds nothing here: ``validate_file``
    already reports it.  *graph* is a graph already built from *spec_root* and *repo_root* (no ``files``/``steps``
    narrowing); when ``None`` the check builds it.  A missing or unreadable ``tools/entry_key_registry.json`` (or step order) gives that one E520.
    """
    if graph is None:
        try:
            graph = build_graph(spec_root, repo_root)
        except KindRegistryError as exc:
            return [exc.error]
    return [*check_unique_ids(graph), *resolve_graph(graph)]
