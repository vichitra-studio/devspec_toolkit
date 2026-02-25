import unittest
import os
import json
import sys
from pathlib import Path

# Ensure local tools package is importable when tests run from repo roots
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from specdev_tools.validate import validate_file

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

if __name__ == '__main__':
    unittest.main()
