"""``specdev coverage``: views over the reverse index of the graph.  Nothing here is a rule, an error or a stored file.

The reverse index lists, for a node, the links that point at it and whether each is *current*: the lock entry of the
link stores the content hash its target had when the holder accepted it, and the link is current while that equals the
target's content hash now (a changed obligation is uncovered until it is refined again).  Links held by historical nodes
are listed (a closed refinement counts while its hash still matches); a suspect link held by a live node is listed and
marked.  Three link counts (FR with an API, FR with a fixture, capability with an FR), the FR-centred matrix and the
share of criteria with a current refinement are computed from it, direct links only.  Coverage gaps of the role rules
come from the gap seam (``trace.gaps``) and are only grouped here.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Link, Node
from specdev_tools.trace.gaps import coverage_gaps
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import Lock
from specdev_tools.trace.suspects import EntryIndex, find_suspects

KIND_FR = "fr"
KIND_CRITERION = "criterion"
KIND_API = "api"
KIND_FIXTURE = "fixture"
KIND_CAPABILITY = "capability"
FIELD_DERIVES_FROM = "derives_from"
FIELD_VERIFIES = "verifies"
FIELD_REFINES = "refines"
REFINING_STEP = "14"
PARKED_SCOPES = ("later", "out")
REFINED_CURRENT, REFINED_STALE, REFINED_NONE = "current", "stale", "none"
RATIO_DIGITS = 4


@dataclass(frozen=True)
class LinkRow:
    """One link of the reverse index, seen from *node* (the holder of an incoming link, the target of an outgoing one)."""

    node: str
    kind: str
    field: str
    current: bool
    suspect: bool
    historical: bool


@dataclass(frozen=True)
class Exempt:
    """A node left out of every denominator: ``reason`` is ``not_applicable``, ``scope_later`` or ``scope_out``."""

    id: str
    kind: str
    reason: str


@dataclass(frozen=True)
class Dimension:
    """One link count: how many of the *total* nodes are *linked*; ``unlinked`` are the ids that are not."""

    linked: int
    total: int
    unlinked: tuple[str, ...]

    @property
    def ratio(self) -> float:
        """``linked / total`` rounded to four places; ``1.0`` when there is nothing to link."""
        return round(self.linked / self.total, RATIO_DIGITS) if self.total else 1.0


@dataclass(frozen=True)
class CriterionRow:
    """A criterion of an FR with the nodes that link it and its ``refined`` state (``current``, ``stale`` or ``none``)."""

    id: str
    label: str
    refined: str
    groups: tuple[tuple[str, tuple[LinkRow, ...]], ...]


@dataclass(frozen=True)
class FrRow:
    """An in-scope FR: the nodes that link it directly, grouped by kind, and its criteria."""

    id: str
    label: str
    groups: tuple[tuple[str, tuple[LinkRow, ...]], ...]
    criteria: tuple[CriterionRow, ...]


@dataclass(frozen=True)
class Report:
    """What ``specdev coverage`` prints: the three counts, the refined criteria, the exempt nodes and the role findings."""

    dimensions: tuple[tuple[str, Dimension], ...]
    criteria_refined: Dimension
    exempt: tuple[Exempt, ...]
    gaps_by_step: tuple[tuple[str | None, tuple[tuple[str, str], ...]], ...]
    gap_counts: tuple[tuple[str, int], ...]


def exemption(node: Node) -> str | None:
    """Why *node* is outside every denominator: ``not_applicable``, ``scope_later`` or ``scope_out``; ``None`` when it counts."""
    if node.lifecycle == NOT_APPLICABLE:
        return NOT_APPLICABLE
    return f"scope_{node.scope}" if node.scope in PARKED_SCOPES else None


class ReverseIndex:
    """The links of a graph read from their target's side, each with its ``current``, ``suspect`` and ``historical`` flags.

    Built once from the graph, the lock and the seed texts (seed id to text); every method is a lookup afterwards.
    """

    def __init__(self, graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> None:
        self._graph = graph
        self._entries = EntryIndex(graph, lock)
        self._hashes = compute_all(graph, seed_texts)
        self._suspect = {suspect.key for suspect in find_suspects(graph, lock, seed_texts)}
        self._historical = historical_node_ids(graph)

    def _row(self, link: Link, node: Node, target: Node) -> LinkRow:
        entry = self._entries.get(link.source, link.field, target.id)
        hashes = self._hashes.get(target.id)
        current = entry is not None and hashes is not None and entry.content_hash == hashes[0]
        suspect = (link.source, link.field, link.target) in self._suspect
        return LinkRow(node.id, node.kind, link.field, current, suspect, link.source in self._historical)

    def _ordered(self, rows: list[tuple[Node, LinkRow]]) -> list[LinkRow]:
        order = self._graph.shape.order_key
        return [row for _node, row in sorted(rows, key=lambda pair: (order(pair[0]), pair[1].field))]

    def incoming(self, target_id: str) -> list[LinkRow]:
        """The links that point at *target_id* (an id or an alias), held by nodes that are not ``not_applicable``, in step then id order."""
        target = self._graph.find(target_id)
        if target is None:
            return []
        rows = []
        for link in self._graph.incoming.get(target.id, []):
            holder = self._graph.by_id.get(link.source)
            if holder is not None and holder.lifecycle != NOT_APPLICABLE:
                rows.append((holder, self._row(link, holder, target)))
        return self._ordered(rows)

    def outgoing(self, holder_id: str, kind: str) -> list[LinkRow]:
        """The links *holder_id* holds to nodes of *kind* (``node`` is the target), in step then id order."""
        holder = self._graph.find(holder_id)
        if holder is None:
            return []
        rows = []
        for link in holder.links:
            target = self._graph.find(link.target)
            if target is not None and target.kind == kind and target.lifecycle != NOT_APPLICABLE:
                rows.append((target, self._row(link, target, target)))
        return self._ordered(rows)


def _group_by_kind(rows: list[LinkRow]) -> tuple[tuple[str, tuple[LinkRow, ...]], ...]:
    """*rows* grouped by node kind; groups in the order of their first row (rows are already in step then id order)."""
    grouped: dict[str, list[LinkRow]] = defaultdict(list)
    for row in rows:
        grouped[row.kind].append(row)
    return tuple((kind, tuple(group)) for kind, group in grouped.items())


def refined_state(rows: list[LinkRow], graph: Graph) -> str:
    """``current`` when a step-14 node ``refines`` with a current link, ``stale`` when refinements exist and none is, else ``none``."""
    refinements = [row for row in rows if row.field == FIELD_REFINES and graph.by_id[row.node].step == REFINING_STEP]
    if not refinements:
        return REFINED_NONE
    return REFINED_CURRENT if any(row.current for row in refinements) else REFINED_STALE


def _criteria_of(graph: Graph, fr: Node) -> list[Node]:
    children = (graph.by_id[child] for child in graph.children.get(fr.id, ()) if child in graph.by_id)
    return sorted((child for child in children if child.kind == KIND_CRITERION), key=graph.shape.order_key)


def _in_scope(graph: Graph, kind: str) -> tuple[list[Node], list[Exempt]]:
    """The nodes of *kind* that count, in step then id order, and the ones that are exempt."""
    counted, exempt = [], []
    for node in sorted(graph.by_kind.get(kind, []), key=graph.shape.order_key):
        reason = exemption(node)
        if reason is None:
            counted.append(node)
        else:
            exempt.append(Exempt(node.id, node.kind, reason))
    return counted, exempt


def _linked_by(graph: Graph, node: Node, holder_kind: str, field: str) -> bool:
    for link in graph.incoming.get(node.id, []):
        holder = graph.by_id.get(link.source)
        if holder is not None and holder.kind == holder_kind and link.field == field and holder.lifecycle != NOT_APPLICABLE:
            return True
    return False


def _dimension(nodes: list[Node], linked: Mapping[str, bool]) -> Dimension:
    unlinked = tuple(node.id for node in nodes if not linked[node.id])
    return Dimension(len(nodes) - len(unlinked), len(nodes), unlinked)


def link_counts(graph: Graph) -> tuple[tuple[str, Dimension], ...]:
    """The three link counts (FR with an API, FR with a fixture, capability with an FR) over the nodes that count: FR with an API, FR with a fixture, capability with an FR.

    FR with an API: an API ``derives_from`` it.  FR with a fixture: a fixture ``verifies`` one of its criteria.
    Capability with an FR: an FR ``derives_from`` it.  Direct links only; ``not_applicable`` holders do not count.
    """
    frs, _ = _in_scope(graph, KIND_FR)
    capabilities, _ = _in_scope(graph, KIND_CAPABILITY)
    with_api = {fr.id: _linked_by(graph, fr, KIND_API, FIELD_DERIVES_FROM) for fr in frs}
    with_fixture = {fr.id: any(_linked_by(graph, criterion, KIND_FIXTURE, FIELD_VERIFIES) for criterion in _criteria_of(graph, fr)) for fr in frs}
    with_fr = {cap.id: _linked_by(graph, cap, KIND_FR, FIELD_DERIVES_FROM) for cap in capabilities}
    return (
        ("fr_api_coverage", _dimension(frs, with_api)),
        ("fr_fixture_coverage", _dimension(frs, with_fixture)),
        ("capability_fr_coverage", _dimension(capabilities, with_fr)),
    )


def _counted_criteria(graph: Graph) -> list[Node]:
    """The criteria that count: neither they nor the FR that holds them are exempt."""
    frs, _ = _in_scope(graph, KIND_FR)
    return sorted(
        (criterion for fr in frs for criterion in _criteria_of(graph, fr) if exemption(criterion) is None),
        key=graph.shape.order_key,
    )


def criteria_refined(graph: Graph, index: ReverseIndex) -> Dimension:
    """The criteria that count, with ``linked`` = those whose ``refined`` state is ``current``; ``unlinked`` the rest."""
    criteria = _counted_criteria(graph)
    state = {criterion.id: refined_state(index.incoming(criterion.id), graph) == REFINED_CURRENT for criterion in criteria}
    return _dimension(criteria, state)


def exempt_nodes(graph: Graph) -> list[Exempt]:
    """Every exempt FR, capability and criterion (a criterion of an exempt FR is exempt with its FR's reason)."""
    found: list[Exempt] = []
    for kind in (KIND_FR, KIND_CAPABILITY):
        found += _in_scope(graph, kind)[1]
    for fr in graph.by_kind.get(KIND_FR, []):
        fr_reason = exemption(fr)
        for criterion in _criteria_of(graph, fr):
            reason = fr_reason or exemption(criterion)
            if reason is not None:
                found.append(Exempt(criterion.id, criterion.kind, reason))
    return sorted(found, key=lambda item: graph.shape.order_key(graph.by_id[item.id]))


def _gaps(graph: Graph, lock: Lock) -> tuple[tuple[tuple[str | None, tuple[tuple[str, str], ...]], ...], tuple[tuple[str, int], ...]]:
    """The gaps of the registered providers grouped by owner step (waterfall order) as (code, node) pairs, and the count per code."""
    by_step: dict[str | None, list[tuple[str, str]]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for gap in coverage_gaps(graph, lock):
        by_step[gap.owner_step].append((gap.code, gap.node))
        counts[gap.code] += 1
    steps = sorted(by_step, key=graph.shape.step_key)
    ordered_counts = sorted(counts.items())
    return tuple((step, tuple(sorted(by_step[step]))) for step in steps), tuple(ordered_counts)


def build_report(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> Report:
    """The default view: three link counts, refined criteria, exempt nodes and the role findings of the gap seam."""
    index = ReverseIndex(graph, lock, seed_texts)
    by_step, counts = _gaps(graph, lock)
    return Report(link_counts(graph), criteria_refined(graph, index), tuple(exempt_nodes(graph)), by_step, counts)


def build_fr_matrix(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> tuple[FrRow, ...]:
    """The FR-centred matrix: one row per FR that counts, with the nodes that link it or one of its criteria directly.

    An FR row lists the nodes that link the FR (and the capability the FR itself links); a criterion row lists the nodes
    that link the criterion and its ``refined`` state.  Each link carries ``current``, ``suspect`` and ``historical``.
    """
    index = ReverseIndex(graph, lock, seed_texts)
    frs, _ = _in_scope(graph, KIND_FR)
    rows = []
    for fr in frs:
        criteria = tuple(_criterion_row(graph, index, criterion) for criterion in _criteria_of(graph, fr) if exemption(criterion) is None)
        links = [*index.outgoing(fr.id, KIND_CAPABILITY), *index.incoming(fr.id)]
        rows.append(FrRow(fr.id, fr.label, _group_by_kind(links), criteria))
    return tuple(rows)


def _criterion_row(graph: Graph, index: ReverseIndex, criterion: Node) -> CriterionRow:
    links = index.incoming(criterion.id)
    return CriterionRow(criterion.id, criterion.label, refined_state(links, graph), _group_by_kind(links))


def _link_to_dict(row: LinkRow) -> dict[str, Any]:
    return {"node": row.node, "field": row.field, "current": row.current, "suspect": row.suspect, "historical": row.historical}


def _groups_to_dict(groups: tuple[tuple[str, tuple[LinkRow, ...]], ...]) -> list[dict[str, Any]]:
    return [{"kind": kind, "links": [_link_to_dict(row) for row in rows]} for kind, rows in groups]


def _dimension_to_dict(dimension: Dimension) -> dict[str, Any]:
    return {"linked": dimension.linked, "total": dimension.total, "ratio": dimension.ratio, "unlinked": list(dimension.unlinked)}


def _exempt_to_dict(exempt: tuple[Exempt, ...]) -> list[dict[str, str]]:
    return [{"id": item.id, "kind": item.kind, "reason": item.reason} for item in exempt]


def report_to_dict(report: Report) -> dict[str, Any]:
    """The ``--json`` form of the default view: ``counts``, ``criteria_refined``, ``exempt`` and ``role_findings``."""
    return {
        "command": "coverage",
        "counts": {name: _dimension_to_dict(dimension) for name, dimension in report.dimensions},
        "criteria_refined": _dimension_to_dict(report.criteria_refined),
        "exempt": _exempt_to_dict(report.exempt),
        "role_findings": {
            "counts": dict(report.gap_counts),
            "by_step": [{"step": step, "findings": [{"code": code, "node": node} for code, node in found]} for step, found in report.gaps_by_step],
        },
    }


def matrix_to_dict(matrix: tuple[FrRow, ...], exempt: tuple[Exempt, ...]) -> dict[str, Any]:
    """The ``--json`` form of ``--by fr``: ``by_fr`` (one entry per FR with ``groups`` and ``criteria``) and ``exempt``."""
    return {
        "command": "coverage",
        "by": "fr",
        "by_fr": [
            {
                "id": fr.id,
                "label": fr.label,
                "groups": _groups_to_dict(fr.groups),
                "criteria": [{"id": c.id, "label": c.label, "refined": c.refined, "groups": _groups_to_dict(c.groups)} for c in fr.criteria],
            }
            for fr in matrix
        ],
        "exempt": _exempt_to_dict(exempt),
    }


def _flags(row: LinkRow) -> str:
    marks = [] if row.current else ["not current"]
    marks += ["suspect"] if row.suspect else []
    marks += ["closed"] if row.historical else []
    return f" [{', '.join(marks)}]" if marks else ""


def _group_lines(groups: tuple[tuple[str, tuple[LinkRow, ...]], ...], indent: str) -> list[str]:
    if not groups:
        return [f"{indent}(no links)"]
    return [f"{indent}{kind}: " + "; ".join(f"{row.node} ({row.field}){_flags(row)}" for row in rows) for kind, rows in groups]


def _dimension_line(label: str, dimension: Dimension) -> str:
    tail = f"  unlinked: {', '.join(dimension.unlinked)}" if dimension.unlinked else ""
    return f"  {label}: {dimension.linked}/{dimension.total} ({dimension.ratio:.0%}){tail}"


def _exempt_lines(exempt: tuple[Exempt, ...]) -> list[str]:
    if not exempt:
        return []
    return ["", "Exempt (outside every count):", *(f"  {item.id} ({item.kind}): {item.reason}" for item in exempt)]


def render_report(report: Report) -> str:
    """Text form of the default view; information only."""
    lines = ["Link counts (information only; no rule requires them):"]
    lines += [_dimension_line(name, dimension) for name, dimension in report.dimensions]
    lines += ["", "Criteria with a current refinement:", _dimension_line("criteria_refined", report.criteria_refined)]
    lines += _exempt_lines(report.exempt)
    lines += ["", "Role findings:"]
    if not report.gaps_by_step:
        lines.append("  none")
    for step, found in report.gaps_by_step:
        lines.append(f"  step {step or '-'}: " + "; ".join(f"{code} {node}" for code, node in found))
    lines += [f"  {code}: {count}" for code, count in report.gap_counts]
    return "\n".join(lines)


def render_matrix(matrix: tuple[FrRow, ...], exempt: tuple[Exempt, ...]) -> str:
    """Text form of ``--by fr``: per FR the direct links by kind, then per criterion its ``refined`` state and links."""
    lines: list[str] = []
    for fr in matrix:
        lines += [f"{fr.id}  {fr.label}", *_group_lines(fr.groups, "  ")]
        for criterion in fr.criteria:
            lines += [f"  {criterion.id}  refined: {criterion.refined}", *_group_lines(criterion.groups, "    ")]
        lines.append("")
    lines += _exempt_lines(exempt)
    return "\n".join(lines).rstrip()
