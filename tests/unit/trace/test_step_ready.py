"""The pieces of ``step ready`` that need no command line: which steps have a file, the required inputs, and the verdict from values."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.trace.replay import ReplayPlan, compute_replay
from specdev_tools.graph.queries import plural
from specdev_tools.trace.step_ready import Blocker, Readiness, check_ready, first_clause, link_steps, not_ready_error, present_steps, required_spec_inputs

from ..graph._synth import ROOT
from ._suspects_support import Example
from ._lock_support import EXAMPLE_HOST


@pytest.fixture
def example(tmp_path: Path) -> Example:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    return Example(host)


def test_present_steps_are_the_steps_with_a_spec_file(example: Example) -> None:
    present = present_steps(example.graph(), str(example.spec))
    assert {"00", "02", "02a", "04", "16"} <= present and "16b" not in present
    (example.spec / "16b_extra.json").write_text("{}", encoding="utf-8")
    assert "16b" in present_steps(example.graph(), str(example.spec))


def test_a_file_that_is_not_json_does_not_make_its_step_present(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "05_notes.txt").write_text("not a spec file", encoding="utf-8")
    graph = Example(tmp_path).graph()
    assert present_steps(graph, str(spec)) == frozenset()


def test_a_file_of_step_02a_is_not_a_file_of_step_02(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "02a_delivery_baseline.json").write_text("{}", encoding="utf-8")
    graph = Example(tmp_path).graph()  # no spec files of the example: an empty graph
    assert present_steps(graph, str(spec)) == {"02a"}


def test_required_spec_inputs_come_from_the_step_order_file() -> None:
    assert "13" in required_spec_inputs(str(ROOT), "14")
    assert required_spec_inputs(str(ROOT), "no-such-step") == []


def test_step_14_no_longer_requires_13a() -> None:
    assert "13a" not in required_spec_inputs(str(ROOT), "14")


def test_13a_is_not_a_step() -> None:
    steps = json.loads((Path(ROOT) / "tools" / "step_order.json").read_text(encoding="utf-8"))["steps"]
    assert "13a" not in steps and required_spec_inputs(str(ROOT), "13a") == []


def test_check_ready_takes_the_present_steps_as_values(example: Example) -> None:
    graph = example.graph()
    linked = link_steps(graph, "06")
    assert linked
    empty = ReplayPlan(())
    assert check_ready(graph, empty, "06", [], frozenset(linked)).ready
    missing = check_ready(graph, empty, "06", [], frozenset(linked) - {linked[0]})
    assert [(blocker.step, blocker.reason) for blocker in missing.blockers] == [(linked[0], "missing")]
    assert missing.replay_first == linked[0]


def _blocker(step: str, reason: str) -> Blocker:
    return Blocker(step, reason, node=None if reason == "missing" else "n-1", code="E743" if reason == "gap" else None)


@pytest.mark.parametrize(
    ("reasons", "clause"),
    [
        (("missing",), "write step 08 first"),
        (("suspect",), "replay step 08 first"),
        (("gap", "gap"), "fix the coverage gaps of step 08 first"),
        (("suspect", "gap"), "replay step 08 first and fix its coverage gaps"),
        (("gap", "suspect"), "replay step 08 first and fix its coverage gaps"),
        (("suspect", "missing"), "replay step 08 first"),
        (("missing", "suspect"), "write step 08 first"),
    ],
)
def test_the_last_clause_is_worded_by_what_blocks_the_first_step(reasons: tuple[str, ...], clause: str) -> None:
    """A coverage gap is fixed in the nodes (a fixture, a scope): no replay and no attest clears it, so the clause for a step that has only gaps does not say replay."""
    readiness = Readiness("14", ("08",), tuple(_blocker("08", reason) for reason in reasons))
    assert first_clause(readiness) == clause
    assert not_ready_error(readiness).message == f"step 14 is not ready: step 08 ({plural(len(reasons), 'blocker')}); {clause}"


def test_the_clause_is_about_the_first_step_only() -> None:
    """Step 05 has a suspect link and step 08 has gaps: the first step decides the clause, step 08's gaps are not mentioned yet."""
    readiness = Readiness("14", ("05", "08"), (_blocker("05", "suspect"), _blocker("08", "gap")))
    assert first_clause(readiness) == "replay step 05 first"


def test_the_step_to_replay_first_is_the_earliest_pending_step_above_even_when_it_is_not_linked(example: Example) -> None:
    """A seed edit makes step 00's links suspect; step 01's links are suspect too and cannot be attested before 00's, though step 04 links to 01 only."""
    example.edit_seed()
    graph = example.graph()
    plan = compute_replay(graph, example.lock(), example.seed_texts(graph))
    pending = [item.step for item in plan.steps if item.nodes]
    assert pending[:2] == ["00", "01"]
    present = present_steps(graph, str(example.spec))
    readiness = check_ready(graph, plan, "04", required_spec_inputs(str(ROOT), "04"), present)
    assert not readiness.ready
    assert {blocker.step for blocker in readiness.blockers} == {"01"}
    assert readiness.replay_first == "00"
    assert first_clause(readiness) == "replay step 00 first"
    assert "step 01 (" in not_ready_error(readiness).message and not_ready_error(readiness).message.endswith("replay step 00 first")
    assert check_ready(graph, plan, "01", [], present).replay_first == "00"


def test_a_pending_step_above_that_is_not_linked_does_not_block_a_step_whose_own_links_are_clean(example: Example) -> None:
    example.edit_criterion()
    graph = example.graph()
    plan = compute_replay(graph, example.lock(), example.seed_texts(graph))
    present = present_steps(graph, str(example.spec))
    readiness = check_ready(graph, plan, "04", [], present)
    assert readiness.ready and readiness.replay_first is None and readiness.earlier == ()
