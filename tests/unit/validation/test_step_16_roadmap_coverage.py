"""E304 ROADMAP_TASK_UNCOVERED: a roadmap task with no plan item realising a criterion of it."""
from __future__ import annotations

from typing import Any

from specdev_tools.validation.validators.step_16 import _check_roadmap_coverage

_NO_CRITERION = (
    "ROADMAP_TASK_UNCOVERED: roadmap task 't-1' of milestone 'ms-a' has no acceptance criterion, so no plan item "
    "can realise it; add a criterion to the task or give it a disposition"
)


def _roadmap(task: dict[str, Any]) -> dict[str, Any]:
    return {"milestones": [{"milestone_id": "ms-a", "tasks": [{"task_id": "t-1", **task}]}]}


def _messages(task: dict[str, Any], checklist: list[dict[str, Any]]) -> list[str]:
    errors: list = []
    _check_roadmap_coverage({"milestone": "ms-a"}, checklist, _roadmap(task), errors)
    return [f"{e.code} {e.message}" for e in errors]


def test_a_task_without_a_criterion_gets_e304_that_says_no_item_can_realise_it() -> None:
    assert _messages({}, []) == [f"E304 {_NO_CRITERION}"]
    assert _messages({"acceptance_criteria": [{"text": "no id"}]}, []) == [f"E304 {_NO_CRITERION}"]


def test_a_task_set_aside_by_its_disposition_needs_neither_criterion_nor_item() -> None:
    assert _messages({"disposition": {"value": "deferred"}}, []) == []


def test_a_task_with_criteria_that_no_item_realises_keeps_the_existing_message() -> None:
    found = _messages({"acceptance_criteria": [{"criterion_id": "c-1"}]}, [])
    assert found == [
        "E304 ROADMAP_TASK_UNCOVERED: roadmap task 't-1' of milestone 'ms-a' has no plan item that realises one of "
        "its acceptance criteria"
    ]
