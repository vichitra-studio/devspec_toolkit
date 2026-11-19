"""Suspect links and the lock checks: which links carry a lock entry, which entries are missing, orphaned or stale.

A link carries a lock entry when the resolver accepts it (its target exists, has the right kind and sits in an earlier
step), its field is not a history field, its holder is not a record and neither end is ``not_applicable``.  The entry
stores the hashes of the target when the holder accepted the link (``trace.hashing``); the link is *suspect* when the
target's chain stamp has moved since.  Links held by historical nodes (``trace.history``) are never suspect.

This module also holds the two pieces the ``spec-check`` checks are built from: ``LockHook``, which the ``graph``
check passes to the resolver (E761 for a link with no entry, W720 for a new link to a deprecated node, E778 for a link
that names an alias), and
``check_lock``, the findings of the ``trace-lock`` check (E762, E763, E882).
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from specdev_tools.core.errors import SpecError, link_target, make_error
from specdev_tools.graph.kinds import RECORD_ROLE
from specdev_tools.graph.model import DEPRECATED, NOT_APPLICABLE, Graph, Link, Node
from specdev_tools.graph.ownership import step_owner
from specdev_tools.graph.resolve import HISTORY_FIELDS, link_target_allowed
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import MERGE_CHECK_OWNER, Lock, LockEntry

CAUSE_CONTENT = "content_changed"
CAUSE_UPSTREAM = "upstream_changed"
MAX_ROOTS = 3
_CAUSE_TEXT = {
    CAUSE_CONTENT: "the target itself was edited",
    CAUSE_UPSTREAM: "something above the target changed",
}
_LinkKey = tuple[str, str, str]


@dataclass(frozen=True)
class LockedLink:
    """A link that carries a lock entry: its holder, the link as declared, and the node it resolves to."""

    holder: Node
    link: Link
    target: Node

    @property
    def key(self) -> _LinkKey:
        """The (holder id, field, target as written) triple that names the link in the lock."""
        return (self.holder.id, self.link.field, self.link.target)


@dataclass(frozen=True)
class SuspectLink:
    """A link whose target changed after the holder accepted it.

    ``cause`` is ``content_changed`` when the target's own content hash differs from the stored one, else
    ``upstream_changed`` (something above the target moved its chain stamp).  ``roots`` are up to three of the nearest
    upstream nodes (the target first, then containment parent, folded criteria and link targets, level by level) with
    an accepted link into them whose stored content hash no longer matches: where the change came from.
    """

    holder: str
    field: str
    target: str
    holder_step: str | None
    cause: str
    roots: tuple[str, ...] = ()

    @property
    def key(self) -> _LinkKey:
        """The (holder, field, target) triple that names the link in the lock."""
        return (self.holder, self.field, self.target)


def lock_links(graph: Graph) -> list[LockedLink]:
    """Every link of *graph* that carries a lock entry, in step order, then holder id, field and target.

    A holder defined twice gives each link once.  See the module docstring for which links count.
    """
    found: dict[_LinkKey, LockedLink] = {}
    for holder in sorted(graph.gated_nodes(), key=graph.shape.order_key):
        if holder.role == RECORD_ROLE:
            continue
        for link in holder.links:
            target = graph.find(link.target)
            if link.field in HISTORY_FIELDS or target is None or target.lifecycle == NOT_APPLICABLE:
                continue
            if link_target_allowed(link.decl, holder.step, target, graph.shape):
                found.setdefault((holder.id, link.field, link.target), LockedLink(holder, link, target))
    return sorted(found.values(), key=lambda item: (graph.shape.order_key(item.holder), item.link.field, item.link.target))


def _canonical(graph: Graph, target: str) -> str:
    node = graph.find(target)
    return node.id if node is not None else target


class EntryIndex:
    """The entries of a lock by (holder, field, id of the node the target names): an alias and its node share one."""

    def __init__(self, graph: Graph, lock: Lock) -> None:
        self._entries: dict[_LinkKey, LockEntry] = {}
        for entry in lock.entries:
            self._entries.setdefault((entry.source, entry.field, _canonical(graph, entry.target)), entry)

    def get(self, holder: str, field: str, target_id: str) -> LockEntry | None:
        return self._entries.get((holder, field, target_id))


def missing_entries(graph: Graph, lock: Lock) -> list[LockedLink]:
    """The links of *graph* that have no entry in *lock*."""
    index = EntryIndex(graph, lock)
    return [item for item in lock_links(graph) if index.get(item.holder.id, item.link.field, item.target.id) is None]


def _declared_keys(graph: Graph) -> set[_LinkKey]:
    """(holder, field, node id of the target) of every link a non-record node declares, whatever its resolution."""
    return {
        (node.id, link.field, _canonical(graph, link.target))
        for node in graph.nodes
        if node.role != RECORD_ROLE
        for link in node.links
        if link.field not in HISTORY_FIELDS
    }


def _is_out_of_play(graph: Graph, entry: LockEntry) -> bool:
    """True when the entry's holder or target is ``not_applicable``: the entry is kept and ignored."""
    ends = (graph.by_id.get(entry.source), graph.find(entry.target))
    return any(node is not None and node.lifecycle == NOT_APPLICABLE for node in ends)


def orphan_entries(graph: Graph, lock: Lock) -> list[LockEntry]:
    """The entries of *lock* whose holder, field or target link no longer exists in *graph*.

    An entry whose target resolves through an alias is not an orphan, and neither is one whose holder still declares the
    link while the target node is gone (that is a resolver error of the holder's step).  An entry with a
    ``not_applicable`` holder or target is kept and ignored.  When two entries are for one link (a rename on one branch
    and an attest on the other, merged), the one stored under the old spelling of the target, not the id the link names
    now, is the orphan.
    """
    declared = _declared_keys(graph)
    by_link: dict[_LinkKey, list[LockEntry]] = {}
    for entry in lock.entries:
        by_link.setdefault((entry.source, entry.field, _canonical(graph, entry.target)), []).append(entry)

    def is_orphan(entry: LockEntry) -> bool:
        key = (entry.source, entry.field, _canonical(graph, entry.target))
        if _is_out_of_play(graph, entry):
            return False
        # one entry per link stays: the one stored under the id the link names, else the first
        kept = next((other for other in by_link[key] if other.target == key[2]), by_link[key][0])
        return key not in declared or entry is not kept

    return [entry for entry in lock.entries if is_orphan(entry)]


def _upstream(graph: Graph, node: Node) -> Iterator[str]:
    """The ids a node's chain stamp is built from: its containment parent, folded criteria and link targets."""
    if node.parent is not None and node.parent in graph.by_id:
        yield node.parent
    yield from node.children
    for link in node.links:
        target = graph.find(link.target)
        if target is not None and link.field not in HISTORY_FIELDS:
            yield target.id


def _roots(graph: Graph, start: str, changed: set[str]) -> tuple[str, ...]:
    """Up to ``MAX_ROOTS`` ids of *changed* found walking upstream from *start*, nearest first, ties by id."""
    seen = {start}
    level = [start]
    roots: list[str] = []
    while level and len(roots) < MAX_ROOTS:
        roots.extend(node_id for node_id in sorted(level) if node_id in changed)
        following = {up for node_id in level for up in _upstream(graph, graph.by_id[node_id])} - seen
        seen |= following
        level = sorted(following)
    return tuple(roots[:MAX_ROOTS])


def _changed_targets(graph: Graph, lock: Lock, hashes: Mapping[str, tuple[str, str]]) -> set[str]:
    """Ids of the nodes some entry targets whose stored content hash differs from the node's current content.

    A node that folds in a changed criterion is left out: the criterion is the change, the FR or task only carries it.
    """
    changed: set[str] = set()
    for entry in lock.entries:
        node_id = _canonical(graph, entry.target)
        current = hashes.get(node_id)
        if current is not None and current[0] != entry.content_hash:
            changed.add(node_id)
    return {node_id for node_id in changed if not changed.intersection(graph.children.get(node_id, ()))}


def find_suspects(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> list[SuspectLink]:
    """The links whose stored chain stamp differs from the chain stamp their target has now.

    *seed_texts* maps a seed id to its whitespace-collapsed text (``graph.gitview.read_seed_texts``).  Links held by
    historical nodes, links with no entry (see ``missing_entries``) and links with a ``not_applicable`` end are not
    reported.  The result follows ``lock_links`` order.
    """
    hashes = compute_all(graph, seed_texts)
    index = EntryIndex(graph, lock)
    historical = historical_node_ids(graph)
    changed: set[str] | None = None
    suspects: list[SuspectLink] = []
    for item in lock_links(graph):
        entry = index.get(item.holder.id, item.link.field, item.target.id)
        current = hashes.get(item.target.id)
        if entry is None or current is None or item.holder.id in historical or entry.chain_stamp == current[1]:
            continue
        if changed is None:
            changed = _changed_targets(graph, lock, hashes)
        cause = CAUSE_CONTENT if entry.content_hash != current[0] else CAUSE_UPSTREAM
        suspects.append(SuspectLink(
            item.holder.id, item.link.field, item.link.target, item.holder.step, cause, _roots(graph, item.target.id, changed)
        ))
    return suspects


def _node_error(code: str, node: Node | None, message: str, owner: str | None, *, link: tuple[str, str]) -> SpecError:
    """A finding about the link *link* (``(field, target)``) of *node* (when the graph has it) with *owner*."""
    target = link_target(*link)
    if node is None:
        return make_error(code, message, owner=owner, target=target)
    return make_error(
        code, message, file=node.file, jq_path=node.jq_path or None, owner=owner, node_id=node.id, target=target
    )


def _link_text(holder: str, field: str, target: str) -> str:
    return f"{holder}, field {field}, target '{target}'"


def _accept_with(holder: str) -> str:
    """The sentence that names both attest commands: the bare one only shows, the one with ``--yes`` writes."""
    return f"`specdev attest {holder}` shows what would be written, `specdev attest {holder} --yes` writes it"


def _missing_entry_error(holder: Node, link: Link) -> SpecError:
    """E761: the lock has no entry for *link* of *holder*; owned by the holder's step."""
    message = (
        f"{_link_text(holder.id, link.field, link.target)}: the trace lock has no entry for this link; "
        f"once the target is checked, {_accept_with(holder.id)}"
    )
    return _node_error("E761", holder, message, step_owner(holder), link=(link.field, link.target))


def _deprecated_target_warning(holder: Node, link: Link, target: Node) -> SpecError:
    """W720: *link* of *holder* is new (no lock entry) and names the deprecated node *target*; owned by the holder's step."""
    message = (
        f"{_link_text(holder.id, link.field, link.target)}: '{target.id}' is deprecated; "
        "point the link at the node that replaces it"
    )
    return _node_error("W720", holder, message, step_owner(holder), link=(link.field, link.target))


def _stale_alias_error(holder: Node, link: Link, target: Node) -> SpecError:
    """E778: *link* of *holder* names an alias of *target* instead of its current id; owned by the holder's step."""
    message = (
        f"{_link_text(holder.id, link.field, link.target)}: '{link.target}' is an old id of '{target.id}'; "
        f"use the current id '{target.id}'"
    )
    return _node_error("E778", holder, message, step_owner(holder), link=(link.field, link.target))


class LockHook:
    """The resolver hook of the ``graph`` check: reports a link that has no lock entry (E761), a new link to a
    deprecated node (W720) and a link of a live node that names an alias (E778).  All are owned by the holder's step.

    A historical holder is exempt from E778: its links are frozen and resolve through the target's ``aliases``.
    """

    def __init__(self, graph: Graph, lock: Lock) -> None:
        self._index = EntryIndex(graph, lock)
        self._historical = historical_node_ids(graph)

    def on_link(self, link: Link, source: Node, target: Node) -> list[SpecError]:
        """Findings for *link* of *source* once the resolver has accepted it.

        E778 when a live holder wrote an alias; then none when the link has an entry or the target is ``not_applicable``.
        """
        stale = [_stale_alias_error(source, link, target)] if link.target != target.id and source.id not in self._historical else []
        if target.lifecycle == NOT_APPLICABLE or self._index.get(source.id, link.field, target.id) is not None:
            return stale
        findings = [*stale, _missing_entry_error(source, link)]
        if target.lifecycle == DEPRECATED:
            findings.append(_deprecated_target_warning(source, link, target))
        return findings


def _orphan_error(graph: Graph, entry: LockEntry) -> SpecError:
    message = (
        f"trace lock entry ({_link_text(entry.source, entry.field, entry.target)}) has no link any more; "
        "remove it with `specdev attest --prune`"
    )
    return _node_error("E762", graph.by_id.get(entry.source), message, MERGE_CHECK_OWNER, link=(entry.field, entry.target))


def check_lock_orphans(graph: Graph, lock: Lock) -> list[SpecError]:
    """E762 for each entry ``orphan_entries`` reports; owned by the merge check."""
    return [_orphan_error(graph, entry) for entry in orphan_entries(graph, lock)]


def _suspect_error(graph: Graph, suspect: SuspectLink) -> SpecError:
    roots = f"; changed above: {', '.join(suspect.roots)}" if suspect.roots else ""
    message = (
        f"{_link_text(suspect.holder, suspect.field, suspect.target)}: suspect link, {_CAUSE_TEXT[suspect.cause]}{roots}. "
        f"Review the change, then edit {suspect.holder} or accept it: {_accept_with(suspect.holder)}"
    )
    return _node_error("E763", graph.by_id.get(suspect.holder), message, MERGE_CHECK_OWNER, link=(suspect.field, suspect.target))


def _baseline_errors(graph: Graph, lock: Lock) -> list[SpecError]:
    """E882 for each ``baseline`` entry of a live link whose holder is not historical; owned by the holder's step."""
    historical = historical_node_ids(graph)
    live = {(item.holder.id, item.link.field, item.target.id) for item in lock_links(graph)}
    errors: list[SpecError] = []
    for entry in lock.entries:
        holder = graph.by_id.get(entry.source)
        if not entry.baseline or holder is None or holder.id in historical:
            continue
        if (entry.source, entry.field, _canonical(graph, entry.target)) not in live:
            continue
        message = (
            f"trace lock entry ({_link_text(entry.source, entry.field, entry.target)}) still carries the migration "
            f"baseline marker; check the link, then clear it: {_accept_with(entry.source)}"
        )
        errors.append(_node_error("E882", holder, message, step_owner(holder), link=(entry.field, entry.target)))
    return errors


def check_lock(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> list[SpecError]:
    """The findings of the ``trace-lock`` check: E762 (orphan entries), E763 (suspect links) and E882 (baseline marker on a live link).

    Never E761: the ``graph`` check reports links with no entry.  The order is orphans, suspects, baseline entries.
    """
    suspects = [_suspect_error(graph, suspect) for suspect in find_suspects(graph, lock, seed_texts)]
    return [*check_lock_orphans(graph, lock), *suspects, *_baseline_errors(graph, lock)]
