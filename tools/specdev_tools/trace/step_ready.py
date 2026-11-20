"""``specdev step ready NN``: may step NN start, or is something above it still to be replayed?

A step is ready when every step above it is present and none of the steps its nodes link to has pending replay.
Present: a ``spec/MM_*.json`` file exists, for each step MM that NN's nodes link to and each step in
``step_metadata[NN].required_spec_inputs`` of ``tools/step_order.json`` (hand-kept, and it under-declares real inputs,
so it adds to the presence check and nothing else).  Pending replay is looked for in the steps NN links to, read from
the lock links its nodes hold: a suspect link, or a coverage gap, owned by one of those steps blocks.  NN's own step is
never checked: its suspects and gaps are NN's own replay work.
"""
from __future__ import annotations

import os
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.step_order import load_step_order
from specdev_tools.core.step_paths import STEP_JSON_RE
from specdev_tools.graph.kinds import SEED_STEP
from specdev_tools.graph.model import Graph
from specdev_tools.graph.queries import plural
from specdev_tools.trace import replay
from specdev_tools.trace.suspects import lock_links

REASON_MISSING = "missing"
REASON_SUSPECT = "suspect"
REASON_GAP = "gap"


@dataclass(frozen=True)
class Blocker:
    """One thing that keeps a step from being ready, owned by the upstream step *step*.

    ``reason`` is ``missing`` (the step has no spec file), ``suspect`` (the link ``node.field -> target`` changed
    after it was accepted; ``cause`` and ``roots`` say what changed) or ``gap`` (the coverage gap ``code`` of ``node``).
    """

    step: str
    reason: str
    node: str | None = None
    field: str | None = None
    target: str | None = None
    cause: str | None = None
    roots: tuple[str, ...] = ()
    code: str | None = None


@dataclass(frozen=True)
class Readiness:
    """The verdict on step *step*: the upstream steps checked, in waterfall order, and the blockers, sorted by step then node."""

    step: str
    upstream: tuple[str, ...]
    blockers: tuple[Blocker, ...]

    @property
    def ready(self) -> bool:
        """True when nothing blocks."""
        return not self.blockers

    @property
    def replay_first(self) -> str | None:
        """The upstream step to deal with first (the earliest in the waterfall that has a blocker), or ``None`` when ready."""
        return self.blockers[0].step if self.blockers else None


def first_clause(readiness: Readiness) -> str:
    """What to do first, worded by the blockers of the first step: ``write step NN first`` for a missing file; ``replay step NN first`` for suspect links; ``fix the coverage gaps of step NN first`` when there are only coverage gaps (no replay or attest clears a gap); ``replay step NN first and fix its coverage gaps`` for both."""
    step = readiness.replay_first
    reasons = {blocker.reason for blocker in readiness.blockers if blocker.step == step}
    if readiness.blockers and readiness.blockers[0].reason == REASON_MISSING:
        return f"write step {step} first"
    if reasons == {REASON_GAP}:
        return f"fix the coverage gaps of step {step} first"
    return f"replay step {step} first and fix its coverage gaps" if REASON_GAP in reasons else f"replay step {step} first"


def link_steps(graph: Graph, step: str) -> tuple[str, ...]:
    """The steps, in waterfall order, of the targets of the lock links the nodes of *step* hold; not *step* itself and not the seeds."""
    found: set[str] = set()
    for item in lock_links(graph):
        target_step = item.target.step
        if item.holder.step == step and target_step is not None and target_step not in (step, SEED_STEP):
            found.add(target_step)
    return tuple(sorted(found, key=graph.shape.step_key))


def _replay_blockers(item: replay.ReplayStep) -> list[Blocker]:
    step = item.step or ""
    suspects = [
        Blocker(step, REASON_SUSPECT, node.node, link.field, link.target, link.cause, tuple(link.roots))
        for node in item.nodes
        for link in node.links
    ]
    gaps = [Blocker(step, REASON_GAP, gap.node, code=gap.code) for gap in item.coverage_gaps]
    return [*suspects, *gaps]




def required_spec_inputs(repo_root: str, step: str) -> list[str]:
    """The ``required_spec_inputs`` of *step* in ``tools/step_order.json`` under *repo_root* (none when it has no entry)."""
    return load_step_order(repo_root).get("step_metadata", {}).get(step, {}).get("required_spec_inputs", [])


def present_steps(graph: Graph, spec_root: str) -> frozenset[str]:
    """The steps that have a spec file: a file the registry assigns to a step, or ``<step>_*.json`` in *spec_root*."""
    found = {step for step, files in graph.shape.files_by_step.items() if files}
    found.update(match.group(1) for name in os.listdir(spec_root) if (match := STEP_JSON_RE.match(name)))
    return frozenset(found)


def check_ready(
    graph: Graph,
    plan: replay.ReplayPlan,
    step: str,
    required_inputs: Collection[str],
    present: Collection[str],
) -> Readiness:
    """Whether *step* is ready, given the replay *plan* of the spec, the step's ``required_spec_inputs`` and the steps that
    have a spec file (*present*, see ``present_steps``).

    The blockers are sorted by the waterfall order of their step, then node, field, target and code.
    """
    linked = link_steps(graph, step)
    upstream = tuple(sorted({*linked, *required_inputs}, key=graph.shape.step_key))
    blockers = [Blocker(name, REASON_MISSING) for name in upstream if name not in present]
    for item in replay.pending_replay(plan, linked):
        blockers.extend(_replay_blockers(item))
    blockers.sort(key=lambda b: (graph.shape.step_key(b.step), b.node or "", b.field or "", b.target or "", b.code or ""))
    return Readiness(step, upstream, tuple(blockers))


# --- output ---------------------------------------------------------------------------------------------------------

def _blocker_line(blocker: Blocker) -> str:
    if blocker.reason == REASON_MISSING:
        return f"  step {blocker.step}: no spec file yet"
    if blocker.reason == REASON_GAP:
        return f"  step {blocker.step}: coverage gap {blocker.code}: {blocker.node}"
    roots = f", roots: {', '.join(blocker.roots)}" if blocker.roots else ""
    return f"  step {blocker.step}: {blocker.node}.{blocker.field} -> {blocker.target} ({blocker.cause}{roots})"


def render_text(readiness: Readiness) -> str:
    """The verdict as text: ``ready``, or the blockers one per line and the step to replay first."""
    if readiness.ready:
        return f"step {readiness.step}: ready"
    lines = [f"step {readiness.step}: not ready, {plural(len(readiness.blockers), 'blocker')}"]
    lines.extend(_blocker_line(blocker) for blocker in readiness.blockers)
    lines.append(first_clause(readiness))
    return "\n".join(lines)


def to_dict(readiness: Readiness) -> dict[str, Any]:
    """The verdict as a JSON-able dict: ``step``, ``ready``, ``upstream``, ``replay_first`` and ``blockers``."""
    return {
        "step": readiness.step,
        "ready": readiness.ready,
        "upstream": list(readiness.upstream),
        "replay_first": readiness.replay_first,
        "blockers": [
            {
                "step": b.step, "reason": b.reason, "node": b.node, "field": b.field, "target": b.target,
                "cause": b.cause, "roots": list(b.roots), "code": b.code,
            }
            for b in readiness.blockers
        ],
    }


def not_ready_error(readiness: Readiness) -> SpecError:
    """The E773 finding of a step that is not ready; the message names each step with blockers and the step to replay first."""
    per_step: dict[str, int] = {}
    for blocker in readiness.blockers:
        per_step[blocker.step] = per_step.get(blocker.step, 0) + 1
    steps = "; ".join(f"step {name} ({plural(count, 'blocker')})" for name, count in per_step.items())
    return make_error("E773", f"step {readiness.step} is not ready: {steps}; {first_clause(readiness)}")

