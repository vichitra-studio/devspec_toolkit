"""The two values the trace lock stores for a link target: its content hash and its chain stamp.

``own(X)`` hashes what the node says by itself: its kind and its contract view (contract fields and its own outgoing
link ids) without the folded criteria.  A link id is hashed under the FIRST NAME of its target: the first entry of the
target's ``aliases`` when it has any, else its id.  ``specdev node rename`` appends the old id to ``aliases``, so the
first name never changes and a rename changes no value computed here.  From ``own``:

* ``content(X)`` is ``own(X)``; for an FR and a task it also covers the ``own`` of each folded criterion.
* ``up(X)`` covers ``own(X)``, ``up`` of the containment parent and the ``chain`` of every link target, so a change
  anywhere above a node reaches it.  A criterion takes ``up`` of its parent, not the parent's folded content, so editing
  one criterion does not reach its siblings.
* ``chain(X)`` is ``up(X)``; for an FR and a task it also covers ``up`` of each folded criterion, so a criterion edit
  moves the chain of its FR and of everything that links to the FR.
* A seed has one value, the hash of its whitespace-collapsed text, for both content and chain.

Where an id enters a digest (the ``cycle:`` marker) or decides an order (which node of a cycle is evaluated first), the
first name is used as well.  The functions are pure: seed text comes in as a mapping (seed id to text, see ``graph.gitview.read_seed_texts``), and
nothing here touches a file or git.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from specdev_tools.graph.contract import contract_view
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph, Node, collapse_whitespace, first_name_index

HASH_PREFIX = "sha256:"
_UP, _CHAIN = "up", "chain"
_Key = tuple[str, str]


def _digest(parts: Iterable[Any]) -> str:
    """``sha256:<hex>`` of the canonical JSON of *parts* (sorted keys, no extra spaces, characters kept as they are)."""
    text = json.dumps(list(parts), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return HASH_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_hash(text: str) -> str:
    """Hash of a seed's text with every run of whitespace collapsed to one space and the ends stripped."""
    return _digest([collapse_whitespace(text)])


def _missing_seed_hash(seed_id: str) -> str:
    return _digest([f"missing:{seed_id}"])


@dataclass(frozen=True)
class _Own:
    """``own`` of one node and the ids of the criteria folded into it (empty unless an FR or a task)."""

    own: str
    folded: tuple[str, ...]


def _own_of(node: Node, graph: Graph, names: Mapping[str, str]) -> _Own:
    """``own`` of *node* with link ids and folded criteria named through *names* (``first_name_index``)."""
    view = contract_view(node, graph, aliases=names)
    criteria = view.pop("criteria", {})
    folded = sorted(criteria, key=lambda criterion: (names.get(criterion, criterion), criterion))
    return _Own(_digest([node.kind, view]), tuple(folded))


class _Hasher:
    """One pass over a graph: ``own``, ``up`` and ``chain`` per node, each computed once and kept.

    ``up`` and ``chain`` depend on each other through links, so they are evaluated with an explicit stack (a deep chain
    does not hit the recursion limit).  A dependency that is still being evaluated is a link cycle and contributes
    ``cycle:<id>``; a link target that is not in the graph contributes ``missing:<id>``.  The resolver reports both.
    """

    def __init__(self, graph: Graph, seed_texts: Mapping[str, str]) -> None:
        self._graph = graph
        self._seed_texts = seed_texts
        self._names = first_name_index(graph)
        self._own: dict[str, _Own] = {}
        self._values: dict[_Key, str] = {}
        self._open: set[_Key] = set()

    def name(self, node_id: str) -> str:
        """The first name of the node *node_id*: what a digest and an order use instead of its current id."""
        return self._names.get(node_id, node_id)

    def sort_key(self, node_id: str) -> tuple[str, str]:
        """The order of evaluation: by first name, then id."""
        return (self.name(node_id), node_id)

    def own(self, node_id: str) -> _Own:
        if node_id not in self._own:
            self._own[node_id] = _own_of(self._graph.by_id[node_id], self._graph, self._names)
        return self._own[node_id]

    def content(self, node_id: str) -> str:
        if self._graph.by_id[node_id].kind == SEED_KIND:
            return self.value((_UP, node_id))
        own = self.own(node_id)
        if not own.folded:
            return own.own
        return _digest([own.own, sorted(self.own(child).own for child in own.folded)])

    def value(self, key: _Key) -> str:
        """The ``up`` or ``chain`` value named by *key*, evaluating whatever it needs first."""
        stack = [key]
        while stack:
            current = stack[-1]
            if current in self._values:
                stack.pop()
            elif current in self._open:
                self._values[current] = self._combine(current)
                self._open.discard(current)
                stack.pop()
            else:
                self._open.add(current)
                stack.extend(dep for dep in self._deps(current) if dep not in self._values and dep not in self._open)
        return self._values[key]

    def _deps(self, key: _Key) -> list[_Key]:
        """The keys whose values *key* is built from, for the nodes the graph holds."""
        kind, node_id = key
        node = self._graph.by_id[node_id]
        if node.kind == SEED_KIND:
            return []
        if kind == _CHAIN:
            return [(_UP, node_id), *((_UP, child) for child in self.own(node_id).folded)]
        parent = self._parent(node)
        return ([(_UP, parent)] if parent else []) + [(_CHAIN, target) for target in self._targets(node) if target in self._graph.by_id]

    def _parent(self, node: Node) -> str | None:
        """The containment parent of *node* when the graph holds it."""
        return node.parent if node.parent in self._graph.by_id else None

    def _targets(self, node: Node) -> list[str]:
        """The current ids the links of *node* point at (a link that names no node keeps its text), without repeats, in first-name order."""
        return sorted({self._graph.canonical_id(link.target) for link in node.links}, key=self.sort_key)

    def _contribution(self, dep: _Key) -> str:
        if dep in self._values:
            return self._values[dep]
        return f"cycle:{self.name(dep[1])}"

    def _combine(self, key: _Key) -> str:
        kind, node_id = key
        node = self._graph.by_id[node_id]
        if node.kind == SEED_KIND:
            text = self._seed_texts.get(node_id)
            return _missing_seed_hash(node_id) if text is None else seed_hash(text)
        if kind == _CHAIN:
            folded = [self._contribution((_UP, child)) for child in self.own(node_id).folded]
            return _digest([self._contribution((_UP, node_id)), sorted(folded)])
        parts: list[Any] = [self.own(node_id).own]
        parent = self._parent(node)
        if parent:
            parts.append(self._contribution((_UP, parent)))
        parts.append(sorted(
            self._contribution((_CHAIN, target)) if target in self._graph.by_id else f"missing:{target}"
            for target in self._targets(node)
        ))
        return _digest(parts)


def _hasher_for(node_id: str, graph: Graph, seed_texts: Mapping[str, str]) -> _Hasher:
    """A hasher over *graph*; ``KeyError`` when *node_id* is not one of its nodes."""
    if node_id not in graph.by_id:
        raise KeyError(node_id)
    return _Hasher(graph, seed_texts)


def own_hash(node_id: str, graph: Graph) -> str:
    """``own`` of the node *node_id*: its kind and contract view without the folded criteria.

    Raises:
        KeyError: *node_id* is not a node of *graph*.
    """
    return _hasher_for(node_id, graph, {}).own(node_id).own


def compute_all(graph: Graph, seed_texts: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    """``{node id: (content, chain)}`` for every node of *graph* whose lifecycle is not ``not_applicable``.

    Both values are ``sha256:<64 hex>``.  *seed_texts* maps a seed id to its whitespace-collapsed text; a seed with no
    entry hashes as ``missing:<id>``, so every link into it is suspect.  An id defined twice is hashed from its first
    definition.  Link cycles are broken at the node evaluated first (nodes are visited in first-name order), so the result
    depends neither on file order nor on a rename.
    """
    hasher = _Hasher(graph, seed_texts)
    ids = sorted({node.id for node in graph.gated_nodes()}, key=hasher.sort_key)
    return {node_id: (hasher.content(node_id), hasher.value((_CHAIN, node_id))) for node_id in ids}


def content_hash(node_id: str, graph: Graph, seed_texts: Mapping[str, str]) -> str:
    """The content hash of *node_id*: what a lock entry stores as ``content_hash``.

    Raises:
        KeyError: *node_id* is not a node of *graph*.
    """
    hasher = _hasher_for(node_id, graph, seed_texts)
    return hasher.content(node_id)


def chain_stamp(node_id: str, graph: Graph, seed_texts: Mapping[str, str]) -> str:
    """The chain stamp of *node_id*: what a lock entry stores as ``chain_stamp``.

    Raises:
        KeyError: *node_id* is not a node of *graph*.
    """
    hasher = _hasher_for(node_id, graph, seed_texts)
    return hasher.value((_CHAIN, node_id))
