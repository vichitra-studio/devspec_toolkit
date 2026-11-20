"""``specdev node rename --label <term-id> "<new label>"``: change the label of a glossary term and every exact use of it.

The label of a term is its ``term`` field.  A use is a string of a node of steps 04 to 15 (a node that is not a record
and not ``not_applicable``) that holds the old label as whole words, spelled exactly (the case counts); the id fields,
the link fields, ``aliases`` and the fields that hold an id or a reference are not read.  Each use is rewritten and
listed with the node, the field path and the old and new text.  Nothing is added to ``aliases`` (it holds old ids only)
and no old label is matched afterwards.  Closed work is frozen: the uses in the nodes of a closed milestone are not
rewritten and are listed as skipped.

The change is planned in memory, every file is checked against its schema, and the spec files are then written under
the write lock of the spec folder, as for the id rename (``trace.rename``).  The trace lock is not touched: the new
label is a contract change of the term and the uses are contract changes of their nodes, so the links into them
become suspect, which ``specdev stale`` then lists.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any

from specdev_tools.core.schema_validate import jq_key
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.kinds import RECORD_ROLE
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node, article
from specdev_tools.graph.queries import unknown_node_error
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.writing import writing_graph
from specdev_tools.trace.rename import FileEdit, FileEditor, refuse, write_edits

TERM_KIND = "term"
LABEL_KEY = "term"
FIRST_STEP, LAST_STEP = "04", "15"
_SKIPPED_KEYS = re.compile(r"^(?:\$schema|aliases|ids?|refs?|.+_(?:ids?|refs?))$")


@dataclass(frozen=True)
class LabelUse:
    """A use of the old label that was rewritten: the node, the jq path of the string inside the node and its old and new text."""

    node_id: str
    field_path: str
    old_text: str
    new_text: str


@dataclass(frozen=True)
class LabelSkip:
    """A use of the old label that was not rewritten because its node belongs to a closed milestone (frozen work)."""

    node_id: str
    field_path: str


@dataclass(frozen=True)
class LabelRenameResult:
    """What a label rename did (or, for a dry run, would do); ``uses`` are in step order, then node id and field path."""

    term_id: str
    old_label: str
    new_label: str
    file: str
    jq_path: str
    written: bool
    uses: tuple[LabelUse, ...]
    files: tuple[str, ...]
    skipped: tuple[LabelSkip, ...] = ()


def _term_to_relabel(graph: Graph, term_id: str, new_label: str) -> tuple[Node, str]:
    """The term node *term_id* names and its label; E706 when no node has the id, E770 when it cannot be relabelled."""
    node = graph.find(term_id)
    if node is None:
        raise unknown_node_error(graph, term_id)
    if node.id in graph.dups:
        raise refuse(f"node id {node.id!r} is defined more than once (E704); fix the duplicate first")
    if node.kind != TERM_KIND:
        raise refuse(f"{node.id!r} is {article(node.kind)} {node.kind}, not a glossary term; only a term has a label to rename")
    held = (item_of(graph, node) or {}).get(LABEL_KEY)
    if not isinstance(held, str) or not held.strip():
        raise refuse(f"{node.id!r} has no {LABEL_KEY!r} text to rename")
    if not new_label.strip() or new_label != new_label.strip():
        raise refuse(f"{new_label!r} is not a label: it must be text with no space at either end")
    if new_label == held:
        raise refuse(f"{node.id!r} already has the label {held!r}")
    return node, held


def label_users(graph: Graph) -> list[Node]:
    """The nodes whose text is read for uses: steps 04 to 15 by rank, not a record, not ``not_applicable``."""
    ranks = graph.shape.step_ranks
    low, high = ranks.get(FIRST_STEP), ranks.get(LAST_STEP)
    if low is None or high is None:
        return []
    return [
        node for node in graph.nodes
        if node.step is not None and low <= graph.shape.rank_of(node.step) <= high
        and node.role != RECORD_ROLE and node.lifecycle != NOT_APPLICABLE
    ]


def _leaves(value: Any, path: str, skipped_paths: frozenset[str]) -> Iterator[tuple[str, str]]:
    """Every string of *value* that is not under a skipped key or path, with its jq path from *path*."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, f"{path}[{index}]", skipped_paths)
    elif isinstance(value, dict):
        yield from _object_leaves(value, path, skipped_paths)


def _object_leaves(value: dict[str, Any], path: str, skipped_paths: frozenset[str]) -> Iterator[tuple[str, str]]:
    """The strings of the members of the object *value* whose key and path are not skipped."""
    for key, item in value.items():
        child = path + jq_key(key)
        if not _SKIPPED_KEYS.match(key) and child not in skipped_paths:
            yield from _leaves(item, child, skipped_paths)


def own_leaves(graph: Graph, node: Node) -> Iterator[tuple[str, str]]:
    """The strings of the item of *node* that a use may be in: not its id, its links, its aliases or its child nodes."""
    item, decl = item_of(graph, node), graph.decls.get(node.kind)
    if item is None or decl is None:
        return
    skipped = {jq_key(name) for name in (decl.id_field, *(link.field for link in decl.links)) if name}
    skipped.update(nested.array_path for nested in decl.nested)
    yield from _leaves(item, "", frozenset(skipped))


def _uses(graph: Graph, old_label: str, new_label: str) -> tuple[list[LabelUse], list[LabelSkip]]:
    """Every string of a user that holds *old_label* as whole words, with the text it will have.

    Closed work is frozen: a string of a node of a closed milestone (``trace.history.historical_node_ids``) is not
    rewritten and comes back in the second list.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(old_label)}(?!\w)")
    frozen = historical_node_ids(graph)
    found: list[LabelUse] = []
    skipped: list[LabelSkip] = []
    for node in sorted(label_users(graph), key=graph.shape.order_key):
        for path, text in own_leaves(graph, node):
            if not pattern.search(text):
                continue
            if node.id in frozen:
                skipped.append(LabelSkip(node.id, path))
            else:
                found.append(LabelUse(node.id, path, text, pattern.sub(lambda _match: new_label, text)))
    return found, skipped


def _edits(graph: Graph, spec_root: str, repo_root: str, term: Node, new_label: str, uses: list[LabelUse]) -> tuple[FileEdit, ...]:
    editor = FileEditor(spec_root)
    editor.patch(term.file, f"{term.jq_path}{jq_key(LABEL_KEY)}", new_label)
    for use in uses:
        holder = graph.by_id[use.node_id]
        editor.patch(holder.file, f"{holder.jq_path}{use.field_path}", use.new_text)
    return editor.edits(repo_root)


def _plan(graph: Graph, spec_root: str, repo_root: str, term_id: str, new_label: str) -> tuple[LabelRenameResult, tuple[FileEdit, ...]]:
    """The result of the rename of *term_id* as a dry run, and the file edits that carry it out."""
    term, old_label = _term_to_relabel(graph, term_id, new_label)
    uses, skipped = _uses(graph, old_label, new_label)
    edits = _edits(graph, spec_root, repo_root, term, new_label, uses)
    return LabelRenameResult(
        term.id, old_label, new_label, term.file, term.jq_path, False, tuple(uses), tuple(edit.rel for edit in edits),
        tuple(skipped),
    ), edits


def rename_label(
    spec_dir: str, repo_root: str, term_id: str, new_label: str, *, apply: bool = False, graph: Graph | None = None
) -> LabelRenameResult:
    """Change the label of the glossary term *term_id* (an id or an alias) of *spec_dir* to *new_label* and rewrite its uses.

    With ``apply=False`` (``--dry-run``) nothing is written.  A write takes the write lock of the folder, builds the graph
    again under it and writes every changed spec file or, when one write fails, none.  A dry run uses *graph* when given.

    Returns:
        A ``LabelRenameResult``; its ``written`` is ``apply``.

    Raises:
        FindingError: E706 when no node has the id *term_id* (the message names the nearest ids).
        RenameRefusedError: E770 for a node that is not a term, an id defined twice, a label that is empty, padded or
            unchanged, or an edit that adds a schema violation.
        LockError: E769 when another specdev write is running.
    """
    with writing_graph(graph, spec_dir, repo_root, "node rename --label", write=apply) as planned:
        result, edits = _plan(planned, spec_dir, repo_root, term_id, new_label)
        if apply:
            write_edits(spec_dir, edits)
    return replace(result, written=True) if apply else result
