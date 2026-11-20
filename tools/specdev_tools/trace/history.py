"""Historical nodes: the milestones that are done, what they contain, and the plans written for them.

Work of a closed milestone is history: its links keep their lock entries and their resolver checks, but they take no
part in suspect detection, replay or attest (S-003).  A node is historical when it belongs to a milestone whose anchor
row has status ``done``: the milestone itself, everything it contains (tasks and their criteria) and the nodes of the
plan files that name it.

The second half of the module recovers the text a changed node had when a holder last accepted a link to it
(``OldTextResolver``), for the upstream diff of ``specdev stale --diff``.
"""
from __future__ import annotations

import json
import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass

from specdev_tools.graph.contract import contract_view, item_of
from specdev_tools.graph.gitview import (
    GitViewError,
    commits_touching,
    is_shallow_repository,
    load_graph_at,
    read_seed_texts_at,
    spec_path_in_repo,
)
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.queries import ROADMAP_MILESTONE
from specdev_tools.trace.hashing import content_hash
from specdev_tools.trace.lockfile import LockEntry

ANCHOR_ROW_KIND = "anchor-row"
ABOUT_FIELD = "about"
DONE_STATUS = "done"
_DEFAULT_STATUS = "pending"


def _anchor_status(graph: Graph, anchor: Node) -> str:
    item = item_of(graph, anchor)
    status = item.get("status") if item is not None else None
    return status if isinstance(status, str) else _DEFAULT_STATUS


def done_milestones(graph: Graph) -> set[str]:
    """Ids of the roadmap milestones that a live anchor row with status ``done`` is about."""
    done: set[str] = set()
    for anchor in graph.gated_nodes():
        if anchor.kind != ANCHOR_ROW_KIND or _anchor_status(graph, anchor) != DONE_STATUS:
            continue
        for link in anchor.links:
            milestone = graph.find(link.target) if link.field == ABOUT_FIELD else None
            if milestone is not None and milestone.kind == ROADMAP_MILESTONE:
                done.add(milestone.id)
    return done


def contained(graph: Graph, root: str) -> set[str]:
    """*root* and every node below it through containment."""
    found: set[str] = set()
    pending = [root]
    while pending:
        node_id = pending.pop()
        if node_id not in found:
            found.add(node_id)
            pending.extend(graph.children.get(node_id, ()))
    return found


def historical_node_ids(graph: Graph) -> set[str]:
    """Ids of the live nodes that belong to a milestone whose anchor row status is ``done``.

    That is each such milestone, the nodes it contains (tasks, task criteria) and the nodes whose plan file names it
    (``Node.milestone``).  A node whose lifecycle is ``not_applicable`` is left out; so is a milestone whose anchor row
    is missing or has any other status.  Returns an empty set for a graph with no anchor row.
    """
    milestones = done_milestones(graph)
    if not milestones:
        return set()
    historical: set[str] = set()
    for milestone in milestones:
        historical |= contained(graph, milestone)
    historical |= {node.id for node in graph.nodes if node.milestone is not None and graph.canonical_id(node.milestone) in milestones}
    return historical & {node.id for node in graph.gated_nodes()}


# --- old text of a changed node ---------------------------------------------------------------------------------------

MAX_COMMITS = 50
NOTE_NO_EARLIER = "no earlier version found"
NOTE_BASELINE = "stamped by migration, no earlier text recorded"
NOTE_NO_HISTORY = "history unavailable"
_SENTENCE_END = re.compile(r"(?<=[.!?]) ")


@dataclass(frozen=True)
class OldText:
    """The old text of a node as lines, or, when it cannot be recovered, ``lines`` ``None`` and a ``note`` that says why."""

    lines: tuple[str, ...] | None
    note: str | None = None


@dataclass(frozen=True)
class _OldTree:
    """The spec at one commit: its graph and the text of its seed files."""

    graph: Graph
    seeds: Mapping[str, str]


def _value_text(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)


def _view_lines(view: Mapping[str, object], prefix: str = "") -> list[str]:
    fields = view.get("fields")
    links = view.get("links")
    criteria = view.get("criteria")
    lines = [f"{prefix}{name}: {_value_text(value)}" for name, value in sorted(fields.items())] if isinstance(fields, Mapping) else []
    if isinstance(links, Mapping):
        lines += [f"{prefix}link {name}: {', '.join(ids)}" for name, ids in sorted(links.items())]
    if isinstance(criteria, Mapping):
        for criterion_id, criterion in sorted(criteria.items()):
            lines += _view_lines(criterion, f"{criterion_id}.")
    return lines


def contract_lines(node: Node, graph: Graph, seed_texts: Mapping[str, str], aliases: Mapping[str, str] | None = None) -> list[str]:
    """The contract text of *node* as lines, one per contract field or link (a criterion's lines start with its id).

    A seed has no contract fields: its lines are the sentences of its text in *seed_texts* (none when it has no text).
    *aliases* (alias id to current id) is passed through to ``contract_view``; the default is ``graph.alias_index``.
    """
    if node.kind == SEED_KIND:
        return _SENTENCE_END.split(seed_texts.get(node.id, ""))
    return _view_lines(contract_view(node, graph, graph.alias_index if aliases is None else aliases))


class OldTextResolver:
    """Finds the text a node had when a lock entry was written, from git.

    The lock holds hashes only.  For an entry, the resolver walks the commits that touched the target's file (newest
    first, at most ``MAX_COMMITS``), builds the graph at each with the current toolkit and takes the first one where the
    target's content hash equals the entry's.  A rename or a lock rewrite changes no hash, so neither hides the old
    text.  The content hash is computed with the current contract fields, so after a change of those fields or for a
    tree from before the node model no commit matches.  Graphs are cached per commit.
    """

    def __init__(self, graph: Graph, *, git_root: str, spec_root: str, repo_root: str) -> None:
        self._graph = graph
        self._git_root = git_root
        self._spec_root = spec_root
        self._repo_root = repo_root
        self._trees: dict[str, _OldTree | None] = {}

    def old_text(self, entry: LockEntry) -> OldText:
        """The old text of the target of *entry*; ``lines`` is ``None`` with a note for a baseline entry, no git history
        and no commit within the limit that matches."""
        if entry.baseline:
            return OldText(None, NOTE_BASELINE)
        target = self._graph.find(entry.target)
        if target is None:
            return OldText(None, NOTE_NO_EARLIER)
        try:
            commits = self._commits(target)
        except GitViewError:
            return OldText(None, NOTE_NO_HISTORY)
        for commit in commits:
            tree = self._tree(commit)
            lines = self._lines_matching(tree, target, entry.content_hash) if tree is not None else None
            if lines is not None:
                return OldText(tuple(lines))
        return OldText(None, NOTE_NO_HISTORY if self._is_shallow() else NOTE_NO_EARLIER)

    def _commits(self, target: Node) -> list[str]:
        """Up to ``MAX_COMMITS`` commit ids that touched the file of *target*, newest first."""
        path = target.file if target.kind == SEED_KIND else posixpath.join(spec_path_in_repo(self._spec_root, self._git_root), target.file)
        return commits_touching(self._git_root, path, MAX_COMMITS)

    def _is_shallow(self) -> bool:
        try:
            return is_shallow_repository(self._git_root)
        except GitViewError:
            return True

    def _tree(self, commit: str) -> _OldTree | None:
        """The spec at *commit*; ``None`` when it cannot be read or has no graph nodes."""
        if commit not in self._trees:
            try:
                graph = load_graph_at(commit, self._git_root, spec_path_in_repo(self._spec_root, self._git_root), self._repo_root)
                self._trees[commit] = _OldTree(graph, read_seed_texts_at(commit, self._git_root, graph))
            except GitViewError:
                self._trees[commit] = None
        return self._trees[commit]

    def _lines_matching(self, tree: _OldTree, target: Node, stored_hash: str) -> list[str] | None:
        """The lines of *target* in *tree* when its content hash there equals *stored_hash*, else ``None``.

        The node is looked up by its current id and by every alias that points at it.
        """
        aliases = self._graph.alias_index
        names = [target.id, *sorted(alias for alias, current in aliases.items() if current == target.id)]
        for name in names:
            node = tree.graph.find(name)
            if node is not None and content_hash(node.id, tree.graph, tree.seeds) == stored_hash:
                return contract_lines(node, tree.graph, tree.seeds, aliases)
        return None
