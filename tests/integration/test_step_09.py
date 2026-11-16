#!/usr/bin/env python3
"""Thin CLI wrapper for Step 09 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_09.py <fixture>")
    fixture = Path(sys.argv[1])
    toolkit_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "validate", str(fixture),
         "--repo-root", str(toolkit_root)],
        cwd=str(toolkit_root),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Pytest-style tests
# ---------------------------------------------------------------------------

import json
import tempfile
import unittest
from typing import Any, Callable

from specdev_tools.validation.validate import validate_file as specdev_validate_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_09"

# The worked example of the spec-graph design (design milestone "New" form): status and deliverables go,
# `schedules` names the nodes the milestone delivers.
_DOC_EXAMPLE_MILESTONE: dict[str, Any] = {
    "milestone_id": "milestone-account-recovery",
    "name": "Account Recovery",
    "schedules": ["fr-password-reset", "risk-reset-link-takeover"],
}


class Step09IntegrationTests(unittest.TestCase):
    def _milestone_errors(self, mutate: Callable[[dict], None]) -> list[str]:
        """Rendered E520 errors for the design-doc milestone after ``mutate`` edits a copy of it."""
        spec = json.loads((_FIXTURES / "valid_minimal.json").read_text())
        milestone = json.loads(json.dumps(_DOC_EXAMPLE_MILESTONE))
        mutate(milestone)
        spec["milestones"] = [milestone]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "09_impl_plan.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def _assert_milestone_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = self._milestone_errors(mutate)
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_doc_example_validates(self):
        self.assertEqual(self._milestone_errors(lambda milestone: None), [])

    def test_milestone_with_status_fails(self):
        self._assert_milestone_fails_naming(lambda milestone: milestone.update(status="pending"), "status")

    def test_milestone_with_depends_on_fails(self):
        self._assert_milestone_fails_naming(
            lambda milestone: milestone.update(depends_on=["milestone-other"]), "depends_on"
        )

    def test_milestone_with_dependencies_or_dependency_ref_fails(self):
        self._assert_milestone_fails_naming(
            lambda milestone: milestone.update(dependencies=["Auth team"]), "dependencies"
        )
        self._assert_milestone_fails_naming(
            lambda milestone: milestone.update(
                dependency_ref={"id": "cn:project:dependency:auth", "kind": "dependency"}
            ),
            "dependency_ref",
        )

    def test_plan_without_schedules_fails(self):
        self._assert_milestone_fails_naming(lambda milestone: milestone.pop("schedules"), "schedules")
        self._assert_milestone_fails_naming(lambda milestone: milestone.update(schedules=[]), "schedules")

    def test_schedules_accepts_a_risk_id(self):
        self.assertEqual(
            self._milestone_errors(lambda milestone: milestone.update(schedules=["risk-reset-link-takeover"])), []
        )

    def test_old_top_level_fields_fail(self):
        for field, value in (("tech_stack", {}), ("trace", []), ("dependencies", []), ("tech_stack_ref", {})):
            spec = json.loads((_FIXTURES / "valid_minimal.json").read_text())
            spec[field] = value
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "09_impl_plan.json"
                path.write_text(json.dumps(spec))
                rendered = [e.render() for e in specdev_validate_file(str(_REPO_ROOT), str(path)) if e.code == "E520"]
            self.assertTrue(any(field in msg for msg in rendered), (field, rendered))
