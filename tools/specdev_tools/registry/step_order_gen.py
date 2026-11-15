"""Derive the step order from the ``x-node`` / ``x-link`` annotations (E-008a).

``derive_step_order`` turns the link graph between kinds into a step DAG:

* a step is every step that owns at least one declared kind (``x-node.step``, else the
  numeric prefix of the schema file name; ``seed`` and other step-less kinds are not steps);
* an ``x-link`` field held by a non-``record`` kind of step H, pointing at a kind of another
  step T that is not external, gives the edge ``H -> T`` (H requires T);
* links whose ``kinds`` is ``"*"``, links held by ``record``-role kinds, and links to kinds
  without a home step create no edge;
* the order is a topological sort (inputs first), ties broken by step id string order.

``tools/step_order.json`` stays the hand file and the authority; nothing here writes into
``tools/`` unless ``registry-generate --step-order-out`` names a path.

Errors are ``AnnotationError`` with the ``ANNOT-`` prefix: ANNOT-20 (the derived step graph
has a cycle), ANNOT-21 (an ``x-link`` kind lives in the holder's own step and is not in
``same_step_kinds``).  Lint issues of the annotations themselves are raised first.
"""
from __future__ import annotations

import heapq
import itertools
import os
from dataclasses import dataclass
from typing import Any, Iterable

from specdev_tools.registry.annotation_scan import step_of_schema_file
from specdev_tools.registry.annotations import (
    AnnotationDecls,
    AnnotationError,
    LinkDecl,
    NodeDecl,
    collect_annotations,
    lint_annotations,
)

Pair = tuple[str, str]  # (holder step, target step): the holder requires the target


@dataclass(frozen=True)
class Disagreement:
    """One pair on which the derivation and the hand file differ.

    ``kind`` is ``"missing_in_hand"`` (derivation requires ``consumer`` to read ``input``;
    the hand file lacks it) or ``"extra_in_hand"`` (the hand file lists it; derivation does not
    require it).
    """

    kind: str
    consumer: str
    input: str


@dataclass(frozen=True)
class _Edge:
    holder: str
    target: str
    schema: str
    field: str
    kind: str

    def describe(self) -> str:
        if not self.schema:
            return f"{self.holder} -> {self.target} (extra edge)"
        return f"{self.holder} -> {self.target} ({self.schema} field {self.field!r} kind {self.kind!r})"


def _norm_pairs(extra_edges: Iterable[Pair]) -> list[Pair]:
    return sorted({(str(a), str(b)) for a, b in extra_edges})


def _step_of(node: Any) -> str | None:
    step = node.value.get("step") if isinstance(node.value, dict) else None
    if isinstance(step, str):
        return step
    return step_of_schema_file(os.path.basename(node.schema_file))


def _find_cycle(adj: dict[str, list[str]], scc: list[str]) -> list[str]:
    """One simple cycle inside *scc*, as ``[A, B, ..., A]``, deterministic."""
    members = set(scc)
    start = min(scc)
    path: list[str] = [start]
    on_path = {start}

    def dfs(node: str) -> list[str] | None:
        for nxt in sorted(adj.get(node, ())):
            if nxt not in members:
                continue
            if nxt == start:
                return path + [start]
            if nxt in on_path:
                continue
            path.append(nxt)
            on_path.add(nxt)
            hit = dfs(nxt)
            if hit:
                return hit
            path.pop()
            on_path.discard(nxt)
        return None

    return dfs(start) or [start, start]


def _sccs(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """Strongly connected components with more than one node (recursive Tarjan; depth is bounded by the step count)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    out: list[list[str]] = []
    counter = [0]

    def strong(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in sorted(adj.get(v, ())):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))

    for n in sorted(nodes):
        if n not in index:
            strong(n)
    return sorted(out)


def _collect_kinds(
    nodes: Iterable[NodeDecl],
) -> tuple[set[str], dict[str, set[str]], dict[str, Any]]:
    """Steps, the steps owning each kind, and each kind's role, from the ``x-node`` declarations."""
    steps: set[str] = set()
    kind_steps: dict[str, set[str]] = {}
    kind_role: dict[str, Any] = {}
    for n in nodes:
        if not isinstance(n.kind, str) or n.value.get("top_of_graph"):
            continue
        kind_role[n.kind] = n.value.get("role")
        step = _step_of(n)
        if step:
            steps.add(step)
            kind_steps.setdefault(n.kind, set()).add(step)
    return steps, kind_steps, kind_role


def _edges_for_target(
    lk: LinkDecl,
    holder: str,
    hstep: str,
    target: str,
    kind_steps: dict[str, set[str]],
    allowed_same: set[str],
    is_record: bool,
) -> tuple[list[_Edge], list[str]]:
    """Edges and ANNOT-21 issues one link field yields for one (holder step, target kind)."""
    edges: list[_Edge] = []
    same_step: list[str] = []
    for tstep in sorted(kind_steps.get(target, ())):
        if tstep == hstep:
            if target not in allowed_same:
                same_step.append(
                    f"ANNOT-21 {lk.schema_file} {lk.path}: x-link field {lk.field_name!r} "
                    f"of kind {holder!r} points at kind {target!r} of the same step "
                    f"{hstep}, which is not in same_step_kinds"
                )
        elif not is_record:  # record holders are exempt from edges only
            edges.append(_Edge(hstep, tstep, lk.schema_file, lk.field_name or "", target))
    return edges, same_step


def _edges_for_link(
    lk: LinkDecl,
    kind_steps: dict[str, set[str]],
    kind_role: dict[str, Any],
) -> tuple[list[_Edge], list[str]]:
    """Edges and ANNOT-21 issues of one ``x-link`` declaration over all its holders and targets."""
    kinds = lk.value.get("kinds")
    if kinds == "*" or not isinstance(kinds, list):
        return [], []
    allowed_same = set(lk.value.get("same_step_kinds") or [])
    edges: list[_Edge] = []
    same_step: list[str] = []
    for holder in sorted(lk.holders):
        is_record = kind_role.get(holder) == "record"
        for hstep, target in itertools.product(sorted(kind_steps.get(holder, ())), kinds):
            found, issues = _edges_for_target(
                lk, holder, hstep, target, kind_steps, allowed_same, is_record
            )
            edges.extend(found)
            same_step.extend(issues)
    return edges, same_step


def _build_edges(
    links: Iterable[LinkDecl],
    kind_steps: dict[str, set[str]],
    kind_role: dict[str, Any],
) -> tuple[dict[Pair, _Edge], list[str]]:
    """Step edges of the link graph (first declaration wins) and the ANNOT-21 issues."""
    edges: dict[Pair, _Edge] = {}
    same_step: list[str] = []
    for lk in sorted(links, key=lambda x: (x.schema_file, x.path, x.field_name or "")):
        found, issues = _edges_for_link(lk, kind_steps, kind_role)
        same_step.extend(issues)
        for e in found:
            edges.setdefault((e.holder, e.target), e)
    return edges, same_step


def _check_acyclic(steps: set[str], edges: dict[Pair, _Edge]) -> None:
    """Raise ``AnnotationError`` (ANNOT-20) naming one cycle per cyclic component."""
    adj: dict[str, list[str]] = {s: [] for s in steps}
    for h, t in edges:
        adj[h].append(t)
    cycle_issues: list[str] = []
    for scc in _sccs(sorted(steps), adj):
        cyc = _find_cycle(adj, scc)
        legs = "; ".join(edges[(a, b)].describe() for a, b in zip(cyc, cyc[1:]))
        cycle_issues.append(f"ANNOT-20 the derived step graph contains a cycle {' -> '.join(cyc)}: {legs}")
    if cycle_issues:
        raise AnnotationError(cycle_issues)


def _topo_order(steps: set[str], edges: dict[Pair, _Edge]) -> dict[str, Any]:
    """Kahn order (inputs first, smallest step id first) with each step's inputs and consumers."""
    inputs: dict[str, list[str]] = {s: sorted({t for (h, t) in edges if h == s}) for s in steps}
    consumers: dict[str, list[str]] = {s: sorted({h for (h, t) in edges if t == s}) for s in steps}
    pending = {s: len(inputs[s]) for s in steps}
    ready = [s for s, c in pending.items() if c == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        s = heapq.heappop(ready)
        order.append(s)
        for c in consumers[s]:
            pending[c] -= 1
            if pending[c] == 0:
                heapq.heappush(ready, c)
    return {
        "steps": order,
        "step_metadata": {s: {"required_spec_inputs": inputs[s]} for s in order},
        "downstream_consumers": {s: consumers[s] for s in order},
    }


def derive_from_decls(decls: AnnotationDecls, extra_edges: Iterable[Pair] = ()) -> dict[str, Any]:
    """Derive ``steps``, ``step_metadata`` and ``downstream_consumers`` from collected declarations.

    Pure: reads nothing from disk.  ``extra_edges`` are ``(holder, target)`` step pairs
    counted as required edges.  Raises ``AnnotationError`` (the annotation lint issues,
    then ANNOT-21, then ANNOT-20).
    """
    issues = lint_annotations(decls)
    if issues:
        raise AnnotationError(issues)
    steps, kind_steps, kind_role = _collect_kinds(decls.nodes)
    edges, same_step = _build_edges(decls.links, kind_steps, kind_role)
    if same_step:
        raise AnnotationError(sorted(set(same_step)))
    for h, t in _norm_pairs(extra_edges):
        steps.update((h, t))
        if h != t:
            edges.setdefault((h, t), _Edge(h, t, "", "", ""))
    _check_acyclic(steps, edges)
    return _topo_order(steps, edges)


def derive_step_order(repo_root: str, extra_edges: Iterable[Pair] = ()) -> dict[str, Any]:
    """Derive ``steps``, ``step_metadata`` and ``downstream_consumers`` from the annotations.

    ``extra_edges`` are ``(holder, target)`` step pairs counted as required edges.
    Raises ``AnnotationError`` (ANNOT-20, ANNOT-21, or the annotation lint issues).
    """
    return derive_from_decls(collect_annotations(repo_root), extra_edges)


def _input_pairs(doc: dict[str, Any]) -> set[Pair]:
    """``(step, input)`` pairs listed under ``step_metadata[*].required_spec_inputs``."""
    return {
        (step, inp)
        for step, meta in (doc.get("step_metadata") or {}).items()
        for inp in (meta or {}).get("required_spec_inputs") or []
    }


def _hand_pairs(hand: dict[str, Any]) -> set[Pair]:
    """Pairs of the hand file: its inputs plus the reverse of ``downstream_consumers``."""
    reverse = {
        (c, producer)
        for producer, consumers in (hand.get("downstream_consumers") or {}).items()
        for c in consumers or []
    }
    return _input_pairs(hand) | reverse


def diff_against_hand(
    generated: dict[str, Any],
    hand: dict[str, Any],
    extra_edges: Iterable[Pair] = (),
) -> list[Disagreement]:
    """Pairs the derivation requires and the hand file lacks, and the reverse.

    Pairs named in ``extra_edges`` count as required and are never reported.
    Result is sorted by (kind, consumer, input).
    """
    extras = set(_norm_pairs(extra_edges))
    gen = _input_pairs(generated) | extras
    old = _hand_pairs(hand)
    out = [Disagreement("missing_in_hand", c, i) for c, i in gen - old - extras]
    out += [Disagreement("extra_in_hand", c, i) for c, i in old - gen]
    return sorted(out, key=lambda d: (d.kind, d.consumer, d.input))


def build_step_order_document(derived: dict[str, Any], hand: dict[str, Any]) -> dict[str, Any]:
    """The derived structure plus ``version``, ``policy`` and ``coverage_thresholds`` from the hand file."""
    return {
        "version": hand["version"],
        "policy": hand["policy"],
        "steps": derived["steps"],
        "coverage_thresholds": hand["coverage_thresholds"],
        "step_metadata": derived["step_metadata"],
        "downstream_consumers": derived["downstream_consumers"],
    }
