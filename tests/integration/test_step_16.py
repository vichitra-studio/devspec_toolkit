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
        self.assertTrue(any(e.code == "E301" for e in errors), f"Expected E301. Got: {errors}")

    def test_invalid_bad_enum(self):
        # Expect failure due to bad enum
        path = os.path.join(self.fixtures_dir, "invalid_bad_enum.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (bad enum) should fail validation")
        self.assertTrue(any(e.code == "E530" for e in errors), f"Expected E530. Got: {errors}")
    
    def test_invalid_missing_nfr_refs(self):
        # Expect failure because non-deferred item has no nfr_refs
        path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing nfr_refs) should fail validation")
        self.assertTrue(any(e.code == "E520" for e in errors), f"Expected E520. Got: {errors}")
    
    def test_invalid_missing_fixture_ref(self):
        # Expect failure because non-deferred item has no fixture_ref
        path = os.path.join(self.fixtures_dir, "invalid_missing_fixture_ref.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing fixture_ref) should fail validation")
        self.assertTrue(any(e.code == "E520" for e in errors), f"Expected E520. Got: {errors}")
    
    def test_invalid_invalid_type(self):
        # Expect failure due to invalid type
        path = os.path.join(self.fixtures_dir, "invalid_invalid_type.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (invalid type) should fail validation")
        self.assertTrue(any(e.code == "E530" for e in errors), f"Expected E530. Got: {errors}")
    
    def test_invalid_invalid_layer(self):
        # Expect failure due to invalid layer
        path = os.path.join(self.fixtures_dir, "invalid_invalid_layer.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (invalid layer) should fail validation")
        self.assertTrue(any(e.code == "E530" for e in errors), f"Expected E530. Got: {errors}")
    
    def test_invalid_verified_red_ci(self):
        # E303: verdict=verified but ci_status=red should fail
        path = os.path.join(self.fixtures_dir, "invalid_verified_red_ci.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E303 fixture should fail validation")
        self.assertTrue(
            any(e.code == "E303" for e in errors),
            f"Expected E303 error. Got: {errors}"
        )

    def test_invalid_unexecuted_planned(self):
        # E305: active checklist item not in satisfied_checklist_ids when CI is green
        path = os.path.join(self.fixtures_dir, "invalid_unexecuted_planned.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E305 fixture should fail validation")
        self.assertTrue(
            any(e.code == "E305" for e in errors),
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
        self.assertTrue(any(e.code == "E520" for e in errors), f"Expected E520. Got: {errors}")

    def test_invalid_verified_no_fixture_status(self):
        # E303: verified verdict with absent fixture_status should fire E303
        path = os.path.join(self.fixtures_dir, "invalid_verified_no_fixture_status.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Verified with no fixture_status should fail E303")
        self.assertTrue(
            any(e.code == "E303" for e in errors),
            f"Expected E303 error for absent fixture_status. Got: {errors}"
        )

    def test_e304_roadmap_task_uncovered(self):
        # E304: roadmap has implement-logout but checklist only covers implement-login
        path = os.path.join(self.fixtures_dir, "e304_roadmap", "impl_context", "ms_test_plan.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E304 fixture should fail validation")
        self.assertTrue(
            any(e.code == "E304" for e in errors),
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
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        self.assertTrue(
            any(e.code == "E306" for e in errors),
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
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        e306_errors = [e for e in errors if e.code == "E306"]
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
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir / "14_roadmap.json").write_text(json.dumps(malformed_roadmap), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )

            validate_file(self.repo_root, str(fixture_path))

        # With the bug fix, a malformed roadmap should either produce E304 errors
        # or at least not silently pass. The roadmap missing 'milestones' key
        # should work (it defaults to empty list via .get("milestones", []))
        # so this test is really about ensuring the except clause doesn't swallow errors.
        # Let's test with truly invalid JSON instead:

        with tempfile.TemporaryDirectory() as td2:
            tmp_dir2 = Path(td2)
            impl_context_dir2 = tmp_dir2 / "impl_context"
            impl_context_dir2.mkdir()
            fixture_path2 = impl_context_dir2 / "ms_test_plan.json"
            fixture_path2.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir2 / "14_roadmap.json").write_text("{invalid json", encoding="utf-8")
            common_dir2 = tmp_dir2 / "common"
            common_dir2.mkdir()
            (common_dir2 / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )

            errors2 = validate_file(self.repo_root, str(fixture_path2))

        self.assertTrue(
            any(e.code == "E304" for e in errors2),
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
                    "type": "fr",
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
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        self.assertTrue(
            any(e.code == "E307" for e in errors),
            f"Expected E307 BEHAVIOR_VALIDATION_PAIRING error. Got: {errors}"
        )

    def test_e307_code_spec_ref_type_excluded(self):
        """E307 does NOT fire when spec_ref.type is 'code' — non-behavioral work items are excluded."""
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # code-type spec_ref with behavior-only checklist — should NOT trigger E307
        data["plan"]["spec_alignment"]["checklist"] = [
            {
                "id": "WORK_ITEM_B",
                "spec_ref": {
                    "type": "code",
                    "id": "task-code-impl",
                    "line_range": "L1-L50",
                    "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                },
                "description": "Implement code change",
                "type": "behavior",
                "layer": "api",
                "linked_test_expectation": "passes tests",
                "nfr_refs": ["nfr-availability-uptime"],
                "fixture_ref": "fixture-impl"
            }
        ]
        data.pop("execution", None)
        data["review"] = {}
        data["plan"].pop("review_requirements", None)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))

        e307_errors = [e for e in errors if e.code == "E307"]
        self.assertEqual(e307_errors, [], f"Did not expect E307 for code spec_ref.type. Got: {e307_errors}")

    def _make_milestone_ref_fixture(self, tmpdir, checklist_items, roadmap_milestones):
        """Helper to create a step_16 fixture with roadmap for milestone_ref tests."""
        tmp_dir = Path(tmpdir)
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-ms-ref-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
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
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": []
        }
        impl_context_dir = tmp_dir / "impl_context"
        impl_context_dir.mkdir(exist_ok=True)
        fixture_path = impl_context_dir / "ms_test_plan.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        roadmap = {"milestones": roadmap_milestones}
        (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")

        common_dir = tmp_dir / "common"
        common_dir.mkdir()
        (common_dir / "seed_manifest.json").write_text(
            json.dumps({"doc_paths": ["README.md", "docs/**"]}),
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
            any(e.code == "W581" for e in errors),
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

        w581 = [e for e in errors if e.code == "W581"]
        e582 = [e for e in errors if e.code == "E582"]
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
            any(e.code == "E582" for e in errors),
            f"Expected E582 milestone_ref mismatch. Got: {errors}"
        )

    def _make_e304_fixture(self, tmpdir, impl_context_data, roadmap_milestones):
        """Helper to write a step_16 fixture + roadmap for E304 tests.

        The fixture is placed inside impl_context/ so _is_anchor() correctly
        identifies it as a 16a plan (not an anchor) and E304/W581 fire as expected.
        The roadmap is at the parent level (tmp_dir/14_roadmap.json).
        """
        tmp_dir = Path(tmpdir)
        impl_context_dir = tmp_dir / "impl_context"
        impl_context_dir.mkdir(exist_ok=True)
        fixture_path = impl_context_dir / "ms_test_plan.json"
        fixture_path.write_text(json.dumps(impl_context_data), encoding="utf-8")
        roadmap = {"milestones": roadmap_milestones}
        (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")
        common_dir = tmp_dir / "common"
        common_dir.mkdir(exist_ok=True)
        (common_dir / "seed_manifest.json").write_text(
            json.dumps({"doc_paths": []}),
            encoding="utf-8"
        )
        return str(fixture_path)

    def _minimal_impl_context(self, checklist_items, milestone_ref=None):
        """Build a minimal impl_context dict for E304 tests."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-e304-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "E304 test case.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": []
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": checklist_items
                },
                "docs_impact": {"status": "not_required", "rationale": "No code changes."}
            },
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": []
        }
        if milestone_ref is not None:
            data["milestone_ref"] = milestone_ref
        return data

    def _make_checklist_item(self, item_id, task_id, milestone_ref=None):
        """Build a minimal valid checklist item referencing a roadmap task_id."""
        item = {
            "id": item_id,
            "spec_ref": {
                "type": "fr",
                "id": task_id,
                "line_range": "L1-L10",
                "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"
            },
            "description": f"Implement {task_id}",
            "type": "behavior",
            "layer": "api",
            "linked_test_expectation": f"pytest test_{task_id}",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": f"fixture-{task_id}",
        }
        if milestone_ref is not None:
            item["milestone_ref"] = milestone_ref
        return item

    def test_e304_milestone_ref_scoping(self):
        """E304 fires for uncovered tasks only within the scoped milestone (m1), not m2."""
        # Checklist only covers t1; t2 is in m1 (uncovered); t3 is in m2 (out of scope)
        checklist = [
            self._make_checklist_item("CHK_T1_B", "t1", milestone_ref="m1"),
            self._make_checklist_item("CHK_T1_V", "t1", milestone_ref="m1"),
        ]
        # Add validation pair for t1 so E307 doesn't fire
        checklist[1]["type"] = "validation"
        checklist[1]["layer"] = "tests"

        roadmap_milestones = [
            {
                "milestone_id": "m1",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{"task_id": "t1"}, {"task_id": "t2"}]
            },
            {
                "milestone_id": "m2",
                "status": "planned",
                "fr_refs": [],
                "tasks": [{"task_id": "t3"}]
            }
        ]

        impl_context = self._minimal_impl_context(checklist, milestone_ref="m1")

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        e304_messages = [e.message for e in e304_errors]

        # t2 is in m1 (the scoped milestone) and uncovered — must fire E304
        self.assertTrue(
            any("t2" in msg for msg in e304_messages),
            f"Expected E304 for uncovered task 't2' in milestone m1. Got E304 errors: {e304_messages}"
        )
        # t3 is in m2 (out of scope) — must NOT fire E304
        self.assertFalse(
            any("t3" in msg for msg in e304_messages),
            f"Did not expect E304 for task 't3' in out-of-scope milestone m2. Got E304 errors: {e304_messages}"
        )

    def test_e304_skips_done_milestones(self):
        """E304 skips milestones with status 'done'; fires only for in_progress milestones."""
        # Checklist is empty — no tasks covered
        checklist = []

        roadmap_milestones = [
            {
                "milestone_id": "ms-done",
                "status": "done",
                "fr_refs": [],
                "tasks": [{"task_id": "t1"}]
            },
            {
                "milestone_id": "ms-active",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{"task_id": "t2"}]
            }
        ]

        # No milestone_ref set — should include non-done milestones only
        impl_context = self._minimal_impl_context(checklist)

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        e304_messages = [e.message for e in e304_errors]

        # t2 is in in_progress milestone — must fire E304
        self.assertTrue(
            any("t2" in msg for msg in e304_messages),
            f"Expected E304 for uncovered task 't2' in in_progress milestone. Got E304 errors: {e304_messages}"
        )
        # t1 is in done milestone — must NOT fire E304
        self.assertFalse(
            any("t1" in msg for msg in e304_messages),
            f"Did not expect E304 for task 't1' in done milestone. Got E304 errors: {e304_messages}"
        )

    def test_invalid_verified_no_semantic_review(self):
        """E520: verified verdict without semantic_review triggers schema allOf violation."""
        path = os.path.join(self.fixtures_dir, "invalid_verified_no_semantic_review.json")
        errors = validate_file(self.repo_root, path)

        self.assertTrue(len(errors) > 0, "Fixture with verified verdict but no semantic_review should fail validation")

        e520_errors = [e for e in errors if e.code == "E520"]
        self.assertTrue(
            len(e520_errors) > 0,
            f"Expected at least one E520 error. Got: {errors}"
        )
        self.assertTrue(
            any("semantic_review" in e.message for e in e520_errors),
            f"Expected an E520 error mentioning 'semantic_review'. Got E520 errors: {[e.message for e in e520_errors]}"
        )

    def test_valid_with_emergent_ambiguities(self):
        """Valid fixture with emergent_ambiguities covering 'low' and 'high' severities should pass."""
        path = os.path.join(self.fixtures_dir, "valid_with_emergent_ambiguities.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid emergent_ambiguities fixture should pass. Errors: {errors}")

    def test_invalid_emergent_ambiguity_severity(self):
        """emergent_ambiguities entry with invalid severity value should fail schema validation."""
        path = os.path.join(self.fixtures_dir, "invalid_emergent_ambiguity_severity.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            len(errors) > 0,
            "Invalid emergent_ambiguity severity fixture should fail validation"
        )
        self.assertTrue(any(e.code == "E520" for e in errors), f"Expected E520. Got: {errors}")

    def test_e582_artifact_milestone_ref_not_in_roadmap(self):
        """E582: top-level milestone_ref pointing to a non-existent roadmap milestone fires E582."""
        # Roadmap has milestone 'ms-real'; artifact claims milestone_ref='ms-ghost' (does not exist)
        checklist = [
            self._make_checklist_item("CHK_T1_B", "t1", milestone_ref="ms-ghost"),
            self._make_checklist_item("CHK_T1_V", "t1", milestone_ref="ms-ghost"),
        ]
        checklist[1]["type"] = "validation"
        checklist[1]["layer"] = "tests"

        roadmap_milestones = [
            {
                "milestone_id": "ms-real",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{"task_id": "t1"}, {"task_id": "t2"}]
            }
        ]

        # milestone_ref at artifact level points to a non-existent milestone
        impl_context = self._minimal_impl_context(checklist, milestone_ref="ms-ghost")

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e582_errors = [e for e in errors if e.code == "E582"]
        self.assertTrue(
            len(e582_errors) > 0,
            f"Expected E582 for artifact milestone_ref 'ms-ghost' not in roadmap. Got: {errors}"
        )
        self.assertTrue(
            any("ms-ghost" in e.message for e in e582_errors),
            f"Expected E582 message to contain 'ms-ghost'. Got E582 errors: {[e.message for e in e582_errors]}"
        )


    def test_step_16c_w582_fires_when_milestone_fr_not_in_fr_coverage(self):
        """When verdict=='verified' and a milestone FR is not in semantic_review.fr_coverage, W582 fires."""
        from specdev_tools.validation.validators.step_16c import validate_step_16c

        # Build a valid 16c artifact with verdict=verified and fr_coverage only covering fr-login.
        # The roadmap milestone ms-v1 has fr_refs: [fr-login, fr-logout].
        # W582 should fire for fr-logout (present in milestone but absent from fr_coverage).
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-w582-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "W582 test: milestone FR not covered.",
                    "scope_in": ["auth-api"],
                    "scope_out": [],
                    "target_file_patterns": ["src/auth.py"]
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Auth", "summary": "Test"}],
                    "checklist": [
                        {
                            "id": "CHK_LOGIN_B",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10",
                                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Implement login",
                            "type": "behavior",
                            "layer": "api",
                            "linked_test_expectation": "POST /login returns 200",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login",
                            "milestone_ref": "ms-v1",
                            "implementation": {
                                "status": "verified",
                                "files_touched": ["src/auth.py"],
                                "actions": [
                                    {
                                        "type": "file_edit",
                                        "target": "src/auth.py",
                                        "description": "Add login handler",
                                        "evidence": {"type": "snippet", "content": "def login(): pass"}
                                    }
                                ]
                            }
                        },
                        {
                            "id": "CHK_LOGIN_V",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10",
                                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Validate login",
                            "type": "validation",
                            "layer": "tests",
                            "linked_test_expectation": "pytest test_login",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login",
                            "milestone_ref": "ms-v1",
                            "implementation": {
                                "status": "verified",
                                "files_touched": ["tests/test_auth.py"],
                                "actions": [
                                    {
                                        "type": "manual_verification",
                                        "description": "Verify test passes",
                                        "evidence": {"type": "log", "content": "PASSED test_login"}
                                    }
                                ]
                            }
                        }
                    ]
                },
                "docs_impact": {"status": "not_required", "rationale": "No doc changes."},
                "review_requirements": {"test_commands": ["pytest tests/"]}
            },
            "execution": {
                "execution_results": [
                    {
                        "command": "pytest tests/",
                        "status": "passed",
                        "outcome_description": "All tests passed.",
                        "reasoning": "Tests cover login.",
                        "evidence": "1 passed",
                        "evidence_ref": "ci-001",
                        "evidence_binding": {
                            "timestamp": "2024-01-01T00:00:00Z",
                            "sha256": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                            "exit_code": 0,
                            "command": "pytest tests/"
                        }
                    }
                ],
                "final_status": {"ci_status": "green"},
                "critical_evidence": {
                    "passed_test_commands": ["pytest tests/"],
                    "satisfied_checklist_ids": ["CHK_LOGIN_B", "CHK_LOGIN_V"]
                }
            },
            "review": {
                "verdict": "verified",
                "fixture_status": {
                    "implemented_interfaces": ["auth-login"],
                    "test_results": [{"fixture_ref": "fixture-login", "status": "pass"}],
                    "ci_status": "green"
                },
                "semantic_review": {
                    "fr_coverage": [
                        {
                            "fr_id": "fr-login",
                            "satisfied": True,
                            "evidence_summary": "Login endpoint implemented and verified.",
                            "checklist_ids": ["CHK_LOGIN_B"]
                        }
                    ],
                    "hallucinated_features": [],
                    "scope_delta": "None."
                }
            },
            "canonical_refs_used": []
        }

        # Roadmap has fr_refs: [fr-login, fr-logout] for ms-v1
        roadmap = {
            "milestones": [
                {
                    "milestone_id": "ms-v1",
                    "fr_refs": ["fr-login", "fr-logout"],
                    "tasks": [{"task_id": "fr-login"}, {"task_id": "fr-logout"}]
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": []}), encoding="utf-8"
            )

            errors = validate_step_16c(data, self.repo_root, spec_path=str(fixture_path))

        w582_errors = [e for e in errors if e.code == "W582"]

        # W582 should fire for fr-logout (in milestone but not in fr_coverage)
        self.assertTrue(
            any("fr-logout" in e.message for e in w582_errors),
            f"Expected W582 for 'fr-logout'. Got W582 errors: {[e.message for e in w582_errors]}"
        )

        # W582 should NOT fire for fr-login (covered in fr_coverage)
        self.assertFalse(
            any("fr-login" in e.message for e in w582_errors),
            f"Did not expect W582 for 'fr-login'. Got W582 errors: {[e.message for e in w582_errors]}"
        )

    def test_step_16c_w582_does_not_fire_when_verdict_is_not_verified(self):
        """W582 must NOT fire when verdict is needs_work, blocked, or deferred."""
        from specdev_tools.validation.validators.step_16c import validate_step_16c

        # Roadmap has fr_refs for ms-v1 but fr_coverage is empty/absent.
        # W582 must stay silent for all non-verified verdicts.
        roadmap = {
            "milestones": [
                {
                    "milestone_id": "ms-v1",
                    "fr_refs": ["fr-login", "fr-logout"],
                    "tasks": [{"task_id": "fr-login"}, {"task_id": "fr-logout"}]
                }
            ]
        }

        base_data = {
            "$schema": "vc:16-impl-context",
            "id": "step-w582-negative-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "W582 negative test.",
                    "scope_in": ["auth-api"],
                    "scope_out": [],
                    "target_file_patterns": ["src/auth.py"]
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Auth", "summary": "Test"}],
                    "checklist": [
                        {
                            "id": "CHK_LOGIN_B",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10",
                                         "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Implement login",
                            "type": "behavior",
                            "layer": "api",
                            "linked_test_expectation": "POST /login returns 200",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login",
                            "milestone_ref": "ms-v1",
                            "implementation": {
                                "status": "verified",
                                "files_touched": ["src/auth.py"],
                                "actions": [
                                    {
                                        "type": "file_edit",
                                        "target": "src/auth.py",
                                        "description": "Add login handler",
                                        "evidence": {"type": "snippet", "content": "def login(): pass"}
                                    }
                                ]
                            }
                        }
                    ]
                },
                "docs_impact": {"status": "not_required", "rationale": "No doc changes."},
                "review_requirements": {"test_commands": ["pytest tests/"]}
            },
            "execution": {
                "execution_results": [
                    {
                        "command": "pytest tests/",
                        "status": "passed",
                        "outcome_description": "All tests passed.",
                        "reasoning": "Tests cover login.",
                        "evidence": "1 passed",
                        "evidence_ref": "ci-001",
                        "evidence_binding": {
                            "timestamp": "2024-01-01T00:00:00Z",
                            "sha256": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                            "exit_code": 0,
                            "command": "pytest tests/"
                        }
                    }
                ],
                "final_status": {"ci_status": "green"},
                "critical_evidence": {
                    "passed_test_commands": ["pytest tests/"],
                    "satisfied_checklist_ids": ["CHK_LOGIN_B"]
                }
            },
            "canonical_refs_used": []
        }

        for non_verified_verdict in ("needs_work", "blocked", "deferred"):
            data = dict(base_data)
            data["review"] = {
                "verdict": non_verified_verdict,
                "fixture_status": {
                    "implemented_interfaces": [],
                    "test_results": [],
                    "ci_status": "green"
                },
                # fr_coverage is empty — W582 must still NOT fire
                "semantic_review": {
                    "fr_coverage": [],
                    "hallucinated_features": [],
                    "scope_delta": "None."
                }
            }

            with tempfile.TemporaryDirectory() as td:
                tmp_dir = Path(td)
                fixture_path = tmp_dir / "16_impl_context.json"
                fixture_path.write_text(json.dumps(data), encoding="utf-8")
                (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")
                common_dir = tmp_dir / "common"
                common_dir.mkdir()
                (common_dir / "seed_manifest.json").write_text(
                    json.dumps({"doc_paths": []}), encoding="utf-8"
                )

                errors = validate_step_16c(data, self.repo_root, spec_path=str(fixture_path))

            w582_errors = [e for e in errors if e.code == "W582"]
            self.assertEqual(
                [],
                w582_errors,
                f"W582 must NOT fire when verdict='{non_verified_verdict}'. "
                f"Got: {[e.message for e in w582_errors]}"
            )


    # --- Evidence validation tests (Bug fixes: W599, W600, E301) ---

    def _make_evidence_test_data(self, item_id, actions):
        """Build a minimal impl_context dict with a single verified checklist item for evidence tests."""
        return {
            "$schema": "vc:16-impl-context",
            "id": f"step-evidence-test-{item_id}",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Evidence validation test case.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": []
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": [
                        {
                            "id": item_id,
                            "spec_ref": {
                                "type": "fr",
                                "id": f"task-{item_id}",
                                "line_range": "L1-L10",
                                "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"
                            },
                            "description": f"Evidence test item {item_id}",
                            "type": "behavior",
                            "layer": "api",
                            "linked_test_expectation": f"pytest test_{item_id}",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": f"fixture-{item_id}",
                            "implementation": {
                                "status": "verified",
                                "files_touched": [],
                                "actions": actions
                            }
                        },
                        {
                            "id": f"{item_id}-VAL",
                            "spec_ref": {
                                "type": "fr",
                                "id": f"task-{item_id}",
                                "line_range": "L1-L10",
                                "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"
                            },
                            "description": f"Validation item for {item_id}",
                            "type": "validation",
                            "layer": "tests",
                            "linked_test_expectation": f"pytest test_{item_id}_val",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": f"fixture-{item_id}"
                        }
                    ]
                },
                "docs_impact": {"status": "not_required", "rationale": "No code changes."}
            },
            "canonical_refs_used": []
        }

    def test_w599_fires_for_short_evidence(self):
        """W599 fires when verified action evidence content is shorter than 50 characters."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Check output",
                "evidence": {"type": "log", "content": "PASS short"}
            }
        ]
        data = self._make_evidence_test_data("CHK_W599_SHORT", actions)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        w599_errors = [e for e in errors if e.code == "W599"]
        self.assertTrue(
            len(w599_errors) > 0,
            f"Expected W599 for short evidence content. Got: {errors}"
        )
        self.assertTrue(
            any("CHK_W599_SHORT" in e.message for e in w599_errors),
            f"Expected W599 message to reference item id. Got: {[e.message for e in w599_errors]}"
        )

    def test_e301_fires_no_success_marker(self):
        """E301 EVIDENCE_CONTENT_INVALID fires when evidence content has no success marker keyword."""
        long_content = (
            "This is a detailed description of what was done during the implementation "
            "phase with no markers indicating test outcome at all."
        )
        self.assertGreaterEqual(len(long_content), 50, "Test content must be >= 50 chars")
        actions = [
            {
                "type": "manual_verification",
                "description": "Detailed check",
                "evidence": {"type": "log", "content": long_content}
            }
        ]
        data = self._make_evidence_test_data("CHK_E301_NO_MARKER", actions)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        e301_content_errors = [
            e for e in errors if e.code == "E301" and "EVIDENCE_CONTENT_INVALID" in e.message
        ]
        self.assertTrue(
            len(e301_content_errors) > 0,
            f"Expected E301 EVIDENCE_CONTENT_INVALID for missing success marker. Got: {errors}"
        )

    def test_structured_evidence_bypasses_success_marker_check(self):
        """Structured evidence (stdout/stderr present) does not require a success marker keyword."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Run build",
                "evidence": {"type": "log", "stdout": "build output here..."}
            }
        ]
        data = self._make_evidence_test_data("CHK_STRUCTURED_EVIDENCE", actions)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        e301_content_errors = [
            e for e in errors if e.code == "E301" and "EVIDENCE_CONTENT_INVALID" in e.message
        ]
        self.assertEqual(
            e301_content_errors, [],
            f"Structured evidence (stdout present) must not fire E301 EVIDENCE_CONTENT_INVALID. "
            f"Got: {e301_content_errors}"
        )

    def test_w600_fires_per_action_not_all_or_nothing(self):
        """W600 fires for each individual verified action missing evidence, even if other actions have evidence."""
        long_ok_content = "Tests passed: 12/12. All assertions OK. PASS - 0 failures detected in suite."
        actions = [
            {
                "type": "file_edit",
                "target": "src/main.py",
                "description": "Action with valid evidence",
                "evidence": {"type": "log", "content": long_ok_content}
            },
            {
                "type": "manual_verification",
                "description": "Action without evidence — should trigger W600"
            }
        ]
        data = self._make_evidence_test_data("CHK_W600_PER_ACTION", actions)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        w600_errors = [e for e in errors if e.code == "W600"]
        self.assertTrue(
            len(w600_errors) > 0,
            f"Expected W600 for the second action which has no evidence. Got: {errors}"
        )
        self.assertTrue(
            any("CHK_W600_PER_ACTION" in e.message for e in w600_errors),
            f"Expected W600 message to reference checklist item id. Got: {[e.message for e in w600_errors]}"
        )
        # The overall item has_evidence = True (first action has evidence),
        # so E301 'no evidence in any action' must NOT fire
        e301_no_evidence = [
            e for e in errors if e.code == "E301" and "contains no evidence in any action" in e.message
        ]
        self.assertEqual(
            e301_no_evidence, [],
            f"E301 'no evidence' must not fire when at least one action has evidence. "
            f"Got: {e301_no_evidence}"
        )

    def test_non_dict_evidence_bypasses_quality_check(self):
        """Non-dict evidence (e.g., plain string) satisfies presence check without triggering W599 or W600."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Action with plain-string evidence",
                "evidence": "plain string evidence value"
            }
        ]
        data = self._make_evidence_test_data("CHK_NON_DICT_EVIDENCE", actions)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        w599_errors = [e for e in errors if e.code == "W599"]
        w600_errors = [e for e in errors if e.code == "W600"]
        self.assertEqual(
            w599_errors, [],
            f"Non-dict evidence must not trigger W599. Got: {w599_errors}"
        )
        self.assertEqual(
            w600_errors, [],
            f"Non-dict evidence must not trigger W600. Got: {w600_errors}"
        )

    def test_w600_empty_dict_evidence_fires_evidence_no_content(self):
        """W600 with EVIDENCE_NO_CONTENT fires when evidence is {} (empty dict).
        E301 'no evidence in any action' must NOT fire because the evidence key IS present.
        """
        actions = [
            {
                "type": "manual_verification",
                "description": "Action with empty dict evidence",
                "evidence": {}
            }
        ]
        data = self._make_evidence_test_data("CHK_W600_EMPTY_DICT", actions)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        # W600 must fire with EVIDENCE_NO_CONTENT label (empty dict — evidence present but no fields)
        w600_errors = [e for e in errors if e.code == "W600"]
        self.assertTrue(
            len(w600_errors) > 0,
            f"Expected W600 for empty dict evidence. Got: {errors}"
        )
        self.assertTrue(
            any("EVIDENCE_NO_CONTENT" in e.message for e in w600_errors),
            f"Expected W600 message label EVIDENCE_NO_CONTENT for empty dict. "
            f"Got W600 messages: {[e.message for e in w600_errors]}"
        )
        # E301 'contains no evidence in any action' must NOT fire — evidence key IS present
        e301_no_evidence = [
            e for e in errors if e.code == "E301" and "contains no evidence in any action" in e.message
        ]
        self.assertEqual(
            e301_no_evidence, [],
            f"E301 'no evidence in any action' must not fire when evidence key is present (even if empty). "
            f"Got: {e301_no_evidence}"
        )

    def test_execution_files_touched_outside_patterns_fires_e520(self):
        """E520 fires when execution.files_touched contains a file not covered by target_file_patterns."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-exec-files-touched-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Execution files_touched scope test.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": ["src/*.py"]
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": []
                },
                "docs_impact": {"status": "not_required", "rationale": "No code changes."}
            },
            "execution": {
                "files_touched": ["src/main.py", "infra/deploy.sh"]
            },
            "canonical_refs_used": []
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

        e520_errors = [e for e in errors if e.code == "E520"]
        self.assertTrue(
            any("infra/deploy.sh" in e.message for e in e520_errors),
            f"Expected E520 for 'infra/deploy.sh' outside target_file_patterns. "
            f"Got E520 errors: {[e.message for e in e520_errors]}"
        )
        # src/main.py matches src/*.py — must NOT fire E520
        self.assertFalse(
            any("src/main.py" in e.message for e in e520_errors),
            f"Did not expect E520 for 'src/main.py' which matches pattern 'src/*.py'. "
            f"Got E520 errors: {[e.message for e in e520_errors]}"
        )


if __name__ == '__main__':
    unittest.main()
