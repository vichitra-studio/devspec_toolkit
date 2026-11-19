"""The step-gate classifier: one rule per bucket, the baseline key, and the multi-step run."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import FindingError, SpecError, link_target
from specdev_tools.core.git_base import BaselineResult
from specdev_tools.core.step_order import load_step_order
from specdev_tools.validation.spec_check import _check_result
from specdev_tools.validation.step_gate import (
    StepGateResult,
    WaitingOn,
    classify_for_step,
    classify_for_steps,
    declared_owner,
    identity_key,
)

ROOT = Path(__file__).parents[3]
ORDER = {step: index for index, step in enumerate(load_step_order(str(ROOT))["steps"])}
OK_BASELINE = BaselineResult("ok")
UNAVAILABLE = BaselineResult("unavailable")
OPEN_ITEM = "waiting on amb-open"


def err(code: str, owner: str | None, node_id: str | None = None, message: str = "m", **fields: str) -> SpecError:
    return SpecError(code=code, message=message, owner=owner, node_id=node_id, **fields)


def baseline_of(*errors: SpecError) -> BaselineResult:
    return BaselineResult("ok", tuple(errors))


def gate(errors: list[SpecError], step: str, baseline: BaselineResult = OK_BASELINE, waiting: WaitingOn | None = None, **kwargs) -> StepGateResult:
    return classify_for_step(errors, step, declared_owner, ORDER, baseline, waiting, **kwargs)


def waiting_on(node_id: str) -> WaitingOn:
    return WaitingOn({"amb-open": frozenset({node_id})}, {"amb-open": frozenset({"seed-x"})})


# --- gates and unowned ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("owner", ["merge-check", "close-gate", "release-gate"])
def test_gate_owned_error_is_listed_and_never_blocks(owner: str) -> None:
    error = err("E762", owner, "fr-a")
    result = gate([error], "05")
    assert result.gate_owned == (error,) and result.clear


def test_unowned_error_is_gate_owned() -> None:
    error = err("E999", None)
    result = gate([error], "05")
    assert result.gate_owned == (error,) and result.clear and not result.own_warnings


def test_e763_is_gate_owned_in_step_05_and_06() -> None:
    suspect = err("E763", "merge-check", "fr-a", target=link_target("derives_from", "seed-x"))
    for step in ("05", "06"):
        result = gate([suspect], step)
        assert result.gate_owned == (suspect,) and result.clear


def test_e703_same_step_cycle_is_not_gate_owned() -> None:
    cycle = err("E703", "step:05", "fr-a")
    result = gate([cycle], "05")
    assert not result.gate_owned and result.blocking.own == (cycle,)


# --- the step's own errors --------------------------------------------------------------------------------------

def test_own_error_blocks() -> None:
    error = err("E500", "step:05", "api-a")
    result = gate([error], "05")
    assert result.blocking.own == (error,) and not result.clear


def test_own_warning_is_listed_not_blocking() -> None:
    warning = err("W500", "step:05", "api-a")
    result = gate([warning], "05")
    assert result.own_warnings == (warning,) and result.clear


def test_own_error_under_an_open_item_is_waiting() -> None:
    error = err("E500", "step:05", "api-a")
    result = gate([error], "05", waiting=waiting_on("api-a"))
    assert result.waiting[0].error == error and result.waiting[0].reasons == (OPEN_ITEM,)
    assert result.clear and not result.own_warnings


def test_promoted_code_owned_by_n_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
    reset_config()
    try:
        promoted = _check_result([err("W615", "step:05", "inv-a")])["errors"]
        result = gate(promoted, "05")
    finally:
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS")
        reset_config()
    assert [e.code for e in result.blocking.own] == ["E615"]


# --- earlier steps ----------------------------------------------------------------------------------------------

def test_new_upstream_error_blocks() -> None:
    error = err("E500", "step:04", "fr-a")
    result = gate([error], "05")
    assert result.blocking.new_upstream == (error,) and not result.clear


def test_new_upstream_error_with_no_baseline_available_blocks() -> None:
    error = err("E500", "step:04", "fr-a")
    assert gate([error], "05", UNAVAILABLE).blocking.new_upstream == (error,)


def test_new_upstream_error_under_an_open_item_still_blocks() -> None:
    error = err("E500", "step:04", "fr-a")
    result = gate([error], "05", waiting=waiting_on("fr-a"))
    assert result.blocking.new_upstream == (error,) and not result.waiting


def test_upstream_error_present_at_baseline_is_debt() -> None:
    error = err("E500", "step:04", "fr-a")
    result = gate([error], "05", baseline_of(error))
    assert result.upstream_debt == (error,) and result.clear


def test_new_upstream_warning_is_shown_not_blocking() -> None:
    warning = err("W500", "step:04", "fr-a")
    result = gate([warning], "05")
    assert result.new_upstream_warnings == (warning,) and result.clear


def test_renamed_node_old_error_stays_debt() -> None:
    old = err("E500", "step:04", "fr-old")
    now = err("E500", "step:04", "fr-new")
    renames = {"fr-old": "fr-new"}
    result = gate([now], "05", baseline_of(old), canonical_id=lambda name: renames.get(name, name))
    assert result.upstream_debt == (now,) and result.clear


def test_changed_message_is_not_a_new_error() -> None:
    old = err("E700", "step:04", "fr-a", message="no node 'ac-a'", target=link_target("derives_from", "ac-a"))
    now = err("E700", "step:04", "fr-a", message="no node 'ac-a'; nearest: ac-b", target=link_target("derives_from", "ac-a"))
    result = gate([now], "05", baseline_of(old))
    assert result.upstream_debt == (now,) and result.clear


def test_two_broken_links_of_one_node_the_new_one_blocks() -> None:
    old = err("E700", "step:04", "fr-a", target=link_target("derives_from", "ac-a"))
    new = err("E700", "step:04", "fr-a", target=link_target("derives_from", "ac-b"))
    result = gate([old, new], "05", baseline_of(old))
    assert result.upstream_debt == (old,) and result.blocking.new_upstream == (new,)


# --- later steps ------------------------------------------------------------------------------------------------

def test_later_step_error_is_pending_grouped_by_owner() -> None:
    six, seven = err("E600", "step:06", "api-a"), err("E700", "step:07", "inv-a")
    result = gate([six, seven, err("E601", "step:06", "api-b")], "05")
    assert set(result.pending) == {"06", "07"} and len(result.pending["06"]) == 2 and result.pending["07"] == (seven,)


def test_pending_error_for_step_06_does_not_block_step_05() -> None:
    assert gate([err("E600", "step:06", "api-a")], "05").clear


def test_e560_owned_by_step_01_is_pending_for_step_00_and_blocks_step_01() -> None:
    error = err("E560", "step:01", "cap-a")
    assert gate([error], "00").pending == {"01": (error,)}
    assert gate([error], "01").blocking.own == (error,)


def test_trinity_steps_come_after_16() -> None:
    plan = err("E900", "step:16a", "ms-a")
    anchor = err("E901", "step:16", "ms-a")
    assert gate([plan], "16").pending == {"16a": (plan,)}
    assert gate([anchor], "16a").blocking.new_upstream == (anchor,)


# --- identity and dedup -----------------------------------------------------------------------------------------

def test_same_code_and_message_with_different_owners_both_reach_classification() -> None:
    own, later = err("E500", "step:05", "api-a", message="same"), err("E500", "step:06", "api-a", message="same")
    result = gate([own, later], "05")
    assert result.blocking.own == (own,) and result.pending == {"06": (later,)}


def test_same_code_and_message_with_different_nodes_both_survive() -> None:
    first, second = err("E500", "step:05", "api-a", message="same"), err("E500", "step:05", "api-b", message="same")
    assert gate([first, second], "05").blocking.own == (first, second)


def test_the_same_finding_twice_is_one_finding() -> None:
    error = err("E500", "step:05", "api-a")
    assert gate([error, error], "05").blocking.own == (error,)


def test_the_key_is_the_seven_fields_and_no_message() -> None:
    error = SpecError("E700", "text", "p", "sub", "spec/a.json", ".x[0]", "v", "step:04", "fr-a", "derives_from->ac-a")
    assert identity_key(error, declared_owner) == ("E700", "step:04", "fr-a", "derives_from->ac-a", "spec/a.json", ".x[0]", "sub")


# --- steps ------------------------------------------------------------------------------------------------------

def test_unknown_step_is_e706() -> None:
    with pytest.raises(FindingError) as caught:
        gate([], "99")
    assert caught.value.error.code == "E706" and "known steps" in caught.value.error.message


def test_repeated_step_blocks_if_any_listed_step_blocks() -> None:
    errors = [err("E500", "step:08", "fx-a")]
    results = classify_for_steps(errors, ["05", "08"], declared_owner, ORDER, OK_BASELINE)
    assert [r.step for r in results] == ["05", "08"]
    assert [r.clear for r in results] == [True, False]
    assert results[0].pending == {"08": tuple(errors)}
