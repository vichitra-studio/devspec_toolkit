import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from specdev_tools.validation.validate import validate_file
from unit.graph._synth import accept_links, graph_check

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_14"

# The worked example of the spec-graph design (roadmap milestone, task and task criteria, "New" form).
_DOC_EXAMPLE_MILESTONE: dict[str, Any] = {
    "milestone_id": "ms-account-recovery",
    "name": "Account Recovery",
    "target_date": "2026-12-15",
    "user_story": "As a registered member, I want to reset a forgotten password so that I can get back in without support.",
    "tasks": [
        {
            "task_id": "task-implement-password-reset-confirm",
            "description": "Implement the confirm endpoint that redeems a reset token and sets the new password.",
            "acceptance_criteria": [
                {
                    "criterion_id": "tc-confirm-expired-token",
                    "text": (
                        "POST /v1/password-resets/{token} with a token issued 31 minutes earlier returns HTTP 410 "
                        "with error token-expired and leaves the password hash unchanged."
                    ),
                    "refines": ["ac-password-reset-3"],
                    "verified_by": ["fix-password-reset-expired-token"],
                },
                {
                    "criterion_id": "tc-confirm-reused-token",
                    "text": "A second redemption of a token that already changed the password returns HTTP 410, even within 30 minutes.",
                    "refines": ["inv-reset-token-single-use"],
                    "verified_by": ["fix-password-reset-reused-token"],
                },
            ],
        }
    ],
}

_TEMP_NAME = "14_tmp_roadmap.json"


class Step14IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = _REPO_ROOT
        self.fixtures_dir = _FIXTURES

    def _errors(self, mutate: Callable[[dict], None]) -> list[Any]:
        """Validation errors for the valid fixture with the design-doc milestone, after ``mutate`` edits the copy."""
        spec = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        spec["milestones"] = [copy.deepcopy(_DOC_EXAMPLE_MILESTONE)]
        mutate(spec)
        tmp_path = self.fixtures_dir / _TEMP_NAME
        try:
            tmp_path.write_text(json.dumps(spec), encoding="utf-8")
            return validate_file(str(self.repo_root), str(tmp_path))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def _assert_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = [e.render() for e in self._errors(mutate)]
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_doc_example_validates(self):
        self.assertEqual([], [e.render() for e in self._errors(lambda spec: None) if e.code == "E520"])

    def test_task_criterion_without_refines_or_removes_rejected(self):
        def drop_refines(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["acceptance_criteria"][0].pop("refines")

        self._assert_fails_naming(drop_refines, "acceptance_criteria/0")

    def test_removes_criterion_without_refines_accepted(self):
        def removes_only(spec: dict) -> None:
            criterion = spec["milestones"][0]["tasks"][0]["acceptance_criteria"][0]
            criterion.pop("refines")
            criterion["removes"] = ["api-legacy-password-reset"]

        self.assertEqual([], [e for e in self._errors(removes_only) if e.code == "E520"])

    def test_task_deferred_without_reason_rejected(self):
        def deferred_no_reason(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["disposition"] = {"value": "deferred"}

        self._assert_fails_naming(deferred_no_reason, "reason")

    def test_task_deferred_with_reason_accepted(self):
        def deferred(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["disposition"] = {
                "value": "deferred",
                "reason": "Blocked on vendor API access; resume once sandbox credentials are granted.",
            }

        self.assertEqual([], [e for e in self._errors(deferred) if e.code == "E520"])

    def test_no_status_property_on_milestone_or_task(self):
        self._assert_fails_naming(lambda spec: spec["milestones"][0].update(status="pending"), "status")
        self._assert_fails_naming(lambda spec: spec["milestones"][0]["tasks"][0].update(status="pending"), "status")
        self._assert_fails_naming(lambda spec: spec["milestones"][0]["tasks"][0].update(status_reason="r"), "status_reason")

    def test_removed_fields_are_rejected(self):
        for field, value in (("tech_stack", {}), ("dependencies", []), ("trace", [])):
            with self.subTest(field=field):
                self._assert_fails_naming(lambda spec, f=field, v=value: spec.update({f: v}), field)
        for field in ("fr_refs", "capability_refs", "source_milestones", "deliverables"):
            with self.subTest(field=field):
                self._assert_fails_naming(lambda spec, f=field: spec["milestones"][0].update({f: []}), field)
        for field in ("assumptions", "exit_conditions", "fr_refs", "invariant_refs"):
            with self.subTest(field=field):
                self._assert_fails_naming(lambda spec, f=field: spec["milestones"][0]["tasks"][0].update({f: []}), field)

    def test_fixture_ref_is_replaced_by_verified_by(self):
        def old_name(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["acceptance_criteria"][0]["fixture_ref"] = "fix-x"

        self._assert_fails_naming(old_name, "fixture_ref")

    def test_valid_roadmap_fixtures_pass_schema_validation(self):
        for name in (
            "valid_roadmap.json",
            "valid_roadmap_migration.json",
            "valid_roadmap_with_refs.json",
            "valid_refines_invariant.json",
        ):
            errors = validate_file(str(self.repo_root), str(self.fixtures_dir / name))
            self.assertEqual([], errors, msg=f"{name} failed validation: {errors}")

    def test_invalid_roadmap_fixtures_fail_validation(self):
        for name in (
            "invalid_date_order.json",
            "invalid_missing_target_date.json",
            "invalid_missing_refines.json",
            "invalid_disposition_value.json",
            "invalid_disposition_without_reason.json",
            "invalid_risk_status_enum.json",
            "invalid_task_acceptance_criteria.json",
        ):
            errors = validate_file(str(self.repo_root), str(self.fixtures_dir / name))
            self.assertTrue(errors, msg=f"{name} unexpectedly passed validation")

    def test_milestones_are_in_chronological_order_for_valid_fixture(self):
        data = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        dates = [m.get("target_date") for m in data.get("milestones", [])]
        self.assertEqual(sorted(dates), dates, msg="Milestones are not in chronological order")

    def _as_step_14_file(self, fixture: str, folder: str) -> Path:
        """Copy *fixture* to ``<folder>/14_roadmap.json``, the name the registry knows."""
        target = Path(folder) / "14_roadmap.json"
        shutil.copyfile(self.fixtures_dir / fixture, target)
        return target

    def test_invalid_depends_on_cycle(self):
        """A task cycle is E703 from ``spec-check``, owned by step 14; the single-file validator no longer reports it."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._as_step_14_file("invalid_depends_on_cycle.json", tmp)
            self.assertEqual([], validate_file(str(self.repo_root), str(path)))
            graph = graph_check(accept_links(Path(tmp)))
        self.assertEqual("FAIL", graph["status"])
        self.assertEqual([("E703", "step:14")], [(f["code"], f["owner"]) for f in graph["findings"]])
        for task in ("task-a", "task-b", "task-c"):
            self.assertIn(task, graph["findings"][0]["message"])

    def test_invalid_task_format_duplicate_task_id_is_e704(self):
        """The fixture repeats a task id: the one-file id check of ``validate`` reports it as E704."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._as_step_14_file("invalid_task_format.json", tmp)
            errors = validate_file(str(self.repo_root), str(path))
        self.assertEqual([("E704", "step:14", "setup-health-check")], [(e.code, e.owner, e.node_id) for e in errors])

    def test_valid_roadmap_with_refs(self):
        errors = validate_file(str(self.repo_root), str(self.fixtures_dir / "valid_roadmap_with_refs.json"))
        self.assertEqual([], errors, f"valid_roadmap_with_refs.json should pass validation. Errors: {errors}")

    def test_no_cross_step_check_on_upstream_ids(self):
        """No sibling artifact is read: a roadmap whose criteria refine unknown ids and sit beside no 09/04/01 passes."""
        errors = validate_file(str(self.repo_root), str(self.fixtures_dir / "valid_roadmap.json"))
        self.assertEqual([], [e for e in errors if e.code in {"E590", "W590", "E142"}])


if __name__ == "__main__":
    unittest.main()
