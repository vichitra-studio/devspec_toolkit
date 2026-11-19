"""The contract view of a node: the one definition of "what a node says", shared by ``diff`` (M4) and hashing (M5).

A node's contract view holds its contract fields (text normalised), the ids of the links it declares (an alias is
mapped to the current id, so a rename changes nothing) and, for an FR and a task, the views of their criteria.
Status, notes, tags and owner are not part of it.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node, collapse_whitespace

EXCLUDED_FIELDS = frozenset({"status", "notes", "tags", "owner"})
CRITERION_KIND_OF = {"fr": "criterion", "task": "task-criterion"}

_TYPOGRAPHY = {
    **dict.fromkeys((0x2018, 0x2019, 0x201A, 0x201B), "'"),
    **dict.fromkeys((0x201C, 0x201D, 0x201E, 0x201F), '"'),
    **dict.fromkeys((*range(0x2010, 0x2016), 0x2212), "-"),
}
_PATH_STEP = re.compile(r'\.([^.\[\]]+)|\[(\d+)\]|\[("(?:[^"\\]|\\.)*")\]')


def normalise_text(text: str) -> str:
    """Unicode NFC, curly quotes to ASCII, every dash U+2010..U+2015 and the minus U+2212 to ``-``, whitespace collapsed.

    Case is kept: it can carry meaning (MUST).
    """
    return collapse_whitespace(unicodedata.normalize("NFC", text).translate(_TYPOGRAPHY))


def _normalise_value(value: Any) -> Any:
    """*value* with every string in it passed through ``normalise_text``; other scalars are kept."""
    if isinstance(value, str):
        return normalise_text(value)
    if isinstance(value, list):
        return [_normalise_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalise_value(item) for key, item in value.items()}
    return value


def value_at(document: Mapping[str, Any], jq_path: str) -> Any:
    """The value at the jq-style *jq_path* (``.milestones[0].tasks[2]``, ``.environments["prod"]``) of *document*.

    Returns ``None`` when the path leads nowhere (a JSON ``null`` gives ``None`` too); never raises.
    """
    current: Any = document
    position = 0
    while position < len(jq_path):
        step = _PATH_STEP.match(jq_path, position)
        if step is None:
            return None
        name, index, quoted = step.groups()
        try:
            if name is not None:
                current = current[name]
            elif index is not None:
                current = current[int(index)]
            else:
                current = current[json.loads(quoted)]
        except (KeyError, IndexError, TypeError):
            return None
        position = step.end()
    return current


def item_at(document: Mapping[str, Any], jq_path: str) -> Mapping[str, Any] | None:
    """The object at *jq_path* of *document* (as ``value_at`` reads it), or ``None`` when the path does not lead to an object; never raises."""
    current = value_at(document, jq_path)
    return current if isinstance(current, dict) else None


def item_of(graph: Graph, node: Node) -> Mapping[str, Any] | None:
    """The item of the spec file *node* is defined by, as parsed; ``None`` when the graph holds no document for the file or the path misses."""
    document = graph.documents.get(node.file)
    return item_at(document, node.jq_path) if document is not None else None


def _own_fields(node: Node, graph: Graph) -> dict[str, Any]:
    decl, item = graph.decls.get(node.kind), item_of(graph, node)
    if decl is None or item is None:
        return {}
    names = sorted(name for name in decl.contract if name in item and name not in EXCLUDED_FIELDS)
    return {name: _normalise_value(item[name]) for name in names}


def _own_links(node: Node, aliases: Mapping[str, str]) -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}
    for link in node.links:
        targets.setdefault(link.field, []).append(aliases.get(link.target, link.target))
    return {field: sorted(ids) for field, ids in sorted(targets.items())}


def _own_view(node: Node, aliases: Mapping[str, str], graph: Graph) -> dict[str, Any]:
    return {"fields": _own_fields(node, graph), "links": _own_links(node, aliases)}


def contract_view(node: Node, graph: Graph, aliases: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The contract view of *node*: ``{"fields", "links"}``, plus ``"criteria"`` (criterion id to its view) for an FR or a task.

    ``fields`` holds the contract fields the node's kind declares, text normalised; ``links`` maps each link field to the
    sorted ids of the node's own outgoing links, each id passed through *aliases* (alias id to current id).  Criteria
    whose lifecycle is ``not_applicable`` are left out.  A node whose document or kind declaration is not on *graph* has
    no fields.

    The content is read from ``graph.documents`` and ``graph.decls`` (filled by ``build_graph``).

    Returns a JSON-able dict that compares equal when the node's contract is unchanged.
    """
    view = _own_view(node, aliases or {}, graph)
    criterion_kind = CRITERION_KIND_OF.get(node.kind)
    if criterion_kind is not None:
        children = (graph.by_id.get(child) for child in node.children)
        view["criteria"] = {
            child.id: _own_view(child, aliases or {}, graph)
            for child in sorted((c for c in children if c is not None), key=lambda c: c.id)
            if child.kind == criterion_kind and child.lifecycle != NOT_APPLICABLE
        }
    return view
