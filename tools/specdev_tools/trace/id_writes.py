"""Id-keyed writes: ``specdev json patch|insert|delete --id <node-id>`` and ``json insert --step NN``.

A write names a node by its id, not by a position in a file, so an edit can never land on the wrong node after another
edit moved the items around.  The id is looked up with ``Graph.find`` and becomes a file and a jq path; the edit is
applied to the file text in memory; and nothing is written until every check passes:

1. the payload stores no value the toolkit computes (E768);
2. the edit adds no schema violation (the differential check of ``json patch``);
3. the edited spec resolves no worse than it did (no new E700 to E703, no duplicate id, no alias that is not free), except that a deletion may
   leave the links that pointed at the deleted node broken: they are reported, not refused.

The spec file is written first, then the lock (a crash between the two leaves a state the checks report).  A link the
edit adds gets a lock entry with the hashes its target has now; a link the edit removes, and every link a deleted node
held, loses its entry; links other nodes held into a deleted node keep theirs.  Every write holds the write lock of the
spec folder (E769 when another specdev write runs).  A refusal is a ``WriteRefusedError`` (E767); an unknown id is E706.

``write_new_file`` is the same write for a spec file that does not exist yet (``specdev step create``).
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.json_utils import (
    JQ_INDENT,
    JsonUtilsError,
    check_edit,
    delete_text,
    insert_text,
    json_schema_discovery,
    json_write_atomic,
    patch_text,
)
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import check_alias_space
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.ids import check_unique_ids, mint_slug, suggest_prefix
from specdev_tools.graph.kinds import SEED_KIND, KindDecl, load_kind_registry
from specdev_tools.graph.model import Graph, Link, Node, node_label
from specdev_tools.graph.queries import require_known_step, unknown_node_error
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.trace.computed_fields import COMPUTED_VIEWS
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import contract_lines
from specdev_tools.trace.lockfile import Lock, LockEntry, read_lock, replace_file_atomically, write_lock, writing_graph
from specdev_tools.trace.suspects import find_suspects, lock_links, orphan_entries
from specdev_tools.validation.linter_utils import graph_known_ids

ACTIONS = ("patch", "insert", "delete")
TARGET_TEXT_CHARS = 300
_FIELD_PATH = re.compile(r"^(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\]|\[\"[^\"\\]*\"\])+$")
_COLLECTION_PATH = re.compile(r"^(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_PIN_OBJECT_KEYS = ("spec_ref", "spec_refs")
_PIN_FIELDS = ("line_range", "commit_hash")
_LinkKey = tuple[str, str, str]


class WriteRefusedError(FindingError):
    """A write that is refused; ``error`` is the E767 finding (E768 for a payload that stores a computed field)."""


def _refuse(message: str, *, code: str = "E767", node_id: str | None = None) -> WriteRefusedError:
    return WriteRefusedError(make_error(code, message, node_id=node_id))


@dataclass(frozen=True)
class WriteRequest:
    """One write: *action* on the node *node_id*, or (``insert`` only) a new node into the collection *path* of step *step*.

    ``path`` is a jq path relative to the node (``.statement``) for ``patch`` and ``insert`` by id, and the collection of
    the step's file (``.functional_requirements``) for ``insert`` by step; ``value`` is JSON text, or a plain string
    when ``raw``.  ``full`` only changes how much target text the result shows.
    """

    action: str
    node_id: str | None = None
    step: str | None = None
    path: str | None = None
    value: str | None = None
    raw: bool = False
    full: bool = False


@dataclass(frozen=True)
class LinkTarget:
    """A link the edit wrote and what it points at: the target's kind, step and contract text (cut unless ``full``)."""

    holder: str
    field: str
    target: str
    kind: str
    step: str | None
    text: str


@dataclass(frozen=True)
class BrokenLink:
    """A link of a node other than the deleted one that now points at a node that is gone."""

    holder: str
    field: str
    target: str


@dataclass(frozen=True)
class WriteResult:
    """What a write did (or, for a dry run, would do).

    ``node_id`` is the node written (for ``insert --step`` the new node's id) and ``file`` / ``jq_path`` where it is;
    ``minted`` the ids made for items that had none; ``targets`` the links written; ``lock_written`` and ``lock_removed`` the lock entries added or replaced and dropped;
    ``newly_suspect`` per step in step order the number of links the edit made suspect; ``broken`` the inbound links a
    deletion left dangling.
    """

    action: str
    node_id: str
    file: str
    jq_path: str
    written: bool
    minted: tuple[str, ...]
    targets: tuple[LinkTarget, ...]
    lock_written: tuple[LockEntry, ...]
    lock_removed: tuple[LockEntry, ...]
    newly_suspect: tuple[tuple[str, int], ...]
    broken: tuple[BrokenLink, ...]


@dataclass(frozen=True)
class _Edit:
    """The planned change to one spec file: its new text and document, and the node the change is about."""

    file: str
    new_text: str
    document: dict[str, Any]
    node_id: str
    jq_path: str
    minted: tuple[str, ...] = ()
    new_file: bool = False


# --- finding the node -----------------------------------------------------------------------------------------------

def _node_to_write(graph: Graph, node_id: str) -> Node:
    """The node *node_id* names (an id or an alias); E706 when none does, E767 for a duplicated id or a seed."""
    node = graph.find(node_id)
    if node is None:
        raise unknown_node_error(graph, node_id)
    if node.id in graph.dups:
        raise _refuse(f"node id {node.id!r} is defined more than once (E704); fix the duplicate first", node_id=node.id)
    if node.kind == SEED_KIND:
        raise _refuse(f"{node.id!r} is a seed; a seed is edited as a file, not by id", node_id=node.id)
    return node


def _field_path(path: str | None, decl: KindDecl | None, node: Node) -> str:
    """The jq path *path* relative to *node*, when it names a field of the node other than its id."""
    if path is None or not _FIELD_PATH.match(path):
        raise _refuse(
            f"the field path {path!r} must be a plain jq path inside the node, such as .statement or .derives_from",
            node_id=node.id,
        )
    first = re.match(r"\.([A-Za-z_][A-Za-z0-9_]*)", path)
    if decl is not None and first is not None and first.group(1) == decl.id_field:
        raise _refuse(f"{path} is the id of {node.id!r}; an id is changed with `specdev node rename`", node_id=node.id)
    return path


# --- payload checks -------------------------------------------------------------------------------------------------

def _keys_of(value: Any) -> Iterator[str]:
    """Every object key in *value*, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys_of(item)


def _pin_objects(value: Any) -> Iterator[dict[str, Any]]:
    """Every object stored under a ``spec_ref`` or ``spec_refs`` key of *value* (alone or in a list), at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _PIN_OBJECT_KEYS:
                held = item if isinstance(item, list) else [item]
                yield from (found for found in held if isinstance(found, dict))
            yield from _pin_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from _pin_objects(item)


def _computed_names(kind: str | None) -> dict[str, str]:
    """Each stored name the toolkit rejects on a node of *kind*, with the sentence that says how to get the value."""
    names: dict[str, str] = {}
    for view in COMPUTED_VIEWS:
        if view.scope is None or kind in view.scope:
            how = view.remedy or f"compute it with {view.source}"
            names.update(dict.fromkeys(view.names, f"it is computed ({view.view}); {how}"))
    return names


def _payload_problem(kind: str | None, field: str | None, payload: Any, node_id: str | None = None) -> str | None:
    """The first reason the payload (or the field it is written to) stores something the toolkit computes or no longer stores.

    *node_id* is the node the write goes to (none for a new node); the message names it as the check's message does.
    """
    names = _computed_names(kind)
    written = [*([field.split("[")[0].lstrip(".")] if field else []), *_keys_of(payload)]
    for name in written:
        if name in names:
            where = f" to {node_id}" if node_id else ""
            return f"the write{where} stores '{name}': {names[name]}"
    for pin in _pin_objects(payload):
        for name in _PIN_FIELDS:
            if name in pin:
                return f"the write stores '{name}' in a spec_ref: a spec_ref no longer pins a line range or a commit"
    return None


def _parse_payload(value: str | None, raw: bool) -> Any:
    if raw:
        return value
    try:
        return json.loads(value or "")
    except ValueError as error:
        raise _refuse(f"the value is not valid JSON ({error}); use --raw to write it as a string") from None


# --- minting ids ----------------------------------------------------------------------------------------------------

def _nested_array(decl: KindDecl, field: str) -> KindDecl | None:
    """The nested kind of *decl* whose collection is the single-name field *field*, or ``None``."""
    return next((child for child in decl.nested if child.array_path.lstrip(".") == field.lstrip(".")), None)


def with_ids(item: Any, decl: KindDecl, taken: set[str], minted: list[str]) -> Any:
    """*item* (an object of kind *decl*) with an id for it, and for its nested items, minted where the id is missing.

    Each id minted is added to *taken* and appended to *minted*.
    """
    if not isinstance(item, dict) or decl.map_keyed or decl.id_field is None:
        return item
    result = dict(item)
    if not result.get(decl.id_field):
        label = node_label(result)
        try:
            new_id = mint_slug(label, taken, prefix=suggest_prefix(decl.kind))
        except ValueError:
            raise _refuse(f"the new {decl.kind} has no {decl.id_field} and no text to make one from; give it an id") from None
        taken.add(new_id)
        minted.append(new_id)
        result[decl.id_field] = new_id
    else:
        taken.add(result[decl.id_field])
    for child in decl.nested:
        name = child.array_path.lstrip(".")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and isinstance(result.get(name), list):
            result[name] = [with_ids(entry, child, taken, minted) for entry in result[name]]
    return result


# --- planning the edit ----------------------------------------------------------------------------------------------

def _read_file(spec_root: str, rel: str) -> str:
    try:
        with open(os.path.join(spec_root, rel), encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise _refuse(f"cannot read {rel}: {error.strerror or error}") from None


def _edited(rel: str, content: str, new_text: str, repo_root: str, node_id: str, jq_path: str, minted: Sequence[str] = ()) -> _Edit:
    """The edit of *rel*, after the schema check of ``json patch`` (refused as E767 when the edit adds a violation)."""
    try:
        check_edit(rel, content, new_text, repo_root)
        document = json.loads(new_text)
    except (JsonUtilsError, ValueError) as error:
        raise _refuse(str(error), node_id=node_id) from None
    return _Edit(rel, new_text, document, node_id, jq_path, tuple(minted))


def _plan_delete(node: Node, content: str, repo_root: str) -> _Edit:
    """The edit that removes *node* (and so its nested nodes) from its file."""
    if not node.jq_path:
        raise _refuse(f"{node.id!r} is the whole file {node.file}; delete the file instead", node_id=node.id)
    try:
        new_text = delete_text(content, node.jq_path)
    except JsonUtilsError as error:
        raise _refuse(str(error), node_id=node.id) from None
    return _edited(node.file, content, new_text, repo_root, node.id, node.jq_path)


def _declared_array(spec_root: str, node: Node, field: str, repo_root: str) -> bool:
    """Whether the schema of the file of *node* declares *field* of the node as an array."""
    try:
        found = json.loads(json_schema_discovery(os.path.join(spec_root, node.file), node.jq_path + field, repo_root) or "{}")
    except (JsonUtilsError, ValueError):
        return False
    return isinstance(found, dict) and "error" not in found and found.get("type") == "array"


def _plan_field_write(graph: Graph, spec_root: str, node: Node, content: str, repo_root: str, request: WriteRequest) -> _Edit:
    """The edit of ``patch`` or ``insert`` into a field of *node*."""
    decl = graph.decls.get(node.kind)
    field = _field_path(request.path, decl, node)
    payload = _parse_payload(request.value, request.raw)
    problem = _payload_problem(node.kind, field, payload, node.id)
    if problem is not None:
        raise _refuse(problem, code="E768", node_id=node.id)
    path, minted = node.jq_path + field, []
    try:
        if request.action == "patch":
            new_text = patch_text(content, path, request.value or "", not request.raw)
        else:
            item = _minted_for_field(graph, decl, field, payload, minted)
            create = _declared_array(spec_root, node, field, repo_root)
            new_text = insert_text(content, path, request.value or "" if request.raw else json.dumps(item), not request.raw, create=create)
    except JsonUtilsError as error:
        if request.action == "insert" and "Cannot insert into null" in str(error):
            raise _refuse(
                f"{node.id!r} has no {field.lstrip('.')} and its schema does not declare {field} as an array, "
                "so there is nothing to insert into; set the field with `specdev json patch --id`",
                node_id=node.id,
            ) from None
        raise _refuse(str(error), node_id=node.id) from None
    return _edited(node.file, content, new_text, repo_root, node.id, node.jq_path, minted)


def _plan_node_edit(graph: Graph, spec_root: str, repo_root: str, request: WriteRequest) -> _Edit:
    """The edit of ``patch`` or ``insert`` by id, or ``delete``."""
    node = _node_to_write(graph, request.node_id or "")
    content = _read_file(spec_root, node.file)
    if request.action == "delete":
        return _plan_delete(node, content, repo_root)
    return _plan_field_write(graph, spec_root, node, content, repo_root, request)


def _minted_for_field(graph: Graph, decl: KindDecl | None, field: str, payload: Any, minted: list[str]) -> Any:
    """The payload of an insert into *field* with ids minted (and listed in *minted*) when the field holds a nested kind."""
    child = _nested_array(decl, field) if decl is not None else None
    return with_ids(payload, child, set(graph_known_ids(graph)), minted) if child is not None else payload


def _step_file(graph: Graph, step: str) -> str:
    """The one spec file of *step*; E706 for a step that does not exist, E767 when it has no file or several."""
    require_known_step(graph, step)
    files = graph.shape.files_by_step.get(step, ())
    if len(files) != 1:
        what = "has no file in this spec" if not files else f"has several files ({', '.join(files)}); write by --id into one of them"
        raise _refuse(f"step {step} {what}")
    return files[0]


def _collection_decl(repo_root: str, step: str, path: str) -> KindDecl:
    """The kind whose collection is *path* in a file of *step*; E767 naming the collections there are when none is."""
    declared = [kind for file in load_kind_registry(repo_root).files if file.step == step for kind in file.kinds]
    for kind in declared:
        if kind.array_path.removesuffix("{}").lstrip(".") == path.lstrip("."):  # a map-keyed collection is declared as `.name{}`
            return kind
    names = ", ".join(sorted(
        f"{kind.array_path.removesuffix('{}')} ({kind.kind}, map: not added by this command)" if kind.map_keyed
        else f"{kind.array_path} ({kind.kind})"
        for kind in declared
    )) or "none"
    raise _refuse(f"step {step} has no node collection {path}; its collections: {names}")


def _plan_step_insert(graph: Graph, spec_root: str, repo_root: str, request: WriteRequest) -> _Edit:
    """The edit of ``insert --step``: the new node appended to the collection of the step's file, its ids minted."""
    step, path = request.step or "", request.path or ""
    rel = _step_file(graph, step)
    if not _COLLECTION_PATH.match(path):
        raise _refuse(f"the collection path {path!r} must be a plain jq path such as .functional_requirements")
    decl = _collection_decl(repo_root, step, path)
    if decl.map_keyed:
        raise _refuse(f"{path} is a map keyed by id, and `specdev json insert --step` does not add to a map")
    payload = _parse_payload(request.value, request.raw)
    if not isinstance(payload, dict):
        raise _refuse(f"the new {decl.kind} must be a JSON object")
    problem = _payload_problem(decl.kind, None, payload)
    if problem is not None:
        raise _refuse(problem, code="E768")
    minted: list[str] = []
    item = with_ids(payload, decl, set(graph_known_ids(graph)), minted)
    content = _read_file(spec_root, rel)
    try:
        new_text = insert_text(content, path, json.dumps(item), True, create=True)
    except JsonUtilsError as error:
        raise _refuse(str(error)) from None
    return _edited(rel, content, new_text, repo_root, str(item[decl.id_field]), path, minted)


# --- judging the candidate graph ------------------------------------------------------------------------------------

def _finding_keys(graph: Graph) -> dict[tuple[str, str | None, str], SpecError]:
    """The link-resolution, duplicate-id and alias-space findings of *graph* by (code, node id, message)."""
    errors = (*resolve_graph(graph), *check_unique_ids(graph), *check_alias_space(graph))
    return {(error.code, error.node_id, error.message): error for error in errors}


def _link_keys(graph: Graph) -> set[_LinkKey]:
    return {(node.id, link.field, link.target) for node in graph.nodes for link in node.links}


def _candidate_hint(base: Graph, candidate: Graph, holders: Iterable[str], new_links: Iterable[_LinkKey]) -> str:
    """The `specdev node candidates` commands that list valid targets for the new links of *holders*."""
    wanted = set(holders)
    commands: list[str] = []
    for holder, field, _target in sorted(new_links):
        if holder not in wanted:
            continue
        scope = f"--for {holder}" if holder in base.by_id else f"--kind {candidate.by_id[holder].kind}"
        commands.append(f"specdev node candidates {scope} --field {field}")
    return f"; valid targets: {'; '.join(dict.fromkeys(commands))}" if commands else ""


def _refuse_new_findings(base: Graph, candidate: Graph) -> None:
    """E767 when the edit would leave a link-resolution or duplicate-id finding that the spec did not have."""
    before, after = _finding_keys(base), _finding_keys(candidate)
    added = [after[key] for key in after if key not in before]
    if not added:
        return
    holders = {error.node_id for error in added if error.node_id}
    hint = _candidate_hint(base, candidate, holders, _link_keys(candidate) - _link_keys(base))
    lines = "\n".join(f"  {error.render()}" for error in added)
    raise _refuse(f"the edit would leave the spec with:\n{lines}\nnothing was written{hint}")


def _target_text(target: Node, graph: Graph, seed_texts: Mapping[str, str], full: bool) -> str:
    text = " ".join(contract_lines(target, graph, seed_texts))
    return text if full or len(text) <= TARGET_TEXT_CHARS else text[:TARGET_TEXT_CHARS].rstrip() + "..."


def _written_targets(base: Graph, candidate: Graph, seed_texts: Mapping[str, str], full: bool) -> tuple[LinkTarget, ...]:
    """What every link the edit added points at, in step order, then holder, field and target."""
    new_links = _link_keys(candidate) - _link_keys(base)
    found: list[tuple[Node, Link, Node]] = []
    for node in candidate.nodes:
        for link in node.links:
            target = candidate.find(link.target)
            if (node.id, link.field, link.target) in new_links and target is not None:
                found.append((node, link, target))
    found.sort(key=lambda item: (candidate.shape.order_key(item[0]), item[1].field, item[1].target))
    return tuple(
        LinkTarget(holder.id, link.field, link.target, target.kind, target.step, _target_text(target, candidate, seed_texts, full))
        for holder, link, target in found
    )


# --- the lock -------------------------------------------------------------------------------------------------------

def _lock_after(base: Graph, candidate: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> tuple[Lock, tuple[LockEntry, ...], tuple[LockEntry, ...]]:
    """The lock after the edit, and the entries added and removed.

    A link the edit added (one the base graph did not declare) gets an entry with the hashes of its target now; an entry
    the edit orphaned is dropped.  An entry that was already an orphan, and the entries of links that point into a
    deleted node, stay: a link whose target is deleted and then added again is not new, so its old entry shows the change.
    """
    hashes = compute_all(candidate, seed_texts)
    had = _link_keys(base)
    written = tuple(
        LockEntry(item.holder.id, item.link.field, item.link.target, *hashes[item.target.id])
        for item in lock_links(candidate)
        if item.key not in had and item.target.id in hashes
    )
    orphaned_before = {entry.key for entry in orphan_entries(base, lock)}
    removed = tuple(entry for entry in orphan_entries(candidate, lock) if entry.key not in orphaned_before)
    gone = {entry.key for entry in (*written, *removed)}
    kept = tuple(entry for entry in lock.entries if entry.key not in gone)
    return Lock((*kept, *written)), written, removed


def _newly_suspect(base: Graph, candidate: Graph, lock: Lock, new_lock: Lock, seed_texts: Mapping[str, str]) -> tuple[tuple[str, int], ...]:
    """The number of links the edit made suspect, per step of the holder; ``find_suspects`` lists them in step order."""
    before = {suspect.key for suspect in find_suspects(base, lock, seed_texts)}
    counts = Counter(
        suspect.holder_step or "" for suspect in find_suspects(candidate, new_lock, seed_texts) if suspect.key not in before
    )
    return tuple(counts.items())


def broken_holders(graph: Graph, deleted: Iterable[str]) -> list[BrokenLink]:
    """The links of live nodes of *graph* that point at one of the ids *deleted*, sorted by holder, field and target.

    A holder whose lifecycle is ``not_applicable`` is not live: the resolver does not check it, so it is not reported.
    """
    gone = set(deleted)
    live = {node.id for node in graph.gated_nodes()} - gone
    found = {
        BrokenLink(link.source, link.field, link.target)
        for target in gone
        for link in graph.incoming.get(target, ())
        if link.source in live
    }
    return sorted(found, key=lambda link: (link.holder, link.field, link.target))


# --- running a write ------------------------------------------------------------------------------------------------

def _plan_edit(graph: Graph, spec_root: str, repo_root: str, request: WriteRequest) -> _Edit:
    if request.action not in ACTIONS:
        raise ValueError(f"action must be one of {', '.join(ACTIONS)}, not {request.action!r}")
    if request.step is not None:
        return _plan_step_insert(graph, spec_root, repo_root, request)
    return _plan_node_edit(graph, spec_root, repo_root, request)


def _apply_edit(
    graph: Graph, spec_root: str, repo_root: str, git_root: str, edit: _Edit, *, action: str, full: bool, write: bool
) -> WriteResult:
    """Judge *edit* against *graph* and, when *write*, write the spec file first and then the lock."""
    candidate = build_graph(spec_root, repo_root, overrides={edit.file: edit.document})
    if action != "delete":
        _refuse_new_findings(graph, candidate)
    lock, seed_texts = read_lock(spec_root), read_seed_texts(graph, git_root)
    new_lock, written, removed = _lock_after(graph, candidate, lock, seed_texts)
    result = WriteResult(
        action=action,
        node_id=edit.node_id,
        file=edit.file,
        jq_path=edit.jq_path,
        written=write,
        minted=edit.minted,
        targets=_written_targets(graph, candidate, seed_texts, full),
        lock_written=written,
        lock_removed=removed,
        newly_suspect=_newly_suspect(graph, candidate, lock, new_lock, seed_texts),
        broken=tuple(broken_holders(graph, set(graph.by_id) - set(candidate.by_id))),
    )
    if write:
        target = os.path.join(spec_root, edit.file)
        if edit.new_file:
            replace_file_atomically(target, edit.new_text)
        else:
            json_write_atomic(target, edit.new_text)
        if new_lock != lock:
            write_lock(spec_root, new_lock)
    return result


def _write_on(graph: Graph, spec_root: str, repo_root: str, git_root: str, request: WriteRequest, *, write: bool) -> WriteResult:
    edit = _plan_edit(graph, spec_root, repo_root, request)
    return _apply_edit(graph, spec_root, repo_root, git_root, edit, action=request.action, full=request.full, write=write)


def write_new_file(
    graph: Graph,
    spec_root: str,
    repo_root: str,
    git_root: str,
    rel: str,
    document: dict[str, Any],
    node_id: str,
    minted: Sequence[str] = (),
    *,
    full: bool = False,
    write: bool = True,
) -> WriteResult:
    """Create the spec file *rel* (relative to *spec_root*) from *document*, with the lock entries of its links.

    The caller holds the write lock of the folder (when *write*), passes the *graph* it built under that lock and has
    checked that the file does not exist and that *document* is valid against its schema.  The candidate graph must
    resolve no worse than *graph* (E767 otherwise, nothing written); the lock gets one entry per link of the new nodes,
    with the hashes their targets have now.  *node_id* names the file in the result; *minted* lists the ids made.
    The result has ``action`` ``"create"``; the spec file is written first, then the lock.

    Raises:
        WriteRefusedError: E767 when the new file would leave a link that does not resolve or a duplicate id.
        LockError: E760 when the lock file cannot be read.
    """
    text = json.dumps(document, indent=JQ_INDENT, ensure_ascii=False) + "\n"
    edit = _Edit(rel, text, document, node_id, "", tuple(minted), new_file=True)
    return _apply_edit(graph, spec_root, repo_root, git_root, edit, action="create", full=full, write=write)


def execute_write(
    graph: Graph, spec_root: str, repo_root: str, git_root: str, request: WriteRequest, *, dry_run: bool = False
) -> WriteResult:
    """Run *request* against the spec folder *spec_root*; writes the spec file and the lock unless *dry_run*.

    *graph* is the graph of *spec_root* (used as it is for a dry run).  A write takes the write lock of the folder
    first and builds the graph again under it, so the edit is planned from the files as they are when it is written.

    Raises:
        WriteRefusedError: E767 (the edit is refused; nothing is written) or E768 (a computed field in the payload).
        FindingError: E706 for an unknown id or step; ``LockError`` (E769) when another write holds the lock, or
            (E760) when the lock file cannot be read.
    """
    what = f"json {request.action} --{'step' if request.step else 'id'}"
    with writing_graph(graph, spec_root, repo_root, what, write=not dry_run) as planned:
        return _write_on(planned, spec_root, repo_root, git_root, request, write=not dry_run)
