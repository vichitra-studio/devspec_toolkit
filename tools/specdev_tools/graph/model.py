"""Graph model: ``Node``, ``Link``, ``LoadError`` and the indexed ``Graph``."""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.graph.kinds import KindDecl, LinkDecl

LIFECYCLES = ("active", "deprecated", "not_applicable")
DEFAULT_LIFECYCLE = "active"
NOT_APPLICABLE = "not_applicable"
DEPRECATED = "deprecated"
# First non-empty field of a node item that names it for a reader (PD-09); one rule for every kind.
LABEL_FIELDS = ("title", "name", "statement", "text", "description", "summary", "label", "preferred_label")
LABEL_MAX_CHARS = 120
UNRANKED = 10**6  # sort rank of a node with no step, or a step that is not in the waterfall: after every real rank
_WHITESPACE = re.compile(r"\s+")


def collapse_whitespace(text: str) -> str:
    """*text* with every run of whitespace replaced by one space and the ends trimmed."""
    return _WHITESPACE.sub(" ", text).strip()


def node_label(item: Mapping[str, Any]) -> str:
    """Short text that names a node: the first non-empty ``LABEL_FIELDS`` string, whitespace-collapsed, cut at 120 characters.

    Returns an empty string when no such field holds text; never raises on a wrong-typed value.
    """
    for name in LABEL_FIELDS:
        value = item.get(name)
        text = collapse_whitespace(value) if isinstance(value, str) else ""
        if text:
            return text[:LABEL_MAX_CHARS]
    return ""


@dataclass(frozen=True)
class Link:
    """One declared link: node ``source`` points at ``target`` through ``field``; ``decl`` is the field's declaration."""

    source: str
    field: str
    target: str
    decl: LinkDecl


@dataclass(frozen=True)
class Node:
    """One graph node.

    ``file`` is relative to the spec root (for a seed, the seed file path of its manifest entry); ``step`` is ``None``
    for a kind with no home step and ``"seed"`` for a seed; ``milestone`` is the ``milestone`` key of a plan file.
    """

    id: str
    kind: str
    step: str | None
    role: str | None
    file: str
    jq_path: str
    parent: str | None
    children: tuple[str, ...]
    lifecycle: str
    scope: str | None
    links: tuple[Link, ...]
    label: str
    milestone: str | None = None


@dataclass(frozen=True)
class LoadError:
    """A registered file the builder skipped: ``file`` relative to the spec root, and why."""

    file: str
    message: str


@dataclass(frozen=True)
class SpecShape:
    """What the builder knew about the spec and the registry, for readers that judge links.

    ``step_ranks`` maps each step to its place in the waterfall (``"seed"`` is ``-1``); ``kind_steps`` maps a kind to
    the steps whose files declare it; ``files_by_step`` lists the files present in the spec folder (relative paths),
    per step, whether or not the build read them.
    """

    step_ranks: Mapping[str, int] = field(default_factory=dict)
    kind_steps: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    files_by_step: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def rank_of(self, step: str | None) -> int:
        """Sort rank of *step*: its place in the waterfall; ``None`` (no home step) and an unknown step rank ``UNRANKED``, last."""
        return self.step_ranks.get(step, UNRANKED) if step is not None else UNRANKED


@dataclass
class Graph:
    """Nodes in build order plus the indexes every reader uses.

    ``by_id`` keeps the first definition of an id; ``dups`` lists every definition of an id defined more than once;
    ``alias_index`` is empty until M5 fills it; ``shape``, ``documents`` (the parsed files the build read,
    by path relative to the spec root) and ``decls`` (kind name to declaration) are empty for a graph built from nodes alone.
    """

    nodes: list[Node] = field(default_factory=list)
    load_errors: list[LoadError] = field(default_factory=list)
    by_id: dict[str, Node] = field(default_factory=dict)
    by_kind: dict[str, list[Node]] = field(default_factory=dict)
    dups: dict[str, list[Node]] = field(default_factory=dict)
    outgoing: dict[str, list[Link]] = field(default_factory=dict)
    incoming: dict[str, list[Link]] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)
    alias_index: dict[str, str] = field(default_factory=dict)
    shape: SpecShape = field(default_factory=SpecShape)
    documents: dict[str, Mapping[str, Any]] = field(default_factory=dict, repr=False, compare=False)
    decls: dict[str, KindDecl] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_nodes(
        cls, nodes: list[Node], load_errors: list[LoadError] | None = None, shape: SpecShape | None = None
    ) -> Graph:
        """Index *nodes* (in the order given) into a ``Graph``."""
        graph = cls(nodes=list(nodes), load_errors=list(load_errors or []), shape=shape or SpecShape())
        defined: dict[str, list[Node]] = defaultdict(list)
        by_kind: dict[str, list[Node]] = defaultdict(list)
        outgoing: dict[str, list[Link]] = defaultdict(list)
        incoming: dict[str, list[Link]] = defaultdict(list)
        for node in nodes:
            defined[node.id].append(node)
            by_kind[node.kind].append(node)
            for link in node.links:
                outgoing[node.id].append(link)
                incoming[link.target].append(link)
            if node.children:
                graph.children[node.id] = list(node.children)
        graph.by_id = {node_id: found[0] for node_id, found in defined.items()}
        graph.dups = {node_id: found for node_id, found in defined.items() if len(found) > 1}
        graph.by_kind, graph.outgoing, graph.incoming = dict(by_kind), dict(outgoing), dict(incoming)
        return graph

    def live_nodes(self) -> list[Node]:
        """Every node; used only by the uniqueness check."""
        return list(self.nodes)

    def gated_nodes(self) -> list[Node]:
        """Every node except those whose lifecycle is ``not_applicable``; what every other consumer reads."""
        return [node for node in self.nodes if node.lifecycle != NOT_APPLICABLE]
