"""Unit tests for step_16a validator — review→plan feedback loop (W584).

Post-split, the 16a plan, 16b execution, and 16c review all live in the same
``spec/impl_context/{milestone_id}.json`` artifact that grows as phases run.
When chain-up validation reaches ``validate_step_16a`` for a 16c-phase
artifact, the ``review`` block is already on ``data`` — no sibling file lookup
required.  These tests inline ``review`` into the same data dict.
"""
from __future__ import annotations

import unittest

from specdev_tools.validation.validators.step_16a import validate_step_16a


def _make_minimal_16a() -> dict:
    return {
        "$schema": "vc:16-impl-context",
        "id": "step-16a-test",
        "owner": "api",
        "created_at": "2024-01-01T00:00:00Z",
        "plan": {
            "status": "active",
            "summary": {
                "functional_summary": "Test implementation",
                "scope_in": ["auth-api"],
                "scope_out": [],
                "target_file_patterns": ["src/auth.py"],
            },
            "spec_alignment": {
                "requirements_summary": [{"theme": "Auth", "summary": "Login flow"}],
                "checklist": [],
            },
        },
    }


def _review_with_remediation(task_ids: list[str]) -> dict:
    findings = []
    for task_id in task_ids:
        findings.append({
            "severity": "major",
            "description": f"Issue requiring {task_id}",
            "remediation_task": {
                "task_id": task_id,
                "summary": f"Fix for {task_id}",
                "files_to_modify": [],
                "checklist_item_ids": [],
            },
        })
    return {"verdict": "needs_work", "findings": findings}


class TestStep16aFeedbackLoop(unittest.TestCase):
    """W584 fires when the review on this artifact surfaces a remediation_task
    that is not represented as a checklist item."""

    def test_no_review_no_w584(self):
        """A plan-only artifact (no review yet) never triggers W584."""
        data = _make_minimal_16a()
        errors = validate_step_16a(data, ".", spec_path=None)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_review_with_all_tasks_covered_no_w584(self):
        """When remediation tasks are represented in the checklist, W584 stays quiet."""
        data = _make_minimal_16a()
        data["plan"]["spec_alignment"]["checklist"] = [
            {"id": "task-fix-auth", "spec_ref": {"type": "fr", "id": "fr-auth"}, "description": "Fix auth"},
        ]
        data["review"] = _review_with_remediation(["task-fix-auth"])
        errors = validate_step_16a(data, ".", spec_path=None)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_review_with_uncovered_task_fires_w584(self):
        """A remediation_task missing from the checklist fires W584 with the task id in the message."""
        data = _make_minimal_16a()
        # Checklist is empty — remediation task is uncovered
        data["review"] = _review_with_remediation(["task-fix-missing"])
        errors = validate_step_16a(data, ".", spec_path=None)
        w584 = [e for e in errors if e.code == "W584"]
        self.assertEqual(len(w584), 1)
        self.assertIn("task-fix-missing", w584[0].message)

    def test_multiple_uncovered_tasks_fire_multiple_w584(self):
        """Each uncovered remediation task produces its own W584."""
        data = _make_minimal_16a()
        data["review"] = _review_with_remediation(["task-a", "task-b"])
        errors = validate_step_16a(data, ".", spec_path=None)
        w584_messages = {e.message for e in errors if e.code == "W584"}
        self.assertEqual(len(w584_messages), 2)

    def test_review_feedback_does_not_require_spec_path(self):
        """W584 depends only on ``data`` — passing or omitting spec_path is equivalent."""
        data = _make_minimal_16a()
        data["review"] = _review_with_remediation(["task-only-in-review"])
        errors_no_path = validate_step_16a(data, ".", spec_path=None)
        errors_with_path = validate_step_16a(data, ".", spec_path="/tmp/any/path.json")
        codes_no_path = {e.code for e in errors_no_path}
        codes_with_path = {e.code for e in errors_with_path}
        self.assertIn("W584", codes_no_path)
        self.assertIn("W584", codes_with_path)


if __name__ == "__main__":
    unittest.main()
