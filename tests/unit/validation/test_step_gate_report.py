"""The step-gate report built from hand-made results: the union of the ``pending`` bucket and the suspect hint."""
from __future__ import annotations

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import BaselineResult
from specdev_tools.validation.step_gate import StepGateResult
from specdev_tools.validation.step_gate_report import DETAIL_SUMMARY, render_step_gate, step_gate_json

BASELINE = BaselineResult("unavailable")


def _error(code: str, owner: str, node_id: str) -> SpecError:
    return SpecError(code=code, message="m", owner=owner, node_id=node_id)


def test_pending_in_json_is_the_union_over_the_steps() -> None:
    """Step 06 has pending work for owner 07 only; step 05 has it for owner 06 only: the object has both."""
    first = StepGateResult("05", pending={"06": (_error("E500", "step:06", "a"),)})
    second = StepGateResult("06", pending={"07": (_error("E500", "step:07", "b"),), "06": (_error("E500", "step:06", "a"),)})
    pending = step_gate_json([first, second], BASELINE)["pending"]
    assert sorted(pending) == ["06", "07"]
    assert [entry["node_id"] for entry in pending["07"]] == ["b"]
    assert [entry["node_id"] for entry in pending["06"]] == ["a"], "a finding pending for two steps is listed once"


@pytest.mark.parametrize("code", ["E762", "E763"])
def test_a_gate_owned_suspect_gives_the_stale_hint_for_both_codes(code: str) -> None:
    """The hint is on the summary line; ``--detail all`` lists the findings instead."""
    result = StepGateResult("05", gate_owned=(_error(code, "merge-check", "fr-a"),))
    assert "(incl. suspects: specdev stale)" in render_step_gate([result], BASELINE, DETAIL_SUMMARY)


def test_other_gate_owned_findings_give_no_stale_hint() -> None:
    result = StepGateResult("05", gate_owned=(_error("E608", "merge-check", "fr-a"),))
    assert "specdev stale" not in render_step_gate([result], BASELINE)
