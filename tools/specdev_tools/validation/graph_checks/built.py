"""The built view of an obligation: a computed three-state result, never stored (E-034, E-057).

An obligation is BUILT when work of a closed milestone refines it at its current content (a task criterion of a
``done`` milestone whose lock entry holds the hash the obligation has now), or, for a parent, when its in-scope
children are; a coarse node is built through the obligations derived from it.  A kind whose proof is evidence (a gate,
a rule, a threat) is ``PENDING_EVIDENCE`` until a provider is registered (``register_built_provider``); ``proof.built_evidence``
supplies one for a given gate cap (``built_at_cap``), and a node whose proof waits only for a later stage is ``RELIEVED``.

``compute_built`` is a library function: no command shows it and no error is raised for "not built" here.  The close
gate reads it for the closing milestone and the release gate for every in-scope obligation; the scaffold path check
reads it for an API.  ``walk_derivations`` is the one traversal along the built verbs, shared with the milestone
coverage checks, which read no hashes.
"""
from __future__ import annotations

import enum
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Link, Node
from specdev_tools.trace.hashing import compute_all

from .context import GraphCheckContext
from .names import API, CAPABILITY, COMPONENT, CONNECTION, CONSTRAINT, CONSTRAINS, DERIVES_FROM, PROVIDED_BY, REFINES, RULE, THIRD_PARTY

OBLIGATION_ROLES = frozenset({"obligation-system", "obligation-delivery"})
EVIDENCE_KINDS = frozenset({"environment", "gate", "secret", RULE, "threat", "edge-case"})
"""Kinds proved by evidence (step 02a deliveries, step-10 rules, step-11 threats and edge cases): ``PENDING_EVIDENCE`` by default."""
COARSE_KINDS = frozenset({"scope-item", "risk", CAPABILITY})
COMPONENT_USE_FIELDS = frozenset({PROVIDED_BY, CONSTRAINS})
RELIES_ON = frozenset({"relies_on"})
PAUSED_DISPOSITIONS = frozenset({"deferred", "wont_do"})
"""``disposition.value`` of a task that is postponed or cancelled: its criteria give no coverage (DOC L684)."""
PIN_OK = "OK"
PIN_MISMATCH = "MISMATCH"


class BuiltState(str, enum.Enum):
    """The state of a node: ``IGNORED`` is for a node that takes no part (out of play, or not an obligation)."""

    BUILT = "BUILT"
    NOT_BUILT = "NOT_BUILT"
    PENDING_EVIDENCE = "PENDING_EVIDENCE"
    RELIEVED = "RELIEVED"
    IGNORED = "IGNORED"


SATISFIED = frozenset({BuiltState.BUILT, BuiltState.RELIEVED})
"""The states that count as built for an ancestor and for the node itself: a relieved node waits only for proof at a stage above the gate (DOC 5.3, \"at the tag\")."""


@dataclass(frozen=True)
class BuiltResult:
    """The state of one node, why, and the ids (refining criteria, children, derived nodes) that decided it; ``waits_for`` is the stage a ``RELIEVED`` node waits for."""

    state: BuiltState
    reason: str
    via: tuple[str, ...] = ()
    waits_for: str | None = None


BuiltProvider = Callable[["BuiltComputation", Node], BuiltResult]
"""``fn(computation, node)``: the state of *node*.  The running ``BuiltComputation`` gives the context (``computation.ctx``) and the state of any other node (``computation.result_of(other)``) through the memo and the cycle guard of the same run."""
KindPredicate = Callable[[Node], bool]


@dataclass(frozen=True)
class _Provider:
    matches: KindPredicate
    compute: BuiltProvider


_providers: tuple[_Provider, ...] = ()


def register_built_provider(kind_predicate: KindPredicate, fn: BuiltProvider) -> Callable[[], None]:
    """Decide the built state of every in-play node *kind_predicate* matches with *fn* instead of the default branches.

    Providers are consulted in registration order and the first one whose predicate matches decides (a later one that
    also matches is not asked); an out-of-play node is ``IGNORED`` before any provider is asked.  Returns the function that removes this provider; it removes only its own, in
    whatever order the restores are called, and a second call does nothing.
    """
    global _providers
    mine = _Provider(kind_predicate, fn)
    _providers = (*_providers, mine)

    def restore() -> None:
        global _providers
        _providers = tuple(provider for provider in _providers if provider is not mine)

    return restore


def inbound_sources(ctx: GraphCheckContext, node: Node, verbs: Iterable[str] | None = None) -> list[tuple[Node, Link]]:
    """The in-play nodes that link to *node*, with the link, in listing order.

    *verbs* picks the link fields to follow; ``None`` follows every field the registry declares ``built``, so a new
    built verb needs no edit here.
    """
    wanted = None if verbs is None else frozenset(verbs)
    graph = ctx.graph
    found: dict[tuple[str, str], tuple[Node, Link]] = {}
    for link in graph.incoming.get(node.id, ()):
        source = graph.by_id.get(link.source)
        followed = link.decl.built if wanted is None else link.field in wanted
        if source is not None and followed and ctx.in_play(source):
            found.setdefault((source.id, link.field), (source, link))
    return sorted(found.values(), key=lambda pair: (*ctx.graph.shape.order_key(pair[0]), pair[1].field))


def walk_derivations(ctx: GraphCheckContext, node: Node, verbs: Iterable[str]) -> list[Node]:
    """Every in-play node reached from *node* by following inbound links of *verbs*, again and again, in listing order; *node* itself is not listed.

    No hash is read and no milestone state: this is the reach of the verbs alone.
    """
    wanted = frozenset(verbs)
    reached: dict[str, Node] = {}
    pending = [node]
    while pending:
        current = pending.pop()
        for source, _link in inbound_sources(ctx, current, wanted):
            if source.id != node.id and source.id not in reached:
                reached[source.id] = source
                pending.append(source)
    return sorted(reached.values(), key=ctx.graph.shape.order_key)


def combine(members: list[tuple[str, BuiltResult]], what: str) -> BuiltResult:
    """One state for the *members* of a node (id and result of each, *what* names them in the reason): any NOT_BUILT, else any PENDING_EVIDENCE, else BUILT (a RELIEVED member counts as built); ``via`` names the members that decided it."""
    for state, text in ((BuiltState.NOT_BUILT, "is not built"), (BuiltState.PENDING_EVIDENCE, "waits for evidence")):
        deciding = tuple(sorted(member_id for member_id, result in members if result.state is state))
        if deciding:
            return BuiltResult(state, f"a {what} {text}", deciding)
    return BuiltResult(BuiltState.BUILT, f"every {what} is built", tuple(sorted(member_id for member_id, _result in members)))


class BuiltComputation:
    """One run of ``compute_built``: the memo, the derivation guard and the hashes (computed once, when first needed).

    A provider is handed the run: ``ctx`` is the context and ``result_of(node)`` the state of any node, computed once per run;
    a node reached again while it is being computed reads NOT_BUILT (a cycle ends there, not in recursion).
    """

    def __init__(self, ctx: GraphCheckContext) -> None:
        self.ctx = ctx
        self._memo: dict[str, BuiltResult] = {}
        self._active: set[str] = set()
        self._hashes: dict[str, tuple[str, str]] | None = None

    def result_of(self, node: Node) -> BuiltResult:
        """The state of *node*, computed once; a node reached again while it is being computed (a derivation cycle) reads NOT_BUILT."""
        if node.id in self._memo:
            return self._memo[node.id]
        if node.id in self._active:
            return BuiltResult(BuiltState.NOT_BUILT, "derivation cycle")
        self._active.add(node.id)
        try:
            decided = self._decide(node)
        finally:
            self._active.discard(node.id)
        self._memo[node.id] = decided
        return decided

    def _decide(self, node: Node) -> BuiltResult:
        if not self.ctx.in_play(node):
            return BuiltResult(BuiltState.IGNORED, "out of play")
        for provider in _providers:
            if provider.matches(node):
                return provider.compute(self, node)
        return self.by_default(node)

    def by_default(self, node: Node) -> BuiltResult:
        """The state of the in-play *node* by the branches of this module alone, as if no provider matched it (a provider that refines the default asks for it)."""
        if node.role not in OBLIGATION_ROLES:
            return BuiltResult(BuiltState.IGNORED, f"a {node.role or 'node'} is not built")
        if node.kind in EVIDENCE_KINDS:
            return BuiltResult(BuiltState.PENDING_EVIDENCE, f"{node.kind} is proven by evidence")
        if node.kind == CONSTRAINT:
            return self._constraint(node)
        if node.kind in COARSE_KINDS:
            return self._coarse(node)
        if node.kind == API:
            return self._refined(node) or BuiltResult(BuiltState.NOT_BUILT, "no counting refinement")
        return self._refined(node) or self._parent(node)

    # --- counting refinements ---------------------------------------------------------------------------------------

    def _refined(self, node: Node) -> BuiltResult | None:
        """BUILT through the criteria that count for *node*, or ``None`` when none does."""
        criteria = tuple(sorted(source.id for source, link in inbound_sources(self.ctx, node, (REFINES,)) if self._counts(source, link, node)))
        return BuiltResult(BuiltState.BUILT, "refined by a closed milestone at its current content", criteria) if criteria else None

    def _counts(self, criterion: Node, link: Link, target: Node) -> bool:
        if criterion.id not in self.ctx.historical or self._task_paused(criterion):
            return False
        lock = self.ctx.lock
        entry = lock.get(criterion.id, link.field, link.target) if lock is not None else None
        return entry is not None and entry.content_hash == self._content_hash(target)

    def _task_paused(self, criterion: Node) -> bool:
        task = self.ctx.graph.by_id.get(criterion.parent) if criterion.parent else None
        item = item_of(self.ctx.graph, task) if task is not None else None
        disposition = item.get("disposition") if item is not None else None
        return isinstance(disposition, dict) and disposition.get("value") in PAUSED_DISPOSITIONS

    def _content_hash(self, node: Node) -> str | None:
        if self._hashes is None:
            self._hashes = compute_all(self.ctx.graph, self.ctx.seed_texts)
        pair = self._hashes.get(node.id)
        return pair[0] if pair is not None else None

    # --- the other branches -----------------------------------------------------------------------------------------

    def _parent(self, node: Node) -> BuiltResult:
        """A parent is built when every in-scope child is; a leaf, or a parent none of whose children is in scope, needs a refinement of its own."""
        children = self._members(self.ctx.graph.by_id.get(child) for child in self.ctx.graph.children.get(node.id, ()))
        if not children:
            return BuiltResult(BuiltState.NOT_BUILT, "no counting refinement" + (" and no in-scope child" if node.children else ""))
        return combine(children, "child")

    def _coarse(self, node: Node) -> BuiltResult:
        """A coarse node is built when something is derived from it and everything derived from it is built (none: not built)."""
        derived = self._members(source for source, _link in inbound_sources(self.ctx, node))
        if not derived:
            return BuiltResult(BuiltState.NOT_BUILT, "no obligation derives from it")
        return combine(derived, "derived obligation")

    def _constraint(self, node: Node) -> BuiltResult:
        """The coarse branch, plus the components and third parties that derive from the constraint once a built obligation uses them."""
        derived = self._members(source for source, _link in inbound_sources(self.ctx, node))
        derived += self._components(node) + self._third_parties(node)
        if not derived:
            return BuiltResult(BuiltState.NOT_BUILT, "nothing derives from it that is built or waits for evidence")
        return combine(derived, "derived node")

    def _members(self, nodes: Iterable[Node | None]) -> list[tuple[str, BuiltResult]]:
        """The (id, result) of each obligation of *nodes* that takes part: an ignored or non-obligation node is left out of the count."""
        found: dict[str, BuiltResult] = {}
        for node in nodes:
            if node is not None and node.role in OBLIGATION_ROLES and node.id not in found:
                result = self.result_of(node)
                if result.state is not BuiltState.IGNORED:
                    found[node.id] = result
        return list(found.items())

    def _components(self, constraint: Node) -> list[tuple[str, BuiltResult]]:
        built = BuiltResult(BuiltState.BUILT, "used by a built obligation")
        return [
            (source.id, built) for source, _link in inbound_sources(self.ctx, constraint, (DERIVES_FROM,))
            if source.kind == COMPONENT and self._component_used(source)
        ]

    def _component_used(self, component: Node) -> bool:
        """Whether a built obligation provides, or is constrained by, the component or a connection that derives from it."""
        connections = [source for source, _link in inbound_sources(self.ctx, component, (DERIVES_FROM,)) if source.kind == CONNECTION]
        return any(self._built_users(target, COMPONENT_USE_FIELDS) for target in (component, *connections))

    def _third_parties(self, constraint: Node) -> list[tuple[str, BuiltResult]]:
        return [
            (source.id, self._pin_result(source)) for source, _link in inbound_sources(self.ctx, constraint, (DERIVES_FROM,))
            if source.kind == THIRD_PARTY and self._built_users(source, RELIES_ON)
        ]

    def _pin_result(self, third_party: Node) -> BuiltResult:
        pin = self.ctx.pin_matches(third_party)
        if pin == PIN_OK:
            return BuiltResult(BuiltState.BUILT, "relied on by a built obligation, pin matches")
        if pin == PIN_MISMATCH:
            return BuiltResult(BuiltState.NOT_BUILT, "its pin does not match")
        return BuiltResult(BuiltState.PENDING_EVIDENCE, "its pin is not known yet")

    def _built_users(self, target: Node, verbs: frozenset[str]) -> list[str]:
        """The ids of the built obligations that link to *target* through *verbs*."""
        return [
            source.id for source, _link in inbound_sources(self.ctx, target, verbs)
            if source.role in OBLIGATION_ROLES and self.result_of(source).state in SATISFIED
        ]


def compute_built(ctx: GraphCheckContext, node_id: str | None = None) -> dict[str, BuiltResult]:
    """The built state of every node that is not ``not_applicable`` (in listing order), or of *node_id* alone.

    One hash computation serves the whole run.  A node out of play, and a node that is not an obligation, is
    ``IGNORED``.  Nothing is stored.

    Raises:
        KeyError: *node_id* names no node of the graph.
    """
    run = BuiltComputation(ctx)
    graph = ctx.graph
    if node_id is not None:
        node = graph.find(node_id)
        if node is None:
            raise KeyError(node_id)
        return {node.id: run.result_of(node)}
    nodes = sorted((node for node in graph.gated_nodes() if graph.by_id.get(node.id) is node), key=graph.shape.order_key)
    return {node.id: run.result_of(node) for node in nodes}

