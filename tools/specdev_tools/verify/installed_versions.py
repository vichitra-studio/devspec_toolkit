"""The versions of the third parties a binding relies on, as the working tree declares them, for the evidence of a run.

A third party is relied on by a proved node when that node links to it with ``relies_on`` or when a component the node is
``provided_by`` connects to it through one of its connections (``graph.queries.relied_on_third_parties``).  Its version is read from the
first pin source the host declares for it (``spec/common/host_declarations.json``), unless the caller names the version the
deploy installed.  A third party with no declared source has no entry: it is compared against nothing.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from specdev_tools.core.errors import refusal
from specdev_tools.core.host_declarations import HostDeclarations
from specdev_tools.core.pin_sources import SourceError, read_source
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import THIRD_PARTY
from specdev_tools.graph.queries import relied_on_third_parties, unknown_node_error


def installed_pairs(items: Sequence[str]) -> list[tuple[str, str]] | None:
    """``(third party, version)`` from ``TP=VERSION`` items; ``None`` when one is not of that form."""
    pairs: list[tuple[str, str]] = []
    for item in items:
        name, separator, version = item.partition("=")
        if not separator or not name or not version:
            return None
        pairs.append((name, version))
    return pairs


def third_party_of(graph: Graph, name: str) -> Node:
    """The third-party node *name* (an id or an alias) names.

    Raises:
        FindingError: E706 when no node has the id, or the node is not a third party.
    """
    node = graph.find(name)
    if node is None:
        raise unknown_node_error(graph, name)
    if node.kind != THIRD_PARTY:
        raise refusal("E706", f"'{node.id}' is of kind {node.kind}, not a third party; give the id of a third-party node")
    return node


def installed_overrides(pairs: Sequence[tuple[str, str]], graph: Graph) -> dict[str, str]:
    """``{third party id: version}`` for the *pairs* of ``installed_pairs``, each name resolved through the aliases: the one reading of ``--installed``.

    Raises:
        FindingError: E706 when a name is no node, or is not a third party.
        ValueError: a third party is named twice (the message is the usage error).
    """
    overrides: dict[str, str] = {}
    for name, version in pairs:
        node_id = third_party_of(graph, name).id
        if node_id in overrides:
            raise ValueError(f"--installed names '{node_id}' twice; give one version for each third party")
        overrides[node_id] = version
    return overrides


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
