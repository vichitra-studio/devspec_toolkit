"""The plan-time file boundary of a milestone plan: E520 for a file action whose target the plan's own patterns do not cover."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from specdev_tools.validation.validators.step_16 import _is_doc_path, validate_step_16


def _plan(actions: list[dict[str, Any]], patterns: list[str], supporting: list[str] | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {"target_file_patterns": patterns}
    if supporting is not None:
        summary["milestone_supporting_files"] = supporting
    return {
        "plan": {
            "summary": summary,
            "spec_alignment": {"checklist": [{"id": "PWRESET_CONFIRM_01", "type": "feature", "layer": "api", "implementation": {"actions": actions}}]},
            "docs_impact": {"status": "not_required", "rationale": "The actions under test change no documented behaviour."},
        }
    }


def _boundary_messages(data: dict[str, Any], spec_path: str | None = None) -> list[str]:
    return [e.message for e in validate_step_16(data, ".", spec_path=spec_path) if e.code == "E520" and "target_file_patterns does not cover" in e.message]


def test_a_file_action_outside_the_patterns_is_e520_and_names_the_action() -> None:
    data = _plan(
        [
            {"id": "a01", "type": "file_edit", "target": "src/routes/password-resets/confirm.ts"},
            {"id": "a02", "type": "file_create", "target": "src/auth/session.ts"},
        ],
        ["src/routes/password-resets/**"],
    )
    assert _boundary_messages(data) == [
        "Action 'a02' of plan item 'PWRESET_CONFIRM_01' targets 'src/auth/session.ts', which "
        "plan.summary.target_file_patterns does not cover: add a pattern for it, or change the action."
    ]


def test_a_file_action_inside_the_patterns_or_among_the_supporting_files_is_not_reported() -> None:
    data = _plan(
        [
            {"id": "a01", "type": "file_edit", "target": "./src/routes/password-resets/confirm.ts"},
            {"id": "a02", "type": "file_edit", "target": "README.md"},
        ],
        ["src/routes/password-resets/*.ts"],
        supporting=["README.md"],
    )
    assert _boundary_messages(data) == []


def test_only_file_create_and_file_edit_targets_are_compared() -> None:
    data = _plan(
        [
            {"id": "a01", "type": "run_command", "target": "infra/deploy.sh"},
            {"id": "a02", "type": "file_read", "target": "src/auth/session.ts"},
            {"id": "a03", "type": "file_edit"},
        ],
        ["src/routes/**"],
    )
    assert _boundary_messages(data) == []


def test_a_legacy_closed_plan_is_history_and_is_not_compared(tmp_path) -> None:
    data = _plan([{"id": "a01", "type": "file_edit", "target": "src/auth/session.ts"}], ["src/routes/**"])
    plan_file = tmp_path / "impl_context" / "ms_account_recovery_plan.json"
    plan_file.parent.mkdir()
    plan_file.write_text("{}", encoding="utf-8")
    assert len(_boundary_messages(data, str(plan_file))) == 1
    with patch("specdev_tools.validation.validators.step_16.is_legacy_closed_plan", return_value=True):
        assert _boundary_messages(data, str(plan_file)) == []


def test_is_doc_path_keeps_a_dot_folder() -> None:
    assert _is_doc_path(".github/docs/x.md", [".github/**"])
    assert _is_doc_path("./.github/docs/x.md", [".github/**"])
    assert not _is_doc_path(".github/docs/x.md", ["github/**"])
