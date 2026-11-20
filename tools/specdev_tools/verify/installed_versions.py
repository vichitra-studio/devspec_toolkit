"""The versions of the third parties a binding relies on, as the working tree declares them, for the evidence of a run.

A third party is relied on by a proved node when that node links to it with ``relies_on`` or when a component the node is
``provided_by`` connects to it through one of its connections (``graph.queries.relied_on_third_parties``).  Its version is read from the
first pin source the host declares for it (``spec/common/host_declarations.json``), unless the caller names the version the
deploy installed.  A third party with no declared source has no entry: it is compared against nothing.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from specdev_tools.core.host_declarations import HostDeclarations
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.queries import relied_on_third_parties
from specdev_tools.thirdparty.sources import SourceError, read_source


def installed_versions(
    nodes: Iterable[Node], graph: Graph, declarations: HostDeclarations, git_root: str, overrides: Mapping[str, str]
) -> tuple[dict[str, str], list[str]]:
    """``(versions, notes)`` for the third parties the *nodes* rely on.

    A version in *overrides* wins; else the first declared source is read under *git_root*.  A source that cannot give a
    version adds a note (a plain line) and the third party has no entry.
    """
    versions: dict[str, str] = {}
    notes: list[str] = []
    for third_party in relied_on_third_parties(graph, nodes):
        if third_party in overrides:
            versions[third_party] = overrides[third_party]
            continue
        sources = declarations.pin_sources.get(third_party, ())
        if not sources:
            continue
        try:
            versions[third_party] = read_source(sources[0], git_root)
        except SourceError as exc:
            notes.append(f"no installed version recorded for '{third_party}': {exc}")
    return versions, notes
