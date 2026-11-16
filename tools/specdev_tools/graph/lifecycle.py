"""Lifecycle changes of graph nodes (``specdev node status``).

The decision (``plan_lifecycle_change``) reads only the graph; the write (``apply_lifecycle_change``) goes through
``core.json_utils``, which validates the edit against the file's own schema and writes atomically.  ``active`` is the
default, so it is written as the absence of the ``lifecycle`` key.  A lifecycle is outside the content hash, so a
change needs no lock work.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.json_utils import json_delete, json_patch
from specdev_tools.graph.kinds import SEED_KIND, has_lifecycle
from specdev_tools.graph.model import DEFAULT_LIFECYCLE, LIFECYCLES, Graph, Node

LIFECYCLE_KEY = "lifecycle"
NOT_APPLICABLE_GUIDANCE = (
    "not_applicable is for a closed milestone's historical step-14 nodes whose built target was deleted"
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


def _refuse(message: str) -> LifecycleRefusedError:
    return LifecycleRefusedError(make_error("E705", message))


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _refusal_for_node(graph: Graph, node_id: str) -> str | None:
    """Why *node_id* cannot take a lifecycle, or ``None`` when it can."""
    if node_id in graph.dups:
        return f"node id {node_id!r} is defined more than once (E704); fix the duplicate first"
    node = graph.by_id.get(node_id)
    if node is None:
        return f"no node has the id {node_id!r}"
    if node.kind == SEED_KIND:
        return f"{node_id!r} is a seed, and a seed has no lifecycle"
    if not has_lifecycle(node.kind, node.role):
        return f"{node_id!r} is {_article(node.kind)} {node.kind}, which is a record, and a record has no lifecycle"
    return None


def plan_lifecycle_change(graph: Graph, node_id: str, value: str) -> LifecycleChange:
    """The change that sets the lifecycle of *node_id* to *value*.

    Raises ``LifecycleRefusedError`` (E705) for a value outside the lifecycle enum, an unknown or duplicated id, and a
    node of role ``record`` or kind ``seed``.  Any other node accepts any lifecycle value.
    """
    if value not in LIFECYCLES:
        raise _refuse(f"lifecycle {value!r} is not one of {', '.join(LIFECYCLES)}")
    problem = _refusal_for_node(graph, node_id)
    if problem is not None:
        raise _refuse(problem)
    node: Node = graph.by_id[node_id]
    return LifecycleChange(node_id, node.lifecycle, value, node.file, node.jq_path)


def apply_lifecycle_change(spec_root: str, repo_root: str, change: LifecycleChange) -> None:
    """Write *change* into its file under *spec_root*.

    ``active`` deletes the ``lifecycle`` key; another value patches it.  Raises ``JsonUtilsError`` when the file is
    missing or the edit would introduce a schema violation; nothing is written then.
    """
    path = str(Path(spec_root) / change.file)
    key_path = f"{change.jq_path}.{LIFECYCLE_KEY}"
    if change.new == DEFAULT_LIFECYCLE:
        json_delete(path, key_path)
    else:
        json_patch(path, key_path, f'"{change.new}"', repo_root=repo_root)


def set_lifecycle(graph: Graph, spec_root: str, repo_root: str, node_id: str, value: str) -> LifecycleChange:
    """Plan and apply the change of *node_id* to *value*; returns the change.  Raises what the two steps raise."""
    change = plan_lifecycle_change(graph, node_id, value)
    apply_lifecycle_change(spec_root, repo_root, change)
    return change
