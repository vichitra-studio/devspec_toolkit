"""Node-level diff of two spec snapshots and the advisory version bump.

Per node id: added, removed, changed (the contract view differs), lifecycle changed, kind changed.  Seeds compare the
whitespace-collapsed content of their file.  A node whose lifecycle differs between the two snapshots is reported as a
lifecycle change, never as added or removed; one that is ``not_applicable`` wherever it exists is left out.  The bump is
advice only: major when an ``obligation-system`` node is removed or a ``removes`` link appears, minor when one is added
or its contract view changed, patch for anything else; a node that stops (starts) being ``obligation-system`` follows
the removed (added) rule.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from specdev_tools.graph.contract import contract_view
from specdev_tools.graph.gitview import Snapshot, load_snapshot_at, require_git_root_folder, spec_path_in_repo
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import NOT_APPLICABLE, Node

ADDED, REMOVED, CHANGED, LIFECYCLE, KIND = "added", "removed", "changed", "lifecycle", "kind"
MAJOR, MINOR, PATCH, NO_BUMP = "major", "minor", "patch", "none"
OBLIGATION_ROLE = "obligation-system"
REMOVES_FIELD = "removes"
NO_ROLE = "(no role)"


@dataclass(frozen=True)
class NodeChange:
    """What changed for one node id: ``changes`` holds one or more of the change names.

    ``kind`` and ``role`` are the node's in the newer snapshot (the older one for a removed node); ``old_kind`` and ``old_role`` are
    set for a kind change and ``lifecycle`` is ``(old, new)`` for a lifecycle change.
    """

    id: str
    kind: str
    role: str | None
    changes: tuple[str, ...]
    old_kind: str | None = None
    old_role: str | None = None
    lifecycle: tuple[str, str] | None = None


@dataclass(frozen=True)
class GraphDiff:
    """The changes between two snapshots, in node-id order, the ``removes`` links that appeared, and the advised bump."""

    changes: tuple[NodeChange, ...]
    new_removes: tuple[tuple[str, str], ...]
    bump: str
    old_ref: str = ""
    new_ref: str = ""


def _present(snapshot: Snapshot) -> dict[str, Node]:
    """The nodes of *snapshot* that can be compared, by id (first definition): a seed only when its file exists."""
    found: dict[str, Node] = {}
    for node in snapshot.graph.nodes:
        if node.kind != SEED_KIND or node.id in snapshot.seeds:
            found.setdefault(node.id, node)
    return found


def _fingerprint(node: Node, snapshot: Snapshot) -> Any:
    """What is compared for *node*: the seed text for a seed, else its contract view."""
    if node.kind == SEED_KIND:
        return snapshot.seeds[node.id]
    return contract_view(node, snapshot.graph, snapshot.graph.alias_index)


def _compare(old: Node, new: Node, old_snapshot: Snapshot, new_snapshot: Snapshot) -> NodeChange | None:
    changes: list[str] = []
    if old.kind != new.kind:
        changes.append(KIND)
    if old.lifecycle != new.lifecycle:
        changes.append(LIFECYCLE)
    if _fingerprint(old, old_snapshot) != _fingerprint(new, new_snapshot):
        changes.append(CHANGED)
    if not changes:
        return None
    return NodeChange(
        id=new.id, kind=new.kind, role=new.role, changes=tuple(changes),
        old_kind=old.kind if KIND in changes else None,
        old_role=old.role if KIND in changes else None,
        lifecycle=(old.lifecycle, new.lifecycle) if LIFECYCLE in changes else None,
    )


def _removes_links(snapshot: Snapshot) -> set[tuple[str, str]]:
    return {
        (link.source, link.target)
        for node in snapshot.graph.gated_nodes()
        for link in node.links
        if link.field == REMOVES_FIELD
    }


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


def _change_of(old: Node | None, new: Node | None, old_snapshot: Snapshot, new_snapshot: Snapshot) -> NodeChange | None:
    """The change of one id between the snapshots, or ``None``: a node that is ``not_applicable`` wherever it exists is out."""
    if old is not None and new is not None:
        both_out = old.lifecycle == NOT_APPLICABLE and new.lifecycle == NOT_APPLICABLE
        return None if both_out else _compare(old, new, old_snapshot, new_snapshot)
    node = new or old
    if node is None or node.lifecycle == NOT_APPLICABLE:
        return None
    return NodeChange(node.id, node.kind, node.role, (ADDED,) if new else (REMOVED,))


def diff_snapshots(old: Snapshot, new: Snapshot) -> GraphDiff:
    """The node-level difference from *old* to *new* and the version bump it suggests."""
    before, after = _present(old), _present(new)
    changes: list[NodeChange] = []
    for node_id in sorted(before.keys() | after.keys()):
        change = _change_of(before.get(node_id), after.get(node_id), old, new)
        if change is not None:
            changes.append(change)
    new_removes = tuple(sorted(_removes_links(new) - _removes_links(old)))
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
    if change.old_kind:
        entry["old_kind"] = change.old_kind
    if change.lifecycle:
        entry["lifecycle"] = {"from": change.lifecycle[0], "to": change.lifecycle[1]}
    return entry
