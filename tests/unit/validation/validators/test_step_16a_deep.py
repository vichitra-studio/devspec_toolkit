"""Unit tests for step_16a validator — 16c→16a feedback loop (W584)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
import tempfile
import os

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


def _make_16c_with_remediation(task_ids: list[str]) -> dict:
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
    return {
        "$schema": "vc:16-impl-context",
        "id": "step-16c-test",
        "owner": "api",
        "created_at": "2024-01-01T00:00:00Z",
        "review": {
            "verdict": "needs_work",
            "findings": findings,
        },
    }


class TestStep16aFeedbackLoop(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_json(self, filename: str, data: dict) -> str:
        path = os.path.join(self.tmpdir, filename)
        Path(path).write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_no_16c_file_no_w584(self):
        """When no 16c file exists, W584 should not fire."""
        data = _make_minimal_16a()
        spec_path = os.path.join(self.tmpdir, "16a_plan.json")
        errors = validate_step_16a(data, ".", spec_path)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_16c_with_all_tasks_covered_no_w584(self):
        """When 16c remediation tasks are all in the 16a checklist, W584 should not fire."""
        data = _make_minimal_16a()
        data["plan"]["spec_alignment"]["checklist"] = [
            {"id": "task-fix-auth", "spec_ref": {"type": "fr", "id": "fr-auth"}, "description": "Fix auth"},
        ]
        self._write_json("16c_review.json", _make_16c_with_remediation(["task-fix-auth"]))
        spec_path = os.path.join(self.tmpdir, "16a_plan.json")
        errors = validate_step_16a(data, ".", spec_path)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_16c_with_uncovered_task_fires_w584(self):
        """When a 16c remediation task is not in the 16a checklist, W584 should fire."""
        data = _make_minimal_16a()
        # Checklist is empty — remediation task is not covered
        self._write_json("16c_review.json", _make_16c_with_remediation(["task-fix-missing"]))
        spec_path = os.path.join(self.tmpdir, "16a_plan.json")
        errors = validate_step_16a(data, ".", spec_path)
        w584 = [e for e in errors if e.code == "W584"]
        self.assertEqual(len(w584), 1)
        self.assertIn("task-fix-missing", w584[0].message)

    def test_16c_multiple_uncovered_tasks_fires_multiple_w584(self):
        """Each uncovered remediation task fires its own W584."""
        data = _make_minimal_16a()
        self._write_json("16c_review.json", _make_16c_with_remediation(["task-a", "task-b"]))
        spec_path = os.path.join(self.tmpdir, "16a_plan.json")
        errors = validate_step_16a(data, ".", spec_path)
        w584_ids = {e.message for e in errors if e.code == "W584"}
        self.assertEqual(len(w584_ids), 2)

    def test_no_spec_path_no_w584(self):
        """Without spec_path, 16c lookup is skipped."""
        data = _make_minimal_16a()
        errors = validate_step_16a(data, ".", spec_path=None)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)


if __name__ == "__main__":
    unittest.main()
