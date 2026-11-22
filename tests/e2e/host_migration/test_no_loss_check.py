"""The harness's no-loss check exempts a lost open item only when it was resolved or a worklist item names it (A-4 of round 1)."""

from __future__ import annotations

from .harness import split_lost_ids

KIND = "ambiguity-item"
BEFORE = {
    "amb-done": [("impl_context/ms_a_plan.json", KIND)],
    "amb-open": [("impl_context/ms_a_plan.json", KIND)],
    "amb-frozen": [("impl_context/ms_b_plan.json", KIND)],
    "fr-x": [("04_fr_list.json", "functional-requirement")],
}
CAPTURE = {"ambiguities": [{"file": "impl_context/ms_a_plan.json", "step": "16a", "legacy_item": {"id": "amb-open"}}, {"file": "impl_context/ms_b_plan.json", "step": "16a", "legacy_item": {"id": "amb-frozen"}}]}
FROZEN_ITEM = {"kind": "legacy-open-item", "evidence": "amb-frozen in the closed plan impl_context/ms_b_plan.json: it was open"}


def test_a_resolved_item_and_a_frozen_one_a_worklist_item_names_are_exempt_and_nothing_else_is():
    resolved, gone = split_lost_ids(["amb-done", "amb-open", "amb-frozen", "fr-x"], BEFORE, CAPTURE, [FROZEN_ITEM])
    assert sorted(resolved) == ["amb-done", "amb-frozen"]
    assert gone == ["amb-open", "fr-x"]


def test_an_open_item_no_worklist_item_names_is_a_loss():
    resolved, gone = split_lost_ids(["amb-frozen"], BEFORE, CAPTURE, [])
    assert (resolved, gone) == ([], ["amb-frozen"])


def test_a_worklist_item_of_another_kind_or_naming_a_longer_id_does_not_exempt():
    other = {"kind": "ambiguity-about", "evidence": "amb-frozen in x"}
    longer = {"kind": "legacy-open-item", "evidence": "amb-frozen-2 in the closed plan"}
    assert split_lost_ids(["amb-frozen"], BEFORE, CAPTURE, [other, longer]) == ([], ["amb-frozen"])
