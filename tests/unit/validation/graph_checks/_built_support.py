"""Small hand-built graphs for the built-state tests: nodes, the closed milestone that refines them, a lock at their current hashes."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node, SpecShape
from specdev_tools.graph.ownership import OwnerContext
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.lockfile import Lock, LockEntry
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.graph._synth import ROOT

BUILT_FIELDS = frozenset({"refines", "derives_from", "mitigated_by", "realises"})
STEP_RANKS = {"00": 0, "01": 1, "02": 2, "04": 3, "05": 4, "06": 5, "07": 6, "09": 7, "10": 8, "14": 9, "16": 10}
STALE_HASH = "sha256:" + "0" * 64
TASK_FILE, ANCHOR_FILE = "14_roadmap.json", "16_impl_context.json"


def link(source: str, field: str, target: str, *, built: bool | None = None) -> Link:
    """A link; *built* defaults to the verbs the registry declares ``built``."""
    flag = field in BUILT_FIELDS if built is None else built
    return Link(source, field, target, LinkDecl(field, (), False, flag, ()))


def node(
    node_id: str, kind: str, role: str | None = "obligation-system", *, step: str = "04", parent: str | None = None,
    children: Iterable[str] = (), scope: str | None = None, lifecycle: str = "active",
    links: Iterable[tuple[str, str]] = (), file: str = "spec.json", jq_path: str = "",
) -> Node:
    """A node; *links* are ``(field, target)`` pairs."""
    made = tuple(link(node_id, field, target) for field, target in links)
    return Node(node_id, kind, step, role, file, jq_path, parent, tuple(children), lifecycle, scope, made, node_id)


def closed_work(
    refines: Mapping[str, str], *, done: bool = True, disposition: str | None = None,
) -> tuple[list[Node], dict[str, Any]]:
    """A milestone with one task whose criteria refine as *refines* says (criterion id to target id), the anchor row and the documents.

    The anchor row says ``done`` unless *done* is false; the task carries ``disposition`` (``deferred`` or ``wont_do``) when given.
    """
    criteria = [node(cid, "task-criterion", "plan", step="14", parent="task-t", links=[("refines", target)]) for cid, target in refines.items()]
    nodes = [
        node("ms-m", "roadmap-milestone", "plan", step="14", children=["task-t"]),
        node("task-t", "task", "plan", step="14", parent="ms-m", children=list(refines), file=TASK_FILE, jq_path=".task"),
        *criteria,
        node("anchor-m", "anchor-row", "record", step="16", links=[("about", "ms-m")], file=ANCHOR_FILE, jq_path=".anchor"),
    ]
    task: dict[str, Any] = {} if disposition is None else {"disposition": {"value": disposition, "reason": "later"}}
    documents = {TASK_FILE: {"task": task}, ANCHOR_FILE: {"anchor": {"status": "done" if done else "in_progress"}}}
    return nodes, documents


def graph_of(nodes: Iterable[Node], documents: Mapping[str, Any] | None = None) -> Graph:
    graph = Graph.from_nodes(list(nodes), shape=SpecShape(step_ranks=STEP_RANKS))
    graph.documents = dict(documents or {})
    return graph


def current_lock(graph: Graph, *, stale: Iterable[str] = (), skip: Iterable[str] = ()) -> Lock:
    """A lock that holds every ``refines`` link of *graph* at the current hash of its target, except the holders in *skip* (no entry) and *stale* (an old hash)."""
    hashes = compute_all(graph, {})
    stale_ids, skipped = set(stale), set(skip)
    entries = [
        LockEntry(item.source, item.field, item.target, STALE_HASH if item.source in stale_ids else hashes[graph.canonical_id(item.target)][0], STALE_HASH)
        for holder in graph.nodes for item in holder.links
        if item.field == "refines" and item.source not in skipped
    ]
    return Lock(entries=tuple(entries))


def context_of(graph: Graph, lock: Lock | None) -> GraphCheckContext:
    return GraphCheckContext(graph=graph, lock=lock, owner_context=OwnerContext(rows=()), repo_root=str(ROOT))


def built_context(nodes: Iterable[Node], refines: Mapping[str, str] | None = None, **closed: Any) -> GraphCheckContext:
    """The context of *nodes* plus the closed work *refines* (see ``closed_work``) with a lock at the current hashes."""
    work, documents = closed_work(refines or {}, **closed)
    graph = graph_of([*nodes, *work], documents)
    return context_of(graph, current_lock(graph))
