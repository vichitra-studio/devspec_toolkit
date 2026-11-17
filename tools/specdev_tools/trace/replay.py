"""Replay: what is still to be re-read after an upstream change, grouped by owning step in waterfall order.

A replay holds two kinds of item: the suspect links (``trace.suspects``; links held by historical nodes are outside
replay) and the coverage gaps the registered providers report (``trace.gaps``).  Within a step the nodes that hold
suspect links are listed upward first, a node after the nodes of its own step it links to, which is the order in which
``attest`` can succeed.  ``--diff`` adds, per root of a change, the text the changed node had when the lock entry was
written (``trace.history``).
"""
from __future__ import annotations

import difflib
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from specdev_tools.graph.model import Graph
from specdev_tools.trace.gaps import CoverageGap, coverage_gaps
from specdev_tools.trace.history import NOTE_NO_EARLIER, OldTextResolver, contract_lines
from specdev_tools.trace.lockfile import Lock, LockEntry
from specdev_tools.trace.suspects import SuspectLink, find_suspects

NOTE_SAME_TEXT = "its own contract text is unchanged; something above it or folded into it changed"
NO_STEP_LABEL = "(no step)"


@dataclass(frozen=True)
class ReplayNode:
    """A node that holds suspect links, with those links in lock order."""

    node: str
    links: tuple[SuspectLink, ...]


@dataclass(frozen=True)
class ReplayStep:
    """The replay items owned by one step: the nodes with suspect links, upward first, and the coverage gaps."""

    step: str | None
    nodes: tuple[ReplayNode, ...]
    coverage_gaps: tuple[CoverageGap, ...]

    @property
    def link_count(self) -> int:
        """Number of suspect links the step holds."""
        return sum(len(node.links) for node in self.nodes)


@dataclass(frozen=True)
class ReplayPlan:
    """The pending replay, one ``ReplayStep`` per step that has an item, in waterfall order."""

    steps: tuple[ReplayStep, ...]

    @property
    def node_count(self) -> int:
        """Number of nodes that hold suspect links."""
        return sum(len(step.nodes) for step in self.steps)

    @property
    def link_count(self) -> int:
        """Number of suspect links in the plan."""
        return sum(step.link_count for step in self.steps)

    @property
    def gap_count(self) -> int:
        """Number of coverage gaps in the plan."""
        return sum(len(step.coverage_gaps) for step in self.steps)


@dataclass(frozen=True)
class RootDiff:
    """The change of one root: the unified diff of its contract text, or the ``note`` that says why there is none."""

    root: str
    note: str | None
    diff: tuple[str, ...] = ()


def _upward_first(graph: Graph, holders: Collection[str]) -> list[str]:
    """*holders* ordered so that a node follows the holders of its own step that it links to, ties by id."""
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        node = graph.by_id[node_id]
        for link in node.links:
            target = graph.find(link.target)
            if target is not None and target.step == node.step:
                visit(target.id)
        if node_id in holders:
            ordered.append(node_id)

    for holder in sorted(holders):
        visit(holder)
    return ordered


def _replay_step(graph: Graph, step: str | None, suspects: list[SuspectLink], gaps: list[CoverageGap]) -> ReplayStep:
    by_holder: dict[str, list[SuspectLink]] = {}
    for suspect in suspects:
        by_holder.setdefault(suspect.holder, []).append(suspect)
    nodes = tuple(ReplayNode(holder, tuple(by_holder[holder])) for holder in _upward_first(graph, by_holder))
    return ReplayStep(step, nodes, tuple(sorted(gaps, key=lambda gap: (gap.code, gap.node))))


def compute_replay(graph: Graph, lock: Lock, seed_texts: Mapping[str, str]) -> ReplayPlan:
    """The pending replay of *graph* against *lock*, grouped by owning step in the step order of ``graph.shape``.

    *seed_texts* is what ``graph.gitview.read_seed_texts`` returns for the host.  A step with no suspect and no gap has
    no entry; a suspect belongs to the step of its holder, a gap to its ``owner_step``.
    """
    suspects: dict[str | None, list[SuspectLink]] = {}
    for suspect in find_suspects(graph, lock, seed_texts):
        suspects.setdefault(suspect.holder_step, []).append(suspect)
    gaps: dict[str | None, list[CoverageGap]] = {}
    for gap in coverage_gaps(graph, lock):
        gaps.setdefault(gap.owner_step, []).append(gap)
    steps = sorted({*suspects, *gaps}, key=graph.shape.step_key)
    return ReplayPlan(tuple(_replay_step(graph, step, suspects.get(step, []), gaps.get(step, [])) for step in steps))


def pending_replay(plan: ReplayPlan, steps: Collection[str]) -> tuple[ReplayStep, ...]:
    """The part of *plan* that belongs to *steps*, in plan order."""
    return tuple(step for step in plan.steps if step.step in steps)


def _roots(plan: ReplayPlan) -> list[str]:
    """The roots named by the suspect links of *plan*, in order of first appearance."""
    found: dict[str, None] = {}
    for step in plan.steps:
        for node in step.nodes:
            for link in node.links:
                found.update(dict.fromkeys(link.roots))
    return list(found)


def _entries_by_root(graph: Graph, lock: Lock, roots: Collection[str]) -> dict[str, LockEntry]:
    """For each of *roots* the first lock entry (in lock order) whose target is that node, aliases resolved."""
    found: dict[str, LockEntry] = {}
    for entry in lock.entries:
        target = graph.find(entry.target)
        if target is not None and target.id in roots:
            found.setdefault(target.id, entry)
    return found


def root_diffs(
    graph: Graph, lock: Lock, plan: ReplayPlan, seed_texts: Mapping[str, str], resolver: OldTextResolver
) -> list[RootDiff]:
    """One ``RootDiff`` per root named in *plan*, in order of first appearance.

    The old text of a root is what *resolver* recovers for the lock entry that targets it; the new text is the root as
    it is in *graph*.  A root with no old text carries the resolver's note.
    """
    roots = _roots(plan)
    entries = _entries_by_root(graph, lock, roots)
    diffs: list[RootDiff] = []
    for root in roots:
        node, entry = graph.by_id[root], entries.get(root)
        old = resolver.old_text(entry) if entry is not None else None
        if old is None or old.lines is None:
            diffs.append(RootDiff(root, old.note if old is not None else NOTE_NO_EARLIER))
            continue
        lines = tuple(difflib.unified_diff(old.lines, contract_lines(node, graph, seed_texts), "old", "new", lineterm="", n=1))
        diffs.append(RootDiff(root, None if lines else NOTE_SAME_TEXT, lines))
    return diffs


# --- output ---------------------------------------------------------------------------------------------------------

def _step_label(step: str | None) -> str:
    return NO_STEP_LABEL if step is None else step


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _suspect_text(link: SuspectLink) -> str:
    roots = f", roots: {', '.join(link.roots)}" if link.roots else ""
    return f"    {link.field} -> {link.target} ({link.cause}{roots})"


def _step_text(step: ReplayStep) -> list[str]:
    lines = [f"step {_step_label(step.step)}: {_plural(len(step.nodes), 'suspect node')}, {_plural(step.link_count, 'suspect link')}, {_plural(len(step.coverage_gaps), 'coverage gap')}"]
    for node in step.nodes:
        lines.append(f"  {node.node}")
        lines.extend(_suspect_text(link) for link in node.links)
    lines.extend(f"  coverage gap {gap.code}: {gap.node}" for gap in step.coverage_gaps)
    return lines


def diff_lines(diff: RootDiff) -> list[str]:
    body = [f"  {line}" for line in diff.diff] if diff.diff else [f"  ({diff.note})"]
    return [f"changed above: {diff.root}", *body]


def render_text(plan: ReplayPlan, diffs: Sequence[RootDiff] | None = None) -> str:
    """The plan as text: one block per step, the diffs of the roots when given, and the closing totals."""
    if not plan.steps:
        return "stale: no pending replay"
    lines = ["stale: pending replay by step"]
    for step in plan.steps:
        lines.extend(_step_text(step))
    for diff in diffs or ():
        lines.extend(diff_lines(diff))
    lines.append(f"total: {_plural(plan.link_count, 'suspect link')} in {_plural(plan.node_count, 'node')}, {_plural(plan.gap_count, 'coverage gap')}")
    return "\n".join(lines)


def _link_dict(link: SuspectLink) -> dict[str, Any]:
    return {"field": link.field, "target": link.target, "cause": link.cause, "roots": list(link.roots)}


def _step_dict(step: ReplayStep) -> dict[str, Any]:
    return {
        "step": step.step,
        "suspect_nodes": [{"node": node.node, "links": [_link_dict(link) for link in node.links]} for node in step.nodes],
        "coverage_gaps": [{"code": gap.code, "node": gap.node, "owner_step": gap.owner_step} for gap in step.coverage_gaps],
    }


def plan_to_dict(plan: ReplayPlan, diffs: Sequence[RootDiff] | None = None) -> dict[str, Any]:
    """The plan as a JSON-able dict: ``steps`` and ``totals``, plus ``diffs`` (one ``{root, note, diff}`` per root) when given."""
    document: dict[str, Any] = {
        "steps": [_step_dict(step) for step in plan.steps],
        "totals": {"suspect_nodes": plan.node_count, "suspect_links": plan.link_count, "coverage_gaps": plan.gap_count},
    }
    if diffs is not None:
        document["diffs"] = [{"root": diff.root, "note": diff.note, "diff": list(diff.diff)} for diff in diffs]
    return document
