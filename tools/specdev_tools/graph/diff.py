"""Node-level diff of two spec snapshots and the advisory version bump.

Per node id: added, removed, changed (the contract view differs), lifecycle changed, kind changed, renamed.  A node of
the newer snapshot whose ``aliases`` hold an id that exists in the older snapshot and no longer exists in the newer one
is that node renamed: it is reported once, as renamed (old id to new id), and its contract is compared through the first
names of both snapshots (``model.first_name_index``), so a link or a criterion that a rename rewrote is not a change.
Seeds compare the whitespace-collapsed content of their file.  A node whose lifecycle differs between the two snapshots is reported as a
lifecycle change, never as added or removed; one that is ``not_applicable`` wherever it exists is left out.  The bump is
advice only: major when an ``obligation-system`` node is removed or a ``removes`` link appears, minor when one is added
or its contract view changed, patch for anything else (a rename alone is patch); a node that stops (starts) being ``obligation-system`` follows
the removed (added) rule.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from specdev_tools.graph.contract import contract_view
from specdev_tools.graph.gitview import Snapshot, load_snapshot_at, require_git_root_folder, spec_path_in_repo
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import NOT_APPLICABLE, Node, first_name_index
from specdev_tools.graph.names import REMOVES

ADDED, REMOVED, CHANGED, LIFECYCLE, KIND, RENAMED = "added", "removed", "changed", "lifecycle", "kind", "renamed"
MAJOR, MINOR, PATCH, NO_BUMP = "major", "minor", "patch", "none"
OBLIGATION_ROLE = "obligation-system"
NO_ROLE = "(no role)"


@dataclass(frozen=True)
class NodeChange:
    """What changed for one node id: ``changes`` holds one or more of the change names.

    ``kind`` and ``role`` are the node's in the newer snapshot (the older one for a removed node); ``old_kind`` and ``old_role`` are
    set for a kind change, ``lifecycle`` is ``(old, new)`` for a lifecycle change and ``old_id`` is the id the node had in the
    older snapshot when it was renamed.
    """

    id: str
    kind: str
    role: str | None
    changes: tuple[str, ...]
    old_kind: str | None = None
    old_role: str | None = None
    lifecycle: tuple[str, str] | None = None
    old_id: str | None = None


@dataclass(frozen=True)
class GraphDiff:
    """The changes between two snapshots, in node-id order, the ``removes`` links that appeared, and the advised bump."""

    changes: tuple[NodeChange, ...]
    new_removes: tuple[tuple[str, str], ...]
    bump: str
    old_ref: str = ""
    new_ref: str = ""


@dataclass(frozen=True)
class _Side:
    """One snapshot as the diff reads it: the snapshot, its comparable nodes by id and its first names."""

    snapshot: Snapshot
    nodes: dict[str, Node] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, snapshot: Snapshot) -> _Side:
        """The nodes of *snapshot* that can be compared, by id (first definition): a seed only when its file exists."""
        found: dict[str, Node] = {}
        for node in snapshot.graph.nodes:
            if node.kind != SEED_KIND or node.id in snapshot.seeds:
                found.setdefault(node.id, node)
        return cls(snapshot, found, first_name_index(snapshot.graph))

    def fingerprint(self, node: Node) -> Any:
        """What is compared for *node*: the seed text for a seed, else its contract view named through the first names."""
        if node.kind == SEED_KIND:
            return self.snapshot.seeds[node.id]
        view = contract_view(node, self.snapshot.graph, self.names)
        if "criteria" in view:
            view["criteria"] = {self.names.get(key, key): value for key, value in view["criteria"].items()}
        return view

    def removes_links(self) -> dict[tuple[str, str], tuple[str, str]]:
        """The ``removes`` links by (first name of holder, first name of target), each with its ids as written."""
        return {
            (self.names.get(link.source, link.source), self.names.get(link.target, link.target)): (link.source, link.target)
            for node in self.snapshot.graph.gated_nodes()
            for link in node.links
            if link.field == REMOVES
        }


def _renames(before: _Side, after: _Side) -> dict[str, str]:
    """``{new id: old id}`` for the nodes of *after* that are a node of *before* renamed.

    A node of *after* is a rename of the id in its ``aliases`` that *before* has and *after* no longer has, when its own
    id is new in *after*; one old id is claimed once, by the first new id in sorted order.
    """
    found: dict[str, str] = {}
    for node_id, node in sorted(after.nodes.items()):
        old = next((alias for alias in node.aliases if alias in before.nodes and alias not in after.nodes), None)
        if old is not None and node_id not in before.nodes and old not in found.values():
            found[node_id] = old
    return found


def _compare(old: Node, new: Node, before: _Side, after: _Side) -> NodeChange | None:
    changes: list[str] = []
    if old.id != new.id:
        changes.append(RENAMED)
    if old.kind != new.kind:
        changes.append(KIND)
    if old.lifecycle != new.lifecycle:
        changes.append(LIFECYCLE)
    if before.fingerprint(old) != after.fingerprint(new):
        changes.append(CHANGED)
    if not changes:
        return None
    return NodeChange(
        id=new.id, kind=new.kind, role=new.role, changes=tuple(changes),
        old_kind=old.kind if KIND in changes else None,
        old_role=old.role if KIND in changes else None,
        lifecycle=(old.lifecycle, new.lifecycle) if LIFECYCLE in changes else None,
        old_id=old.id if RENAMED in changes else None,
    )


def _bump_of(change: NodeChange) -> str:
    """The bump one node change asks for: the obligation rule on its role, now and before a kind change."""
    names, obligation = set(change.changes), change.role == OBLIGATION_ROLE
    stops = KIND in names and change.old_role == OBLIGATION_ROLE and not obligation
    starts = KIND in names and obligation and change.old_role != OBLIGATION_ROLE
    if stops or (obligation and REMOVED in names):
        return MAJOR
    if starts or (obligation and names & {ADDED, CHANGED}):
        return MINOR
    return PATCH


def suggest_bump(changes: tuple[NodeChange, ...], new_removes: tuple[tuple[str, str], ...]) -> str:
    """The advised version bump: ``major``, ``minor``, ``patch``, or ``none`` when nothing changed."""
    asked = {_bump_of(change) for change in changes}
    if new_removes or MAJOR in asked:
        return MAJOR
    if MINOR in asked:
        return MINOR
    return PATCH if changes else NO_BUMP


def _change_of(old: Node | None, new: Node | None, before: _Side, after: _Side) -> NodeChange | None:
    """The change of one id between the snapshots, or ``None``: a node that is ``not_applicable`` wherever it exists is out."""
    if old is not None and new is not None:
        both_out = old.lifecycle == NOT_APPLICABLE and new.lifecycle == NOT_APPLICABLE
        return None if both_out else _compare(old, new, before, after)
    node = new or old
    if node is None or node.lifecycle == NOT_APPLICABLE:
        return None
    return NodeChange(node.id, node.kind, node.role, (ADDED,) if new else (REMOVED,))


def diff_snapshots(old: Snapshot, new: Snapshot) -> GraphDiff:
    """The node-level difference from *old* to *new* and the version bump it suggests."""
    before, after = _Side.of(old), _Side.of(new)
    renamed = _renames(before, after)
    gone = set(renamed.values())
    changes: list[NodeChange] = []
    for node_id in sorted((before.nodes.keys() - gone) | after.nodes.keys()):
        old_node = before.nodes.get(renamed.get(node_id, node_id))
        change = _change_of(old_node, after.nodes.get(node_id), before, after)
        if change is not None:
            changes.append(change)
    appeared = after.removes_links()
    new_removes = tuple(sorted(appeared[key] for key in appeared.keys() - before.removes_links().keys()))
    return GraphDiff(tuple(changes), new_removes, suggest_bump(tuple(changes), new_removes))


def diff_refs(old_ref: str, new_ref: str, git_root: str, spec_root: str, repo_root: str) -> GraphDiff:
    """The diff of the spec folder *spec_root* between the refs *old_ref* and *new_ref* of the repository at *git_root*.

    Raises:
        GitViewError: E708 when *git_root* is not a folder, *spec_root* is outside it, or a ref or the spec folder at a
            ref cannot be read; E709 when the tree at a ref has no graph
            node (seeds do not count).
        KindRegistryError: the registry of the toolkit is missing or unreadable (E520).
    """
    require_git_root_folder(git_root)
    spec_path = spec_path_in_repo(spec_root, git_root)
    old = load_snapshot_at(old_ref, git_root, spec_path, repo_root)
    new = load_snapshot_at(new_ref, git_root, spec_path, repo_root)
    return replace(diff_snapshots(old, new), old_ref=old_ref, new_ref=new_ref)


def group_changes(diff: GraphDiff) -> dict[tuple[str, str], list[NodeChange]]:
    """The changes grouped by ``(role, kind)``, groups in sorted order, changes in id order."""
    groups: dict[tuple[str, str], list[NodeChange]] = defaultdict(list)
    for change in diff.changes:
        groups[(change.role or NO_ROLE, change.kind)].append(change)
    return dict(sorted(groups.items()))


def _describe(change: NodeChange) -> str:
    parts = list(change.changes)
    if change.old_id:
        parts[parts.index(RENAMED)] = f"renamed from {change.old_id}"
    if change.lifecycle:
        parts[parts.index(LIFECYCLE)] = f"lifecycle {change.lifecycle[0]} -> {change.lifecycle[1]}"
    if change.old_kind:
        parts[parts.index(KIND)] = f"kind {change.old_kind} -> {change.kind}"
    return f"{change.id}: {', '.join(parts)}"


def render_text(diff: GraphDiff) -> str:
    """The diff as text: a header, one block per ``(role, kind)`` group, the new ``removes`` links and the bump."""
    lines = [f"diff {diff.old_ref} -> {diff.new_ref}: {len(diff.changes)} node(s) changed"]
    for (role, kind), changes in group_changes(diff).items():
        lines.append(f"{role} / {kind}")
        lines.extend(f"  {_describe(change)}" for change in changes)
    if diff.new_removes:
        lines.append("new removes links")
        lines.extend(f"  {source} removes {target}" for source, target in diff.new_removes)
    lines.append(f"suggested bump: {diff.bump}")
    return "\n".join(lines)


def diff_to_dict(diff: GraphDiff) -> dict[str, Any]:
    """The diff as a JSON-able dict (the ``--json`` output)."""
    return {
        "from": diff.old_ref,
        "to": diff.new_ref,
        "bump": diff.bump,
        "groups": [
            {"role": role, "kind": kind, "nodes": [_change_to_dict(change) for change in changes]}
            for (role, kind), changes in group_changes(diff).items()
        ],
        "new_removes": [{"source": source, "target": target} for source, target in diff.new_removes],
    }


def _change_to_dict(change: NodeChange) -> Mapping[str, Any]:
    entry: dict[str, Any] = {"id": change.id, "changes": list(change.changes)}
    if change.old_id:
        entry["old_id"] = change.old_id
    if change.old_kind:
        entry["old_kind"] = change.old_kind
    if change.lifecycle:
        entry["lifecycle"] = {"from": change.lifecycle[0], "to": change.lifecycle[1]}
    return entry
