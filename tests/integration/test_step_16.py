import unittest
import os
import json
import tempfile
from pathlib import Path

from specdev_tools.validation.validate import validate_file

class TestStep16(unittest.TestCase):
    def setUp(self):
        # Resolve to the toolkit root, not the host workspace root
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)
        self.fixtures_dir = str(toolkit_root / "tests" / "fixtures" / "step_16")

    def test_valid_minimal(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid minimal fixture should pass. Errors: {errors}")

    def test_valid_full(self):
        path = os.path.join(self.fixtures_dir, "valid_full.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid full fixture should pass. Errors: {errors}")

    def test_valid_empty_execution_and_review(self):
        path = os.path.join(self.fixtures_dir, "valid_empty_execution_review.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid empty execution/review fixture should pass. Errors: {errors}")

    def test_invalid_missing_evidence(self):
        # Expect failure because 'verified' implementation requires evidence in actions
        path = os.path.join(self.fixtures_dir, "invalid_missing_evidence.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing evidence) should fail validation")
        # Optional: check message content
        # print(f"Invalid Evidence Errors: {errors}")

    def test_invalid_bad_enum(self):
        # Expect failure due to bad enum
        path = os.path.join(self.fixtures_dir, "invalid_bad_enum.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (bad enum) should fail validation")
    
    def test_invalid_missing_nfr_refs(self):
        # Expect failure because non-deferred item has no nfr_refs
        path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing nfr_refs) should fail validation")
    
    def test_invalid_missing_fixture_ref(self):
        # Expect failure because non-deferred item has no fixture_ref
        path = os.path.join(self.fixtures_dir, "invalid_missing_fixture_ref.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing fixture_ref) should fail validation")
    
    def test_invalid_invalid_type(self):
        # Expect failure due to invalid type
        path = os.path.join(self.fixtures_dir, "invalid_invalid_type.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (invalid type) should fail validation")
    
    def test_invalid_invalid_layer(self):
        # Expect failure due to invalid layer
        path = os.path.join(self.fixtures_dir, "invalid_invalid_layer.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (invalid layer) should fail validation")
    
    def test_valid_with_new_fields(self):
        # Test that valid fixtures with new fields pass validation
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid minimal fixture with new fields should pass. Errors: {errors}")
    
    def test_valid_full_with_new_fields(self):
        # Test that valid_full fixture with new fields passes validation
        path = os.path.join(self.fixtures_dir, "valid_full.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid full fixture with new fields should pass. Errors: {errors}")

    def test_invalid_verified_red_ci(self):
        # E303: verdict=verified but ci_status=red should fail
        path = os.path.join(self.fixtures_dir, "invalid_verified_red_ci.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E303 fixture should fail validation")
        self.assertTrue(
            any("E303" in e for e in errors),
            f"Expected E303 error. Got: {errors}"
        )

    def test_invalid_unexecuted_planned(self):
        # E305: active checklist item not in satisfied_checklist_ids when CI is green
        path = os.path.join(self.fixtures_dir, "invalid_unexecuted_planned.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E305 fixture should fail validation")
        self.assertTrue(
            any("E305" in e for e in errors),
            f"Expected E305 error. Got: {errors}"
        )

    def test_valid_with_semantic_review(self):
        # Valid fixture with semantic_review populated and verdict=verified should pass
        path = os.path.join(self.fixtures_dir, "valid_with_semantic_review.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid semantic_review fixture should pass. Errors: {errors}")

    def test_invalid_missing_semantic_review(self):
        # verified verdict without semantic_review should fail schema allOf conditional
        path = os.path.join(self.fixtures_dir, "invalid_missing_semantic_review.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Missing semantic_review on verified verdict should fail validation")

    def test_invalid_verified_no_fixture_status(self):
        # E303: verified verdict with absent fixture_status should fire E303
        path = os.path.join(self.fixtures_dir, "invalid_verified_no_fixture_status.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Verified with no fixture_status should fail E303")
        self.assertTrue(
            any("E303" in e for e in errors),
            f"Expected E303 error for absent fixture_status. Got: {errors}"
        )

    def test_e304_roadmap_task_uncovered(self):
        # E304: roadmap has implement-logout but checklist only covers implement-login
        path = os.path.join(self.fixtures_dir, "e304_roadmap", "16_impl_context.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E304 fixture should fail validation")
        self.assertTrue(
            any("E304" in e for e in errors),
            f"Expected E304 error. Got: {errors}"
        )

    def test_e306_semantic_review_invalid_fr_id(self):
        """E306: fr_coverage with non-existent fr_id triggers E306."""
        # Load the valid semantic review fixture as base
        base_path = os.path.join(self.fixtures_dir, "valid_with_semantic_review.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Change the fr_id to something non-existent
        data["review"]["semantic_review"]["fr_coverage"][0]["fr_id"] = "fr-nonexistent"

        # Create Step 04 with known fr_ids
        step04 = {
            "functional_requirements": [
                {"fr_id": "fr-user-login"},
                {"fr_id": "fr-user-registration"}
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            # Write the modified fixture
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Write Step 04
            (tmp_dir / "04_fr_list.json").write_text(json.dumps(step04), encoding="utf-8")
            # Also need a seed_manifest for docs validation
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"docs_policy": {"doc_paths": ["README.md", "docs/**"]}}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        self.assertTrue(
            any("E306" in e for e in errors),
            f"Expected E306 error for non-existent fr_id. Got: {errors}"
        )

    def test_e306_semantic_review_valid_fr_id(self):
        """Valid fr_id in fr_coverage should not trigger E306."""
        base_path = os.path.join(self.fixtures_dir, "valid_with_semantic_review.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # The fixture has fr_id "fr-user-login" — make Step 04 include it
        step04 = {
            "functional_requirements": [
                {"fr_id": "fr-user-login"}
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir / "04_fr_list.json").write_text(json.dumps(step04), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"docs_policy": {"doc_paths": ["README.md", "docs/**"]}}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        e306_errors = [e for e in errors if "E306" in e]
        self.assertEqual(e306_errors, [], f"Did not expect E306 errors. Got: {e306_errors}")

    def test_e304_malformed_roadmap_reports_error(self):
        """E304: Malformed 14_roadmap.json should produce E304 parse/structure error, not silent pass."""
        base_path = os.path.join(self.fixtures_dir, "valid_with_semantic_review.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create a malformed roadmap (valid JSON, but unexpected structure)
        malformed_roadmap = {"not_milestones": "bad data"}

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir / "14_roadmap.json").write_text(json.dumps(malformed_roadmap), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"docs_policy": {"doc_paths": ["README.md", "docs/**"]}}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        # With the bug fix, a malformed roadmap should either produce E304 errors
        # or at least not silently pass. The roadmap missing 'milestones' key
        # should work (it defaults to empty list via .get("milestones", []))
        # so this test is really about ensuring the except clause doesn't swallow errors.
        # Let's test with truly invalid JSON instead:

        with tempfile.TemporaryDirectory() as td2:
            tmp_dir2 = Path(td2)
            fixture_path2 = tmp_dir2 / "16_impl_context.json"
            fixture_path2.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir2 / "14_roadmap.json").write_text("{invalid json", encoding="utf-8")
            common_dir2 = tmp_dir2 / "common"
            common_dir2.mkdir()
            (common_dir2 / "seed_manifest.json").write_text(
                json.dumps({"docs_policy": {"doc_paths": ["README.md", "docs/**"]}}),
                encoding="utf-8"
            )

            errors2 = validate_file(self.repo_root, str(fixture_path2))

        self.assertTrue(
            any("E304" in e for e in errors2),
            f"Expected E304 error for malformed roadmap JSON. Got: {errors2}"
        )

    def test_e307_behavior_validation_pairing(self):
        """E307: roadmap task with only behavior items (no validation) triggers E307."""
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create checklist with one roadmap task covered by behavior only (no validation)
        data["plan"]["spec_alignment"]["checklist"] = [
            {
                "id": "REQ_ONLY_BEHAVIOR",
                "spec_ref": {
                    "type": "code",
                    "id": "task-login-impl",
                    "line_range": "L1-L50",
                    "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                },
                "description": "Implement login endpoint",
                "type": "behavior",
                "layer": "api",
                "linked_test_expectation": "login returns 200",
                "nfr_refs": ["nfr-availability-uptime"],
                "fixture_ref": "fixture-login-api"
            }
        ]
        # Remove execution/review sections to avoid unrelated errors
        data.pop("execution", None)
        data["review"] = {}
        data["plan"].pop("review_requirements", None)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Create seed_manifest for docs validation
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"docs_policy": {"doc_paths": ["README.md", "docs/**"]}}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        self.assertTrue(
            any("E307" in e for e in errors),
            f"Expected E307 BEHAVIOR_VALIDATION_PAIRING error. Got: {errors}"
        )

    def _make_milestone_ref_fixture(self, tmpdir, checklist_items, roadmap_milestones):
        """Helper to create a step_16 fixture with roadmap for milestone_ref tests."""
        tmp_dir = Path(tmpdir)
        data = {
            "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
            "id": "step-ms-ref-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "seed_refs": [{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}],
            "spec_refs_ingested": [],
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Test milestone_ref binding.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": ["src/main.py"]
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": checklist_items
                },
                "docs_impact": {
                    "status": "required",
                    "rationale": "Code changes.",
                    "docs_touched": ["README.md"]
                },
                "review_requirements": {"test_commands": ["pytest tests/"]}
            },
            "generation_quality": {
                "preflight_passed": True,
                "evidence_records": [],
                "unresolved_inputs": [],
                "assumptions": [],
                "placeholder_scan": {"has_placeholders": False, "tokens_found": []},
                "self_check_results": []
            },
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": []
        }
        fixture_path = tmp_dir / "16_impl_context.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        roadmap = {"milestones": roadmap_milestones}
        (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")

        common_dir = tmp_dir / "common"
        common_dir.mkdir()
        (common_dir / "seed_manifest.json").write_text(
            json.dumps({"docs_policy": {"doc_paths": ["README.md", "docs/**"]}}),
            encoding="utf-8"
        )
        return str(fixture_path)

    def test_checklist_missing_milestone_ref_warns_W581(self):
        """W581: checklist item without milestone_ref field emits W581."""
        checklist = [{
            "id": "CHK_01",
            "spec_ref": {"type": "fr", "id": "task-login", "line_range": "L1-L10",
                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "description": "Implement login",
            "type": "behavior",
            "layer": "api",
            "linked_test_expectation": "pytest test_login",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-login"
        }, {
            "id": "CHK_01_VAL",
            "spec_ref": {"type": "fr", "id": "task-login", "line_range": "L1-L10",
                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "description": "Validate login",
            "type": "validation",
            "layer": "tests",
            "linked_test_expectation": "pytest test_login_val",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-login"
        }]
        milestones = [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": [{"task_id": "task-login"}]}]

        with tempfile.TemporaryDirectory() as td:
            path = self._make_milestone_ref_fixture(td, checklist, milestones)
            errors = validate_file(self.repo_root, path)

        self.assertTrue(
            any("W581" in e for e in errors),
            f"Expected W581 MILESTONE_REF_MISSING. Got: {errors}"
        )

    def test_checklist_valid_milestone_ref_passes(self):
        """Valid milestone_ref matching roadmap should not emit W581 or E582."""
        checklist = [{
            "id": "CHK_01",
            "spec_ref": {"type": "fr", "id": "task-login", "line_range": "L1-L10",
                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "description": "Implement login",
            "type": "behavior",
            "layer": "api",
            "linked_test_expectation": "pytest test_login",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-login",
            "milestone_ref": "ms-v1"
        }, {
            "id": "CHK_01_VAL",
            "spec_ref": {"type": "fr", "id": "task-login", "line_range": "L1-L10",
                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "description": "Validate login",
            "type": "validation",
            "layer": "tests",
            "linked_test_expectation": "pytest test_login_val",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-login",
            "milestone_ref": "ms-v1"
        }]
        milestones = [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": [{"task_id": "task-login"}]}]

        with tempfile.TemporaryDirectory() as td:
            path = self._make_milestone_ref_fixture(td, checklist, milestones)
            errors = validate_file(self.repo_root, path)

        w581 = [e for e in errors if "W581" in e]
        e582 = [e for e in errors if "E582" in e]
        self.assertEqual(w581, [], f"Did not expect W581. Got: {w581}")
        self.assertEqual(e582, [], f"Did not expect E582. Got: {e582}")

    def test_checklist_wrong_milestone_ref_errors(self):
        """milestone_ref not matching task_to_milestone mapping should emit E582."""
        checklist = [{
            "id": "CHK_01",
            "spec_ref": {"type": "fr", "id": "task-login", "line_range": "L1-L10",
                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "description": "Implement login",
            "type": "behavior",
            "layer": "api",
            "linked_test_expectation": "pytest test_login",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-login",
            "milestone_ref": "ms-WRONG"
        }, {
            "id": "CHK_01_VAL",
            "spec_ref": {"type": "fr", "id": "task-login", "line_range": "L1-L10",
                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "description": "Validate login",
            "type": "validation",
            "layer": "tests",
            "linked_test_expectation": "pytest test_login_val",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-login",
            "milestone_ref": "ms-v1"
        }]
        milestones = [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": [{"task_id": "task-login"}]}]

        with tempfile.TemporaryDirectory() as td:
            path = self._make_milestone_ref_fixture(td, checklist, milestones)
            errors = validate_file(self.repo_root, path)

        self.assertTrue(
            any("E582" in e for e in errors),
            f"Expected E582 milestone_ref mismatch. Got: {errors}"
        )

if __name__ == '__main__':
    unittest.main()
