"""Link resolver: checks every declared link of a graph (E700-E703) and runs the link hook.

Per link (design Figure 4): the target must exist (E700), be of a kind the field accepts (E701) and sit strictly
earlier in step order, or in the same step when the field declares that kind (E702).  Links that stay inside one step
are then searched for cycles (E703).  ``replaces`` and ``removes`` are history links and are not checked.  A node
whose lifecycle is ``not_applicable`` is not checked as a source.  Deprecated targets raise nothing here; the lock hook
(M5) is the one place that warns about a new link to one.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from specdev_tools.core.errors import SpecError, link_target, make_error
from specdev_tools.graph.kinds import RECORD_ROLE, LinkDecl
from specdev_tools.graph.model import UNRANKED, Graph, Link, Node, SpecShape, article
from specdev_tools.graph.ownership import step_owner

HISTORY_FIELDS = frozenset({"replaces", "removes"})
FROZEN_FIELDS = frozenset({"verified_by", "refines"})
"""The links of closed work that are not resolved against what exists now: a closed criterion keeps naming the fixture and the obligation it had, whether or not they are still in the spec."""


class ResolverHooks(Protocol):
    """The one interface the resolver offers to later layers (the lock check of M5)."""

    def on_link(self, link: Link, source: Node, target: Node) -> list[SpecError]:
        """Extra findings for a link that resolved: called once per spec link, never for a record or history link."""
        ...


class _NullHooks:
    def on_link(self, link: Link, source: Node, target: Node) -> list[SpecError]:
        return []


NULL_HOOKS: ResolverHooks = _NullHooks()


@dataclass
class _SameStepEdges:
    """Links that resolved inside one step: the edges the cycle search runs on."""

    successors: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    order: list[Node] = field(default_factory=list)

    def add(self, source: Node, target: Node, field_name: str) -> None:
        if source.id not in self.successors:
            self.order.append(source)
        self.successors.setdefault(source.id, []).append((target.id, field_name))


def _error(code: str, holder: Node, message: str, *, link: Link | None = None) -> SpecError:
    """A finding about *holder*; with *link*, also about that link (``target`` is ``<field>-><target as written>``)."""
    return make_error(
        code, message, file=holder.file, jq_path=holder.jq_path or None, owner=step_owner(holder), node_id=holder.id,
        target=link_target(link.field, link.target) if link else None,
    )


def _ordered(steps: Iterable[str], shape: SpecShape) -> list[str]:
    return sorted(steps, key=shape.step_key)


def _target_steps(link: Link, shape: SpecShape) -> set[str]:
    """The steps that declare a kind the link is for: a kind accepted only in addition (a seed beside the upstream node) is not where a missing target is looked for."""
    return {step for kind in link.decl.kinds if kind not in link.decl.additional_kinds for step in shape.kind_steps.get(kind, ())}


def _absent_steps(link: Link, shape: SpecShape) -> list[str]:
    """The steps that declare a kind the link is for, when none of them has a file in the spec; else nothing."""
    steps = _target_steps(link, shape)
    if not steps or any(shape.files_by_step.get(step) for step in steps):
        return []
    return _ordered(steps, shape)


def _unreadable_file(link: Link, graph: Graph) -> tuple[str, str] | None:
    """The first ``(step, file)`` that the builder skipped, among the files of the steps that declare a kind the link accepts."""
    skipped = {error.file for error in graph.load_errors}
    for step in _ordered(_target_steps(link, graph.shape), graph.shape):
        for path in graph.shape.files_by_step.get(step, ()):
            if path in skipped:
                return step, path
    return None


def _missing_target_error(holder: Node, link: Link, graph: Graph) -> SpecError:
    shape = graph.shape
    where = f"{holder.id} ({holder.file}), field {link.field}, target '{link.target}'"
    unreadable = _unreadable_file(link, graph)
    if unreadable is not None:
        step, path = unreadable
        return _error(
            "E700", holder,
            f"{where}: the file {path} of step {step} could not be read, so the target cannot be checked",
            link=link,
        )
    absent = _absent_steps(link, shape)
    if absent:
        return _error(
            "E700", holder,
            f"{where}: no file of step {', '.join(absent)} exists in the spec, so the target cannot be found",
            link=link,
        )
    return _error("E700", holder, f"{where}: no node has that id", link=link)


def _wrong_kind_error(holder: Node, link: Link, target: Node) -> SpecError:
    accepted = ", ".join(link.decl.kinds)
    return _error(
        "E701", holder,
        f"{holder.id}, field {link.field}, target '{target.id}' is {article(target.kind)} {target.kind}; the field accepts: {accepted}",
        link=link,
    )


def _only_additional_errors(graph: Graph, holder: Node) -> list[SpecError]:
    """E701 for each required field of *holder* whose targets all resolve to kinds the field accepts only in addition (a seed beside the upstream node, never in its place).

    A field with a target that does not resolve, or one of a kind the field refuses, is left to the finding of that link.
    """
    errors: list[SpecError] = []
    fields: dict[str, list[Link]] = {}
    for link in holder.links:
        if link.decl.required and link.decl.additional_kinds:
            fields.setdefault(link.field, []).append(link)
    for name, links in fields.items():
        decl = links[0].decl
        targets = [graph.find(link.target) for link in links]
        if any(target is None or target.kind not in decl.additional_kinds for target in targets):
            continue
        needed = ", ".join(kind for kind in decl.kinds if kind not in decl.additional_kinds)
        only = ", ".join(decl.additional_kinds)
        errors.append(_error(
            "E701", holder,
            f"{holder.id}, field {name} holds only targets of kind {only} ({', '.join(link.target for link in links)}); "
            f"the field accepts {only} in addition and needs at least one of: {needed}",
            link=links[0],
        ))
    return errors


def direction_allowed(decl: LinkDecl, holder_step: str | None, target: Node, shape: SpecShape) -> bool:
    """True when a link of *decl* from a node in *holder_step* may point at *target* as far as step order goes.

    The target is in an earlier step, or in the holder's step when the field declares the target's kind as same-step.
    A holder or target with no step, or one the step order does not rank, is not constrained.
    """
    if holder_step is None or target.step is None:
        return True
    holder_rank, target_rank = shape.rank_of(holder_step), shape.rank_of(target.step)
    if UNRANKED in (holder_rank, target_rank) or target_rank < holder_rank:
        return True
    return target_rank == holder_rank and target.kind in decl.same_step_kinds


def link_target_allowed(decl: LinkDecl, holder_step: str | None, target: Node, shape: SpecShape) -> bool:
    """True when the resolver would report neither E701 nor E702 for a link of *decl* from *holder_step* to *target*."""
    return decl.accepts(target.kind) and direction_allowed(decl, holder_step, target, shape)


def _direction_error(holder: Node, link: Link, target: Node, shape: SpecShape) -> SpecError | None:
    """E702 when the target is not earlier than the holder and the field does not allow it within one step."""
    if direction_allowed(link.decl, holder.step, target, shape):
        return None
    where = f"{holder.id} (step {holder.step}), field {link.field}, target '{target.id}' (step {target.step})"
    if shape.rank_of(target.step) > shape.rank_of(holder.step):
        return _error("E702", holder, f"{where}: the target is in a later step; a link points to an earlier step", link=link)
    return _error(
        "E702", holder,
        f"{where}: the target is in the same step and {article(target.kind)} {target.kind} is not declared as a same-step target of the field",
        link=link,
    )


def _link_errors(
    graph: Graph, holder: Node, link: Link, edges: _SameStepEdges, hooks: ResolverHooks, *, frozen: bool = False,
) -> list[SpecError]:
    target = graph.find(link.target)
    if frozen and (target is None or not link_target_allowed(link.decl, holder.step, target, graph.shape)):
        return []
    if target is None:
        return [_missing_target_error(holder, link, graph)]
    if not link.decl.accepts(target.kind):
        return [_wrong_kind_error(holder, link, target)]
    direction = _direction_error(holder, link, target, graph.shape)
    if direction is not None:
        return [direction]
    if holder.step is not None and holder.step == target.step:
        edges.add(holder, target, link.field)
    return [] if holder.role == RECORD_ROLE else hooks.on_link(link, holder, target)


class _Tarjan:
    """Tarjan's strongly connected components over ``successors``, run without recursion."""

    def __init__(self, successors: Mapping[str, Sequence[tuple[str, str]]]) -> None:
        self._successors = successors
        self._index: dict[str, int] = {}
        self._low: dict[str, int] = {}
        self._stack: list[str] = []
        self._on_stack: set[str] = set()
        self.components: list[list[str]] = []

    def run(self, order: Sequence[str]) -> list[list[str]]:
        """The components, visiting the nodes of *order* (and what they reach) once each."""
        for root in order:
            if root not in self._index:
                self._visit(root)
        return self.components

    def _open(self, node: str) -> Iterator[tuple[str, str]]:
        self._index[node] = self._low[node] = len(self._index)
        self._stack.append(node)
        self._on_stack.add(node)
        return iter(self._successors.get(node, ()))

    def _close(self, node: str) -> None:
        if self._low[node] != self._index[node]:
            return
        component: list[str] = []
        while not component or component[-1] != node:
            member = self._stack.pop()
            self._on_stack.discard(member)
            component.append(member)
        self.components.append(component)

    def _next_unvisited(self, node: str, pending: Iterator[tuple[str, str]]) -> str | None:
        """The next successor of *node* not seen yet; the ones on the stack lower *node*'s low-link on the way."""
        for follower, _field in pending:
            if follower not in self._index:
                return follower
            if follower in self._on_stack:
                self._low[node] = min(self._low[node], self._index[follower])
        return None

    def _visit(self, root: str) -> None:
        work = [(root, self._open(root))]
        while work:
            node, pending = work[-1]
            follower = self._next_unvisited(node, pending)
            if follower is not None:
                work.append((follower, self._open(follower)))
                continue
            work.pop()
            self._close(node)
            if work:
                parent = work[-1][0]
                self._low[parent] = min(self._low[parent], self._low[node])


def _cycle_errors(edges: _SameStepEdges) -> list[SpecError]:
    """One E703 per cycle among same-step links: a component of two or more nodes, or a node that links to itself.

    The edges come only from holders of the wanted steps and never leave their step, so no cycle needs a step filter here.
    """
    components = _Tarjan(edges.successors).run([node.id for node in edges.order])
    errors: list[SpecError] = []
    for component in components:
        members = set(component)
        fields = sorted({
            name for member in members for target, name in edges.successors.get(member, ()) if target in members
        })
        if len(members) == 1 and not any(
            target == component[0] for target, _name in edges.successors.get(component[0], ())
        ):
            continue
        first = next(node for node in edges.order if node.id in members)
        names = [node.id for node in edges.order if node.id in members]
        errors.append(_error(
            "E703", first,
            f"Link cycle within step {first.step}: {', '.join(names)} (field {', '.join(fields)})",
        ))
    return errors


def resolve_graph(
    graph: Graph, *, hooks: ResolverHooks = NULL_HOOKS, steps: Iterable[str] | None = None, historical: Collection[str] = frozenset(),
) -> list[SpecError]:
    """Check every link of *graph*: E700 to E703 plus whatever *hooks* report.

    With *steps*, only links held by nodes of those steps (and cycles in those steps) are reported.  *historical* is the ids
    of the nodes of closed milestones (``trace.history.historical_node_ids``): a ``verified_by`` or ``refines`` link of such a
    node that names no node, or one the field does not allow, raises nothing.  The graph check passes it; the write paths do not (they compare the findings before and after an edit).  Each finding is
    owned by the step of the node that holds the link and carries that node's id.  A node whose ``lifecycle`` is
    ``not_applicable`` is skipped as a holder; a ``replaces`` or ``removes`` link is skipped.  Nothing is raised for a
    wrong-typed value: the graph holds only what the builder could read.
    """
    wanted = None if steps is None else set(steps)
    edges = _SameStepEdges()
    errors: list[SpecError] = []
    for holder in graph.gated_nodes():
        if wanted is not None and holder.step not in wanted:
            continue
        for link in holder.links:
            if link.field not in HISTORY_FIELDS:
                errors.extend(_link_errors(graph, holder, link, edges, hooks, frozen=link.field in FROZEN_FIELDS and holder.id in historical))
        errors.extend(_only_additional_errors(graph, holder))
    errors.extend(_cycle_errors(edges))
    return errors
