"""Classifier unit tests — pure, no file I/O."""
from __future__ import annotations

import pytest

from specdev_tools.analysis.upstream_backlog import classify


@pytest.mark.parametrize("impact,expected", [
    (["spec/09_impl_plan.json:task-foo"], ("step_09", 1)),
    (["spec/13a_completeness_assessment.json"], ("step_13a", 1)),
    (["spec/02a_system_sketch.json"], ("step_02a", 1)),
    (["devspec_toolkit/tools/whatever.py"], ("toolkit", 2)),
    (["E307 linter says no"], ("toolkit", 2)),
    (["W613 warning about X"], ("toolkit", 2)),
    (["plan.summary"], ("plan_level", 3)),
    (["execution.emergent_ambiguities"], ("plan_level", 3)),
    (["SCREAMING_SNAKE_ID"], ("unclassified", 4)),
    ([], ("unclassified", 4)),
])
def test_rules(impact, expected):
    bucket, rule, _ = classify({"impact": impact})
    assert (bucket, rule) == expected


def test_first_match_precedence_scans_past_unmatched_entries():
    # Per plan: scan continues across non-matching entries until a rule hits.
    bucket, rule, entry = classify({
        "impact": ["SCREAMING_ID", "spec/05_x.json"]
    })
    assert bucket == "step_05"
    assert rule == 1
    assert entry == "spec/05_x.json"


def test_rule_one_match_precedence_when_first():
    bucket, rule, entry = classify({
        "impact": ["spec/05_x.json", "SCREAMING_ID"]
    })
    assert bucket == "step_05"
    assert rule == 1
    assert entry == "spec/05_x.json"


def test_missing_impact_key():
    assert classify({})[0] == "unclassified"


def test_non_list_impact():
    assert classify({"impact": {"not": "a list"}})[0] == "unclassified"


def test_non_string_entries_skipped():
    bucket, rule, entry = classify({
        "impact": [{"not": "string"}, 42, "plan.x"]
    })
    assert bucket == "plan_level"
    assert rule == 3
    assert entry == "plan.x"


def test_all_non_string_falls_through():
    assert classify({"impact": [{}, 1, None]})[0] == "unclassified"
