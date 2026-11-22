"""``p6_baseline``: write the trace lock of a migrated host, every entry marked as a migration baseline.

A 1.1.1 host has no trace lock.  After the earlier phases the spec holds links the 1.2.0 resolver accepts, and each of them
needs a lock entry (E761 otherwise).  This script writes one entry per link that carries one (``trace.suspects.lock_links``)
and has none yet, with the hashes its target has NOW, through the lock's own reader, writer and entry type (``trace.lockfile``,
``trace.hashing``, ``trace.history``): the same format ``specdev attest`` writes.  An entry written here is not an attestation by a
person: it carries ``baseline: true`` (the one marker the format has; it holds no name and no date, so nothing in it depends on
the clock) and says "this link is accepted as the migration found it".  The step pass of each step re-attests its own links with
``specdev attest``, which clears the marker; until then each live baseline entry is one E882, and the step gate's migration
mode treats a step that owns an E882 as not passed.  An entry of a historical holder (a closed milestone) keeps its marker for good.

* An existing entry is never restamped: a link whose entry is there (marked or not) is left as it is, so a second run writes
  nothing and a run after some steps were re-attested brings no marker back.
* A record link (``about``, ``verifies``) and a ``replaces`` / ``removes`` link carry no entry (``lock_links`` leaves them out).
* A link the resolver does not accept (no such node, a kind the field refuses, a target in a later step) gets no entry and one
  operator item on the worklist; the step gate shows it as E700 to E702 meanwhile.

The seeds hash into the entries, so a seed document of the graph must be in the host (``seed_texts_for_write``: E520 when one is
missing).  The lock is written into the scratch spec folder; the runner installs it.  The script touches ``extras/`` only.
"""

from __future__ import annotations

import os
from typing import Any

from specdev_tools.core.constants import TRACE_LOCK_FILENAME
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.registry import PHASE_BASELINE, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.worklist import AUDIENCE_OPERATOR, WORKLIST_FILE, WorklistItem, add_items, make_item, missing_items
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import containers_of, historical_node_ids
from specdev_tools.trace.lockfile import Lock, LockEntry, read_lock, write_lock
from specdev_tools.trace.suspects import missing_entries
from specdev_tools.trace.writing import locked_graph, refuse_unreadable, seed_texts_for_write

SCRIPT = ScriptSpec(id="p6_baseline", phase=PHASE_BASELINE, touches=("extras",))

KIND_UNRESOLVED_LINK = "unresolved-link"
LOCK_REL = f"extras/{TRACE_LOCK_FILENAME}"
_UNRESOLVED_CODES = frozenset({"E700", "E701", "E702"})
_WHAT = "p6_baseline"


def _unresolved_items(graph: Graph) -> list[WorklistItem]:
    """One operator item per link the resolver refuses (E700, E701, E702), from the resolver's own findings."""
    items: list[WorklistItem] = []
    for error in resolve_graph(graph, historical=historical_node_ids(graph)):
        holder = graph.by_id.get(error.node_id or "")
        if error.code not in _UNRESOLVED_CODES or holder is None or error.target is None:
            continue
        items.append(
            make_item(
                holder.step or "",
                KIND_UNRESOLVED_LINK,
                holder.id,
                audience=AUDIENCE_OPERATOR,
                blocking=False,
                evidence=f"{error.code} {error.message}",
                proposal="fix or remove the link; it has no trace lock entry until it resolves, and `specdev attest` writes one then",
                key=error.target,
            )
        )
    return items


def _unlisted(ctx: MigrationContext, graph: Graph) -> list[WorklistItem]:
    return missing_items(ctx, _unresolved_items(graph))


def detect(ctx: MigrationContext) -> int:
    """The number of links to write an entry for plus the unresolved links not yet on the worklist: 0 once both are done.

    Raises ``FindingError`` (E520) when a spec file cannot be read, so the links it holds are not in the graph.
    """
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    refuse_unreadable(graph, _WHAT)
    return len(missing_entries(graph, read_lock(ctx.spec_root))) + len(_unlisted(ctx, graph))


def _baseline_entries(graph: Graph, lock: Lock, host_root: str) -> tuple[LockEntry, ...]:
    """The entries to add to *lock*: one per link that carries an entry and has none, hashes of the target as it is now."""
    links = missing_entries(graph, lock)
    if not links:
        return ()
    hashes = compute_all(graph, seed_texts_for_write(graph, host_root))
    return tuple(
        LockEntry(
            item.holder.id, item.link.field, item.link.target, *hashes[item.target.id],
            baseline=True, target_containers=containers_of(graph, item.target),
        )
        for item in links
    )


def apply(ctx: MigrationContext) -> ScriptResult:
    """Write the missing baseline entries (the write lock held once, around the read and the write of the lock only) and the worklist items."""
    with locked_graph(ctx.spec_root, ctx.toolkit_root, _WHAT) as graph:
        lock = read_lock(ctx.spec_root)
        written = _baseline_entries(graph, lock, ctx.host_root)
        if written:
            write_lock(ctx.spec_root, Lock((*lock.entries, *written)))
    unlisted = _unlisted(ctx, graph)
    added = add_items(ctx, unlisted)
    historical = historical_node_ids(graph)
    live = sum(entry.source not in historical for entry in written)
    summary = (
        f"{len(written)} baseline entr{'y' if len(written) == 1 else 'ies'} written to {LOCK_REL} "
        f"({live} on live holders: one E882 each until the step pass re-attests it; {len(written) - live} on historical holders, which keep the marker)"
    )
    return ScriptResult(
        edits=len(written) + added,
        worklist_items=added,
        residue=(summary, *(f"no entry, the link does not resolve: {item.evidence}" for item in unlisted)),
    )


def _entries(snapshot: Any) -> dict[tuple[Any, Any, Any], dict[str, Any]]:
    """``{(source, field, target): entry}`` of the lock in a runner snapshot; empty when it has no lock."""
    lock = snapshot.documents.get(LOCK_REL)
    raw = lock.get("entries") if isinstance(lock, dict) else None
    entries = [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []
    return {(entry.get("source"), entry.get("field"), entry.get("target")): entry for entry in entries}


def verify(before: Any, after: Any) -> list[Problem]:
    """Only ``extras/`` changed; no entry of the lock was changed or removed; each entry added carries the baseline marker."""
    worklist = WORKLIST_FILE.replace(os.sep, "/")
    problems = [
        Problem(f"changed {rel}; this script writes the lock and the worklist only", rel)
        for rel in sorted(set(before.files) | set(after.files))
        if before.files.get(rel) != after.files.get(rel) and rel not in (LOCK_REL, worklist)
    ]
    old, new = _entries(before), _entries(after)
    problems += [Problem(f"the lock entry {key} was changed or removed; an existing entry is never restamped", LOCK_REL) for key, entry in old.items() if new.get(key) != entry]
    problems += [Problem(f"the lock entry {key} was added without the baseline marker", LOCK_REL) for key, entry in new.items() if key not in old and entry.get("baseline") is not True]
    return problems
