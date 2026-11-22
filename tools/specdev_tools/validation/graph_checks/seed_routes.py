"""The seed route checks (E747, E748, E749): the seed manifest routes each seed to the steps that distil it, and the graph shows the distillation.

E747: a seed listed in ``seeds[]`` that no ``step_requirements`` entry routes (owner step 00).
E748: a route ``(seed, step N)`` that no node of step N backs with a ``derives_from`` link to the seed (owner step N).  When it is the seed's only route, removing it alone would start E747, so the message says to remove the seed with it.
E749: a ``derives_from`` link to a seed that is routed to some step but not to the step of the node that holds the link (owner: the holder's step).
A seed no entry routes anywhere is E747 alone: one fault, one finding.

A record link (``about``, ``replaces``, ``removes``) is never a use of a route.  The manifest is the one the graph read
(``common/seed_manifest.json``); a route to an id that is no seed is E520 of the seed lint, and a ``step_requirements``
value that is not a list is the schema's: neither is reported here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from specdev_tools.core.constants import SEED_MANIFEST_FILE
from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.core.schema_validate import jq_path_of
from specdev_tools.core.seed_routing import resolve_seeds_for_step
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.ownership import STEP_PREFIX

from .codes import SEED_LINK_NOT_ROUTED, SEED_NOT_ROUTED, SEED_ROUTE_UNUSED
from .context import GraphCheckContext, Mode
from specdev_tools.graph.names import DERIVES_FROM
from .removal import links_clause

STEP_REQUIREMENTS = "step_requirements"
GLOBAL_SEED_ORDER = "global_seed_order"
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


def _linking_steps(ctx: GraphCheckContext) -> dict[str, list[str]]:
    """For each seed, the steps of the in-play nodes that list it in ``derives_from``, in step order."""
    steps: dict[str, set[str]] = {}
    for node in ctx.in_play_nodes():
        if node.step is not None:
            for _target, seed in _seed_links(ctx.graph, node):
                steps.setdefault(seed.id, set()).add(node.step)
    return {seed: sorted(found, key=ctx.graph.shape.step_key) for seed, found in steps.items()}


def _seed_parts(ctx: GraphCheckContext, seed: str, *, route: bool = False) -> str:
    """What removing *seed* from the manifest takes, as the text in the brackets of the advice: its ``seeds[]`` entry, its route when asked for, its ``global_seed_order`` entry when it has one, and its document."""
    order = ctx.manifest.get(GLOBAL_SEED_ORDER)
    parts = ["its seeds[] entry", *(["this route"] if route else []), *([f"its {GLOBAL_SEED_ORDER} entry"] if isinstance(order, list) and seed in order else []), "its document"]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _remove_links(ctx: GraphCheckContext, seed: str) -> str:
    """`` and the links to it (N nodes: ...)`` when some node links *seed*; ``""`` when none does."""
    clause = links_clause(ctx.graph, seed)
    return f" and the links to it {clause}" if clause else ""


def _unrouted_message(seed: str, linking: list[str], parts: str, remove_links: str) -> str:
    """E747 with the way out that clears it: route the seed where a node already lists it, or (no node does) route it and have a node list it; or remove the seed with the links to it (*remove_links*, empty when none)."""
    head = f"seed {seed} is listed in the seed manifest but no step_requirements entry routes it to a step; "
    if linking:
        steps = f"step {linking[0]}" if len(linking) == 1 else f"steps {', '.join(linking)}"
        route = f"route it to {steps} (where a node lists it in derives_from)"
    else:
        route = "route it to the step that distils it and list it in derives_from of a node of that step"
    prune = ", then run specdev attest --prune" if remove_links else ""
    return f"{head}{route}, or remove the seed ({parts}){remove_links}{prune}"


def _unrouted_seeds(ctx: GraphCheckContext, routes: Routes) -> list[SpecError]:
    routed = {seed for seeds in routes.values() for seed in seeds}
    linking = _linking_steps(ctx)
    findings = []
    for seed in sorted((node for node in ctx.graph.by_kind.get(SEED_KIND, ()) if ctx.in_play(node)), key=ctx.graph.shape.order_key):
        if seed.id in routed:
            continue
        findings.append(ctx.finding(SEED_NOT_ROUTED, seed, _unrouted_message(seed.id, linking.get(seed.id, []), _seed_parts(ctx, seed.id), _remove_links(ctx, seed.id)), file=SEED_MANIFEST_FILE))
    return findings


def _unused_message(seed: str, step: str, linkable: set[str], remove_links: str | None, parts: str) -> str:
    """E748: why the route is unused and the ways out that clear it.

    When no node of the step can link a seed (a trinity key, or a step none of whose kinds links one), distilling it
    there cannot be done: the route moves to a step that can.  *parts* is what removing the seed takes; *remove_links* is ``None`` unless this is the seed's only
    route: removing it alone would start E747, so the seed goes with it, and with the links to it (*remove_links*, empty
    when no node links the seed).
    """
    where = f"step {step}"
    can_distil = step in linkable and step not in TRINITY_KEYS
    if step in TRINITY_KEYS:
        reason = f"the trinity key {step} cannot be used: no node of the trinity steps links a seed"
    elif step not in linkable:
        reason = f"no node kind of step {step} can link a seed (only the kinds of steps {', '.join(sorted(linkable))} can)"
    else:
        reason = f"no node of {where} lists {seed} in derives_from"
    if remove_links is None:
        remove = "remove the route"
    else:
        remove = (
            f"remove the seed from the manifest ({parts}){remove_links}" + (", then run specdev attest --prune" if remove_links else "")
        )
    if can_distil:
        advice = f"distil the seed in that step (a node of {where} lists {seed} in derives_from), or {remove}"
    else:
        advice = f"move the route to a step whose nodes can link a seed ({', '.join(sorted(linkable))}) and list {seed} in derives_from of a node there, or {remove}"
    return f"the seed manifest routes {seed} to {where} but {reason}; {advice}"


def _unused_routes(ctx: GraphCheckContext, routes: Routes) -> list[SpecError]:
    used, linkable = _used_routes(ctx), _linkable_steps(ctx.graph)
    seed_nodes = {node.id: node for node in ctx.graph.by_kind.get(SEED_KIND, ())}
    findings = []
    routed_steps = Counter(seed for seeds in routes.values() for seed in set(seeds))
    for step in sorted((key for key in routes if key in ctx.graph.shape.step_ranks), key=ctx.graph.shape.step_key):
        for seed in dict.fromkeys(routes[step]):
            if seed in seed_nodes and (seed, step) not in used:
                findings.append(ctx.finding(
                    SEED_ROUTE_UNUSED, seed_nodes[seed], _unused_message(seed, step, linkable, _remove_links(ctx, seed) if routed_steps[seed] == 1 else None, _seed_parts(ctx, seed, route=True)), owner=f"{STEP_PREFIX}{step}", route=(seed, step),
                    file=SEED_MANIFEST_FILE, jq_path=jq_path_of((STEP_REQUIREMENTS, step)),
                ))
    return findings


def _links_to_unrouted_seeds(ctx: GraphCheckContext, routes: Routes) -> list[SpecError]:
    manifest = {STEP_REQUIREMENTS: routes}
    routed_anywhere = {seed for seeds in routes.values() for seed in seeds}
    findings = []
    for holder in ctx.in_play_nodes():
        if holder.step is None:
            continue
        routed = set(resolve_seeds_for_step(holder.step, manifest)[1])
        for target, seed in _seed_links(ctx.graph, holder):
            if seed.id in routed or seed.id not in routed_anywhere:
                continue
            message = f"{holder.id} derives from seed {seed.id}, which the seed manifest does not route to step {holder.step}; add {seed.id} to step_requirements[\"{holder.step}\"], or remove the link and run specdev attest --prune (a derives_from that would be left empty needs another entry)"
            findings.append(ctx.finding(SEED_LINK_NOT_ROUTED, holder, message, target=link_target(DERIVES_FROM, target), route=(seed.id, holder.step)))
    return findings


def check_seed_routes(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E747 for each in-play seed no route names, E748 for each route no node of its step uses, E749 for each in-play node with a ``derives_from`` link to a seed that is routed, but not to its step.

    E747 and E748 point at the seed manifest (E748 at the key of its step in ``step_requirements``); E749 at the holder,
    with the link as ``target``.  E748 and E749 carry ``route=(seed, step)`` for the step gate.
    """
    routes = _routes(ctx)
    return _unrouted_seeds(ctx, routes) + _unused_routes(ctx, routes) + _links_to_unrouted_seeds(ctx, routes)
