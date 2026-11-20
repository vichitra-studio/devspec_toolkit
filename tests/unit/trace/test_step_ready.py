"""The pieces of ``step ready`` that need no command line: which steps have a file, the required inputs, and the verdict from values."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specdev_tools.trace.replay import ReplayPlan
from specdev_tools.trace.step_ready import check_ready, link_steps, present_steps, required_spec_inputs

from ..graph._synth import ROOT
from .test_suspects import Example
from ._lock_support import EXAMPLE_HOST


@pytest.fixture
def example(tmp_path: Path) -> Example:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    return Example(host)


def test_present_steps_are_the_steps_with_a_spec_file(example: Example) -> None:
    present = present_steps(example.graph(), str(example.spec))
    assert {"00", "02", "02a", "04", "16"} <= present and "13a" not in present
    (example.spec / "13a_extra.json").write_text("{}", encoding="utf-8")
    assert "13a" in present_steps(example.graph(), str(example.spec))


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
    assert "13a" in required_spec_inputs(str(ROOT), "14")
    assert required_spec_inputs(str(ROOT), "no-such-step") == []


def test_check_ready_takes_the_present_steps_as_values(example: Example) -> None:
    graph = example.graph()
    linked = link_steps(graph, "06")
    assert linked
    empty = ReplayPlan(())
    assert check_ready(graph, empty, "06", [], frozenset(linked)).ready
    missing = check_ready(graph, empty, "06", [], frozenset(linked) - {linked[0]})
    assert [(blocker.step, blocker.reason) for blocker in missing.blockers] == [(linked[0], "missing")]
    assert missing.replay_first == linked[0]
