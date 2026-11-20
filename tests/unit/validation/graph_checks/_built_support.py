"""Small hand-built graphs for the tests of the graph checks: nodes, a context on them, the closed milestone that refines them, a lock at their current hashes.

``node`` is the one node builder and ``context_of`` the one context builder of the folder; ``graph_of`` places each
node under its ``parent`` (containment in both directions) and ``spec`` is the context on the toolkit's real
ownership table that the checks of links and containment use.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from specdev_tools.graph.kinds import KindDecl, LinkDecl
from specdev_tools.graph.model import Graph, Link, Node, SpecShape
from specdev_tools.graph.ownership import OwnerContext
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.lockfile import Lock, LockEntry
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.graph._synth import ROOT

BUILT_FIELDS = frozenset({"refines", "derives_from", "mitigated_by", "realises"})
STEP_STEPS = ("00", "01", "02", "04", "05", "06", "07", "08", "09", "10", "14", "16")
STEP_RANKS = {step: rank for rank, step in enumerate(STEP_STEPS)}
VERIFIER_KINDS = ("fixture", "job")
PLAN_KINDS = ("task", "task-criterion", "roadmap-milestone", "anchor-row")
MILESTONE_ANCHOR_FILE = "anchors.json"
STALE_HASH = "sha256:" + "0" * 64
TASK_FILE, ANCHOR_FILE = "14_roadmap.json", "16_impl_context.json"


def link(source: str, field: str, target: str, *, built: bool | None = None) -> Link:
    """A link; *built* defaults to the verbs the registry declares ``built``."""
    flag = field in BUILT_FIELDS if built is None else built
    return Link(source, field, target, LinkDecl(field, (), False, flag, ()))


def declared(item: Node, decls: Mapping[str, KindDecl]) -> Node:
    """*item* with each link given the declaration the registry (*decls*) has for its field on its kind, so ``required`` and the accepted kinds are the real ones."""
    by_field = {declared_link.field: declared_link for declared_link in decls[item.kind].links}
    return replace(item, links=tuple(replace(held, decl=by_field.get(held.field, held.decl)) for held in item.links))


def role_of(kind: str) -> str:
    """The role a hand-built node of *kind* has unless the test says otherwise: a verifier, a plan node, or an obligation."""
    return "verifier" if kind in VERIFIER_KINDS else "plan" if kind in PLAN_KINDS else "obligation-system"


def node(
    node_id: str, kind: str, role: str | None = "", *, step: str | None = None, parent: str | None = None,
    children: Iterable[str] = (), scope: str | None = None, lifecycle: str = "active",
    links: Iterable[tuple[str, str]] = (), file: str | None = None, jq_path: str | None = None, **link_fields: list[str],
) -> Node:
    """A node; *links* are ``(field, target)`` pairs and each keyword that is a link field gives that field its target ids.

    The role is ``role_of(kind)`` unless given (``None`` is a role of its own); the step is ``14`` for a plan node and
    ``04`` for any other; the file is ``<id>.json`` and the path ``.item``.  A ``parent`` is placed by ``graph_of``.
    """
    made = tuple(link(node_id, field, target) for field, target in (*links, *((f, t) for f, targets in link_fields.items() for t in targets)))
    role = role_of(kind) if role == "" else role
    step = step if step is not None else "14" if role == "plan" else "04"
    return Node(
        node_id, kind, step, role, f"{node_id}.json" if file is None else file, ".item" if jq_path is None else jq_path,
        parent, tuple(children), lifecycle, scope, made, node_id,
    )


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


def graph_of(
    nodes: Iterable[Node], documents: Mapping[str, Any] | None = None, *, shape: SpecShape | None = None, decls: Mapping[str, KindDecl] | None = None,
) -> Graph:
    """A graph of *nodes*, each also listed as a child of its ``parent`` (the order given kept)."""
    children: dict[str, list[str]] = defaultdict(list)
    placed = list(nodes)
    for item in placed:
        if item.parent:
            children[item.parent].append(item.id)
    placed = [replace(item, children=(*item.children, *(child for child in children[item.id] if child not in item.children))) for item in placed]
    graph = Graph.from_nodes(placed, shape=shape or SpecShape(step_ranks=STEP_RANKS))
    graph.documents = dict(documents or {})
    if decls is not None:
        graph.decls = dict(decls)
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


def context_of(graph: Graph, lock: Lock | None = None, *, real_owners: bool = False) -> GraphCheckContext:
    """The context on *graph*: no ownership rows, or with *real_owners* the toolkit's own table (the owner of a finding)."""
    if real_owners:
        return GraphCheckContext.from_graph(graph, lock, str(ROOT))
    return GraphCheckContext(graph=graph, lock=lock, owner_context=OwnerContext(rows=()), repo_root=str(ROOT))


def spec(*nodes: Node, **graph_options: Any) -> GraphCheckContext:
    """A context on the real ownership table over *nodes* (see ``graph_of``) and the anchor document of ``closed_milestone``."""
    graph = graph_of(nodes, {MILESTONE_ANCHOR_FILE: {"rows": [{"status": "done"}]}}, **graph_options)
    return context_of(graph, real_owners=True)


def closed_milestone(milestone_id: str) -> list[Node]:
    """The milestone *milestone_id* and the anchor row, with status ``done``, that closes it (``spec`` holds the anchor document)."""
    anchor = node(f"anchor-{milestone_id}", "anchor-row", about=[milestone_id], file=MILESTONE_ANCHOR_FILE, jq_path=".rows[0]")
    return [node(milestone_id, "roadmap-milestone"), anchor]


def built_context(
    nodes: Iterable[Node], refines: Mapping[str, str] | None = None, *, decls: Mapping[str, KindDecl] | None = None, **closed: Any,
) -> GraphCheckContext:
    """The context of *nodes* plus the closed work *refines* (see ``closed_work``) with a lock at the current hashes; *decls* are the kind declarations the graph holds (none by default)."""
    work, documents = closed_work(refines or {}, **closed)
    graph = graph_of([*nodes, *work], documents, decls=decls)
    return context_of(graph, current_lock(graph))
