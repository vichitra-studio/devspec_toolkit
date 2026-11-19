"""Context packs: the nodes an agent of a trinity role needs for one unit of work (``specdev trace --recipe <role>``).

A pack is built from the recipe table ``tools/graph_recipes.json`` (hand-kept data, read by ``load_recipes``) and a
built ``Graph``.  The table holds, per role, a start kind and an ordered list of sections.  A section is evaluated like this:

* its ``start_set`` names ``start`` (the node the pack is for) and earlier sections, whose emitted nodes are the
  starting nodes;
* each hop in turn applies one link verb in one direction (``out`` follows the node's own link field, ``in`` the
  reverse index, ``parent`` and ``children`` the containment edge) to the start nodes and to everything the earlier hops
  reached, and admits only nodes of the hop's ``kinds`` (an empty list admits any kind); a hop with ``repeat`` is applied
  again to what it newly reached until nothing is new;
* the section emits the reached nodes whose kind is in its ``kinds``.  Intermediate nodes are traversed, not emitted.
  The start node of the pack is never emitted.  A section with ``include_start_set`` also emits the nodes it started
  from whose kind is in its ``kinds`` (lineage starts from the FR, which the lineage then lists).

Nodes that are ``not_applicable`` and seeds are never entered; deprecated nodes are included and flagged.  A section
with ``whole_kinds`` / ``matched`` / ``pointer`` is not a traversal: it emits every node of the whole kinds, the nodes
of a matched kind whose text field occurs in the labels of the pack, and a pointer to a file of the spec.

Two reports follow the sections: the ambiguity report (open ambiguity items of the milestone's plan file about nodes that
are not in the pack) and, for 16b, the dependency report (changes since a git ref to the nodes the pack depends on).
A finding about the table or the command is raised as ``RecipeError`` carrying it in ``error``.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.scope_helpers import as_str
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.diff import diff_snapshots
from specdev_tools.graph.gitview import GitViewError, Snapshot, default_base_ref, load_snapshot_at, spec_path_in_repo
from specdev_tools.graph.kinds import RECORD_ROLE, SEED_KIND
from specdev_tools.graph.model import DEPRECATED, NOT_APPLICABLE, Graph, Node, article, collapse_whitespace
from specdev_tools.graph.queries import own_content

START = "start"
POINTER_KIND = "pointer"
AMBIGUITY, DEPENDENCY = "ambiguity", "dependency"
REPORT_NAMES = (AMBIGUITY, DEPENDENCY)
OUT, IN, PARENT, CHILDREN = "out", "in", "parent", "children"
DIRECTIONS = (OUT, IN, PARENT, CHILDREN)
ABOUT_FIELD = "about"
ROADMAP_MILESTONE = "roadmap-milestone"
_TABLE_RELATIVE = os.path.join("tools", "graph_recipes.json")
PARENT_VIA = "parent of "
_START_SET_VIA = "start set"
_WHOLE_KIND_VIA = "whole kind"


class RecipeError(FindingError):
    """A recipe cannot be read or run: an unknown role or start id (E706), a start of the wrong kind (E707), or a broken table (E520)."""


# --- the recipe table -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Hop:
    """One traversal step: follow ``verb`` in ``direction`` and admit nodes of ``kinds`` (empty = any); ``repeat`` closes it."""

    verb: str
    direction: str
    kinds: frozenset[str]
    repeat: bool = False


@dataclass(frozen=True)
class MatchRule:
    """Emit the nodes of ``kind`` whose ``field`` text occurs in the labels of the pack."""

    kind: str
    field: str


@dataclass(frozen=True)
class Pointer:
    """A file of the spec (relative to the spec root) and a jq path in it, given to the agent instead of content."""

    file: str
    path: str


@dataclass(frozen=True)
class Section:
    """One section of a pack for the roles in ``roles``; see the module docstring for how it is evaluated."""

    name: str
    roles: frozenset[str]
    start_set: tuple[str, ...] = ()
    hops: tuple[Hop, ...] = ()
    kinds: frozenset[str] = frozenset()
    include_start_set: bool = False
    whole_kinds: frozenset[str] = frozenset()
    matched: tuple[MatchRule, ...] = ()
    pointer: Pointer | None = None

    @property
    def is_universal(self) -> bool:
        """True for a section of whole kinds, matched kinds or a pointer rather than a traversal."""
        return bool(self.whole_kinds or self.matched or self.pointer)

    @property
    def emitted_kinds(self) -> frozenset[str]:
        """Every kind the section can emit."""
        return self.kinds | self.whole_kinds | {rule.kind for rule in self.matched}


@dataclass(frozen=True)
class ReportSpec:
    """A report beside the sections: the roles it is for, the kinds it lists, and (dependency) how its nodes are found."""

    roles: frozenset[str]
    kinds: frozenset[str] = frozenset()
    start_set: tuple[str, ...] = ()
    hops: tuple[Hop, ...] = ()


@dataclass(frozen=True)
class Exemption:
    """A kind that no pack has to place, and the authority for it."""

    kind: str
    authority: str


@dataclass(frozen=True)
class RecipeTable:
    """The parsed ``graph_recipes.json``: the start kind of each role, its sections, the reports and the exemptions.

    ``suffix_fields`` maps a kind to the node field shown after its label in a pack row (a third party's ``pin``).
    """

    start_kinds: Mapping[str, str]
    sections: tuple[Section, ...]
    reports: Mapping[str, ReportSpec]
    exempt: tuple[Exemption, ...]
    suffix_fields: Mapping[str, str] = field(default_factory=dict)

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(self.start_kinds)

    def sections_for(self, role: str) -> tuple[Section, ...]:
        """The sections of *role*, in table order."""
        return tuple(section for section in self.sections if role in section.roles)

    def placed_kinds(self) -> frozenset[str]:
        """The kinds some role's section or report emits, plus the exempt kinds."""
        placed = {kind for section in self.sections for kind in section.emitted_kinds}
        placed.update(kind for report in self.reports.values() for kind in report.kinds)
        return frozenset(placed | {item.kind for item in self.exempt})


def _bad_table(where: str, problem: str) -> RecipeError:
    return RecipeError(make_error("E520", f"{_TABLE_RELATIVE}: {where} {problem}"))


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _bad_table(where, "must be an object")
    return value


def _array(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise _bad_table(where, "must be a list")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise _bad_table(where, "must be a non-empty string")
    return value


def _texts(value: Any, where: str) -> tuple[str, ...]:
    return tuple(_text(item, f"{where}[{index}]") for index, item in enumerate(_array(value, where)))


def _flag(raw: Mapping[str, Any], key: str, where: str) -> bool:
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise _bad_table(f"{where}.{key}", "must be true or false")
    return value


def _parse_hop(raw: Any, where: str) -> Hop:
    hop = _object(raw, where)
    direction = _text(hop.get("direction"), f"{where}.direction")
    if direction not in DIRECTIONS:
        raise _bad_table(f"{where}.direction", f"must be one of {', '.join(DIRECTIONS)}")
    follows_link = direction in (OUT, IN)
    if follows_link != ("verb" in hop):
        raise _bad_table(where, "must name a verb exactly when its direction is out or in")
    verb = _text(hop["verb"], f"{where}.verb") if follows_link else ""
    return Hop(verb, direction, frozenset(_texts(hop.get("kinds"), f"{where}.kinds")), _flag(hop, "repeat", where))


def _parse_hops(raw: Any, where: str) -> tuple[Hop, ...]:
    return tuple(_parse_hop(item, f"{where}[{index}]") for index, item in enumerate(_array(raw if raw is not None else [], where)))


def _parse_roles(raw: Any, where: str, known: Collection[str]) -> frozenset[str]:
    roles = _texts(raw, where)
    unknown = sorted(set(roles) - set(known))
    if not roles or unknown:
        raise _bad_table(where, f"must list roles among {', '.join(sorted(known))}" + (f" (not {', '.join(unknown)})" if unknown else ""))
    return frozenset(roles)


def _parse_match(raw: Any, where: str) -> MatchRule:
    rule = _object(raw, where)
    return MatchRule(_text(rule.get("kind"), f"{where}.kind"), _text(rule.get("field"), f"{where}.field"))


def _parse_pointer(raw: Any, where: str) -> Pointer | None:
    if raw is None:
        return None
    pointer = _object(raw, where)
    return Pointer(_text(pointer.get("file"), f"{where}.file"), _text(pointer.get("path"), f"{where}.path"))


def _parse_section(raw: Any, where: str, roles: Collection[str]) -> Section:
    section = _object(raw, where)
    parsed = Section(
        name=_text(section.get("name"), f"{where}.name"),
        roles=_parse_roles(section.get("roles"), f"{where}.roles", roles),
        start_set=_texts(section.get("start_set", []), f"{where}.start_set"),
        hops=_parse_hops(section.get("hops"), f"{where}.hops"),
        kinds=frozenset(_texts(section.get("kinds", []), f"{where}.kinds")),
        include_start_set=_flag(section, "include_start_set", where),
        whole_kinds=frozenset(_texts(section.get("whole_kinds", []), f"{where}.whole_kinds")),
        matched=tuple(_parse_match(item, f"{where}.matched[{i}]") for i, item in enumerate(_array(section.get("matched", []), f"{where}.matched"))),
        pointer=_parse_pointer(section.get("pointer"), f"{where}.pointer"),
    )
    if parsed.is_universal and (parsed.kinds or parsed.hops or parsed.start_set):
        raise _bad_table(where, "is both a traversal (kinds, hops, start_set) and a universal section (whole_kinds, matched, pointer)")
    if not parsed.is_universal and not parsed.kinds:
        raise _bad_table(where, "emits nothing: give kinds, whole_kinds, matched or pointer")
    return parsed


def _parse_report(name: str, raw: Any, roles: Collection[str]) -> ReportSpec:
    where = f"reports.{name}"
    report = _object(raw, where)
    return ReportSpec(
        roles=_parse_roles(report.get("roles"), f"{where}.roles", roles),
        kinds=frozenset(_texts(report.get("kinds", []), f"{where}.kinds")),
        start_set=_texts(report.get("start_set", []), f"{where}.start_set"),
        hops=_parse_hops(report.get("hops"), f"{where}.hops"),
    )


def _parse_exemption(raw: Any, where: str) -> Exemption:
    item = _object(raw, where)
    return Exemption(_text(item.get("kind"), f"{where}.kind"), _text(item.get("authority"), f"{where}.authority"))


def _traversal_order(sections: Sequence[Section]) -> list[Section]:
    """The traversal sections of one role, each after the sections its start set names.

    Raises ``RecipeError`` (E520) for a start set that names an unknown or universal section, or that loops back.
    """
    by_name = {section.name: section for section in sections if not section.is_universal}
    if len(by_name) != sum(1 for section in sections if not section.is_universal):
        raise _bad_table("sections", "give two sections of one role the same name")
    ordered: list[Section] = []

    def visit(section: Section, trail: tuple[str, ...]) -> None:
        if section in ordered:
            return
        if section.name in trail:
            raise _bad_table(f"section {section.name!r}", "starts from itself through " + " -> ".join(trail))
        for name in section.start_set:
            if name != START and name not in by_name:
                raise _bad_table(f"section {section.name!r}", f"starts from {name!r}, which is not a traversal section of its role")
            if name != START:
                visit(by_name[name], (*trail, section.name))
        ordered.append(section)

    for section in by_name.values():
        visit(section, ())
    return ordered


def parse_recipes(data: Mapping[str, Any]) -> RecipeTable:
    """The ``RecipeTable`` of the parsed ``graph_recipes.json`` *data*.

    Raises:
        RecipeError: E520, naming the field, when a value has the wrong type or the table is inconsistent (an unknown
            role, a start set that names an unknown section or loops).
    """
    starts = _object(data.get("start_kinds"), "start_kinds")
    start_kinds = {role: _text(kind, f"start_kinds.{role}") for role, kind in starts.items()}
    suffixes = _object(data.get("suffix_fields", {}), "suffix_fields")
    reports_raw = _object(data.get("reports", {}), "reports")
    unknown = sorted(set(reports_raw) - set(REPORT_NAMES))
    if unknown:
        raise _bad_table("reports", f"names unknown report(s) {', '.join(unknown)}; known: {', '.join(REPORT_NAMES)}")
    table = RecipeTable(
        start_kinds=start_kinds,
        sections=tuple(_parse_section(item, f"sections[{i}]", start_kinds) for i, item in enumerate(_array(data.get("sections"), "sections"))),
        reports={name: _parse_report(name, raw, start_kinds) for name, raw in reports_raw.items()},
        exempt=tuple(_parse_exemption(item, f"exempt[{i}]") for i, item in enumerate(_array(data.get("exempt", []), "exempt"))),
        suffix_fields={kind: _text(name, f"suffix_fields.{kind}") for kind, name in suffixes.items()},
    )
    for role in table.roles:
        _traversal_order(table.sections_for(role))
    return table


def load_recipes(repo_root: str) -> RecipeTable:
    """Read ``<repo_root>/tools/graph_recipes.json`` into a ``RecipeTable``.

    Raises:
        RecipeError: E520 when the file is missing, unreadable, not a JSON object or inconsistent.
    """
    path = os.path.join(repo_root, _TABLE_RELATIVE)
    data = read_json_object(path)
    if data is None:
        raise RecipeError(make_error("E520", f"{path}: unreadable or not a JSON object"))
    return parse_recipes(data)


# --- traversal ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Reached:
    """A node a hop reached and how: ``via`` is the label naming the node it was reached from and the verb.

    ``container`` and ``source_id`` carry the same fact as data: a ``parent`` hop sets ``container`` and ``source_id`` is
    the id of the node it was reached from (empty for a node of the start set or a whole kind).
    """

    node: Node
    via: str
    container: bool = False
    source_id: str = ""


def _reached(hop: Hop, source: Node, other: Node) -> Reached:
    return Reached(other, _via(hop, source), hop.direction == PARENT, source.id)


def _via(hop: Hop, source: Node) -> str:
    if hop.direction == PARENT:
        return f"{PARENT_VIA}{source.id}"
    if hop.direction == CHILDREN:
        return f"child of {source.id}"
    return f"{hop.verb} {hop.direction} {source.id}"


def _neighbour_ids(graph: Graph, node: Node, hop: Hop) -> list[str]:
    if hop.direction == OUT:
        return [graph.canonical_id(link.target) for link in graph.outgoing.get(node.id, ()) if link.field == hop.verb]
    if hop.direction == IN:
        return [link.source for link in graph.incoming.get(node.id, ()) if link.field == hop.verb]
    if hop.direction == PARENT:
        return [node.parent] if node.parent else []
    return list(node.children)


def _admitted(graph: Graph, node: Node, hop: Hop) -> list[Node]:
    """The neighbours of *node* along *hop* that may enter a pack: present, not ``not_applicable``, not a seed, of the hop's kinds."""
    found = (graph.by_id.get(node_id) for node_id in _neighbour_ids(graph, node, hop))
    return [
        other for other in found
        if other is not None
        and other.lifecycle != NOT_APPLICABLE
        and other.kind != SEED_KIND
        and (not hop.kinds or other.kind in hop.kinds)
    ]


def _apply(graph: Graph, hop: Hop, frontier: Iterable[Node], known: dict[str, Node], reached: dict[str, Reached]) -> list[Node]:
    """Apply *hop* to *frontier* (records are not expanded); return the nodes new to *known*."""
    added: list[Node] = []
    for node in frontier:
        if node.role == RECORD_ROLE or node.kind == SEED_KIND:
            continue
        for other in _admitted(graph, node, hop):
            reached.setdefault(other.id, _reached(hop, node, other))
            if other.id not in known:
                known[other.id] = other
                added.append(other)
    return added


def _reach(graph: Graph, start: Sequence[Node], hops: Sequence[Hop]) -> dict[str, Reached]:
    """Every node the *hops* reach from *start*, in order, each with the way it was first reached."""
    known = {node.id: node for node in start}
    reached: dict[str, Reached] = {}
    for hop in hops:
        frontier = list(known.values())
        while frontier:
            frontier = _apply(graph, hop, frontier, known, reached)
            if not hop.repeat:
                break
    return reached


def _start_nodes(names: Iterable[str], start: Node, found: Mapping[str, Sequence[Reached]]) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    for name in names:
        for node in [start] if name == START else [hit.node for hit in found.get(name, ())]:
            nodes.setdefault(node.id, node)
    return nodes


def _traverse(graph: Graph, section: Section, start: Node, found: Mapping[str, Sequence[Reached]]) -> list[Reached]:
    """The nodes *section* emits for the pack of *start*, ordered by step then id."""
    origin = _start_nodes(section.start_set, start, found)
    hits = {key: hit for key, hit in _reach(graph, list(origin.values()), section.hops).items() if hit.node.kind in section.kinds}
    if section.include_start_set:
        for key, node in origin.items():
            if node.kind in section.kinds:
                hits.setdefault(key, Reached(node, _START_SET_VIA))
    hits.pop(start.id, None)
    return sorted(hits.values(), key=lambda hit: graph.shape.order_key(hit.node))


# --- the pack -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PackEntry:
    """One row of a pack: a node (or the pointer to a file), how it was reached, and what is shown beside its label.

    ``suffix`` is the value of the node field ``suffix_field`` (a third party's pin), already part of ``label``;
    ``content`` is the node's own item, present only when the pack was expanded.  ``container`` is true for a node
    reached by a ``parent`` hop: it holds a member of its section instead of being one.  ``source_id`` is the id of the
    node a hop reached this one from (empty for the start set and for a whole kind); with ``container`` it names the
    member the container holds.  ``via`` is only the label printed for a reader.
    """

    id: str
    kind: str
    step: str | None
    label: str
    via: str
    lifecycle: str = "active"
    suffix_field: str = ""
    suffix: str = ""
    content: Mapping[str, Any] | None = None
    container: bool = False
    source_id: str = ""


@dataclass(frozen=True)
class AmbiguityRow:
    """An open ambiguity item of the milestone's plan file about nodes that are not in the pack."""

    id: str
    file: str
    label: str
    about: tuple[str, ...]


@dataclass(frozen=True)
class DependencyChange:
    """A node the pack depends on that changed since the base ref; ``changes`` holds the change names of ``graph.diff``."""

    id: str
    kind: str
    changes: tuple[str, ...]


@dataclass(frozen=True)
class DependencyReport:
    """The dependency changes since ``base``, or ``unavailable`` (the E708 / E709 finding) when the base cannot be read."""

    base: str
    changes: tuple[DependencyChange, ...] = ()
    unavailable: SpecError | None = None


@dataclass(frozen=True)
class GitContext:
    """Where the dependency report finds history: the repository, the spec folder, the toolkit, and the ref (``None`` = default)."""

    git_root: str
    spec_root: str
    repo_root: str
    since: str | None = None


@dataclass(frozen=True)
class Pack:
    """The context pack of one start node: its sections in table order and the reports the role has (``None`` = not computed)."""

    role: str
    start: PackEntry
    sections: Mapping[str, tuple[PackEntry, ...]]
    ambiguities: tuple[AmbiguityRow, ...] | None = None
    dependency_report: DependencyReport | None = None

    @property
    def node_ids(self) -> frozenset[str]:
        """The ids of the nodes in the sections (a pointer is not a node)."""
        return frozenset(entry.id for entries in self.sections.values() for entry in entries if entry.kind != POINTER_KIND)


def _item(graph: Graph, node: Node) -> Mapping[str, Any]:
    return item_of(graph, node) or {}


def _entry(graph: Graph, table: RecipeTable, node: Node, via: str, container: bool = False, source_id: str = "") -> PackEntry:
    suffix_field = table.suffix_fields.get(node.kind, "")
    suffix = as_str(_item(graph, node).get(suffix_field)) if suffix_field else ""
    label = f"{node.label} {suffix}".strip() if suffix else node.label
    return PackEntry(
        id=node.id,
        kind=node.kind,
        step=node.step,
        label=label,
        via=via,
        lifecycle=node.lifecycle,
        suffix_field=suffix_field if suffix else "",
        suffix=suffix,
        content=None,
        container=container,
        source_id=source_id,
    )


def _gated_of_kind(graph: Graph, kind: str) -> list[Node]:
    return [node for node in graph.by_kind.get(kind, ()) if node.lifecycle != NOT_APPLICABLE]


def _normal(text: str) -> str:
    return collapse_whitespace(text).casefold()


def _mentions(graph: Graph, node: Node, rule: MatchRule, pack_text: str) -> bool:
    needle = _normal(as_str(_item(graph, node).get(rule.field)))
    return bool(needle) and re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", pack_text) is not None


def _universal(graph: Graph, table: RecipeTable, section: Section, pack_text: str) -> list[PackEntry]:
    nodes = [(node, _WHOLE_KIND_VIA) for kind in sorted(section.whole_kinds) for node in _gated_of_kind(graph, kind)]
    for rule in section.matched:
        nodes.extend((node, f"{rule.field} named in the pack") for node in _gated_of_kind(graph, rule.kind) if _mentions(graph, node, rule, pack_text))
    entries = [_entry(graph, table, node, via) for node, via in sorted(nodes, key=lambda pair: graph.shape.order_key(pair[0]))]
    pointer = section.pointer
    if pointer is not None and pointer.file in graph.documents:
        entries.append(PackEntry(pointer.file, POINTER_KIND, None, pointer.path, "pointer"))
    return entries


def _start_node(graph: Graph, table: RecipeTable, role: str, start_id: str) -> Node:
    """The node the pack of *role* is for.  Raises ``RecipeError``: E706 for an unknown role or id, E707 for a wrong kind."""
    expected = table.start_kinds.get(role)
    if expected is None:
        raise RecipeError(make_error("E706", f"no recipe role {role!r}; roles: {', '.join(table.roles)}"))
    node = graph.find(start_id)
    if node is None:
        raise RecipeError(make_error("E706", f"no node has the id {start_id!r}"), unknown_id=True)
    if node.kind != expected:
        raise RecipeError(make_error("E707", f"recipe {role} starts from {article(expected)} {expected}, but {start_id!r} is {article(node.kind)} {node.kind}"))
    return node


def _milestone_of(graph: Graph, start: Node) -> str | None:
    """The id of the milestone *start* belongs to: the ``milestone`` of its plan file, else its containing roadmap milestone."""
    node: Node | None = start
    while node is not None:
        if node.milestone is not None:
            return graph.canonical_id(node.milestone)
        if node.kind == ROADMAP_MILESTONE:
            return node.id
        node = graph.by_id.get(node.parent) if node.parent else None
    return None


def _plan_files(graph: Graph, start: Node) -> set[str]:
    """The plan file(s) whose ``milestone`` is the milestone of *start*."""
    milestone = _milestone_of(graph, start)
    return {
        node.file for node in graph.nodes
        if milestone is not None and node.milestone is not None and graph.canonical_id(node.milestone) == milestone
    }


def _ambiguity_report(graph: Graph, start: Node, pack_ids: Collection[str], spec: ReportSpec) -> tuple[AmbiguityRow, ...]:
    files = _plan_files(graph, start)
    inside = {*pack_ids, start.id}
    rows = []
    for node in graph.nodes:
        if node.kind in spec.kinds and node.file in files:
            targets = (graph.canonical_id(link.target) for link in node.links if link.field == ABOUT_FIELD)
            outside = tuple(target for target in targets if target not in inside)
            if outside:
                rows.append(AmbiguityRow(node.id, node.file, node.label, outside))
    return tuple(rows)


def dependency_ids(graph: Graph, spec: ReportSpec, seed_ids: Iterable[str]) -> frozenset[str]:
    """The ids of the nodes the pack depends on: what the hops of *spec* reach from the nodes *seed_ids* that are on *graph*."""
    seeds = [graph.by_id[node_id] for node_id in seed_ids if node_id in graph.by_id]
    return frozenset(_reach(graph, seeds, spec.hops))


def compare_dependencies(old: Snapshot, new: Snapshot, spec: ReportSpec, seed_ids: Collection[str], base: str) -> DependencyReport:
    """The dependency nodes of *seed_ids* (on either snapshot) that were added, removed or changed from *old* to *new*."""
    scope = dependency_ids(old.graph, spec, seed_ids) | dependency_ids(new.graph, spec, seed_ids)
    changes = tuple(
        DependencyChange(change.id, change.kind, change.changes)
        for change in diff_snapshots(old, new).changes
        if change.id in scope
    )
    return DependencyReport(base, changes)


def dependency_report(graph: Graph, spec: ReportSpec, seed_ids: Collection[str], git: GitContext) -> DependencyReport:
    """The dependency report of the nodes *seed_ids*: *graph* (the working tree) against the spec at ``git.since``.

    The default ref is where HEAD left the default branch (``HEAD~1`` without one).  A ref or spec folder that cannot be
    read, or one whose tree has no graph node, gives a report with ``unavailable`` set to the E708 / E709 finding.

    Raises:
        KindRegistryError: the registry of the toolkit at ``git.repo_root`` is missing or unreadable (E520).
    """
    base = git.since or ""
    try:
        base = git.since or default_base_ref(git.git_root)
        old = load_snapshot_at(base, git.git_root, spec_path_in_repo(git.spec_root, git.git_root), git.repo_root)
    except GitViewError as exc:
        return DependencyReport(base, unavailable=exc.error)
    return compare_dependencies(old, Snapshot(graph, {}), spec, seed_ids, base)


def _contents(graph: Graph, ids: Collection[str]) -> dict[str, Mapping[str, Any] | None]:
    """The own content of each node of *ids*, as ``specdev node`` shows it (first definition of an id)."""
    return {node_id: own_content(graph, graph.by_id[node_id], False) for node_id in ids if node_id in graph.by_id}


def build_pack(
    graph: Graph,
    table: RecipeTable,
    role: str,
    start_id: str,
    *,
    expand: bool = False,
    git: GitContext | None = None,
) -> Pack:
    """The context pack of *role* for the node *start_id*.

    With *expand* each node row carries its own content.  The dependency report (16b) is computed only when *git* is given.

    Raises:
        RecipeError: E706 for an unknown role or id, E707 for a start node of the wrong kind.
        KindRegistryError: with *git*, the toolkit registry is missing or unreadable (E520).
    """
    start = _start_node(graph, table, role, start_id)
    sections = table.sections_for(role)
    found: dict[str, list[Reached]] = {}
    for section in _traversal_order(sections):
        found[section.name] = _traverse(graph, section, start, found)
    pack_text = _normal(" ".join([start.label, *(hit.node.label for hits in found.values() for hit in hits)]))
    entries: dict[str, list[PackEntry]] = {}
    for section in sections:
        if section.is_universal:
            entries[section.name] = _universal(graph, table, section, pack_text)
        else:
            entries[section.name] = [_entry(graph, table, hit.node, hit.via, hit.container, hit.source_id) for hit in found[section.name]]
    pack = Pack(role, _entry(graph, table, start, ""), {name: tuple(rows) for name, rows in entries.items()})
    if expand:
        contents = _contents(graph, pack.node_ids | {start.id})
        pack = replace(pack, sections={n: tuple(replace(e, content=contents.get(e.id)) for e in rows) for n, rows in pack.sections.items()})
    ambiguity, dependency = table.reports.get(AMBIGUITY), table.reports.get(DEPENDENCY)
    if ambiguity is not None and role in ambiguity.roles:
        pack = replace(pack, ambiguities=_ambiguity_report(graph, start, pack.node_ids, ambiguity))
    if dependency is not None and role in dependency.roles and git is not None:
        seeds = [hit.node.id for name in dependency.start_set for hit in found.get(name, ())]
        pack = replace(pack, dependency_report=dependency_report(graph, dependency, seeds, git))
    return pack


# --- output ---------------------------------------------------------------------------------------------------------

def _row(entry: PackEntry) -> str:
    suffix = f" {entry.suffix}" if entry.suffix else ""
    flag = " (deprecated)" if entry.lifecycle == DEPRECATED else ""
    return f"{entry.id}{suffix}{flag}"


def _member_of(entry: PackEntry, by_id: Mapping[str, PackEntry]) -> tuple[str, int] | None:
    """The member a container holds and how many containers lie between them, following a chain of containers.

    A milestone holds a task holds a criterion: for the milestone the answer is the criterion and 2, for the task the
    criterion and 1.  ``None`` when the chain ends in no member of the section or loops.
    """
    seen = {entry.id}
    distance = 0
    while entry.container:
        source = by_id.get(entry.source_id)
        distance += 1
        if source is None or source.id in seen:
            return None
        if not source.container:
            return source.id, distance
        seen.add(source.id)
        entry = source
    return None


def _grouped_rows(entries: Sequence[PackEntry]) -> list[str]:
    """One text row per member, the containers it sits in after it in parentheses, nearest first; a container with no member in the section is a row of its own."""
    by_id = {entry.id: entry for entry in entries}
    holders: dict[str, list[tuple[int, PackEntry]]] = {}
    alone: set[str] = set()
    for entry in entries:
        found = _member_of(entry, by_id) if entry.container else None
        if found is not None:
            holders.setdefault(found[0], []).append((found[1], entry))
        elif entry.container:
            alone.add(entry.id)
    rows = []
    for entry in entries:
        if entry.container and entry.id not in alone:
            continue
        around = ", ".join(_row(holder) for _, holder in sorted(holders.get(entry.id, ()), key=lambda pair: pair[0]))
        rows.append(f"{_row(entry)} ({around})" if around else _row(entry))
    return rows


def _section_lines(name: str, entries: Sequence[PackEntry], width: int) -> list[str]:
    if entries and entries[0].content is not None:
        lines = [name]
        for entry in entries:
            lines.append(f"  {_row(entry)} ({entry.via})" if entry.container else f"  {_row(entry)}")
            lines.extend(f"    {line}" for line in _json_lines(entry.content))
        return lines
    return [f"{name:<{width}}  {', '.join(_grouped_rows(entries)) or 'none'}"]


def _json_lines(content: Mapping[str, Any] | None) -> list[str]:
    return json.dumps(content, indent=2, ensure_ascii=False).splitlines() if content is not None else ["(content not on the graph)"]


def _ambiguity_lines(rows: Sequence[AmbiguityRow], width: int) -> list[str]:
    if not rows:
        return [f"{'ambiguity report':<{width}}  none outside the pack"]
    return [f"{'ambiguity report':<{width}}  {row.id} about {', '.join(row.about)}" for row in rows]


def _dependency_lines(report: DependencyReport, width: int) -> list[str]:
    head = f"{'dependency report':<{width}}  "
    if report.unavailable is not None:
        return [f"{head}unavailable ({report.unavailable.code}): {report.unavailable.message}"]
    if not report.changes:
        return [f"{head}no change since {report.base}"]
    return [f"{head}{change.id} {', '.join(change.changes)} since {report.base}" for change in report.changes]


def render_text(pack: Pack) -> str:
    """The pack as text: a header, one row per section (with *expand*, one block with the content of each node) and the reports."""
    start = pack.start
    lines = [f"pack {pack.role} for {start.id} ({start.kind}, step {start.step or '-'})"]
    width = max([*map(len, pack.sections), len("dependency report")])
    for name, entries in pack.sections.items():
        lines.extend(_section_lines(name, entries, width))
    if pack.ambiguities is not None:
        lines.extend(_ambiguity_lines(pack.ambiguities, width))
    if pack.dependency_report is not None:
        lines.extend(_dependency_lines(pack.dependency_report, width))
    return "\n".join(lines)


def _entry_to_dict(entry: PackEntry) -> dict[str, Any]:
    data: dict[str, Any] = {"id": entry.id, "kind": entry.kind, "step": entry.step, "label": entry.label, "via": entry.via}
    if entry.lifecycle == DEPRECATED:
        data["deprecated"] = True
    if entry.suffix:
        data[entry.suffix_field] = entry.suffix
    if entry.content is not None:
        data["content"] = entry.content
    return data


def _dependency_to_dict(report: DependencyReport) -> dict[str, Any]:
    data: dict[str, Any] = {"base": report.base, "changes": [{"id": c.id, "kind": c.kind, "changes": list(c.changes)} for c in report.changes]}
    if report.unavailable is not None:
        data["unavailable"] = {"code": report.unavailable.code, "message": report.unavailable.message}
    return data


def pack_to_dict(pack: Pack) -> dict[str, Any]:
    """The pack as a JSON-able dict: ``role``, ``start``, ``sections`` (name to rows), ``counts`` and the reports it has."""
    document: dict[str, Any] = {
        "role": pack.role,
        "start": _entry_to_dict(pack.start),
        "sections": {name: [_entry_to_dict(entry) for entry in entries] for name, entries in pack.sections.items()},
        "counts": {"nodes": len(pack.node_ids), "sections": {name: len(entries) for name, entries in pack.sections.items()}},
    }
    if pack.ambiguities is not None:
        document["ambiguity_report"] = [
            {"id": row.id, "file": row.file, "label": row.label, "about": list(row.about)} for row in pack.ambiguities
        ]
    if pack.dependency_report is not None:
        document["dependency_report"] = _dependency_to_dict(pack.dependency_report)
    return document
