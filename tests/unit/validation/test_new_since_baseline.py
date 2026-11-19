"""The count rule of the step gate: a finding is new when its key has more findings now than at the baseline."""
from __future__ import annotations

import pytest

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.validation.step_gate import declared_owner, new_since_baseline

OWNER = "step:04"


def schema_error(message: str) -> SpecError:
    """A schema finding as ``_check_schema_validation`` makes it: owner and message only, so every one of a file has one key."""
    return SpecError("E520", message, owner=OWNER)


def new_flags(current: list[SpecError], baseline: list[SpecError], **kwargs) -> list[bool]:
    return new_since_baseline(current, baseline, declared_owner, **kwargs)


def test_b1_a_second_schema_error_of_one_file_is_new() -> None:
    old, added = schema_error("/0/scope: 'bogus'"), schema_error("/1/scope: 'bogus'")
    assert new_flags([old, added], [old]) == [False, True]


def test_b1_the_new_one_is_found_when_it_comes_first() -> None:
    old, added = schema_error("/0/scope: 'bogus'"), schema_error("/1/scope: 'bogus'")
    assert new_flags([added, old], [old]) == [True, False]


def test_b2_an_insert_before_an_old_error_leaves_it_old() -> None:
    old = SpecError("E700", "no node", owner=OWNER, node_id="fr-a", jq_path=".functional_requirements[2]")
    moved = SpecError("E700", "no node", owner=OWNER, node_id="fr-a", jq_path=".functional_requirements[3]")
    assert new_flags([moved], [old]) == [False]


def test_a_reworded_message_is_old_when_the_count_did_not_grow() -> None:
    old = schema_error("/tmp/base/spec/04.json: bad")
    now = schema_error("/work/spec/04.json: bad")
    assert new_flags([now], [old]) == [False]


def test_a_reworded_old_message_and_one_added_error_give_one_new() -> None:
    old = schema_error("/tmp/base/spec/04.json: bad")
    reworded, added = schema_error("/work/spec/04.json: bad"), schema_error("/work/spec/04.json: worse")
    assert new_flags([reworded, added], [old]) == [False, True]


def test_no_baseline_findings_makes_every_finding_new() -> None:
    assert new_flags([schema_error("a"), schema_error("b")], []) == [True, True]


def test_a_fixed_and_an_added_finding_of_one_key_stays_old_the_known_limit() -> None:
    fixed, added = schema_error("/0/scope: 'bogus'"), schema_error("/5/priority: 'bogus'")
    assert new_flags([added], [fixed]) == [False]


def test_a_finding_of_another_key_is_new() -> None:
    old = SpecError("E700", "m", owner=OWNER, node_id="fr-a", target=link_target("derives_from", "ac-a"))
    other = SpecError("E700", "m", owner=OWNER, node_id="fr-a", target=link_target("derives_from", "ac-b"))
    assert new_flags([old, other], [old]) == [False, True]


def test_the_same_finding_twice_counts_once_on_both_sides() -> None:
    error = schema_error("/0/scope: 'bogus'")
    assert new_flags([error, error], [error, error]) == [False, False]
    added = schema_error("/1/scope: 'bogus'")
    assert new_flags([error, added, added], [error]) == [False, True, True]


def test_two_w630_of_one_id_both_old_when_both_were_there() -> None:
    first = SpecError("W630", "open item amb-x in 05_a.json", owner="step:05", node_id="amb-x")
    second = SpecError("W630", "open item amb-x in 08_b.json", owner="step:05", node_id="amb-x")
    assert new_flags([first, second], [first, second]) == [False, False]
    assert new_flags([first, second], [first]) == [False, True]


def test_an_old_error_of_a_renamed_node_stays_old() -> None:
    old = SpecError("E500", "m", owner=OWNER, node_id="fr-old")
    now = SpecError("E500", "m", owner=OWNER, node_id="fr-new")
    renames = {"fr-old": "fr-new"}
    assert new_flags([now], [old], canonical_id=lambda name: renames.get(name, name)) == [False]


@pytest.mark.parametrize("current", [[], [schema_error("a")]])
def test_the_answer_has_one_flag_per_current_finding(current: list[SpecError]) -> None:
    assert len(new_flags(current, [schema_error("a")])) == len(current)
