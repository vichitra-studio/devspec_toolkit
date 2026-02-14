import unittest
import os
import json
import hashlib
import sys
import tempfile
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

    def test_invalid_missing_plan_summary(self):
        # Expect failure because plan.summary is now required at schema level
        path = os.path.join(self.fixtures_dir, "invalid_missing_plan_summary.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing plan.summary) should fail validation")

    def test_invalid_missing_plan_docs_impact(self):
        # Expect failure because plan.docs_impact is now required at schema level
        path = os.path.join(self.fixtures_dir, "invalid_missing_plan_docs_impact.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing plan.docs_impact) should fail validation")

    def test_invalid_missing_plan_spec_alignment(self):
        # Expect failure because plan.spec_alignment is now required at schema level
        path = os.path.join(self.fixtures_dir, "invalid_missing_plan_spec_alignment.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing plan.spec_alignment) should fail validation")

    def test_invalid_missing_plan_review_requirements(self):
        # Expect failure because plan.review_requirements is now required at schema level
        path = os.path.join(self.fixtures_dir, "invalid_missing_plan_review_requirements.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing plan.review_requirements) should fail validation")

    def test_valid_delivery_planned_with_verification(self):
        # Expect pass: plan.delivery.status == planned includes structured delivery verification evidence
        path = os.path.join(self.fixtures_dir, "valid_delivery_planned_with_verification.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid fixture (delivery planned with verification) should pass. Errors: {errors}")

    def test_invalid_delivery_planned_missing_verification(self):
        # Expect failure: planned delivery requires at least one verification entry in review.delivery_status
        path = os.path.join(self.fixtures_dir, "invalid_delivery_planned_missing_verification.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (delivery planned missing verification) should fail validation")

    def test_invalid_delivery_planned_unverified_items(self):
        # Expect failure: planned dashboard/alert items must have matching verification entries
        path = os.path.join(self.fixtures_dir, "invalid_delivery_planned_unverified_items.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (delivery planned with unverified dashboard/alert items) should fail validation")
    
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

    def test_invalid_execution_files_touched_out_of_scope(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["execution"] = {
            "files_touched": ["scripts/out_of_scope.sh"],
            "execution_results": [
                {
                    "status": "failed",
                    "outcome_description": "Command failed",
                    "reasoning": "Expected failure for scope test",
                    "command": "echo scope",
                    "evidence": "scope validation failed in deterministic test case"
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            step_dir = os.path.join(tmp_dir, "step_16")
            os.makedirs(step_dir, exist_ok=True)
            tmp_path = os.path.join(step_dir, "invalid_execution_scope.json")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2)
            errors = validate_file(self.repo_root, tmp_path)
            self.assertTrue(
                any("touched by execution but not covered by target_file_patterns" in e for e in errors),
                f"Expected execution scope error. Errors: {errors}",
            )

    def test_invalid_planned_non_doc_scope_requires_docs_impact_required(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["plan"]["docs_impact"]["status"] = "not_required"
        payload["plan"]["docs_impact"].pop("docs_touched", None)
        with tempfile.TemporaryDirectory() as tmp_dir:
            step_dir = os.path.join(tmp_dir, "step_16")
            os.makedirs(step_dir, exist_ok=True)
            tmp_path = os.path.join(step_dir, "invalid_docs_impact_required.json")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2)
            errors = validate_file(self.repo_root, tmp_path)
            self.assertTrue(
                any("docs_impact.status must be 'required'" in e for e in errors),
                f"Expected docs_impact requirement error. Errors: {errors}",
            )

    def test_invalid_docs_touched_must_be_in_target_file_patterns(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["plan"]["docs_impact"]["docs_touched"] = ["docs/architecture.md"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            step_dir = os.path.join(tmp_dir, "step_16")
            os.makedirs(step_dir, exist_ok=True)
            tmp_path = os.path.join(step_dir, "invalid_docs_touched_scope.json")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2)
            errors = validate_file(self.repo_root, tmp_path)
            self.assertTrue(
                any("docs_touched includes paths outside plan.summary.target_file_patterns" in e for e in errors),
                f"Expected docs_touched scope error. Errors: {errors}",
            )

    def test_invalid_execution_passed_result_with_bad_evidence_hash(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        evidence = "tests/auth/test_login.py::test_login PASSED [100%] deterministic evidence block"
        good_sha = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        payload["execution"] = {
            "files_touched": ["src/auth.py", "README.md"],
            "execution_results": [
                {
                    "status": "passed",
                    "outcome_description": "Ran linked tests",
                    "reasoning": "Linked test command passed",
                    "command": "pytest -q",
                    "evidence": evidence,
                    "evidence_ref": f"sha256:{good_sha}",
                    "evidence_binding": {
                        "timestamp": "2026-02-13T00:00:00Z",
                        "sha256": "0" * 64,
                        "exit_code": 0,
                        "command": "pytest -q"
                    }
                }
            ],
            "critical_evidence": {
                "satisfied_checklist_ids": ["REQ_CORE_001"],
                "passed_test_commands": ["pytest -q"]
            }
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            step_dir = os.path.join(tmp_dir, "step_16")
            os.makedirs(step_dir, exist_ok=True)
            tmp_path = os.path.join(step_dir, "invalid_bad_evidence_hash.json")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2)
            errors = validate_file(self.repo_root, tmp_path)
            self.assertTrue(
                any("invalid evidence_binding.sha256" in e for e in errors),
                f"Expected evidence hash mismatch error. Errors: {errors}",
            )

    def test_invalid_execution_missing_review_test_command_coverage(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["execution"] = {
            "files_touched": ["src/auth.py", "README.md"],
            "execution_results": [
                {
                    "status": "failed",
                    "outcome_description": "Ran wrong command",
                    "reasoning": "Used wrong command for coverage check",
                    "command": "echo noop",
                    "evidence": "noop command output that is long enough for validation"
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            step_dir = os.path.join(tmp_dir, "step_16")
            os.makedirs(step_dir, exist_ok=True)
            tmp_path = os.path.join(step_dir, "invalid_missing_review_command_coverage.json")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2)
            errors = validate_file(self.repo_root, tmp_path)
            self.assertTrue(
                any("missing required plan.review_requirements.test_commands" in e for e in errors),
                f"Expected review command coverage error. Errors: {errors}",
            )

    def test_invalid_execution_sensitive_evidence_content(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["execution"] = {
            "files_touched": ["src/auth.py", "README.md"],
            "execution_results": [
                {
                    "status": "failed",
                    "outcome_description": "Captured command output",
                    "reasoning": "Secret safety check",
                    "command": "echo token",
                    "evidence": "token=ghp_123456789012345678901234567890123456",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            step_dir = os.path.join(tmp_dir, "step_16")
            os.makedirs(step_dir, exist_ok=True)
            tmp_path = os.path.join(step_dir, "invalid_sensitive_evidence.json")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2)
            errors = validate_file(self.repo_root, tmp_path)
            self.assertTrue(
                any("sensitive content classes" in e for e in errors),
                f"Expected sensitive evidence validation error. Errors: {errors}",
            )
        
if __name__ == '__main__':
    unittest.main()
