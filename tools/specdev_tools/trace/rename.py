"""``specdev node rename <old> <new>``: change the id of a node and keep every reference to it working, in one change.

The node gets its new id and its old id is appended to its ``aliases``.  Every link to the node that a LIVE holder
writes (a holder that is not a record, not historical and not ``not_applicable``) is rewritten to the new id, and so are
the lock entries of those links and the entries the node itself holds.  Links held by historical nodes and by records
keep the old id: they resolve through the alias, and their lock entries keep the old target id.

A rename changes no hash.  The old id stays the node's first name (``model.first_name_index``), and a link id is hashed
under the first name of its target (``trace.hashing``), so no lock entry becomes stale; the stored hashes are copied,
never recomputed, so a link that was already suspect stays suspect.

The write is planned in memory first (every file text, each checked against its schema, then the candidate graph), and
nothing is written unless all of it passes.  The spec files are written one after the other and then the lock; when a
write fails, the files already replaced are put back.  ``--dry-run`` stops after the plan.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.json_utils import JsonUtilsError, check_edit, json_write_atomic, patch_text
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import check_alias_space
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.kinds import RECORD_ROLE, SEED_KIND, KindDecl
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node, article
from specdev_tools.graph.queries import unknown_node_error
from specdev_tools.graph.resolve import HISTORY_FIELDS, resolve_graph
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import (
    Lock,
    LockEntry,
    LockError,
    read_lock,
    replace_file_atomically,
    write_lock,
)
from specdev_tools.trace.writing import writing_graph

ALIASES_KEY = "aliases"
_PLAIN_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class RenameRefusedError(FindingError):
    """A rename (or a label rename) that is refused; the E770 finding is in ``error`` and nothing was written."""


def refuse(message: str) -> RenameRefusedError:
    """The E770 refusal with *message*."""
    return RenameRefusedError(make_error("E770", message))


@dataclass(frozen=True)
class FileEdit:
    """The planned change to one spec file (path relative to the spec root): the text it has now and the text it will have."""

    rel: str
    original: str
    text: str


@dataclass(frozen=True)
class RewrittenLink:
    """A link a rename rewrote: *holder* held it in *field*; ``step`` is the holder's step."""

    holder: str
    field: str
    step: str | None


@dataclass(frozen=True)
class RewrittenEntry:
    """A lock entry a rename re-keyed: ``before`` and ``after`` are its (source, field, target) key."""

    before: tuple[str, str, str]
    after: tuple[str, str, str]


@dataclass(frozen=True)
class RenameResult:
    """What a rename did (or, for a dry run, would do).

    ``links`` are the links rewritten, in step order, then holder and field; ``lock_entries`` the entries re-keyed, in
    the order of the lock; ``files`` the spec files changed (relative to the spec root, sorted).  Hashes never change.
    """

    old_id: str
    new_id: str
    file: str
    jq_path: str
    written: bool
    links: tuple[RewrittenLink, ...]
    lock_entries: tuple[RewrittenEntry, ...]
    files: tuple[str, ...]


@dataclass(frozen=True)
class _Plan:
    """A rename that passed every check: the file edits, the new lock and the report."""

    node: Node
    new_id: str
    edits: tuple[FileEdit, ...]
    links: tuple[RewrittenLink, ...]
    old_lock: Lock
    lock: Lock
    lock_entries: tuple[RewrittenEntry, ...]


def jq_key(name: str) -> str:
    """The jq path step that selects the key *name* of an object: ``.name``, or ``["name"]`` for a key that is not a plain word."""
    return f".{name}" if _PLAIN_KEY.fullmatch(name) else f"[{json.dumps(name)}]"


def read_spec_file(spec_root: str, rel: str) -> str:
    """The text of the spec file *rel* under *spec_root*; E770 when it cannot be read."""
    try:
        with open(os.path.join(spec_root, rel), encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise refuse(f"cannot read {rel}: {error.strerror or error}") from None


class FileEditor:
    """The texts of the spec files being edited: each is read once, patched in memory and checked against its schema at the end."""

    def __init__(self, spec_root: str) -> None:
        self._spec_root = spec_root
        self._original: dict[str, str] = {}
        self._text: dict[str, str] = {}

    def patch(self, rel: str, jq_path: str, value: Any) -> None:
        """Set the value at *jq_path* of the file *rel* to *value* (a JSON-able value)."""
        if rel not in self._text:
            self._original[rel] = self._text[rel] = read_spec_file(self._spec_root, rel)
        try:
            self._text[rel] = patch_text(self._text[rel], jq_path, json.dumps(value, ensure_ascii=False))
        except JsonUtilsError as error:
            raise refuse(str(error)) from None

    def edits(self, repo_root: str) -> tuple[FileEdit, ...]:
        """The edits, sorted by file, after the schema check of ``json patch`` on each (E770 when one adds a violation)."""
        found: list[FileEdit] = []
        for rel in sorted(self._text):
            try:
                check_edit(rel, self._original[rel], self._text[rel], repo_root)
            except JsonUtilsError as error:
                raise refuse(str(error)) from None
            found.append(FileEdit(rel, self._original[rel], self._text[rel]))
        return tuple(found)

    def documents(self, edits: Iterable[FileEdit]) -> dict[str, Any]:
        """The parsed text of each edit, as the ``overrides`` of ``build_graph``."""
        return {edit.rel: json.loads(edit.text) for edit in edits}


# --- the checks that refuse a rename ----------------------------------------------------------------------------------

def _node_to_rename(graph: Graph, old_id: str) -> Node:
    """The node *old_id* names (an id or an alias); E706 when none does, E770 when it cannot be renamed."""
    node = graph.find(old_id)
    if node is None:
        raise unknown_node_error(graph, old_id)
    decl = graph.decls.get(node.kind)
    if node.id in graph.dups:
        raise refuse(f"node id {node.id!r} is defined more than once (E704); fix the duplicate first")
    if node.kind == SEED_KIND:
        raise refuse(f"{node.id!r} is a seed; a seed id is the key of its manifest entry and is changed in the seed manifest")
    if node.role == RECORD_ROLE:
        raise refuse(f"{node.id!r} is {article(node.kind)} {node.kind}, which is a record written by the toolkit, and a record is not renamed")
    if decl is None or decl.map_keyed or decl.id_field is None:
        raise refuse(f"{node.id!r} is {article(node.kind)} {node.kind}, whose id is the key of a map; it is not renamed by id")
    return node


def _check_new_id(graph: Graph, node: Node, new_id: str) -> None:
    if not new_id or new_id != new_id.strip() or any(char.isspace() for char in new_id):
        raise refuse(f"{new_id!r} is not an id: it must be a non-empty word with no spaces")
    if new_id == node.id:
        raise refuse(f"{node.id!r} already has the id {new_id!r}; the old and the new id are the same")
    if new_id in graph.by_id:
        raise refuse(f"{new_id!r} is already the id of {article(graph.by_id[new_id].kind)} {graph.by_id[new_id].kind}; choose an id no node has")
    if new_id in graph.alias_index:
        raise refuse(f"{new_id!r} is an alias of '{graph.alias_index[new_id]}'; choose an id no node or alias has")


def live_holders(graph: Graph, node: Node) -> dict[str, tuple[Node, set[str]]]:
    """The holders whose links to *node* a rename rewrites, each with the link fields to rewrite, by holder id.

    A holder is live when it is not a record, not historical and not ``not_applicable``; ``replaces`` and ``removes``
    name retired ids and are never rewritten.  A holder defined twice is refused.
    """
    historical = historical_node_ids(graph)
    found: dict[str, tuple[Node, set[str]]] = {}
    for link in graph.incoming.get(node.id, ()):
        holder = graph.by_id.get(link.source)
        if holder is None or link.field in HISTORY_FIELDS or holder.role == RECORD_ROLE:
            continue
        if holder.lifecycle == NOT_APPLICABLE or holder.id in historical:
            continue
        if holder.id in graph.dups:
            raise refuse(f"node id {holder.id!r}, which links to {node.id!r}, is defined more than once (E704); fix the duplicate first")
        found.setdefault(holder.id, (holder, set()))[1].add(link.field)
    return found


# --- planning the edit --------------------------------------------------------------------------------------------------

def _renamed_value(graph: Graph, value: Any, node_id: str, new_id: str) -> Any:
    """*value* (a link field: an id or a list of ids) with every name of the node *node_id* replaced by *new_id*, once each."""
    if isinstance(value, str):
        return new_id if graph.canonical_id(value) == node_id else value
    if isinstance(value, list):
        renamed = [new_id if isinstance(item, str) and graph.canonical_id(item) == node_id else item for item in value]
        return list(dict.fromkeys(renamed)) if all(isinstance(item, str) for item in renamed) else renamed
    return value


def _edit_node(editor: FileEditor, graph: Graph, node: Node, decl: KindDecl, new_id: str) -> None:
    """Set the id of *node* and append its old id to its ``aliases``."""
    held = (item_of(graph, node) or {}).get(ALIASES_KEY)
    editor.patch(node.file, f"{node.jq_path}{jq_key(decl.id_field or '')}", new_id)
    editor.patch(node.file, f"{node.jq_path}{jq_key(ALIASES_KEY)}", [*(held if isinstance(held, list) else []), node.id])


def _edit_holders(editor: FileEditor, graph: Graph, node: Node, holders: Mapping[str, tuple[Node, set[str]]], new_id: str) -> tuple[RewrittenLink, ...]:
    """Rewrite the links of *holders* to *node*; the links rewritten, in step order, then holder and field."""
    rewritten: list[RewrittenLink] = []
    for holder, fields in holders.values():
        item = item_of(graph, holder) or {}
        for field in sorted(fields):
            editor.patch(holder.file, f"{holder.jq_path}{jq_key(field)}", _renamed_value(graph, item.get(field), node.id, new_id))
            rewritten.append(RewrittenLink(holder.id, field, holder.step))
    return tuple(sorted(rewritten, key=lambda link: (graph.shape.order_key(graph.by_id[link.holder]), link.field)))


def _rekeyed_lock(graph: Graph, lock: Lock, node: Node, new_id: str, holder_ids: set[str]) -> tuple[Lock, tuple[RewrittenEntry, ...]]:
    """*lock* with the entries the node holds and the entries of the rewritten links re-keyed to *new_id*; the hashes are copied.

    Raises ``RenameRefusedError`` when an entry under the new id already exists (an orphan: run ``attest --prune``).
    """
    entries: list[LockEntry] = []
    changed: list[RewrittenEntry] = []
    for entry in lock.entries:
        source = new_id if entry.source == node.id else entry.source
        points_here = entry.field not in HISTORY_FIELDS and graph.canonical_id(entry.target) == node.id
        target = new_id if points_here and entry.source in holder_ids else entry.target
        entries.append(replace(entry, source=source, target=target))
        if (source, target) != (entry.source, entry.target):
            changed.append(RewrittenEntry(entry.key, entries[-1].key))
    try:
        return Lock(tuple(entries)), tuple(changed)
    except LockError:
        raise refuse(
            f"the trace lock already has entries under the id {new_id!r}; remove them with `specdev attest --prune` first"
        ) from None


def _finding_keys(graph: Graph) -> Counter[tuple[str, str | None]]:
    """The findings of *graph* that a rename could add, counted by (code, node id)."""
    errors: Iterable[SpecError] = (*resolve_graph(graph), *check_unique_ids(graph), *check_alias_space(graph))
    return Counter((error.code, error.node_id) for error in errors)


def _refuse_new_findings(before: Graph, edits: Sequence[FileEdit], editor: FileEditor, spec_root: str, repo_root: str) -> None:
    """E770 when the edited spec would resolve worse than the spec does now (a finding it did not have)."""
    after = build_graph(spec_root, repo_root, overrides=editor.documents(edits))
    added = _finding_keys(after) - _finding_keys(before)
    if added:
        what = ", ".join(f"{code} on {node_id}" if node_id else code for code, node_id in sorted(added, key=str))
        raise refuse(f"the rename would leave the spec with {what}; nothing was written")


def _plan_rename(graph: Graph, spec_root: str, repo_root: str, old_id: str, new_id: str) -> _Plan:
    """Plan the rename of *old_id* to *new_id* on *graph*; raises ``FindingError`` (E706 or E770) for a refusal."""
    node = _node_to_rename(graph, old_id)
    _check_new_id(graph, node, new_id)
    holders = live_holders(graph, node)
    editor = FileEditor(spec_root)
    decl = graph.decls[node.kind]
    _edit_node(editor, graph, node, decl, new_id)
    links = _edit_holders(editor, graph, node, holders, new_id)
    edits = editor.edits(repo_root)
    _refuse_new_findings(graph, edits, editor, spec_root, repo_root)
    old_lock = read_lock(spec_root)
    lock, entries = _rekeyed_lock(graph, old_lock, node, new_id, {*holders, node.id})
    return _Plan(node, new_id, edits, links, old_lock, lock, entries)


# --- writing ----------------------------------------------------------------------------------------------------------

@contextmanager
def restoring_on_failure(spec_root: str, edits: Sequence[FileEdit]) -> Iterator[list[str]]:
    """Yield the list the caller appends each file to as it replaces it; if the block raises, those files get their old text back."""
    written: list[str] = []
    try:
        yield written
    except BaseException:
        originals = {edit.rel: edit.original for edit in edits}
        for rel in written:
            replace_file_atomically(os.path.join(spec_root, rel), originals[rel])
        raise


def write_edits(spec_root: str, edits: Sequence[FileEdit], lock: Lock | None = None, old_lock: Lock | None = None) -> None:
    """Replace every file of *edits*, then write *lock* when it differs from *old_lock*; on a failure the files are put back."""
    with restoring_on_failure(spec_root, edits) as written:
        for edit in edits:
            json_write_atomic(os.path.join(spec_root, edit.rel), edit.text)
            written.append(edit.rel)
        if lock is not None and lock != old_lock:
            write_lock(spec_root, lock)


def _result(plan: _Plan, *, written: bool) -> RenameResult:
    return RenameResult(
        old_id=plan.node.id,
        new_id=plan.new_id,
        file=plan.node.file,
        jq_path=plan.node.jq_path,
        written=written,
        links=plan.links,
        lock_entries=plan.lock_entries,
        files=tuple(edit.rel for edit in plan.edits),
    )


def rename_node(
    spec_dir: str, repo_root: str, old_id: str, new_id: str, *, apply: bool = False, graph: Graph | None = None
) -> RenameResult:
    """Rename the node *old_id* (an id or an alias) of the spec folder *spec_dir* to *new_id*.

    With ``apply=False`` (``--dry-run``) nothing is written and the result says what would be.  A write takes the write
    lock of the folder first and builds the graph again under it, so the plan is made from the files as they are when
    they are written; a dry run uses *graph* (the graph of *spec_dir*) when one is given.  The spec files and then the
    lock are written; when one write fails, the files already replaced get their old text back.

    Returns:
        A ``RenameResult``; its ``written`` is ``apply``.

    Raises:
        FindingError: E706 when no node has the id *old_id* (the message names the nearest ids).
        RenameRefusedError: E770 for a seed, a record, a node whose id is a map key, an id defined twice, the same old and
            new id, a new id that a node or an alias already has, or an edit that adds a schema violation or a finding.
        LockError: E769 when another specdev write is running, E760 when the lock cannot be read.
    """
    with writing_graph(graph, spec_dir, repo_root, "node rename", write=apply) as planned:
        plan = _plan_rename(planned, spec_dir, repo_root, old_id, new_id)
        if apply:
            write_edits(spec_dir, plan.edits, plan.lock, plan.old_lock)
    return _result(plan, written=apply)
