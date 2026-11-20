"""The no-dangling check (E740): an in-play node of an obligation or context kind that nothing downstream uses.

What counts as a use is data, not code (``use_table``): a node is used when a holder that is not out of scope links to
it through one of the (holder kind, verb) pairs of its kind, or when a node it contains is used (the container rule).
Records, plan nodes, verifiers (their use rule is E742), terms (used by label, E741) and scaffold rows (step 15's
path check, E746) are not checked here.  A holder with scope ``later`` counts; a ``not_applicable`` or ``scope: out``
holder does not.  The computed link of a 09 milestone is not read: a 09 milestone is a plan node and is exempt.
"""
from __future__ import annotations

from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.model import NOT_APPLICABLE, Node
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext

from .codes import NODE_DANGLING
from .context import GRAPH_NOT_BUILT, GraphCheckContext, Mode
from .use_table import VERIFIER_ROLE, Use, use_pairs

CHECKED_ROLES = frozenset({"obligation-system", "obligation-delivery", "context"})
SCAFFOLD_ROW = "scaffold-row"
SCOPE_OUT = "out"
MAX_LISTED_USES = 5
"""How many ways to use a kind a message names before it says how many more there are."""


def _counts_as_holder(ctx: GraphCheckContext, holder: Node) -> bool:
    """Whether a link held by *holder* can be a use: it is not ``not_applicable``, not ``scope: out`` (``later`` counts) and not a verifier whose bindings are all retired."""
    if holder.lifecycle == NOT_APPLICABLE or holder.scope == SCOPE_OUT:
        return False
    return not (holder.role == VERIFIER_ROLE and ctx.retired_bindings(holder))


def _used_by_a_link(ctx: GraphCheckContext, node: Node, pairs: frozenset[Use]) -> bool:
    """Whether a stored link into *node* is one of *pairs*, held by a holder that counts."""
    for link in ctx.graph.incoming.get(node.id, ()):
        holder = ctx.graph.by_id.get(link.source)
        if holder is not None and Use(holder.kind, link.field) in pairs and _counts_as_holder(ctx, holder):
            return True
    return False


class _UseSearch:
    """Whether a node is used, directly or through a node it contains; remembers each answer of one run."""

    def __init__(self, ctx: GraphCheckContext) -> None:
        self._ctx = ctx
        self._pairs: dict[str, frozenset[Use]] = {}
        self._answers: dict[str, bool] = {}

    def is_used(self, node: Node) -> bool:
        """The container rule is read through children that are in play; a contained node already being visited counts as unused, so a containment cycle ends."""
        if node.id in self._answers:
            return self._answers[node.id]
        self._answers[node.id] = False
        used = _used_by_a_link(self._ctx, node, self.pairs(node.kind)) or any(
            self._is_used_child(child) for child in self._ctx.graph.children.get(node.id, ())
        )
        self._answers[node.id] = used
        return used

    def pairs(self, kind: str) -> frozenset[Use]:
        """``use_pairs`` of *kind*, computed once per kind."""
        if kind not in self._pairs:
            self._pairs[kind] = use_pairs(kind, self._ctx.graph.decls)
        return self._pairs[kind]

    def _is_used_child(self, child_id: str) -> bool:
        child = self._ctx.graph.by_id.get(child_id)
        return child is not None and self._ctx.in_play(child) and self.is_used(child)


def _what_would_use(ctx: GraphCheckContext, pairs: frozenset[Use]) -> str:
    """The ways to use a kind as text, ``<holder kind> <verb> (step <step>)`` in step order, at most ``MAX_LISTED_USES``."""
    shape = ctx.graph.shape
    ways: list[tuple[tuple[int, str], str, str]] = []
    for use in pairs:
        steps = shape.kind_steps.get(use.holder_kind, ())
        if steps:
            ways.append((shape.step_key(max(steps, key=shape.step_key)), use.holder_kind, use.verb))
    listed = [f"{kind} {verb} (step {key[1]})" for key, kind, verb in sorted(ways)[:MAX_LISTED_USES]]
    more = len(ways) - len(listed)
    return ", ".join(listed) + (f" and {more} more" if more > 0 else "")


def _is_checked(node: Node, search: _UseSearch) -> bool:
    return node.role in CHECKED_ROLES and node.kind != SCAFFOLD_ROW and bool(search.pairs(node.kind))


def check_no_dangling(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E740 for each in-play node of a checked role that no holder uses and none of whose contained nodes is used, in step then id order.

    The owner is the furthest step that can use the kind (the ownership table); ``mode`` is not read, the rule is the
    same at merge, close and release.
    """
    search = _UseSearch(ctx)
    findings: list[SpecError] = []
    for node in ctx.in_play_nodes():
        if _is_checked(node, search) and not search.is_used(node):
            message = (
                f"{node.kind} {node.id} is not used by any node; a node of this kind is used by {_what_would_use(ctx, search.pairs(node.kind))}: "
                f"link it, schedule it, or set scope later or out"
            )
            findings.append(ctx.finding(NODE_DANGLING, node, message))
    return findings


def run_no_dangling(ctx: CheckContext) -> dict[str, Any]:
    """The registered function: E740 findings of ``check_no_dangling`` at merge, or a skip when no graph could be built."""
    gctx = GraphCheckContext.from_registry(ctx)
    if gctx is None:
        return check_registry.skip(GRAPH_NOT_BUILT)
    return check_registry.check_result(check_no_dangling(gctx, "merge"))
