"""Read queries over the spec graph: the view of a node (``specdev node <id>``) and the valid targets of a link field
(``specdev node candidates``).

Both are functions of a built ``Graph`` and read nothing else: a node's own content comes from ``graph.documents``.
A command usage error (an unknown id, kind or field) is raised as ``QueryTargetError`` carrying the E706 finding in
``error``; a duplicated id is a finding about the spec and comes back in ``NodeReport.errors`` beside every definition.
The text and JSON renderers are here so that the command only prints what they return.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.json_utils import _nearest_ids
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node
from specdev_tools.graph.resolve import HISTORY_FIELDS, link_target_allowed

DEPRECATED = "deprecated"
NEAREST_COUNT = 3
_NO_VALUE = "-"


class QueryTargetError(Exception):
    """A read command was given an id, kind or field the graph does not know; the E706 finding is in ``error``."""

    def __init__(self, error: SpecError) -> None:
        super().__init__(error.message)
        self.error = error


def _unknown(message: str) -> QueryTargetError:
    return QueryTargetError(make_error("E706", message))


@dataclass(frozen=True)
class LinkView:
    """One outgoing link of a node and what it points at; ``kind`` is ``None`` when no node has the target id."""

    field: str
    target: str
    kind: str | None
    step: str | None
    lifecycle: str | None
    label: str


@dataclass(frozen=True)
class IncomingCount:
    """How many nodes of ``kind`` point at a node through the link field ``verb``."""

    verb: str
    kind: str
    count: int


@dataclass(frozen=True)
class NodeView:
    """Everything ``specdev node`` shows for one definition of an id.

    ``content`` is the node's own item (its child nodes replaced by their ids unless ``full``), or ``None`` when the
    document or the path is not on the graph.  ``aliases`` is empty until a node has some.
    """

    id: str
    kind: str
    step: str | None
    role: str | None
    lifecycle: str
    scope: str | None
    file: str
    jq_path: str
    label: str
    content: Mapping[str, Any] | None
    children: tuple[str, ...]
    outgoing: tuple[LinkView, ...]
    incoming: tuple[IncomingCount, ...]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class NodeReport:
    """The views for the ids asked, in order (one per definition, so several for a duplicated id), and the E704 findings."""

    views: tuple[NodeView, ...]
    errors: tuple[SpecError, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """One node a link field may point at."""

    id: str
    kind: str
    step: str | None
    file: str
    lifecycle: str
    scope: str | None
    label: str

    @property
    def deprecated(self) -> bool:
        return self.lifecycle == DEPRECATED


@dataclass(frozen=True)
class CandidateList:
    """The candidates shown (cut by ``limit``), how many matched before the cut, and which field they are for."""

    holder_kind: str
    field: str
    candidates: tuple[Candidate, ...]
    total: int = 0


def _nearest_message(subject: str, wanted: str, known: Iterable[str]) -> str:
    near = [entry["id"] for entry in _nearest_ids(wanted, sorted(known), NEAREST_COUNT)]
    suffix = f"; nearest: {', '.join(near)}" if near else ""
    return f"no {subject} {wanted!r}{suffix}"


def _find(graph: Graph, node_id: str) -> Node | None:
    return graph.by_id.get(node_id) or graph.by_id.get(graph.alias_index.get(node_id, ""))


def _link_view(graph: Graph, link_field: str, target_id: str) -> LinkView:
    target = _find(graph, target_id)
    if target is None:
        return LinkView(link_field, target_id, None, None, None, "")
    return LinkView(link_field, target_id, target.kind, target.step, target.lifecycle, target.label)


def _incoming(graph: Graph, node: Node) -> tuple[IncomingCount, ...]:
    counts: Counter[tuple[str, str]] = Counter()
    for link in graph.incoming.get(node.id, ()):
        source = graph.by_id.get(link.source)
        if source is not None and source.lifecycle != NOT_APPLICABLE:
            counts[(link.field, source.kind)] += 1
    return tuple(IncomingCount(verb, kind, count) for (verb, kind), count in sorted(counts.items()))


def _kind_of(graph: Graph, node_id: str) -> str | None:
    node = graph.by_id.get(node_id)
    return node.kind if node is not None else None


def _own_content(graph: Graph, node: Node, full: bool) -> Mapping[str, Any] | None:
    """The node's item; unless *full*, each nested collection of the kind is replaced by the ids of its child nodes."""
    document = graph.documents.get(node.file)
    item = item_at(document, node.jq_path) if document is not None else None
    decl = graph.decls.get(node.kind)
    if item is None or full or decl is None:
        return item
    shown = dict(item)
    for nested in decl.nested:
        key = nested.array_path.lstrip(".")
        if key in shown:
            shown[key] = [child for child in node.children if _kind_of(graph, child) == nested.kind]
    return shown


def _view(graph: Graph, node: Node, full: bool) -> NodeView:
    return NodeView(
        id=node.id,
        kind=node.kind,
        step=node.step,
        role=node.role,
        lifecycle=node.lifecycle,
        scope=node.scope,
        file=node.file,
        jq_path=node.jq_path,
        label=node.label,
        content=_own_content(graph, node, full),
        children=node.children,
        outgoing=tuple(_link_view(graph, link.field, link.target) for link in node.links),
        incoming=_incoming(graph, node),
        aliases=tuple(sorted(alias for alias, current in graph.alias_index.items() if current == node.id)),
    )


def node_view(graph: Graph, ids: Sequence[str], *, full: bool = False) -> NodeReport:
    """The view of each id of *ids*, in the order given.

    An id defined more than once gives one view per definition and the E704 findings for it.  Child nodes are shown by
    id only; *full* includes their content.  Incoming counts leave out nodes whose lifecycle is ``not_applicable``.

    Raises:
        QueryTargetError: one or more ids are not on the graph (E706, one message naming each with its nearest ids).
    """
    resolved = [(node_id, _find(graph, node_id)) for node_id in ids]
    missing = [node_id for node_id, found in resolved if found is None]
    if missing:
        raise _unknown("; ".join(_nearest_message("node with the id", node_id, graph.by_id) for node_id in missing))
    views = [
        _view(graph, definition, full)
        for _, found in resolved
        if found is not None
        for definition in graph.dups.get(found.id, [found])
    ]
    shown = {view.id for view in views}
    errors = tuple(error for error in check_unique_ids(graph) if error.node_id in shown)
    return NodeReport(tuple(views), errors)


@dataclass(frozen=True)
class _Holder:
    """The node or kind a link would start from: its kind, its steps and, for a node, what it already links to."""

    kind: str
    steps: tuple[str, ...]
    node: Node | None = None
    linked: frozenset[str] = field(default_factory=frozenset)


def _holder_of_kind(graph: Graph, kind: str) -> _Holder:
    steps = graph.shape.kind_steps.get(kind)
    if kind not in graph.decls or steps is None:
        raise _unknown(_nearest_message("kind", kind, graph.decls))
    return _Holder(kind, steps)


def _holder_of_node(graph: Graph, node_id: str, link_field: str) -> _Holder:
    node = _find(graph, node_id)
    if node is None:
        raise _unknown(_nearest_message("node with the id", node_id, graph.by_id))
    linked = frozenset(link.target for link in node.links if link.field == link_field)
    return _Holder(node.kind, (node.step,) if node.step is not None else (), node, linked)


def _link_decl(graph: Graph, holder_kind: str, link_field: str) -> LinkDecl:
    if link_field in HISTORY_FIELDS:
        raise _unknown(f"field {link_field!r} targets deleted ids; there are no candidates")
    decl = graph.decls.get(holder_kind)
    links = {link.field: link for link in decl.links} if decl is not None else {}
    if link_field not in links:
        known = ", ".join(sorted(links)) or "none"
        raise _unknown(f"kind {holder_kind!r} has no link field {link_field!r}; its link fields: {known}")
    return links[link_field]


def _same_step_ancestors(graph: Graph, holder: Node) -> set[str]:
    """Ids of the nodes of the holder's step from which the holder can be reached through links inside that step.

    Linking the holder to one of them would close a cycle (E703).
    """
    found: set[str] = set()
    pending = [holder.id]
    while pending:
        for link in graph.incoming.get(pending.pop(), ()):
            source = graph.by_id.get(link.source)
            if source is not None and source.step == holder.step and source.id not in found:
                found.add(source.id)
                pending.append(source.id)
    return found


def _matches(node: Node, query: str | None) -> bool:
    return not query or query.casefold() in f"{node.id} {node.label}".casefold()


def _candidate(node: Node) -> Candidate:
    return Candidate(node.id, node.kind, node.step, node.file, node.lifecycle, node.scope, node.label)


def candidates(
    graph: Graph,
    link_field: str,
    *,
    kind: str | None = None,
    for_id: str | None = None,
    query: str | None = None,
    limit: int | None = None,
) -> CandidateList:
    """The nodes that the link field *link_field* may point at, for a holder of *kind* or for the node *for_id*.

    A candidate is of a kind the field accepts, in a step earlier than the holder's (or the holder's own step when the
    field declares the candidate's kind as same-step) and is not ``not_applicable``; a deprecated one is included.  With
    *for_id* the holder itself, the nodes the holder already links to in this field and the nodes that would close a
    same-step cycle are left out.  *query* keeps the nodes whose id or label contains the text (case-insensitive);
    *limit* cuts the list after sorting by step order, then id; ``total`` counts the matches before the cut.

    Exactly one of *kind* and *for_id* is given (anything else is a ``ValueError``: the command's parser prevents it).

    Raises:
        QueryTargetError: the kind, the node or the field is unknown, or the field is ``replaces`` / ``removes`` (E706).
    """
    if (kind is None) == (for_id is None):
        raise ValueError("give exactly one of kind and for_id")
    holder = _holder_of_kind(graph, kind) if kind is not None else _holder_of_node(graph, for_id or "", link_field)
    decl = _link_decl(graph, holder.kind, link_field)
    excluded = holder.linked
    if holder.node is not None:
        excluded = excluded | {holder.node.id} | _same_step_ancestors(graph, holder.node)
    ranks = graph.shape.step_ranks
    matches = sorted(
        (
            node
            for node in graph.gated_nodes()
            if node.id not in excluded
            and any(link_target_allowed(decl, step, node, graph.shape) for step in holder.steps or (None,))
            and _matches(node, query)
        ),
        key=lambda node: (ranks.get(node.step or "", len(ranks)), node.id),
    )
    shown = matches if limit is None else matches[: max(limit, 0)]
    return CandidateList(holder.kind, link_field, tuple(_candidate(node) for node in shown), len(matches))


def _cell(value: str | None) -> str:
    return value if value else _NO_VALUE


def _link_line(link: LinkView) -> str:
    if link.kind is None:
        return f"  {link.field} -> {link.target}  (not found)"
    return f"  {link.field} -> {link.target}  [{link.kind}, step {_cell(link.step)}, {link.lifecycle}]  {link.label}"


def _view_text(view: NodeView) -> list[str]:
    lines = [
        f"{view.id}  {view.kind}  step {_cell(view.step)}  role {_cell(view.role)}  lifecycle {view.lifecycle}"
        f"  scope {_cell(view.scope)}",
        f"  file {view.file}  path {view.jq_path or '.'}",
    ]
    if view.aliases:
        lines.append(f"  aliases: {', '.join(view.aliases)}")
    if view.content is not None:
        lines.append("  content:")
        lines.extend(f"    {row}" for row in json.dumps(view.content, indent=2, ensure_ascii=False).splitlines())
    lines.append("  links out:" if view.outgoing else "  links out: none")
    lines.extend(_link_line(link) for link in view.outgoing)
    lines.append("  links in:" if view.incoming else "  links in: none")
    lines.extend(f"  {entry.verb} <- {entry.count} {entry.kind}" for entry in view.incoming)
    return lines


def node_text(report: NodeReport) -> str:
    """The short text form of a ``NodeReport``: one block per view, then the E704 findings."""
    lines: list[str] = []
    for view in report.views:
        lines.extend(_view_text(view))
    lines.extend(error.render() for error in report.errors)
    return "\n".join(lines)


def _error_json(error: SpecError) -> dict[str, Any]:
    return {name: value for name, value in asdict(error).items() if value is not None}


def node_json(report: NodeReport) -> dict[str, Any]:
    """The JSON-able form of a ``NodeReport``: ``{"nodes": [...], "errors": [...]}``."""
    return {"nodes": [asdict(view) for view in report.views], "errors": [_error_json(e) for e in report.errors]}


def candidates_text(result: CandidateList) -> str:
    """The short text form of a ``CandidateList``: a header, then one line per candidate (a deprecated one is flagged)."""
    shown = len(result.candidates)
    lines = [f"{result.total} candidates for {result.holder_kind}.{result.field} (showing {shown})"]
    for item in result.candidates:
        flag = "  DEPRECATED" if item.deprecated else ""
        lines.append(
            f"{item.id}  {item.kind}  step {_cell(item.step)}  {item.file}  scope {_cell(item.scope)}"
            f"  {item.lifecycle}{flag}  {item.label}"
        )
    return "\n".join(lines)


def candidates_json(result: CandidateList) -> dict[str, Any]:
    """The JSON-able form of a ``CandidateList``."""
    return {
        "kind": result.holder_kind,
        "field": result.field,
        "total": result.total,
        "candidates": [{**asdict(item), "deprecated": item.deprecated} for item in result.candidates],
    }
