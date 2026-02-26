import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.validate import validate_file


class Step14IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]
        self.fixtures_dir = self.repo_root / "tests" / "fixtures" / "step_14"

    def test_valid_roadmap_fixtures_pass_schema_validation(self):
        for name in ("valid_roadmap.json", "valid_roadmap_migration.json"):
            errors = validate_file(str(self.repo_root), str(self.fixtures_dir / name))
            self.assertEqual([], errors, msg=f"{name} failed validation: {errors}")

    def test_invalid_roadmap_fixtures_fail_validation(self):
        for name in (
            "invalid_date_order.json",
            "invalid_dependency_format.json",
            "invalid_dependency_missing_note.json",
            "invalid_missing_target_date.json",
            "invalid_missing_source_milestones.json",
            "invalid_status_enum.json",
            "invalid_risk_status_enum.json",
            "invalid_task_acceptance_criteria.json",
            "invalid_tech_mismatch.json",
            "invalid_task_format.json",
        ):
            errors = validate_file(str(self.repo_root), str(self.fixtures_dir / name))
            self.assertTrue(errors, msg=f"{name} unexpectedly passed validation")

    def test_milestones_are_in_chronological_order_for_valid_fixture(self):
        data = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        dates = [m.get("target_date") for m in data.get("milestones", [])]
        self.assertEqual(sorted(dates), dates, msg="Milestones are not in chronological order")

    def test_unknown_source_milestone_fails_referential_integrity(self):
        fixture = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        fixture["milestones"][0]["source_milestones"] = ["missing-from-step09"]
        tmp_path = self.fixtures_dir / "14_tmp_invalid_unknown_source_milestone.json"
        try:
            tmp_path.write_text(json.dumps(fixture), encoding="utf-8")
            errors = validate_file(str(self.repo_root), str(tmp_path))
            self.assertTrue(
                any("unknown source_milestone" in e for e in errors),
                msg=f"Expected unknown source_milestone error, got: {errors}",
            )
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_invalid_depends_on_cycle(self):
        errors = validate_file(str(self.repo_root), str(self.fixtures_dir / "invalid_depends_on_cycle.json"))
        self.assertTrue(errors, "Cycle fixture should fail validation")
        self.assertTrue(
            any("E141" in e for e in errors),
            f"Expected E141 TASK_DEPENDENCY_CYCLE error. Got: {errors}",
        )

    def test_valid_roadmap_with_refs(self):
        errors = validate_file(str(self.repo_root), str(self.fixtures_dir / "valid_roadmap_with_refs.json"))
        self.assertEqual([], errors, f"valid_roadmap_with_refs.json should pass validation. Errors: {errors}")

    def test_invalid_bad_fr_ref(self):
        # fr_ref cross-ref only fires when Step 04 artifact exists — create one in a tempdir
        fixture = json.loads((self.fixtures_dir / "invalid_bad_fr_ref.json").read_text(encoding="utf-8"))
        step04 = {
            "functional_requirements": [
                {"fr_id": "fr-user-login"},
                {"fr_id": "fr-user-registration"},
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            tmp_fixture = tmp_dir / "14_roadmap.json"
            tmp_fixture.write_text(json.dumps(fixture), encoding="utf-8")
            (tmp_dir / "04_fr_list.json").write_text(json.dumps(step04), encoding="utf-8")
            errors = validate_file(str(self.repo_root), str(tmp_fixture))
        self.assertTrue(errors, "Fixture with unknown fr_ref should fail validation")
        self.assertTrue(
            any("fr-does-not-exist" in e for e in errors),
            f"Expected unknown fr_ref error. Got: {errors}",
        )

    def test_e142_tech_stack_mismatch(self):
        """E142: roadmap tech not present in Step 09 tech_stack triggers error."""
        # Use valid_roadmap.json as base — it references python, javascript, fastapi, react, etc.
        fixture = json.loads(
            (self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8")
        )
        # Create Step 09 with a completely different tech stack so all roadmap tech names mismatch
        step09 = {
            "tech_stack": {
                "languages": [
                    {"name": "rust", "version": "1.70", "rationale": "Systems language"}
                ],
                "frameworks": [
                    {"name": "actix-web", "version": "4.0", "rationale": "Rust web framework"}
                ],
                "infrastructure": [],
                "tools": []
            },
            "milestones": [
                {
                    "milestone_id": "m1-core-foundation",
                    "deliverables": ["Health endpoint"]
                },
                {
                    "milestone_id": "m2-authentication",
                    "deliverables": ["Auth endpoints"]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            tmp_fixture = tmp_dir / "14_roadmap.json"
            tmp_fixture.write_text(json.dumps(fixture), encoding="utf-8")
            (tmp_dir / "09_impl_plan.json").write_text(json.dumps(step09), encoding="utf-8")
            errors = validate_file(str(self.repo_root), str(tmp_fixture))
        self.assertTrue(
            any("E142" in e for e in errors),
            f"Expected E142 TECH_STACK_MISMATCH error. Got: {errors}",
        )

    def test_missing_step09_artifact_fails_when_source_milestones_present(self):
        fixture = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            tmp_path = tmp_dir / "14_roadmap.json"
            tmp_path.write_text(json.dumps(fixture), encoding="utf-8")
            errors = validate_file(str(self.repo_root), str(tmp_path))
            self.assertTrue(
                any("Missing Step 09 artifact required for source_milestone integrity" in e for e in errors),
                msg=f"Expected missing Step 09 artifact error, got: {errors}",
            )


if __name__ == "__main__":
    unittest.main()
