"""Edits by id of a closed milestone's step-14 nodes: refused, except inside a migration, where each milestone gets one record.

A closed milestone's roadmap milestone, tasks and task criteria are history: the only edits they take are ``node status
<id> not_applicable`` and the edits of a migration, which are recorded on the milestone's ``close`` (``migrations``).
``specdev json patch|insert|delete --id`` and ``specdev node rename`` ask ``edit_of_closed_node`` before they write: outside a migration the answer is
a refusal (E767); while the stamp of the spec folder says the migration is in progress the edit is allowed and, once it is
written, ``record_migration_edit`` adds one record to the close of the milestone (a second edit of the same milestone in the
same migration adds nothing).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..core.constants import STATUS_IN_PROGRESS
from ..core.errors import FindingError, make_error
from ..generation.schema_differ import read_stamp
from ..graph.model import Graph, Node
from ..trace.history import closed_milestone_of
from . import anchor_store, plans


def migration_in_progress(spec_root: str) -> bool:
    """Whether the stamp of the spec folder says a migration has been installed and not yet closed."""
    return (read_stamp(spec_root) or {}).get("migration_status") == STATUS_IN_PROGRESS


def _migration_note(spec_root: str) -> str:
    """The note that names the migration in progress: from which version to which, as the stamp's last history entry says."""
    stamp = read_stamp(spec_root) or {}
    history = stamp.get("migration_history")
    last = history[-1] if isinstance(history, list) and history and isinstance(history[-1], Mapping) else {}
    start, end = last.get("from"), last.get("to") or stamp.get("toolkit_version")
    return f"step-14 nodes edited by the migration from {start} to {end}" if start and end else "step-14 nodes edited by the migration"


def edit_of_closed_node(graph: Graph, spec_root: str, node_id: str, command: str) -> str | None:
    """The closed milestone whose step-14 node *node_id* the id-keyed write *command* (for example ``json patch --id``) would change, when the write is allowed to go on in a migration; ``None`` when the node is not such a node.

    Raises:
        FindingError: E767 when the node is a step-14 node of a closed milestone and no migration is in progress.
    """
    node = graph.find(node_id)
    milestone = closed_milestone_of(graph, node) if node is not None else None
    if node is None or milestone is None or migration_in_progress(spec_root):
        return milestone
    raise FindingError(make_error(
        "E767",
        f"{node.id!r} is a step-14 node ({node.kind}) of milestone {milestone}, which is closed, so `{command}` does not change it: "
        f"a closed milestone's step-14 nodes take `specdev node status {node.id} not_applicable` and the edits of a migration, which are recorded on the milestone's close; "
        f"to change the work, add a new task or milestone",
        node_id=node.id,
    ))


def record_migration_edit(spec_root: str, repo_root: str, milestone: str) -> bool:
    """Add the record of the migration in progress to the close of *milestone*, once; ``True`` when it was added.

    The record is ``{hash_after, note}``: the hash is the one the plan has now (an edit of a step-14 node does not touch the
    plan) and the note names the migration.  A milestone whose close already holds that note, or that has no close or no plan
    hash to store, is left as it is.
    """
    row = anchor_store.read_row(spec_root, milestone)
    close: Mapping[str, Any] | None = row.close if row is not None else None
    if close is None:
        return False
    note = _migration_note(spec_root)
    if any(isinstance(record, Mapping) and record.get("note") == note for record in close.get("migrations", ())):
        return False
    hash_after = plans.stored_plan_hash(close)
    if hash_after is None:
        return False
    anchor_store.append_close_migration(spec_root, milestone, hash_after, note, repo_root=repo_root)
    return True

