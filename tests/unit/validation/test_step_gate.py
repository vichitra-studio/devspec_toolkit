"""The step-gate classifier: one rule per bucket, the baseline key, and the multi-step run."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import FindingError, SpecError, link_target
from specdev_tools.core.git_base import BaselineResult
from specdev_tools.core.step_order import load_step_order
from specdev_tools.validation.check_registry import check_result
from specdev_tools.validation.step_gate import (
    StepGateResult,
    WaitingOn,
    classify_for_step,
    classify_for_steps,
    declared_owner,
    gate_exit_code,
    identity_key,
    reported_errors,
    union_errors,
    union_waiting,
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
        promoted = check_result([err("W615", "step:05", "inv-a")])["errors"]
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


def test_a_reworded_finding_and_a_new_one_under_one_key_make_exactly_one_new() -> None:
    """The baseline had one finding at the key: it places ONE of the two current findings (the reworded one), the other is new."""
    old = err("E500", "step:04", "fr-a", message="A")
    reworded = err("E500", "step:04", "fr-a", message="A, reworded")
    added = err("E500", "step:04", "fr-a", message="B")
    result = gate([reworded, added], "05", baseline_of(old))
    assert result.upstream_debt == (reworded,) and result.blocking.new_upstream == (added,)


def test_a_link_target_renamed_with_an_alias_keeps_its_error_old() -> None:
    """``specdev node rename`` maps the old target id to the new one: the key of the link error follows it."""
    old = err("E701", "step:04", "fr-a", target=link_target("derives_from", "fr-b"))
    now = err("E701", "step:04", "fr-a", target=link_target("derives_from", "fr-b-x"))
    renames = {"fr-b": "fr-b-x"}
    mapped = gate([now], "05", baseline_of(old), canonical_id=lambda name: renames.get(name, name))
    assert mapped.upstream_debt == (now,) and mapped.clear
    unmapped = gate([now], "05", baseline_of(old))
    assert unmapped.blocking.new_upstream == (now,)


def test_two_findings_located_only_by_path_the_new_one_blocks() -> None:
    old = SpecError("E500", "old text", "04_fr_list.json", owner="step:04")
    new = SpecError("E500", "new text", "03_glossary.json", owner="step:04")
    result = gate([old, new], "05", baseline_of(old))
    assert result.upstream_debt == (old,) and result.blocking.new_upstream == (new,)


# --- later steps ------------------------------------------------------------------------------------------------

def test_later_step_error_is_pending_grouped_by_owner() -> None:
    six, seven = err("E600", "step:06", "api-a"), err("E700", "step:07", "inv-a")
    result = gate([six, seven, err("E601", "step:06", "api-b")], "05")
    assert set(result.pending) == {"06", "07"} and len(result.pending["06"]) == 2 and result.pending["07"] == (seven,)


def test_pending_error_for_step_06_does_not_block_step_05() -> None:
    assert gate([err("E600", "step:06", "api-a")], "05").clear


def test_e740_owned_by_step_01_is_pending_for_step_00_and_blocks_step_01() -> None:
    error = err("E740", "step:01", "cap-a")
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


def test_the_key_is_the_eight_fields_no_message_and_no_array_index() -> None:
    error = SpecError("E700", "text", "p", "sub", "spec/a.json", ".x[0].y[12]", "v", "step:04", "fr-a", "derives_from->ac-a")
    key = identity_key(error, declared_owner)
    assert key == ("E700", "step:04", "fr-a", "derives_from->ac-a", "spec/a.json", ".x[].y[]", "sub", "p")
    assert key.location == ".x[].y[]" and key.node_id == "fr-a"


def test_an_insert_before_a_finding_does_not_change_its_key() -> None:
    before = err("E700", "step:04", "fr-a", jq_path=".functional_requirements[2]")
    after = err("E700", "step:04", "fr-a", jq_path=".functional_requirements[3]")
    assert identity_key(before, declared_owner) == identity_key(after, declared_owner)


def test_an_index_inside_a_quoted_key_is_part_of_the_key() -> None:
    first = err("E520", "step:05", jq_path='.a["x[3]"]')
    second = err("E520", "step:05", jq_path='.a["x[4]"]')
    assert identity_key(first, declared_owner) != identity_key(second, declared_owner)
    assert identity_key(first, declared_owner).location == '.a["x[3]"]'


@pytest.mark.parametrize(
    ("before", "after", "location"),
    [
        (".a[3].b", ".a[4].b", ".a[].b"),
        ('.a["00"][1]', '.a["00"][2]', '.a["00"][]'),
        ('.a["q\\"[3]"][5]', '.a["q\\"[3]"][6]', '.a["q\\"[3]"][]'),
    ],
)
def test_an_index_outside_a_quoted_key_is_dropped(before: str, after: str, location: str) -> None:
    keys = [identity_key(err("E520", "step:05", jq_path=place), declared_owner) for place in (before, after)]
    assert keys[0] == keys[1] and keys[0].location == location


def test_two_findings_with_one_key_and_two_messages_are_two_findings_the_same_message_twice_is_one() -> None:
    first, second = err("E520", "step:05", message="/0/scope"), err("E520", "step:05", message="/1/scope")
    result = gate([first, second, first], "05")
    assert result.blocking.own == (first, second)


def test_two_w630_of_one_id_in_two_files_are_both_listed() -> None:
    first = err("W630", "step:05", "amb-x", message="open item amb-x in 05_a.json")
    second = err("W630", "step:05", "amb-x", message="open item amb-x in 08_b.json")
    assert gate([first, second], "05").own_warnings == (first, second)


# --- exit code and the union over steps -------------------------------------------------------------------------

def test_exit_code_is_1_when_any_step_blocks_and_0_otherwise() -> None:
    errors = [err("E500", "step:08", "fx-a")]
    clear, blocked = classify_for_steps(errors, ["05", "08"], declared_owner, ORDER, OK_BASELINE)
    assert (gate_exit_code([clear]), gate_exit_code([clear, blocked]), gate_exit_code([])) == (0, 1, 0)


def test_union_and_reported_errors_list_a_finding_of_two_steps_once() -> None:
    error, warning = err("E500", "step:04", "fr-a"), err("W500", "step:04", "fr-b")
    results = classify_for_steps([error, warning], ["05", "06"], declared_owner, ORDER, OK_BASELINE)
    assert reported_errors(results) == [error, warning]
    assert union_errors(result.blocking.errors for result in results) == [error]


def test_union_waiting_lists_a_waiting_finding_of_two_steps_once() -> None:
    error = err("E500", "step:05", "api-a")
    on = waiting_on("api-a")
    results = (gate([error], "05", waiting=on), gate([error], "05", waiting=on))
    assert [entry.error for entry in union_waiting(results)] == [error]


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


# --- DEVSPEC-207: own warnings compared with the base, and what the base had and the tree no longer has -----------


def _w(code: str, node: str, step: str, message: str = "m") -> SpecError:
    return SpecError(code=code, message=message, node_id=node, owner=f"step:{step}")


def test_an_own_warning_the_base_did_not_have_is_marked_new_and_does_not_block() -> None:
    order = {"04": 0, "05": 1, "06": 2}
    old, new = _w("W576", "fr-a", "05"), _w("W576", "fr-b", "05")
    result = classify_for_step([old, new], "05", declared_owner, order, BaselineResult("ok", (old,)))
    assert result.own_warnings == (old, new) and result.new_own_warnings == (new,) and result.clear
    without = classify_for_step([old, new], "05", declared_owner, order, BaselineResult("unavailable"))
    assert without.new_own_warnings == () and without.no_longer_present == ()


def test_what_the_base_had_and_the_tree_no_longer_has_is_listed_for_the_step_and_the_steps_above() -> None:
    order = {"04": 0, "05": 1, "06": 2}
    stays, fixed_here, fixed_above, below = _w("E743", "fr-a", "05"), _w("W576", "fr-b", "05"), _w("E700", "cap-a", "04"), _w("E744", "inv-a", "06")
    base = BaselineResult("ok", (stays, fixed_here, fixed_above, below))
    result = classify_for_step([stays], "05", declared_owner, order, base)
    assert result.no_longer_present == (fixed_here, fixed_above)  # step 06's finding is not this step's to report
    from specdev_tools.validation.step_gate_report import DETAIL_ALL, render_step_gate, step_gate_json

    text = render_step_gate([result], base, DETAIL_ALL)
    assert "NO LONGER PRESENT (2)" in text and "fr-b" in text and "cap-a" in text
    payload = step_gate_json([result], base)
    assert [e["node_id"] for e in payload["no_longer_present"]] == ["fr-b", "cap-a"] and payload["new_own_warnings"] == []
