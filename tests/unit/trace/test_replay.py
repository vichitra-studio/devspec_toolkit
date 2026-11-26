"""The replay engine and the gap seam (WI-M5-05), on the worked example."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.model import Graph
from specdev_tools.trace.gaps import CoverageGap, coverage_gaps, register_gap_provider
from specdev_tools.trace.history import NOTE_BASELINE, OldText, contract_lines
from specdev_tools.trace.lockfile import Lock, LockEntry
from specdev_tools.trace.replay import (
    NOTE_SAME_TEXT,
    ReplayPlan,
    ReplayStep,
    compute_replay,
    pending_replay,
    plan_to_dict,
    render_text,
    root_diffs,
)

from unit.graph._synth import run_python_seeded

from ._lock_support import EXAMPLE_HOST, ROOT, gap_providers  # noqa: F401  (gap_providers is a fixture)
from ._suspects_support import CLOSED_HOLDERS, CLOSURE_OF_CRITERION_EDIT, CRITERION, Example

TERM = "quokka"
UNRELATED_NODE = "cap-account-recovery"
NEED = "need-fewer-reset-tickets"
METRIC = "metric-recovery-time"


@pytest.fixture
def example(tmp_path: Path, gap_providers: Any) -> Example:
    """The worked example in a copy.  No coverage-gap provider is registered (the ``gap_providers`` fixture clears them): the
    role gaps the real graph checks report on this partial example are not the subject of these tests."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    return Example(host)


def _plan(example: Example) -> ReplayPlan:
    graph = example.graph()
    return compute_replay(graph, example.lock(), example.seed_texts(graph))


def _holders(plan: ReplayPlan) -> set[str]:
    return {node.node for step in plan.steps for node in step.nodes}


def _step(plan: ReplayPlan, name: str) -> ReplayStep:
    return next(step for step in plan.steps if step.step == name)


def _add_term(item: dict[str, object]) -> None:
    item["text"] = f"{item['text']} {TERM}"


# --- gap seam -------------------------------------------------------------------------------------------------------

def test_default_provider_empty() -> None:
    """The real default, in a process of its own (the ``gap_providers`` fixture would hide it): with only ``trace`` imported there are no role gaps on the worked example."""
    code = (
        "import sys; from specdev_tools.graph.build import build_graph; from specdev_tools.trace.gaps import coverage_gaps; "
        "from specdev_tools.trace.lockfile import Lock; "
        f"graph = build_graph({str(EXAMPLE_HOST / 'spec')!r}, {str(ROOT)!r}); "
        "print(len(coverage_gaps(graph, Lock())), 'specdev_tools.validation.graph_checks' in sys.modules)"
    )
    assert run_python_seeded(0, code).split() == ["0", "False"]


def test_coverage_gaps_adapter_returns_registered_provider_output(example: Example, gap_providers: Any) -> None:
    first, second = CoverageGap("E740", "fr-a", "04"), CoverageGap("E742", "fix-b", "08")
    gap_providers(lambda graph, lock: [first])
    gap_providers(lambda graph, lock: [second, first])
    assert coverage_gaps(example.graph(), example.lock()) == [first, second, first]


def test_an_unregistered_provider_is_no_longer_asked(example: Example) -> None:
    remove = register_gap_provider(lambda graph, lock: [CoverageGap("E740", "fr-a", "04")])
    assert len(coverage_gaps(example.graph(), example.lock())) == 1
    remove()
    assert coverage_gaps(example.graph(), example.lock()) == []


# --- compute_replay -------------------------------------------------------------------------------------------------

def test_a_clean_example_has_an_empty_plan(example: Example) -> None:
    plan = _plan(example)
    assert plan.steps == () and (plan.node_count, plan.link_count, plan.gap_count) == (0, 0, 0)
    assert render_text(plan) == "stale: no pending replay"


def test_plan_holds_the_suspect_links_grouped_by_holder_step_in_step_order(example: Example) -> None:
    example.edit_item(CRITERION, _add_term)
    plan = _plan(example)
    assert [step.step for step in plan.steps] == ["05", "06", "07", "08", "09", "11", "14", "15", "16a"]
    assert {link.key for step in plan.steps for node in step.nodes for link in node.links} == CLOSURE_OF_CRITERION_EDIT
    assert (plan.node_count, plan.link_count) == (13, 24)
    assert all(link.holder_step == step.step for step in plan.steps for node in step.nodes for link in node.links)


def test_wording_independent_impact(example: Example) -> None:
    """Impact follows links: a node whose text never says the term is a suspect, a node whose text says it but has no link is not."""
    example.edit_item(CRITERION, _add_term)
    graph = example.graph()
    downstream = _holders(compute_replay(graph, example.lock(), example.seed_texts(graph)))
    assert "api-password-reset-confirm" in downstream
    assert TERM not in " ".join(contract_lines(graph.by_id["api-password-reset-confirm"], graph, {}))
    assert TERM in " ".join(contract_lines(graph.by_id[CRITERION], graph, {}))
    example.attest(*downstream)
    example.edit_item(UNRELATED_NODE, lambda item: item.update(description=f"{item['description']} {TERM}"))
    graph = example.graph()
    assert TERM in " ".join(contract_lines(graph.by_id[UNRELATED_NODE], graph, {}))
    assert UNRELATED_NODE not in _holders(compute_replay(graph, example.lock(), example.seed_texts(graph)))


def test_historical_links_not_in_replay(example: Example) -> None:
    example.close_milestone()
    example.edit_item(CRITERION, _add_term)
    plan = _plan(example)
    assert not CLOSED_HOLDERS & _holders(plan)
    assert "16a" not in {step.step for step in plan.steps}
    assert {link.key for step in plan.steps for node in step.nodes for link in node.links} == {
        key for key in CLOSURE_OF_CRITERION_EDIT if key[0] not in CLOSED_HOLDERS
    }


def test_nodes_of_a_step_are_listed_upward_first(example: Example) -> None:
    """``metric-recovery-time`` links ``need-fewer-reset-tickets`` of its own step, so it comes after it though its id sorts first."""
    example.edit_seed()
    nodes = [node.node for node in _step(_plan(example), "00").nodes]
    assert METRIC < NEED
    assert nodes.index(NEED) < nodes.index(METRIC)
    assert nodes.index("asm-member-controls-email") < nodes.index("risk-reset-link-takeover")


def test_gaps_are_a_group_of_their_own_in_the_step_that_owns_them(example: Example, gap_providers: Any) -> None:
    example.edit_item(CRITERION, _add_term)
    gap_providers(lambda graph, lock: [CoverageGap("E742", "z-node", "05"), CoverageGap("E740", "b-node", "05"), CoverageGap("E740", "a-node", "03")])
    plan = _plan(example)
    assert [step.step for step in plan.steps][:3] == ["03", "05", "06"]
    assert _step(plan, "03").nodes == ()
    assert [(gap.code, gap.node) for gap in _step(plan, "05").coverage_gaps] == [("E740", "b-node"), ("E742", "z-node")]
    assert _step(plan, "05").nodes
    assert plan.gap_count == 3
    assert plan_to_dict(plan)["totals"] == {"suspect_nodes": 13, "suspect_links": 24, "coverage_gaps": 3}


def test_pending_replay_keeps_the_requested_steps_in_plan_order(example: Example) -> None:
    example.edit_item(CRITERION, _add_term)
    plan = _plan(example)
    assert [step.step for step in pending_replay(plan, {"11", "06", "99"})] == ["06", "11"]
    assert pending_replay(plan, []) == ()


# --- root_diffs -----------------------------------------------------------------------------------------------------

class _FixedResolver:
    """Stands in for ``OldTextResolver``: the same answer for every entry."""

    def __init__(self, answer: OldText) -> None:
        self._answer = answer

    def old_text(self, entry: LockEntry) -> OldText:
        return self._answer


def _diffs(example: Example, answer: OldText) -> list:
    graph = example.graph()
    seeds = example.seed_texts(graph)
    plan = compute_replay(graph, example.lock(), seeds)
    return root_diffs(graph, example.lock(), plan, seeds, _FixedResolver(answer))  # type: ignore[arg-type]


def test_root_diff_is_the_unified_diff_of_the_contract_text(example: Example) -> None:
    before = contract_lines(example.graph().by_id[CRITERION], example.graph(), {})
    example.edit_item(CRITERION, _add_term)
    (diff,) = _diffs(example, OldText(tuple(before)))
    assert diff.root == CRITERION and diff.note is None
    assert [line for line in diff.diff if line.startswith(("-", "+")) and not line.startswith(("---", "+++"))] == [
        "-" + before[1], "+" + before[1] + f" {TERM}"
    ]


def test_root_diff_says_so_when_the_own_text_is_the_same(example: Example) -> None:
    example.edit_item(CRITERION, _add_term)
    old = tuple(contract_lines(example.graph().by_id[CRITERION], example.graph(), {}))
    (diff,) = _diffs(example, OldText(old))
    assert (diff.diff, diff.note) == ((), NOTE_SAME_TEXT)


def test_root_diff_carries_the_note_when_there_is_no_old_text(example: Example) -> None:
    example.edit_item(CRITERION, _add_term)
    (diff,) = _diffs(example, OldText(None, NOTE_BASELINE))
    assert (diff.root, diff.diff, diff.note) == (CRITERION, (), NOTE_BASELINE)


def test_contract_lines_of_a_seed_are_its_sentences() -> None:
    graph: Graph = Example(EXAMPLE_HOST).graph()
    seed = graph.by_id["seed-accounts"]
    assert contract_lines(seed, graph, {"seed-accounts": "One. Two! Three?"}) == ["One.", "Two!", "Three?"]
    assert contract_lines(seed, graph, {}) == [""]


def test_contract_lines_of_a_node_are_fields_then_links_then_criteria() -> None:
    graph = Example(EXAMPLE_HOST).graph()
    lines = contract_lines(graph.by_id["fr-password-reset"], graph, {})
    link = lines.index("link derives_from: cap-account-recovery")
    priority = next(index for index, line in enumerate(lines) if line.startswith("priority: "))
    criterion = next(index for index, line in enumerate(lines) if line.startswith("ac-password-reset-1.text: "))
    assert priority < link < criterion


def test_a_lock_with_no_entry_for_the_root_gives_no_earlier_version(example: Example) -> None:
    example.edit_item(CRITERION, _add_term)
    graph = example.graph()
    seeds = example.seed_texts(graph)
    plan = compute_replay(graph, example.lock(), seeds)
    kept = Lock(tuple(entry for entry in example.lock().entries if entry.target != CRITERION))
    assert plan.steps
    (diff,) = root_diffs(graph, kept, plan, seeds, _FixedResolver(OldText(("x",))))  # type: ignore[arg-type]
    assert (diff.root, diff.diff, diff.note) == (CRITERION, (), "no earlier version found")


class _RecordingResolver:
    """Remembers the entries it was asked about and answers with no text."""

    def __init__(self) -> None:
        self.asked: list[LockEntry] = []

    def old_text(self, entry: LockEntry) -> OldText:
        self.asked.append(entry)
        return OldText(None, NOTE_BASELINE)


def test_the_diff_is_recovered_from_an_entry_that_is_not_a_baseline_marker(example: Example) -> None:
    """Entries of one stored hash: a baseline entry has no recoverable text, so the first entry that is not one is asked, whatever the lock order."""
    example.edit_item(CRITERION, _add_term)
    entries = list(example.lock().entries)
    first = next(index for index, entry in enumerate(entries) if entry.target == CRITERION)
    entries[first] = LockEntry(*entries[first].key, entries[first].content_hash, entries[first].chain_stamp, baseline=True)
    graph = example.graph()
    seeds = example.seed_texts(graph)
    lock = Lock(tuple(entries))
    plan = compute_replay(graph, lock, seeds)
    resolver = _RecordingResolver()
    root_diffs(graph, lock, plan, seeds, resolver)  # type: ignore[arg-type]
    assert [entry.baseline for entry in resolver.asked] == [False] and resolver.asked[0].target == CRITERION
    assert resolver.asked[0].key != entries[first].key
