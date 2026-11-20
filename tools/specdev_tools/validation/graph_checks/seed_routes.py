"""The seed route checks (E747, E748, E749): the seed manifest routes each seed to the steps that distil it, and the graph shows the distillation.

E747: a seed listed in ``seeds[]`` that no ``step_requirements`` entry routes (owner step 00).
E748: a route ``(seed, step N)`` that no node of step N backs with a ``derives_from`` link to the seed (owner step N).
E749: a ``derives_from`` link to a seed that is not routed to the step of the node that holds the link (owner: the holder's step).

A record link (``about``, ``replaces``, ``removes``) is never a use of a route.  The manifest is the one the graph read
(``common/seed_manifest.json``); a route to an id that is no seed is E520 of the seed lint, and a ``step_requirements``
value that is not a list is the schema's: neither is reported here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.core.schema_validate import jq_path_of
from specdev_tools.core.seed_routing import resolve_seeds_for_step
from specdev_tools.graph.model import Graph, Node
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext

from .codes import SEED_LINK_NOT_ROUTED, SEED_NOT_ROUTED, SEED_ROUTE_UNUSED
from .context import GRAPH_NOT_BUILT, SEED_MANIFEST_PATH, GraphCheckContext, Mode

SEED_KIND = "seed"
DERIVES_FROM = "derives_from"
STEP_REQUIREMENTS = "step_requirements"
TRINITY_KEYS = frozenset({"16", "16a", "16b", "16c"})
Routes = dict[str, list[str]]


def _routes(ctx: GraphCheckContext) -> Routes:
    """The routes of the manifest as ``{step key: [seed ids]}``: a value that is not a list, or an entry that is not a string, is left out."""
    raw = ctx.manifest.get(STEP_REQUIREMENTS)
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): [seed for seed in value if isinstance(seed, str)]
        for key, value in raw.items()
        if isinstance(value, list)
    }


def _linkable_steps(graph: Graph) -> set[str]:
    """The steps whose kinds may link a seed through ``derives_from``, read from the registry."""
    kinds = {kind for kind, decl in graph.decls.items() if any(link.field == DERIVES_FROM and SEED_KIND in link.kinds for link in decl.links)}
    return {step for kind in kinds for step in graph.shape.kind_steps.get(kind, ())}


def _seed_links(graph: Graph, node: Node) -> list[tuple[str, Node]]:
    """The ``derives_from`` links of *node* that point at a seed, as ``(target as written, seed node)``, in link order.

    A link whose field does not accept a seed (a requirement linking one) is the resolver's wrong-kind error (E701), not a route use.
    """
    found = ((link.target, graph.find(link.target)) for link in node.links if link.field == DERIVES_FROM and link.decl.accepts(SEED_KIND))
    return [(target, seed) for target, seed in found if seed is not None and seed.kind == SEED_KIND]


def _used_routes(ctx: GraphCheckContext) -> set[tuple[str, str]]:
    """The ``(seed id, step)`` pairs some in-play node of that step backs with a ``derives_from`` link."""
    return {
        (seed.id, node.step)
        for node in ctx.in_play_nodes() if node.step is not None
        for _target, seed in _seed_links(ctx.graph, node)
    }


def _unrouted_seeds(ctx: GraphCheckContext, routes: Routes) -> list[SpecError]:
    routed = {seed for seeds in routes.values() for seed in seeds}
    findings = []
    for seed in sorted((node for node in ctx.graph.by_kind.get(SEED_KIND, ()) if ctx.in_play(node)), key=ctx.graph.shape.order_key):
        if seed.id in routed:
            continue
        message = f"seed {seed.id} is listed in the seed manifest but no step_requirements entry routes it to a step; route it to the step that distils it, or remove it"
        findings.append(replace(ctx.finding(SEED_NOT_ROUTED, seed, message), file=SEED_MANIFEST_PATH))
    return findings


def _unused_message(seed: str, step: str, linkable: set[str]) -> str:
    where = f"step {step}"
    if step in TRINITY_KEYS:
        reason = f"the trinity key {step} cannot be used: no node of the trinity steps links a seed"
    elif step not in linkable:
        reason = f"no node kind of step {step} can link a seed (only the kinds of steps {', '.join(sorted(linkable))} can)"
    else:
        reason = f"no node of {where} lists {seed} in derives_from"
    return f"the seed manifest routes {seed} to {where} but {reason}; distil the seed in that step, or remove the route"


def _unused_routes(ctx: GraphCheckContext, routes: Routes) -> list[SpecError]:
    used, linkable = _used_routes(ctx), _linkable_steps(ctx.graph)
    seed_nodes = {node.id: node for node in ctx.graph.by_kind.get(SEED_KIND, ())}
    findings = []
    for step in sorted((key for key in routes if key in ctx.graph.shape.step_ranks), key=ctx.graph.shape.step_key):
        for seed in dict.fromkeys(routes[step]):
            if seed in seed_nodes and (seed, step) not in used:
                finding = ctx.finding(SEED_ROUTE_UNUSED, seed_nodes[seed], _unused_message(seed, step, linkable), owner=f"step:{step}", route=(seed, step))
                findings.append(replace(finding, file=SEED_MANIFEST_PATH, jq_path=jq_path_of((STEP_REQUIREMENTS, step))))
    return findings


def _links_to_unrouted_seeds(ctx: GraphCheckContext, routes: Routes) -> list[SpecError]:
    manifest = {STEP_REQUIREMENTS: routes}
    findings = []
    for holder in ctx.in_play_nodes():
        if holder.step is None:
            continue
        routed = set(resolve_seeds_for_step(holder.step, manifest)[1])
        for target, seed in _seed_links(ctx.graph, holder):
            if seed.id in routed:
                continue
            message = f"{holder.id} derives from seed {seed.id}, which the seed manifest does not route to step {holder.step}; add {seed.id} to step_requirements[\"{holder.step}\"] or remove the link"
            findings.append(ctx.finding(SEED_LINK_NOT_ROUTED, holder, message, target=link_target(DERIVES_FROM, target), route=(seed.id, holder.step)))
    return findings


def check_seed_routes(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E747 for each in-play seed no route names, E748 for each route no node of its step uses, E749 for each in-play node with a ``derives_from`` link to a seed not routed to its step.

    E747 and E748 point at the seed manifest (E748 at the key of its step in ``step_requirements``); E749 at the holder,
    with the link as ``target``.  E748 and E749 carry ``route=(seed, step)`` for the step gate.
    """
    routes = _routes(ctx)
    return _unrouted_seeds(ctx, routes) + _unused_routes(ctx, routes) + _links_to_unrouted_seeds(ctx, routes)


def run_seed_routes(ctx: CheckContext) -> dict[str, Any]:
    """The registered function: the findings of ``check_seed_routes`` at merge, or a skip when no graph could be built."""
    gctx = GraphCheckContext.from_registry(ctx)
    if gctx is None:
        return check_registry.skip(GRAPH_NOT_BUILT)
    return check_registry.check_result(check_seed_routes(gctx, "merge"))
