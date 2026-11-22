"""Lifecycle changes of graph nodes (``specdev node status``).

The decision (``plan_lifecycle_change``) reads only the graph; the write (``apply_lifecycle_change``) goes through
``core.json_utils``, which validates the edit against the file's own schema and writes atomically.  ``active`` is the
default, so it is written as the absence of the ``lifecycle`` key.  A lifecycle is outside the content hash, so a
change needs no lock work.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.core.json_utils import json_delete, json_patch
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import SEED_KIND, has_lifecycle
from specdev_tools.graph.model import DEFAULT_LIFECYCLE, LIFECYCLES, NOT_APPLICABLE, Graph, Node, article
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import with_write_lock

LIFECYCLE_KEY = "lifecycle"
ROADMAP_STEP = "14"
NOT_APPLICABLE_GUIDANCE = (
    "not_applicable is only for a closed milestone's historical step-14 nodes (a task, a task criterion or the milestone) whose "
    "built target was deleted; to take any other node out of use, set it to deprecated"
)


class LifecycleRefusedError(FindingError):
    """A lifecycle change that is refused; the E705 finding is in ``error``."""


@dataclass(frozen=True)
class LifecycleChange:
    """One accepted change: ``node_id`` goes from ``old`` to ``new`` at ``jq_path`` of ``file`` (relative to the spec root)."""

    node_id: str
    old: str
    new: str
    file: str
    jq_path: str


def _refuse(message: str, *, unknown_id: bool = False) -> LifecycleRefusedError:
    return LifecycleRefusedError(make_error("E705", message), unknown_id=unknown_id)


def _node_to_change(graph: Graph, node_id: str) -> Node:
    """The node *node_id* names (an id or an alias), or E705 when it cannot take a lifecycle; an unknown id is marked as such."""
    node = graph.find(node_id)
    if node is None:
        raise _refuse(f"no node has the id {node_id!r}", unknown_id=True)
    if node.id in graph.dups:
        raise _refuse(f"node id {node.id!r} is defined more than once (E704); fix the duplicate first")
    if node.kind == SEED_KIND:
        raise _refuse(f"{node.id!r} is a seed, and a seed has no lifecycle")
    if not has_lifecycle(node.kind, node.role):
        raise _refuse(f"{node.id!r} is {article(node.kind)} {node.kind}, which is a record, and a record has no lifecycle")
    return node


def plan_lifecycle_change(graph: Graph, node_id: str, value: str) -> LifecycleChange:
    """The change that sets the lifecycle of *node_id* to *value*.

    Raises ``LifecycleRefusedError`` (E705) for a value outside the lifecycle enum, an unknown or duplicated id, and a
    node of role ``record`` or kind ``seed``.  ``not_applicable`` is refused (E705) for a node that is not a historical step-14
    node (see ``NOT_APPLICABLE_GUIDANCE``); a node that already has it is not refused.  Any other node accepts any other value.
    """
    if value not in LIFECYCLES:
        raise _refuse(f"lifecycle {value!r} is not one of {', '.join(LIFECYCLES)}")
    node = _node_to_change(graph, node_id)
    if value == NOT_APPLICABLE and node.lifecycle != NOT_APPLICABLE and not (node.step == ROADMAP_STEP and node.id in historical_node_ids(graph)):
        raise _refuse(f"{node.id!r} cannot be set to not_applicable: {NOT_APPLICABLE_GUIDANCE}")
    return LifecycleChange(node.id, node.lifecycle, value, node.file, node.jq_path)


def apply_lifecycle_change(spec_root: str, repo_root: str, change: LifecycleChange) -> None:
    """Write *change* into its file under *spec_root*.

    ``active`` deletes the ``lifecycle`` key; another value patches it.  ``set_lifecycle`` does not call this for a
    node that already has the value, so a file that holds an explicit ``active`` keeps its key.  Raises ``JsonUtilsError`` when the file is
    missing or the edit would introduce a schema violation; nothing is written then.
    """
    path = str(Path(spec_root) / change.file)
    key_path = f"{change.jq_path}.{LIFECYCLE_KEY}"
    if change.new == DEFAULT_LIFECYCLE:
        json_delete(path, key_path)
    else:
        json_patch(path, key_path, f'"{change.new}"', repo_root=repo_root)


def set_lifecycle(graph: Graph, spec_root: str, repo_root: str, node_id: str, value: str) -> LifecycleChange:
    """Plan and apply the change of *node_id* to *value*; returns the change.  Raises what the two steps raise.

    A node that already has *value* is not written: the file stays as it is and the change has ``old == new``.  A write
    takes the write lock of the spec folder and plans again from the graph built under it, as every other write does;
    ``LockError`` (E769) when another specdev write holds it.
    """
    change = plan_lifecycle_change(graph, node_id, value)
    if change.old == change.new:
        return change
    with with_write_lock(spec_root):
        built = build_graph(spec_root, repo_root)
        change = plan_lifecycle_change(built, node_id, value)
        if change.old != change.new:
            apply_lifecycle_change(spec_root, repo_root, change)
    return change
