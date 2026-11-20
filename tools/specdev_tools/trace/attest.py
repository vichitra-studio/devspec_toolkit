"""``specdev attest``: accept the links of a node as they are now, and prune lock entries that have no link.

Attesting a link writes the lock entry of that link with the content hash and chain stamp its target has now (and drops
the migration ``baseline`` marker).  The command never takes a hash from the user.  Three kinds of link are attestable:
suspect links (the target changed after the holder accepted it), links with no entry yet, and links whose entry still
carries the migration baseline marker.

The ordering rule (D-10): a node can be re-attested only when none of its own link targets is still a suspect node,
that is a node that holds a suspect link.  A group of nodes (``--step``) is processed upward first, so a node becomes
attestable once the nodes it links to in its own step are done; what is still blocked at the end is reported (E764).
Planning reads a lock and writes nothing: ``apply_attest`` and ``prune_orphans`` give the lock to write.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.queries import plural, unknown_node_error
from specdev_tools.trace import replay
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.history import containers_of
from specdev_tools.trace.lockfile import Lock, LockEntry
from specdev_tools.trace.replay import ReplayNode, ReplayPlan, ReplayStep, RootDiff
from specdev_tools.trace.suspects import EntryIndex, LockedLink, SuspectLink, lock_links, orphan_entries

REASON_SUSPECT = "suspect"
REASON_MISSING = "missing"
REASON_BASELINE = "baseline"
HASH_PREVIEW_LENGTH = len("sha256:") + 12
_LinkKey = tuple[str, str, str]


class AttestRefusedError(FindingError):
    """``attest`` refuses the request: ``error`` is E706 (unknown link), E704 (duplicate id), E765 (historical node) or E520 (a spec file cannot be read)."""


@dataclass(frozen=True)
class AttestedLink:
    """One lock entry that ``attest`` writes.

    ``old`` is the entry now in the lock (``None`` for a link with no entry), ``new`` the entry that replaces it (same
    key, current hashes, no baseline marker) and ``suspect`` the suspect link it clears, if the link is a suspect one.
    """

    new: LockEntry
    old: LockEntry | None
    suspect: SuspectLink | None

    @property
    def reason(self) -> str:
        """Why the link is attested: ``suspect``, ``missing`` (no entry) or ``baseline`` (entry with the marker)."""
        if self.suspect is not None:
            return REASON_SUSPECT
        return REASON_MISSING if self.old is None else REASON_BASELINE


@dataclass(frozen=True)
class Blocker:
    """A link of a blocked node whose target is a suspect node: ``field`` and the id of that ``target``."""

    field: str
    target: str


@dataclass(frozen=True)
class BlockedNode:
    """A node that cannot be attested yet because of its ``blockers``, sorted by field and target."""

    node: str
    blockers: tuple[Blocker, ...]


@dataclass(frozen=True)
class AttestPlan:
    """What an attest would do: the entries to write, in the order they are attested, and the nodes it had to refuse."""

    links: tuple[AttestedLink, ...]
    blocked: tuple[BlockedNode, ...] = ()

    @property
    def node_count(self) -> int:
        """Number of nodes that have a link to write."""
        return len({link.new.source for link in self.links})


class _State:
    """What planning reads: the locked links by holder, the suspect links, the entries and the current hashes."""

    def __init__(self, graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> None:
        self.graph = graph
        self.index = EntryIndex(graph, lock)
        self.hashes = compute_all(graph, seed_texts)
        self.replay_plan = replay.compute_replay(graph, lock, seed_texts)
        self.suspects: dict[_LinkKey, SuspectLink] = {
            link.key: link for step in self.replay_plan.steps for node in step.nodes for link in node.links
        }
        self.suspect_nodes = frozenset(link.holder for link in self.suspects.values())
        self.locked: dict[str, list[LockedLink]] = {}
        for item in lock_links(graph):
            self.locked.setdefault(item.holder.id, []).append(item)

    def pending(self, holder: str, field: str | None = None, target: str | None = None) -> list[AttestedLink]:
        """The links of *holder* to attest, narrowed to *field* and to the node *target* (an id) when given."""
        links: list[AttestedLink] = []
        for item in self.locked.get(holder, ()):
            if not _matches(item, field, target):
                continue
            entry = self.index.get(holder, item.link.field, item.target.id)
            suspect = self.suspects.get(item.key)
            if entry is not None and suspect is None and not entry.baseline:
                continue
            key = entry.key if entry is not None else item.key
            content, chain = self.hashes[item.target.id]
            links.append(AttestedLink(LockEntry(*key, content, chain, target_containers=containers_of(self.graph, item.target)), entry, suspect))
        return links

    def blockers(self, holder: str, cleared: Collection[str] = ()) -> tuple[Blocker, ...]:
        """The links of *holder* that point at a suspect node not in *cleared*, by field then target id."""
        found = {
            Blocker(item.link.field, item.target.id)
            for item in self.locked.get(holder, ())
            if item.target.id != holder and item.target.id in self.suspect_nodes and item.target.id not in cleared
        }
        return tuple(sorted(found, key=lambda blocker: (blocker.field, blocker.target)))

    def step_holders(self, step: str) -> list[str]:
        """The nodes of *step* that hold suspect links, upward first (the order of the replay)."""
        return [node.node for kept in replay.pending_replay(self.replay_plan, [step]) for node in kept.nodes]


def _matches(item: LockedLink, field: str | None, target_id: str | None) -> bool:
    """Whether *item* is a link of *field* (when given) to the node *target_id* (when given: an id, resolved by the caller)."""
    return (field is None or item.link.field == field) and (target_id is None or item.target.id == target_id)


def _holder_node(graph: Graph, node_id: str) -> Node:
    """The node *node_id* names (an id or an alias) when attest may act on it; otherwise raises ``AttestRefusedError``."""
    node = graph.find(node_id)
    if node is None:
        raise unknown_node_error(graph, node_id)
    if node.id in graph.dups:
        duplicate = next(error for error in check_unique_ids(graph) if error.node_id == node.id)
        raise AttestRefusedError(duplicate)
    if node.id in historical_node_ids(graph):
        raise AttestRefusedError(make_error(
            "E765",
            f"{node.id!r} is historical (it belongs to a closed milestone), so its links are not re-attested; "
            "its lock entries stay as they were",
        ))
    return node


def plan_node_attest(
    graph: Graph, lock: Lock, seed_texts: Mapping[str, str], node_id: str, *, field: str | None = None, target: str | None = None
) -> AttestPlan:
    """The attest of the links held by the node *node_id* (an id or an alias), narrowed to *field* and *target*.

    *seed_texts* is what ``graph.gitview.read_seed_texts`` returns.  The plan has the links to write, or, when a target of
    the node is a suspect node, no link and the node in ``blocked``.  A node with nothing to attest gives an empty plan.

    Raises:
        AttestRefusedError: the id is unknown (E706, with the nearest ids), defined twice (E704, the finding
            ``spec-check`` reports), or the node is historical (E765); *field* or *target* name no link of the node (E706).
    """
    node = _holder_node(graph, node_id)
    state = _State(graph, lock, seed_texts)
    target_id = graph.canonical_id(target) if target else None
    if (field or target) and not any(_matches(item, field, target_id) for item in state.locked.get(node.id, ())):
        given = [*([f"field {field}"] if field else []), *([f"target {target}"] if target else [])]
        raise AttestRefusedError(make_error("E706", f"{node.id!r} holds no link with {' and '.join(given)}"))
    links = state.pending(node.id, field, target_id)
    blockers = state.blockers(node.id) if links else ()
    if blockers:
        return AttestPlan((), (BlockedNode(node.id, blockers),))
    return AttestPlan(tuple(links))


def plan_step_attest(graph: Graph, lock: Lock, seed_texts: Mapping[str, str], step: str) -> AttestPlan:
    """The attest of every node of *step* that holds a suspect link, upward first.

    A node that follows the nodes it links to is attestable once they are; a node still blocked at the end is in
    ``blocked`` with the links that block it, and the nodes after it that link to it are blocked in turn.
    """
    state = _State(graph, lock, seed_texts)
    links: list[AttestedLink] = []
    blocked: list[BlockedNode] = []
    cleared: set[str] = set()
    for holder in state.step_holders(step):
        blockers = state.blockers(holder, cleared)
        if blockers:
            blocked.append(BlockedNode(holder, blockers))
            continue
        links.extend(state.pending(holder))
        cleared.add(holder)
    return AttestPlan(tuple(links), tuple(blocked))


def apply_attest(lock: Lock, plan: AttestPlan) -> Lock:
    """*lock* with the entries of *plan* written: each replaces the entry of the same key, or is added."""
    written = {link.new.key: link.new for link in plan.links}
    return Lock((*(entry for entry in lock.entries if entry.key not in written), *written.values()))


def prune_orphans(graph: Graph, lock: Lock) -> tuple[Lock, tuple[LockEntry, ...]]:
    """*lock* without its orphan entries (``suspects.orphan_entries``), and those entries in lock order."""
    orphans = orphan_entries(graph, lock)
    dropped = {entry.key for entry in orphans}
    return Lock(tuple(entry for entry in lock.entries if entry.key not in dropped)), tuple(orphans)


def _blocked_text(blocked: BlockedNode) -> str:
    links = ", ".join(f"{blocker.field} -> {blocker.target}" for blocker in blocked.blockers)
    return f"{blocked.node!r} links to suspect nodes ({links}); attest those nodes first"


def blocked_error(plan: AttestPlan) -> SpecError:
    """E764 naming each blocked node of *plan* with the links that block it."""
    return make_error("E764", "attest refused: " + "; ".join(_blocked_text(blocked) for blocked in plan.blocked))


def suspect_view(plan: AttestPlan) -> ReplayPlan:
    """The suspect links of *plan* as a one-step replay plan, so ``replay.root_diffs`` can show what changed above them."""
    by_holder: dict[str, list[SuspectLink]] = {}
    for link in plan.links:
        if link.suspect is not None:
            by_holder.setdefault(link.suspect.holder, []).append(link.suspect)
    nodes = tuple(ReplayNode(holder, tuple(links)) for holder, links in by_holder.items())
    return ReplayPlan((ReplayStep(None, nodes, ()),) if nodes else ())


# --- output ---------------------------------------------------------------------------------------------------------

def _preview(text: str | None) -> str:
    return "-" if text is None else text[:HASH_PREVIEW_LENGTH]


def _link_text(link: AttestedLink) -> str:
    cause = f", {link.suspect.cause}" if link.suspect is not None else ""
    before = _preview(link.old.chain_stamp if link.old is not None else None)
    return f"    {link.new.field} -> {link.new.target} ({link.reason}{cause}): {before} -> {_preview(link.new.chain_stamp)}"


def render_text(plan: AttestPlan, *, written: bool, diffs: Sequence[RootDiff] | None = None, dry_run: bool = False) -> str:
    """The links of *plan* as text, grouped by node, with the diffs of what changed above them when *diffs* is given.

    The first line says whether the entries were written or only would be; for a preview it says how to write, which
    is not ``--yes`` again when the command ran with ``--dry-run`` (*dry_run*): that flag writes nothing with or without it.
    """
    if not plan.links:
        return "attest: nothing to attest"
    count = f"{plural(len(plan.links), 'link')} on {plural(plan.node_count, 'node')}"
    how = "--dry-run: nothing is written" if dry_run else "run again with --yes to write"
    lines = [f"attest: wrote {count}" if written else f"attest: would write {count} ({how})"]
    holder = None
    for link in plan.links:
        if link.new.source != holder:
            holder = link.new.source
            lines.append(f"  {holder}")
        lines.append(_link_text(link))
    for diff in diffs or ():
        lines.extend(replay.diff_lines(diff))
    note = replay.unrooted_note(suspect_view(plan)) if diffs is not None else None
    if note:
        lines.append(note)
    return "\n".join(lines)


def _stamps(entry: LockEntry | None) -> dict[str, str] | None:
    return None if entry is None else {"content_hash": entry.content_hash, "chain_stamp": entry.chain_stamp}


def _link_dict(link: AttestedLink) -> dict[str, Any]:
    return {
        "holder": link.new.source,
        "field": link.new.field,
        "target": link.new.target,
        "reason": link.reason,
        "cause": link.suspect.cause if link.suspect is not None else None,
        "old": _stamps(link.old),
        "new": _stamps(link.new),
    }


def _blocked_dict(blocked: BlockedNode) -> dict[str, Any]:
    return {
        "node": blocked.node,
        "code": "E764",
        "message": _blocked_text(blocked),
        "blockers": [{"field": blocker.field, "target": blocker.target} for blocker in blocked.blockers],
    }


def plan_to_dict(plan: AttestPlan, *, written: bool, diffs: Sequence[RootDiff] | None = None) -> dict[str, Any]:
    """The plan as a JSON-able dict: ``written``, ``attested`` (one dict per link, information only), ``blocked``, and ``diffs`` when given."""
    document: dict[str, Any] = {
        "written": written,
        "attested": [_link_dict(link) for link in plan.links],
        "blocked": [_blocked_dict(blocked) for blocked in plan.blocked],
    }
    if diffs is not None:
        document["diffs"] = [
            {"root": diff.root, "note": diff.note, "diff": list(diff.diff), "accepted_by": list(diff.accepted_by)} for diff in diffs
        ]
    return document


def prune_text(dropped: Sequence[LockEntry], *, written: bool, records: Sequence[str] = ()) -> str:
    """The entries ``--prune`` removes (or would remove), one per line, then the record files (*records*, spec-relative) it removes."""
    if not dropped and not records:
        return "attest --prune: no orphan entries"
    head = "removed" if written else "would remove"
    lines: list[str] = []
    if dropped:
        lines.append(f"attest --prune: {head} {plural(len(dropped), 'orphan entry', 'orphan entries')}")
        lines.extend(f"  {entry.source}: {entry.field} -> {entry.target}" for entry in dropped)
    if records:
        lines.append(f"attest --prune: {head} {plural(len(records), 'orphan record', 'orphan records')}")
        lines.extend(f"  {record}" for record in records)
    return "\n".join(lines)


def prune_to_dict(dropped: Sequence[LockEntry], *, written: bool, records: Sequence[str] = ()) -> dict[str, Any]:
    """The pruned entries as a JSON-able dict: ``written`` and ``pruned`` (source, field, target of each); ``pruned_records`` (spec-relative files; empty when none)."""
    document: dict[str, Any] = {"written": written, "pruned": [{"source": entry.source, "field": entry.field, "target": entry.target} for entry in dropped], "pruned_records": list(records)}
    return document
