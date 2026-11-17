import unittest
import os
import sys
import json
import tempfile
from pathlib import Path

from specdev_tools.validation.validate import validate_file

# tests/integration/ has no __init__.py; add it to sys.path so factory modules
# next to this file can be imported by name (matches test_step_16_anchor.py).
_INTEGRATION_DIR = Path(__file__).resolve().parent
if str(_INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_DIR))

from _anchor_factories import make_object_test_command  # noqa: E402

class TestStep16(unittest.TestCase):
    def setUp(self):
        # Resolve to the toolkit root, not the host workspace root
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)
        # impl_context/ contains milestone plan fixtures (vc:16-impl-context).
        # Anchor fixtures live in tests/fixtures/step_16/ root (validated as anchor).
        self.fixtures_dir = str(toolkit_root / "tests" / "fixtures" / "step_16" / "impl_context")
        self.step16_dir = str(toolkit_root / "tests" / "fixtures" / "step_16")

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

    def test_legacy_verified_item_without_evidence_fires_e301(self):
        # A 1.1.1-shaped item (implementation.status 'verified') with no evidence in its actions: the guarded
        # status-keyed rule still fires. # M8 rewrites
        path = os.path.join(self.fixtures_dir, "legacy_verified_missing_evidence.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing evidence) should fail validation")
        self.assertTrue(any(e.code == "E301" for e in errors), f"Expected E301. Got: {errors}")

    def test_invalid_bad_enum(self):
        # Expect failure due to bad enum
        path = os.path.join(self.fixtures_dir, "invalid_bad_enum.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (bad enum) should fail validation")
        self.assertTrue(any(e.code == "E530" for e in errors), f"Expected E530. Got: {errors}")

    def test_valid_metadata_item_without_proof(self):
        # A non-deferred metadata item legitimately omits nfr_refs and fixture_ref.
        # The fixture_ref requirement (schema allOf branch + step_16 TYPES_REQUIRING_PROOF)
        # applies only to proof-types (behavior/constraint/validation/perf/security);
        # metadata/docs/logging are exempt. Guards against a future revert of the schema branch.
        path = os.path.join(self.fixtures_dir, "valid_metadata_no_proof.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid metadata-without-proof fixture should pass. Errors: {errors}")
        self.assertFalse(any(e.code == "E520" for e in errors), f"Metadata item must not trigger E520. Got: {errors}")

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

    def test_legacy_unexecuted_planned_item_fires_e305(self):
        # E305 (guarded, runs on a plan whose item carries implementation.status): an active item not in
        # satisfied_checklist_ids when CI is green. # M8 rewrites
        path = os.path.join(self.fixtures_dir, "legacy_planned_unexecuted.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E305 fixture should fail validation")
        self.assertTrue(
            any(e.code == "E305" for e in errors),
            f"Expected E305 error. Got: {errors}"
        )

    def test_wont_do_item_excluded_from_e305_planned_vs_executed(self):
        """E305 exempts wont_do items from the planned-vs-executed diff, same as
        deferred (DEVSPEC-122 follow-up): a wont_do item was never intended to
        be executed, so it should not count as an unexecuted planned item."""
        path = os.path.join(self.fixtures_dir, "legacy_planned_unexecuted.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # cl-002 was 'deferred' in the base fixture; make it 'wont_do' instead.
        cl_002 = data["plan"]["spec_alignment"]["checklist"][1]
        self.assertEqual(cl_002["id"], "cl-002")
        del cl_002["checklist_status"]
        del cl_002["deferred_reason"]
        cl_002["checklist_status"] = "wont_do"
        cl_002["wont_do_reason"] = "Session-store team abandoned token revocation; logout now client-side only."

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))

        e305_errors = [e for e in errors if e.code == "E305"]
        self.assertFalse(
            any("cl-002" in e.message for e in e305_errors),
            f"Did not expect E305 for wont_do item cl-002. Got: {e305_errors}"
        )
        # Control: cl-001 (still active, still unexecuted) must still fire E305.
        self.assertTrue(
            any("cl-001" in e.message for e in e305_errors),
            f"Expected E305 for still-active unexecuted item cl-001. Got: {e305_errors}"
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
        path = os.path.join(self.step16_dir, "e304_roadmap", "impl_context", "ms_test_plan.json")
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
            # Fixture must live inside impl_context/ so it routes to the 16a validator
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Step 04 lives at spec-root level (parent of impl_context/)
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
            # Fixture inside impl_context/ so it routes to the 16a validator
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Step 04 at spec-root level
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

    def test_e304_plan_not_a_dict_does_not_crash_roadmap_check(self):
        """validate_step_16 must not crash when 'plan' is not a dict and a real
        roadmap is present (regression: data={"plan": None, ...} once raised
        AttributeError in the E304 helper)."""
        base_path = os.path.join(self.fixtures_dir, "valid_with_semantic_review.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["plan"] = None

        roadmap = {"milestones": [{"milestone_id": "m1", "status": "in_progress"}]}

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )

            from specdev_tools.validation.validators.step_16 import validate_step_16
            try:
                errors = validate_step_16(data, self.repo_root, spec_path=str(fixture_path))
            except AttributeError as exc:
                self.fail(f"validate_step_16 crashed on non-dict 'plan' with a roadmap present: {exc}")

        self.assertIsInstance(errors, list)

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
            # Fixture inside impl_context/ so it routes to the 16a validator (not anchor)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
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
            # Fixture inside impl_context/ so it routes to the 16a validator (not anchor)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
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

    def test_e307_deferred_validation_item_still_counts_as_pairing(self):
        """A deferred 'validation' item still satisfies E307 pairing -- paused, not absent."""
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["plan"]["spec_alignment"]["checklist"] = [
            {
                "id": "REQ_BEHAVIOR",
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
            },
            {
                "id": "REQ_VALIDATION_DEFERRED",
                "spec_ref": {
                    "type": "fr",
                    "id": "task-login-impl",
                    "line_range": "L1-L50",
                    "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                },
                "description": "Validate login endpoint edge cases",
                "type": "validation",
                "layer": "tests",
                "checklist_status": "deferred",
                "deferred_reason": "Edge-case test harness not ready yet; resume once fixture-login-api-edge lands."
            }
        ]
        data.pop("execution", None)
        data["review"] = {}
        data["plan"].pop("review_requirements", None)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))

        e307_errors = [e for e in errors if e.code == "E307"]
        self.assertEqual(
            [], e307_errors,
            f"Deferred validation item should still satisfy E307 pairing. Got: {e307_errors}"
        )

    # --- 1.2.0 plan shape: milestone key, realises, no pins ---

    def _doc_plan_example(self):
        """The plan file of the design example (DOC section 12.19): one item realising one task criterion."""
        return {
            "$schema": "vc:16-impl-context",
            "id": "step-ms-account-recovery-plan",
            "owner": "api",
            "created_at": "2026-01-01T00:00:00Z",
            "milestone": "ms-account-recovery",
            "plan": {
                "summary": {
                    "functional_summary": "Reject an expired password-reset token.",
                    "scope_in": ["confirm handler"],
                    "scope_out": [],
                    "target_file_patterns": ["src/routes/**"],
                },
                "spec_alignment": {"checklist": [{
                    "id": "PWRESET_CONFIRM_EXPIRED_01",
                    "realises": ["tc-confirm-expired-token"],
                    "description": "The confirm handler returns 410 token-expired for a token older than 30 minutes.",
                    "type": "behavior",
                    "layer": "api",
                    "implementation": {
                        "files_touched": ["src/routes/password-resets/confirm.ts"],
                        "actions": [{
                            "type": "file_edit",
                            "target": "src/routes/password-resets/confirm.ts",
                            "description": "Reject expired tokens before the password update.",
                        }],
                    },
                }]},
                "docs_impact": {"status": "required", "rationale": "A new status code.", "docs_touched": ["README.md"]},
                "review_requirements": {"test_commands": ["pytest tests/"]},
            },
            "canonical_refs_used": [],
        }

    def _validate_plan_data(self, data, roadmap_milestones=None):
        """Write *data* as ``impl_context/ms_test_plan.json`` beside a seed manifest (and a roadmap) and validate it."""
        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, data, roadmap_milestones) if roadmap_milestones is not None else None
            if path is None:
                impl_context_dir = Path(td) / "impl_context"
                impl_context_dir.mkdir()
                path = str(impl_context_dir / "ms_test_plan.json")
                Path(path).write_text(json.dumps(data), encoding="utf-8")
                (Path(td) / "common").mkdir()
                (Path(td) / "common" / "seed_manifest.json").write_text(json.dumps({"doc_paths": ["README.md"]}), encoding="utf-8")
            return validate_file(self.repo_root, path)

    def test_doc_plan_example_validates(self):
        errors = self._validate_plan_data(self._doc_plan_example())
        self.assertEqual(errors, [], f"The design's plan example must validate. Got: {errors}")

    def test_item_without_realises_fails(self):
        path = os.path.join(self.fixtures_dir, "invalid_missing_realises.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            any(e.code == "E520" and "'realises' is a required property" in e.message for e in errors),
            f"Expected a schema error for the missing realises. Got: {errors}"
        )

    def test_item_with_empty_realises_fails(self):
        data = self._doc_plan_example()
        data["plan"]["spec_alignment"]["checklist"][0]["realises"] = []
        errors = self._validate_plan_data(data)
        self.assertTrue(any(e.code == "E520" and "realises" in e.message for e in errors), f"Got: {errors}")

    def test_plan_without_milestone_fails(self):
        path = os.path.join(self.fixtures_dir, "invalid_missing_milestone.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            any(e.code == "E520" and "'milestone' is a required property" in e.message for e in errors),
            f"Expected a schema error for the missing milestone. Got: {errors}"
        )

    def test_old_spec_ref_line_range_commit_hash_rejected(self):
        path = os.path.join(self.fixtures_dir, "invalid_old_spec_ref_pins.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            any(e.code == "E520" and "'spec_ref' was unexpected" in e.message for e in errors),
            f"The plan item's old spec_ref must be rejected. Got: {errors}"
        )
        data = self._doc_plan_example()
        data["review"] = {"findings": [{
            "id": "finding-one", "type": "bug", "severity": "minor", "description": "A finding.",
            "spec_ref": {"type": "api", "id": "api-one", "line_range": "L1-L10", "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
            "metadata": {"source": "reviewer", "impact": "none"},
        }]}
        errors = self._validate_plan_data(data)
        message = " ".join(e.message for e in errors)
        self.assertIn("'line_range'", message)
        self.assertIn("'commit_hash'", message)

    def test_removed_plan_status_and_item_fields_are_rejected(self):
        data = self._doc_plan_example()
        data["plan"]["status"] = "active"
        item = data["plan"]["spec_alignment"]["checklist"][0]
        item.update({"checklist_status": "active", "linked_test_expectation": "t", "fixture_ref": "fix-a", "nfr_refs": ["nfr-a"], "milestone_ref": "m"})
        item["implementation"]["status"] = "pending"
        message = " ".join(e.message for e in self._validate_plan_data(data))
        for name in ("status", "checklist_status", "linked_test_expectation", "fixture_ref", "nfr_refs", "milestone_ref"):
            self.assertIn(f"'{name}'", message, name)

    def test_plan_item_needs_no_nfr_or_fixture_link(self):
        errors = self._validate_plan_data(self._doc_plan_example())
        self.assertEqual([e for e in errors if e.code == "E520"], [])

    def test_e305_e307_and_status_keyed_e301_guarded_on_new_shape(self):
        """A plan whose items carry no implementation.status gets none of the status-keyed findings."""
        data = self._doc_plan_example()
        data["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"][0]["evidence"] = {"type": "log", "content": "short"}
        data["execution"] = {"final_status": {"ci_status": "green"}}
        data["review"] = {}
        codes = {e.code for e in self._run_step16_validate(data)}
        self.assertFalse(codes & {"E305", "E307", "E301", "W599", "W600", "W601"}, codes)

    def test_e305_e307_and_status_keyed_e301_still_fire_on_legacy_status(self):
        data = self._minimal_impl_context(checklist_items=[{
            "id": "CHK_LEGACY", "spec_ref": {"type": "fr", "id": "fr-legacy"}, "description": "Legacy item",
            "type": "behavior", "layer": "api", "implementation": {"status": "verified", "actions": []},
        }])
        data["execution"] = {"final_status": {"ci_status": "green"}, "critical_evidence": {"satisfied_checklist_ids": []}}  # 1.1.1 key
        codes = {e.code for e in self._run_step16_validate(data)}
        self.assertTrue({"E301", "E305", "E307"} <= codes, codes)

    def test_w616_and_w582_removed(self):
        """A deferred item marked verified (W616) and an uncovered milestone FR at a verified verdict (W582) say nothing."""
        data = self._minimal_impl_context(checklist_items=[{
            "id": "CHK_STALE", "spec_ref": {"type": "fr", "id": "fr-stale"}, "description": "Stale item",
            "type": "behavior", "layer": "api", "checklist_status": "deferred",
            "implementation": {"status": "verified", "actions": [{"type": "manual_verification", "description": "x"}]},
        }], milestone="m1")
        data["review"] = {"verdict": "verified", "semantic_review": {"fr_coverage": []}}
        roadmap = [{"milestone_id": "m1", "fr_refs": ["fr-uncovered"], "tasks": []}]
        errors = self._validate_plan_data(data, roadmap)
        self.assertFalse({e.code for e in errors} & {"W616", "W582"}, [e.code for e in errors])

    # --- E304: the plan's milestone, covered through realised criteria ---

    def _roadmap_task(self, task_id, criterion_ids, disposition=None):
        task = {"task_id": task_id, "acceptance_criteria": [{"criterion_id": c} for c in criterion_ids]}
        if disposition is not None:
            task["disposition"] = {"value": disposition, "reason": "Set aside for this test."}
        return task

    def _e304_messages(self, data, roadmap_milestones):
        errors = self._validate_plan_data(data, roadmap_milestones)
        return [e.message for e in errors if e.code == "E304"]

    def test_e304_uncovered_task_of_plans_milestone(self):
        """Only the tasks of the plan's own milestone count: t2 is uncovered, t1 is realised, t3 belongs to m2."""
        roadmap = [
            {"milestone_id": "m1", "tasks": [self._roadmap_task("t1", ["tc-t1"]), self._roadmap_task("t2", ["tc-t2"])]},
            {"milestone_id": "m2", "tasks": [self._roadmap_task("t3", ["tc-t3"])]},
        ]
        data = self._minimal_impl_context([self._make_checklist_item("CHK_T1", ["tc-t1"])], milestone="m1")
        messages = self._e304_messages(data, roadmap)
        self.assertEqual(len(messages), 1, messages)
        self.assertIn("'t2'", messages[0])

    def test_e304_task_is_covered_by_any_one_of_its_criteria(self):
        roadmap = [{"milestone_id": "m1", "tasks": [self._roadmap_task("t1", ["tc-a", "tc-b"])]}]
        data = self._minimal_impl_context([self._make_checklist_item("CHK_B", ["tc-b"])], milestone="m1")
        self.assertEqual(self._e304_messages(data, roadmap), [])

    def test_e304_milestone_status_does_not_exempt_a_task(self):
        roadmap = [{"milestone_id": "m1", "status": "done", "tasks": [self._roadmap_task("t1", ["tc-t1"])]}]
        data = self._minimal_impl_context([], milestone="m1")
        self.assertEqual(len(self._e304_messages(data, roadmap)), 1)

    def test_e304_skips_deferred_or_wont_do_disposition_task(self):
        roadmap = [{"milestone_id": "m1", "tasks": [
            self._roadmap_task("t1", ["tc-t1"], disposition="deferred"),
            self._roadmap_task("t2", ["tc-t2"], disposition="wont_do"),
        ]}]
        data = self._minimal_impl_context([], milestone="m1")
        self.assertEqual(self._e304_messages(data, roadmap), [])

    def test_e304_unknown_plan_milestone_is_reported(self):
        roadmap = [{"milestone_id": "m1", "tasks": [self._roadmap_task("t1", ["tc-t1"])]}]
        data = self._minimal_impl_context([self._make_checklist_item("CHK_T1", ["tc-t1"])], milestone="ms-ghost")
        messages = self._e304_messages(data, roadmap)
        self.assertEqual(len(messages), 1, messages)
        self.assertIn("ms-ghost", messages[0])

    def _make_e304_fixture(self, tmpdir, impl_context_data, roadmap_milestones):
        """Helper to write a step_16 fixture + roadmap for E304 tests.

        The fixture is placed inside impl_context/ so _is_anchor() correctly
        identifies it as a 16a plan (not an anchor) and E304 fires as expected.
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

    def _minimal_impl_context(self, checklist_items, milestone=None):
        """Build a minimal impl_context dict; *milestone* is the plan's file-level ``milestone`` key."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-e304-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
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
        if milestone is not None:
            data["milestone"] = milestone
        return data

    def _make_checklist_item(self, item_id, criterion_ids):
        """Build a minimal plan item that realises the given acceptance-criterion ids."""
        return {
            "id": item_id,
            "realises": list(criterion_ids),
            "description": f"Implement {item_id}",
            "type": "behavior",
            "layer": "api",
            "implementation": {"actions": [{"type": "manual_verification", "description": f"Verify {item_id}"}]},
        }

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
        """Valid fixture with new-shape emergent_ambiguities (about, optional proposed_assumption) should pass."""
        path = os.path.join(self.fixtures_dir, "valid_with_emergent_ambiguities.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid emergent_ambiguities fixture should pass. Errors: {errors}")

    def test_invalid_emergent_ambiguity_severity(self):
        """An emergent_ambiguities entry in the removed legacy shape (severity, no about) fails schema validation."""
        path = os.path.join(self.fixtures_dir, "invalid_emergent_ambiguity_severity.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            len(errors) > 0,
            "Invalid emergent_ambiguity severity fixture should fail validation"
        )
        self.assertTrue(any(e.code == "E520" for e in errors), f"Expected E520. Got: {errors}")

    def test_impl_context_16c_dispatch_fires_verdict_enum_check(self):
        """Content-based dispatch: an impl_context/ artifact with review.verdict
        must route to validate_step_16c, which enforces the verdict enum.

        Pre-fix, impl_context/*.json always dispatched to validate_step_16a,
        so 16c-specific checks (like the verdict enum) never fired through
        the top-level validate_file pipeline.
        """
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-16c-dispatch-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "16c dispatch test.",
                    "scope_in": ["auth"],
                    "scope_out": [],
                    "target_file_patterns": ["src/auth.py"],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Auth", "summary": "Test"}],
                    "checklist": [],
                },
                "docs_impact": {"status": "not_required", "rationale": "No doc changes."},
                "review_requirements": {"test_commands": ["pytest tests/"]},
            },
            "review": {
                "verdict": "TOTALLY_INVALID_VERDICT",  # 16c validator must flag this
                "fixture_status": {
                    "implemented_interfaces": [],
                    "test_results": [],
                    "ci_status": "green",
                },
            },
            "canonical_refs_used": [],
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_dispatch_review.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": []}), encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        # The 16c validator fires an E520 for the invalid verdict — proof the
        # content-based dispatch promoted this artifact past 16a.
        self.assertTrue(
            any(
                e.code == "E520" and "invalid verdict" in e.message
                for e in errors
            ),
            f"Expected E520 invalid verdict from validate_step_16c. Got: {errors}"
        )

    def test_impl_context_16b_dispatch_fires_duplicate_command_check(self):
        """Content-based dispatch: an impl_context/ artifact with populated
        execution.execution_results (but no review.verdict) must route to
        validate_step_16b, which enforces duplicate-command detection.
        """
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-16b-dispatch-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "16b dispatch test.",
                    "scope_in": ["auth"],
                    "scope_out": [],
                    "target_file_patterns": ["src/auth.py"],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Auth", "summary": "Test"}],
                    "checklist": [],
                },
                "docs_impact": {"status": "not_required", "rationale": "No doc changes."},
                "review_requirements": {"test_commands": ["pytest tests/"]},
            },
            "execution": {
                "execution_results": [
                    {
                        "command": "pytest tests/",
                        "status": "passed",
                        "outcome_description": "Passed.",
                        "reasoning": "OK.",
                        "evidence": "1 passed",
                        "evidence_ref": "ci-001",
                    },
                    {
                        # Duplicate command — 16b validator flags this
                        "command": "pytest tests/",
                        "status": "passed",
                        "outcome_description": "Duplicate.",
                        "reasoning": "OK.",
                        "evidence": "1 passed",
                        "evidence_ref": "ci-002",
                    },
                ],
                "final_status": {"ci_status": "green"},
            },
            "canonical_refs_used": [],
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_dispatch_exec.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": []}), encoding="utf-8"
            )

            errors = validate_file(self.repo_root, str(fixture_path))

        self.assertTrue(
            any(
                e.code == "E520" and "duplicate execution_result command" in e.message
                for e in errors
            ),
            f"Expected E520 duplicate execution_result from validate_step_16b. Got: {errors}"
        )

    def test_impl_context_16a_dispatch_stays_16a_for_plan_only_artifact(self):
        """An impl_context/ artifact with no execution.execution_results and
        no review.verdict stays on the 16a path (default)."""
        from specdev_tools.core.step_paths import refine_impl_context_substep

        plan_only = {
            "$schema": "vc:16-impl-context",
            "plan": {},
        }
        plan_plus_empty_exec = {
            "$schema": "vc:16-impl-context",
            "plan": {},
            "execution": {"execution_results": []},
            "review": {},
        }
        self.assertEqual(refine_impl_context_substep("16a", plan_only), "16a")
        self.assertEqual(refine_impl_context_substep("16a", plan_plus_empty_exec), "16a")
        # Non-impl_context steps are never refined
        self.assertEqual(refine_impl_context_substep("04", plan_only), "04")
        self.assertEqual(refine_impl_context_substep("unknown", plan_only), "unknown")

    def test_e307_doc_spec_ref_type_excluded(self):
        """E307 does NOT fire when spec_ref.type is 'doc' — task references are work
        items, not testable behaviors, and must not require behavior+validation pairing.
        """
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # doc-type spec_ref with behavior-only checklist — should NOT trigger E307
        data["plan"]["spec_alignment"]["checklist"] = [
            {
                "id": "WORK_ITEM_D",
                "spec_ref": {
                    "type": "doc",
                    "id": "task-doc-impl",
                },
                "description": "Implement documentation work item.",
                "type": "behavior",
                "layer": "api",
                "linked_test_expectation": "passes tests",
                "nfr_refs": ["nfr-availability-uptime"],
                "fixture_ref": "fixture-impl",
            }
        ]
        data.pop("execution", None)
        data["review"] = {}
        data["plan"].pop("review_requirements", None)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            # Fixture inside impl_context/ so it routes to the 16a validator (not anchor)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}),
                encoding="utf-8",
            )
            errors = validate_file(self.repo_root, str(fixture_path))

        e307_errors = [e for e in errors if e.code == "E307"]
        self.assertEqual(
            e307_errors, [],
            f"Did not expect E307 for doc spec_ref.type. Got: {e307_errors}"
        )

    def test_impl_context_16a_dispatch_e2e_routes_through_16a_validator(self):
        """End-to-end counterpart to the refiner-only 16a dispatch test.

        Writes a plan-only artifact (no execution.execution_results, no
        review.verdict) through the full validate_file pipeline and pins
        that the 16a-specific remediation-link check fires via dispatch
        (W584) — proving content refinement leaves plan-only artifacts
        on the 16a path rather than demoting to the base or promoting to
        16b/16c.
        """
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Induce a 16a-specific finding: a review remediation task that links
        # a checklist id the plan does not have (checked by validate_step_16a,
        # not the base validator). No verdict, so the artifact stays plan-only.
        data.pop("execution", None)
        data["review"] = {"findings": [{"remediation_task": {"task_id": "fix-1", "checklist_ids": ["NO_SUCH_ITEM"]}}]}
        data["plan"].pop("review_requirements", None)

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_16a_e2e.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": []}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))

        # The unknown checklist id is pinned by validate_step_16a (W584).
        link_errors = [e for e in errors if e.code == "W584" and "NO_SUCH_ITEM" in e.message]
        self.assertEqual(
            len(link_errors), 1,
            f"Expected exactly one remediation-link warning from the "
            f"16a dispatch path. Got: {errors}"
        )

    def test_step_16c_chain_up_deduplicates_base_checks(self):
        """Chain-up (16c → 16b → 16a → base) must not cause base checks to
        fire multiple times on the same artifact.

        Only 16a calls the base validator, so a base-level error (here E307)
        appears exactly once in the list returned by 16c.
        """
        from specdev_tools.validation.validators.step_16c import validate_step_16c

        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Force an E307 (base-level) pairing failure: FR ref with only a
        # behavior item and no validation partner.
        data["plan"]["spec_alignment"]["checklist"] = [
            {
                "id": "FR_ONLY_BEHAVIOR",
                "spec_ref": {"type": "fr", "id": "fr-solo-behavior"},
                "description": "Behavior item without validation partner.",
                "type": "behavior",
                "layer": "api",
                "linked_test_expectation": "passes tests",
                "nfr_refs": ["nfr-availability-uptime"],
                "fixture_ref": "fixture-impl",
            }
        ]
        # Make the artifact 16c-shaped so chain-up runs all three layers.
        data["review"] = {
            "verdict": "verified",
            "fixture_status": {
                "implemented_interfaces": [],
                "test_results": [],
                "ci_status": "green",
            },
        }
        data["execution"] = {"execution_results": []}

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_chainup.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_step_16c(data, self.repo_root, str(fixture_path))

        e307_errors = [
            e for e in errors
            if e.code == "E307" and "fr-solo-behavior" in e.message
        ]
        self.assertEqual(
            len(e307_errors), 1,
            f"Chain-up must fire base-level E307 exactly once (cache dedup). "
            f"Got {len(e307_errors)} occurrences. Full errors: {errors}"
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


    # --- W601 tests ---

    def test_w601_fires_when_evidence_has_no_artifact_ref(self):
        """W601 fires when evidence content contains no spec artifact ID (fr-*, api-*, etc.)."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Action with evidence lacking artifact refs",
                "evidence": {"type": "log", "content": "All tests passed successfully, no issues found in the output logs"}
            }
        ]
        data = self._make_evidence_test_data("CHK_W601_NO_REF", actions)

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

        w601_errors = [e for e in errors if e.code == "W601"]
        self.assertTrue(
            len(w601_errors) > 0,
            f"Expected W601 for evidence without artifact ID refs. Got errors: {[e.code for e in errors]}"
        )
        self.assertTrue(
            any("EVIDENCE_NO_ARTIFACT_REF" in e.message for e in w601_errors),
            f"Expected W601 message to contain EVIDENCE_NO_ARTIFACT_REF. Got: {[e.message for e in w601_errors]}"
        )

    def test_w601_does_not_fire_when_evidence_has_artifact_ref(self):
        """W601 must not fire when evidence content references a spec artifact ID."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Action with artifact ref in evidence",
                "evidence": {"type": "log", "content": "Verified fr-user-login endpoint returns 200 with valid token as per api-session-create contract"}
            }
        ]
        data = self._make_evidence_test_data("CHK_W601_HAS_REF", actions)

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

        w601_errors = [e for e in errors if e.code == "W601"]
        self.assertEqual(
            w601_errors, [],
            f"W601 must not fire when evidence references a spec artifact ID. Got: {w601_errors}"
        )

    def test_w601_does_not_fire_for_metadata_type_item_without_artifact_ref(self):
        """W601 must not fire for type:metadata items — same exemption rationale as E520
        (infra/setup checklist items, e.g. CI config or wrangler routes, legitimately have
        no fr-/nfr-/inv- artifact to cite in evidence, mirroring TYPES_REQUIRING_PROOF)."""
        data = self._make_evidence_test_data("CHK_W601_METADATA", [
            {
                "type": "run_command",
                "description": "Action with evidence lacking artifact refs on a metadata-type item",
                "evidence": {"type": "log", "content": "All tests passed successfully, no issues found in the output logs"}
            }
        ])
        data["plan"]["spec_alignment"]["checklist"][0]["type"] = "metadata"
        del data["plan"]["spec_alignment"]["checklist"][0]["nfr_refs"]
        del data["plan"]["spec_alignment"]["checklist"][0]["fixture_ref"]

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

        w601_errors = [e for e in errors if e.code == "W601"]
        self.assertEqual(
            w601_errors, [],
            f"W601 must not fire for type:metadata items without artifact refs. Got: {w601_errors}"
        )

    # --- W603 tests ---

    def test_w603_fires_for_execution_file_outside_task_scope(self):
        """W603 fires when execution.files_touched has a file not in any checklist item's files_touched."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-w603-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "W603 test for files outside task scope.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": ["src/**", "infra/**"]
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": [
                        {
                            "id": "CHK_W603",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10", "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Login feature",
                            "type": "behavior",
                            "layer": "api",
                            "linked_test_expectation": "pytest test_login",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login",
                            "implementation": {
                                "status": "in_progress",
                                "files_touched": ["src/auth.py"],
                                "actions": []
                            }
                        },
                        {
                            "id": "CHK_W603_VAL",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10", "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Validate login",
                            "type": "validation",
                            "layer": "tests",
                            "linked_test_expectation": "pytest test_login_val",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login"
                        }
                    ]
                },
                "docs_impact": {"status": "not_required", "rationale": "No doc changes."}
            },
            "execution": {
                "files_touched": ["src/auth.py", "infra/deploy.sh"]
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

        w603_errors = [e for e in errors if e.code == "W603"]
        self.assertTrue(
            any("infra/deploy.sh" in e.message for e in w603_errors),
            f"Expected W603 for 'infra/deploy.sh' outside any checklist item's files_touched. "
            f"Got W603 errors: {[e.message for e in w603_errors]}"
        )
        self.assertFalse(
            any("src/auth.py" in e.message for e in w603_errors),
            f"src/auth.py is in checklist files_touched, should not fire W603. Got: {[e.message for e in w603_errors]}"
        )

    def test_w603_does_not_fire_when_all_files_in_scope(self):
        """W603 must not fire when all execution.files_touched are declared in checklist items."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-w603-pass-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "W603 negative test.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": ["src/**"]
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": [
                        {
                            "id": "CHK_W603_OK",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10", "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Login feature",
                            "type": "behavior",
                            "layer": "api",
                            "linked_test_expectation": "pytest test_login",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login",
                            "implementation": {
                                "status": "in_progress",
                                "files_touched": ["src/auth.py", "src/utils.py"],
                                "actions": []
                            }
                        },
                        {
                            "id": "CHK_W603_OK_VAL",
                            "spec_ref": {"type": "fr", "id": "fr-login", "line_range": "L1-L10", "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                            "description": "Validate login",
                            "type": "validation",
                            "layer": "tests",
                            "linked_test_expectation": "pytest test_login_val",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login"
                        }
                    ]
                },
                "docs_impact": {"status": "not_required", "rationale": "No doc changes."}
            },
            "execution": {
                "files_touched": ["src/auth.py", "src/utils.py"]
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

        w603_errors = [e for e in errors if e.code == "W603"]
        self.assertEqual(
            w603_errors, [],
            f"W603 must not fire when all execution files are in checklist scope. Got: {w603_errors}"
        )

    # --- E302 tests ---

    def test_e302_fires_verified_verdict_no_execution(self):
        """E302 fires when review.verdict is 'verified' but no execution section exists."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-e302-no-exec",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "E302 test — verified verdict without execution.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": []
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": []
                },
                "docs_impact": {"status": "not_required", "rationale": "No changes."}
            },
            "review": {
                "verdict": "verified",
                "findings": [],
                "fixture_status": {"ci_status": "green"}
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

        e302_errors = [e for e in errors if e.code == "E302"]
        self.assertTrue(
            any("no execution section" in e.message for e in e302_errors),
            f"Expected E302 for verified verdict without execution. Got: {[e.code + ': ' + e.message for e in errors if e.code == 'E302']}"
        )

    def test_e302_fires_verified_verdict_empty_results(self):
        """E302 fires when review.verdict is 'verified' but execution_results is empty."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-e302-empty-results",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "E302 test — verified verdict with empty execution_results.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": []
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": []
                },
                "docs_impact": {"status": "not_required", "rationale": "No changes."},
                "review_requirements": {"test_commands": ["pytest tests/"]}
            },
            "execution": {
                "execution_results": []
            },
            "review": {
                "verdict": "verified",
                "findings": [],
                "fixture_status": {"ci_status": "green"}
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

        e302_errors = [e for e in errors if e.code == "E302"]
        self.assertTrue(
            any("execution_results is empty" in e.message for e in e302_errors),
            f"Expected E302 for verified verdict with empty execution_results. Got: {[e.code + ': ' + e.message for e in errors if e.code == 'E302']}"
        )

    def test_e302_fires_unproven_test_commands(self):
        """E302 fires when review.verdict is 'verified' but test commands lack proof."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-e302-unproven-cmds",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "E302 test — unproven test commands.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": []
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": []
                },
                "docs_impact": {"status": "not_required", "rationale": "No changes."},
                "review_requirements": {"test_commands": ["pytest tests/", "npm test"]}
            },
            "execution": {
                "execution_results": [
                    {"command": "pytest tests/", "status": "passed", "output": "ok"}
                ]
            },
            "review": {
                "verdict": "verified",
                "findings": [],
                "fixture_status": {"ci_status": "green"}
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

        e302_errors = [e for e in errors if e.code == "E302"]
        self.assertTrue(
            any("npm test" in e.message for e in e302_errors),
            f"Expected E302 for unproven 'npm test' command. Got E302: {[e.message for e in e302_errors]}"
        )

    # --- Object-form test_commands tests (E301 + E302) ---

    def _run_step16_validate(self, data):
        """Helper: write *data* to a temp 16_impl_context.json and run validate_step_16."""
        from specdev_tools.validation.validators.step_16 import validate_step_16
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            return validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

    def _base_step16_artifact(
        self,
        *,
        artifact_id="step-objform",
        summary="Object-form test_commands.",
        test_commands=None,
        execution_results=None,
        review=None,
    ):
        """Minimal valid-shape Step 16 artifact for E301/E302 tests.

        All fields not relevant to a test get sensible defaults; callers override
        only what they need. Keeps each test focused on the behavior under check
        instead of repeating ~50 lines of plan/execution scaffolding.
        """
        data = {
            "$schema": "vc:16-impl-context",
            "id": artifact_id,
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": summary,
                    "scope_in": ["core"], "scope_out": [], "target_file_patterns": [],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": [],
                },
                "docs_impact": {"status": "not_required", "rationale": "No changes."},
                "review_requirements": {"test_commands": test_commands or []},
            },
            "execution": {
                "execution_results": execution_results or [],
            },
            "canonical_refs_used": [],
        }
        if review is not None:
            data["review"] = review
        return data

    def test_e301_object_form_test_commands_pass_when_all_commands_executed(self):
        """E301 must NOT fire when object-form test_commands all appear in execution_results."""
        data = self._base_step16_artifact(
            artifact_id="step-e301-objform-pass",
            summary="Object-form test_commands all executed.",
            test_commands=[
                make_object_test_command("pytest tests/", description="unit tests"),
                make_object_test_command("npm test"),
            ],
            execution_results=[
                {"command": "pytest tests/", "status": "passed", "output": "ok"},
                {"command": "npm test", "status": "passed", "output": "ok"},
            ],
        )
        errors = self._run_step16_validate(data)
        e301 = [e for e in errors if e.code == "E301" and "MISSING_PROOF_CLOSURE" in e.message]
        self.assertEqual(e301, [], f"Expected no E301 MISSING_PROOF_CLOSURE; got: {[e.message for e in e301]}")

    def test_e301_object_form_test_commands_fire_when_command_missing(self):
        """E301 fires when an object-form test_commands entry lacks an execution_results match."""
        data = self._base_step16_artifact(
            artifact_id="step-e301-objform-fail",
            summary="Object-form test_commands with one missing.",
            test_commands=[
                make_object_test_command("pytest tests/"),
                make_object_test_command("npm test"),
            ],
            execution_results=[
                {"command": "pytest tests/", "status": "passed", "output": "ok"},
            ],
        )
        errors = self._run_step16_validate(data)
        e301 = [e for e in errors if e.code == "E301" and "MISSING_PROOF_CLOSURE" in e.message]
        self.assertTrue(
            any("npm test" in e.message for e in e301),
            f"Expected E301 MISSING_PROOF_CLOSURE for 'npm test'; got: {[e.message for e in e301]}"
        )

    def test_string_form_and_object_form_test_commands_produce_identical_e301(self):
        """Regression parity: a string-form entry and an equivalent object-form entry
        must produce the same E301 (MISSING_PROOF_CLOSURE) outcome for the same command."""
        def build(test_commands):
            return self._base_step16_artifact(
                artifact_id="step-parity",
                summary="String/object parity check.",
                test_commands=test_commands,
                # 'npm test' deliberately missing → must fire E301 in both forms
                execution_results=[
                    {"command": "pytest tests/", "status": "passed", "output": "ok"},
                ],
            )

        string_form_errors = self._run_step16_validate(build([
            "pytest tests/", "npm test",
        ]))
        object_form_errors = self._run_step16_validate(build([
            make_object_test_command("pytest tests/"),
            make_object_test_command("npm test"),
        ]))

        def e301_for(errors, needle):
            return [e for e in errors
                    if e.code == "E301"
                    and "MISSING_PROOF_CLOSURE" in e.message
                    and needle in e.message]

        def e301_messages(errors):
            return sorted(e.message for e in errors if e.code == "E301")

        self.assertTrue(
            e301_for(string_form_errors, "npm test"),
            f"string-form must fire E301 for 'npm test'; got: {[e.message for e in string_form_errors if e.code == 'E301']}",
        )
        self.assertTrue(
            e301_for(object_form_errors, "npm test"),
            f"object-form must fire E301 for 'npm test'; got: {[e.message for e in object_form_errors if e.code == 'E301']}",
        )
        # Strict parity: full E301 message set must match between string and object form.
        # Catches regressions where object form silently produces extra/missing E301s
        # for any command (not just 'npm test').
        self.assertEqual(
            e301_messages(string_form_errors),
            e301_messages(object_form_errors),
            "string-form and object-form must produce the identical E301 message set.",
        )

    def test_mixed_string_and_object_test_commands_both_enforced(self):
        """Mixed list (one string entry, one object entry) — both must be enforced
        consistently by E301. Pins that there is no silent-skip for either form
        when the two are interleaved."""
        # An unrelated command was executed; neither 'pytest tests/' nor 'npm test'
        # is in passed_commands → E301 must fire for both forms.
        data = self._base_step16_artifact(
            artifact_id="step-mixed",
            summary="Mixed string+object test_commands.",
            test_commands=[
                "pytest tests/",                          # string form
                make_object_test_command("npm test"),     # object form
            ],
            execution_results=[
                {"command": "echo placeholder", "status": "passed", "output": "ok"},
            ],
        )
        errors = self._run_step16_validate(data)
        e301 = [e for e in errors if e.code == "E301" and "MISSING_PROOF_CLOSURE" in e.message]
        self.assertTrue(any("pytest tests/" in e.message for e in e301),
                        f"E301 must fire for string-form 'pytest tests/'; got: {[e.message for e in e301]}")
        self.assertTrue(any("npm test" in e.message for e in e301),
                        f"E301 must fire for object-form 'npm test'; got: {[e.message for e in e301]}")

    # --- E307 reverse direction test ---

    def test_e307_fires_for_validation_only_without_behavior(self):
        """E307 fires when a spec_ref.id has only validation items but no behavior item."""
        data = self._minimal_impl_context(checklist_items=[
            {
                "id": "CHK_VAL_ONLY",
                "spec_ref": {"type": "fr", "id": "fr-orphan", "line_range": "L1-L10", "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"},
                "description": "Validation without paired behavior",
                "type": "validation",
                "layer": "tests",
                "linked_test_expectation": "pytest test_orphan",
                "nfr_refs": ["nfr-availability-uptime"],
                "fixture_ref": "fixture-orphan"
            }
        ])

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

        e307_errors = [e for e in errors if e.code == "E307"]
        self.assertTrue(
            any("fr-orphan" in e.message for e in e307_errors),
            f"Expected E307 for fr-orphan (validation only, no behavior). Got E307: {[e.message for e in e307_errors]}"
        )


    # --- Schema root-properties shape: no phantom unevaluated-properties companion ---

    def test_schema_accepts_all_root_properties_plan_execution_review(self):
        """After schema restructure, plan/execution/review all evaluate at root; no phantom unevaluated companion."""
        path = os.path.join(self.fixtures_dir, "valid_empty_execution_review.json")
        errors = validate_file(self.repo_root, path)
        unevaluated = [e for e in errors if "Unevaluated properties" in e.message or "unevaluated properties" in e.message.lower()]
        self.assertEqual(unevaluated, [], f"Unexpected phantom unevaluated-properties errors: {[e.message for e in unevaluated]}")

    def test_invalid_fixture_emits_only_real_error_not_phantom(self):
        """Invalid 16-impl-context fixture surfaces a real schema error but no phantom unevaluated companion."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-invalid-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {
                    "functional_summary": "Invalid test.",
                    "scope_in": ["core"],
                    "scope_out": [],
                    "target_file_patterns": ["src/**"],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": [{"id": "CHK", "spec_ref": {"type": "not-a-valid-enum", "id": "fr-x"}, "description": "d", "type": "behavior", "layer": "api"}],
                },
                "docs_impact": {"status": "not_required", "rationale": "n/a"},
            },
            "canonical_refs_used": [],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "16_impl_context.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            (Path(td) / "common").mkdir()
            (Path(td) / "common" / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(p))
        unevaluated = [e for e in errors if "Unevaluated properties" in e.message]
        self.assertEqual(unevaluated, [], f"Phantom unevaluated companion on invalid fixture: {[e.message for e in errors]}")

    def test_invalid_fixtures_09_13_15_emit_no_phantom_unevaluated_companion(self):
        """Steps 09/13/15 share the same schema restructure as 16 — invalid fixtures must surface
        their real errors without triggering a phantom 'Unevaluated properties' companion."""
        cases = [
            "tests/fixtures/step_09/invalid_bad_depends_on.json",
            "tests/fixtures/step_13/invalid_empty_no_decision.json",
            "tests/fixtures/step_15/invalid_green_no_validators.json",
        ]
        for rel in cases:
            with self.subTest(fixture=rel):
                errors = validate_file(self.repo_root, rel)
                unevaluated = [e for e in errors if "Unevaluated properties" in e.message]
                self.assertEqual(
                    unevaluated, [],
                    f"Phantom unevaluated companion on {rel}: {[e.message for e in errors]}",
                )
                self.assertTrue(
                    any(e.code == "E520" for e in errors),
                    f"Expected a real E520 on {rel}, got: {[(e.code, e.message[:80]) for e in errors]}",
                )

    def test_invalid_fixture_step_08_no_phantom_unevaluated_companion(self):
        """Step 08 shares the same schema restructure as 09/13/15/16 — its invalid fixture must
        surface its real error without triggering a phantom 'Unevaluated properties' companion."""
        rel = "tests/fixtures/step_08/invalid/invalid_missing_verifies.json"
        errors = validate_file(self.repo_root, rel)
        unevaluated = [e for e in errors if "Unevaluated properties" in e.message]
        self.assertEqual(
            unevaluated, [],
            f"Phantom unevaluated companion on {rel}: {[e.message for e in errors]}",
        )
        self.assertTrue(
            any(e.code == "E520" for e in errors),
            f"Expected a real E520 on {rel}, got: {[(e.code, e.message[:80]) for e in errors]}",
        )

    # --- ambiguityItem accepts optional decision/proposed_assumption ---

    def test_emergent_ambiguity_with_decision_and_assumption(self):
        """ambiguityItem accepts optional decision + proposed_assumption fields."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-amb-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {"functional_summary": "amb test.", "scope_in": ["core"], "scope_out": [], "target_file_patterns": ["src/**"]},
                "spec_alignment": {"requirements_summary": [{"theme": "Core", "summary": "x"}], "checklist": []},
                "docs_impact": {"status": "not_required", "rationale": "n/a"},
            },
            "execution": {
                "emergent_ambiguities": [
                    {
                        "id": "amb-1",
                        "description": "Ambiguity surfaced during execution",
                        "about": ["fr-core"],
                        "decision": "accepted",
                        "proposed_assumption": "Proceed on the accepted reading.",
                    }
                ]
            },
            "canonical_refs_used": [],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "16_impl_context.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            (Path(td) / "common").mkdir()
            (Path(td) / "common" / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(p))
        e520 = [e for e in errors if e.code == "E520"]
        e530 = [e for e in errors if e.code == "E530"]
        self.assertFalse(
            any("resolved" in e.message or "decision" in e.message for e in e520 + e530),
            f"decision/proposed_assumption must validate. Got: {[e.message for e in errors]}"
        )

    def test_emergent_ambiguity_still_valid_without_decision(self):
        """ambiguityItem without decision/proposed_assumption still validates (fields optional)."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-amb-min",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {"functional_summary": "amb test.", "scope_in": ["core"], "scope_out": [], "target_file_patterns": ["src/**"]},
                "spec_alignment": {"requirements_summary": [{"theme": "Core", "summary": "x"}], "checklist": []},
                "docs_impact": {"status": "not_required", "rationale": "n/a"},
            },
            "execution": {
                "emergent_ambiguities": [
                    {"id": "amb-2", "description": "Minimal ambiguity shape", "about": ["fr-core"]}
                ]
            },
            "canonical_refs_used": [],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "16_impl_context.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            (Path(td) / "common").mkdir()
            (Path(td) / "common" / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(p))
        ambiguity_errors = [e for e in errors if "emergent_ambiguities" in e.message]
        self.assertEqual(ambiguity_errors, [], f"Minimal ambiguity must validate. Got: {[e.message for e in ambiguity_errors]}")

    # --- docs_touched accepts any file whose basename is a canonical doc name ---

    def _docs_touched_impl_context(self, docs_touched: list) -> dict:
        return {
            "$schema": "vc:16-impl-context",
            "id": "step-doc-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "summary": {"functional_summary": "doc test.", "scope_in": ["core"], "scope_out": [], "target_file_patterns": ["src/**"]},
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "x"}],
                    "checklist": [{
                        "id": "CHK_D",
                        "spec_ref": {"type": "fr", "id": "fr-x", "line_range": "L1-L10", "commit_hash": "a" * 40},
                        "description": "implement x",
                        "type": "behavior",
                        "layer": "api",
                        "linked_test_expectation": "pytest x",
                        "nfr_refs": ["nfr-availability-uptime"],
                        "fixture_ref": "fixture-x",
                        "implementation": {
                            "status": "in_progress",
                            "files_touched": ["src/x.py"],
                            "actions": [{"type": "file_edit", "target": "src/x.py", "description": "edit"}],
                        },
                    }],
                },
                "docs_impact": {"status": "required", "rationale": "Code change requires doc update.", "docs_touched": docs_touched},
            },
            "canonical_refs_used": [],
        }

    def _run_docs_test(self, docs_touched: list):
        data = self._docs_touched_impl_context(docs_touched)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "16_impl_context.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            # _find_seed_manifest uses deterministic spec_path-relative resolution:
            # spec_dir = dirname(spec_path) (since basename != "impl_context"),
            # then looks for spec_dir/common/seed_manifest.json.
            # spec_path is td/16_impl_context.json → spec_dir = td/ → place manifest at td/common/.
            (Path(td) / "common").mkdir(parents=True)
            (Path(td) / "common" / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["docs/**/*.md", "CHANGELOG.md"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            return validate_step_16(data, self.repo_root, spec_path=str(p))

    def test_docs_touched_accepts_component_readme(self):
        errors = self._run_docs_test(["theme/README.md"])
        bad = [e for e in errors if "non-doc path" in e.message]
        self.assertEqual(bad, [], f"component README should be accepted. Got: {[e.message for e in bad]}")

    def test_docs_touched_accepts_root_readme(self):
        errors = self._run_docs_test(["README.md"])
        bad = [e for e in errors if "non-doc path" in e.message]
        self.assertEqual(bad, [], f"root README should be accepted. Got: {[e.message for e in bad]}")

    def test_docs_touched_rejects_non_doc_path(self):
        errors = self._run_docs_test(["src/app.py"])
        bad = [e for e in errors if "non-doc path" in e.message and "src/app.py" in e.message]
        self.assertTrue(bad, f"non-doc path must be rejected. Got errors: {[e.message for e in errors]}")

    # --- milestone_supporting_files exempts cross-cutting files from W603 ---

    def _w603_data(self, milestone_supporting_files=None):
        plan = {
            "summary": {
                "functional_summary": "W603 fix test.",
                "scope_in": ["core"],
                "scope_out": [],
                "target_file_patterns": ["src/**", "tests/**"],
            },
            "spec_alignment": {
                "requirements_summary": [{"theme": "Core", "summary": "x"}],
                "checklist": [{
                    "id": "CHK_W603_FIX",
                    "spec_ref": {"type": "fr", "id": "fr-x", "line_range": "L1-L10", "commit_hash": "a" * 40},
                    "description": "work",
                    "type": "behavior",
                    "layer": "api",
                    "linked_test_expectation": "pytest x",
                    "nfr_refs": ["nfr-availability-uptime"],
                    "fixture_ref": "fixture-x",
                    "implementation": {
                        "status": "in_progress",
                        "files_touched": ["src/x.py"],
                        "actions": [],
                    },
                }],
            },
            "docs_impact": {"status": "not_required", "rationale": "n/a"},
        }
        if milestone_supporting_files is not None:
            plan["summary"]["milestone_supporting_files"] = milestone_supporting_files
        return {
            "$schema": "vc:16-impl-context",
            "id": "step-w603-fix",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": plan,
            "execution": {"files_touched": ["src/x.py", "tests/README.md"]},
            "canonical_refs_used": [],
        }

    def _run_w603(self, data):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "16_impl_context.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            (Path(td) / "common").mkdir()
            (Path(td) / "common" / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            from specdev_tools.validation.validators.step_16 import validate_step_16
            return validate_step_16(data, self.repo_root, spec_path=str(p))

    def test_w603_does_not_fire_for_milestone_supporting_file(self):
        data = self._w603_data(milestone_supporting_files=["tests/README.md"])
        w603 = [e for e in self._run_w603(data) if e.code == "W603" and "tests/README.md" in e.message]
        self.assertEqual(w603, [], f"milestone_supporting_files entry must exempt W603. Got: {[e.message for e in w603]}")

    def test_w603_still_fires_for_truly_undeclared_file(self):
        data = self._w603_data(milestone_supporting_files=[])
        w603 = [e for e in self._run_w603(data) if e.code == "W603" and "tests/README.md" in e.message]
        self.assertTrue(w603, "W603 must still fire for undeclared file not in milestone_supporting_files.")

    # --- W570: seed_manifest.json missing / unreadable / missing doc_paths ---

    def _run_w570(self, write_manifest=True, manifest_text=None):
        """Run validate_step_16 over valid_minimal.json with a controllable
        common/seed_manifest.json: absent (write_manifest=False), malformed
        (manifest_text is invalid JSON), or well-formed (manifest_text is a
        dict serialized as-is, e.g. missing/empty doc_paths)."""
        base_path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            fixture_path = tmp_dir / "16_impl_context.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            if write_manifest:
                common_dir = tmp_dir / "common"
                common_dir.mkdir()
                text = manifest_text if isinstance(manifest_text, str) else json.dumps(manifest_text or {})
                (common_dir / "seed_manifest.json").write_text(text, encoding="utf-8")
            from specdev_tools.validation.validators.step_16 import validate_step_16
            return validate_step_16(data, self.repo_root, spec_path=str(fixture_path))

    def test_w570_fires_when_manifest_missing(self):
        # Branch 1: manifest_path is None (no common/seed_manifest.json at all).
        errors = self._run_w570(write_manifest=False)
        w570 = [e for e in errors if e.code == "W570" and "not found" in e.message]
        self.assertTrue(w570, f"Expected W570 for missing seed_manifest.json. Got: {errors}")

    def test_w570_fires_when_manifest_malformed(self):
        # Branch 2: manifest exists but is unreadable/malformed (json.load raises).
        errors = self._run_w570(write_manifest=True, manifest_text="{not valid json")
        w570 = [e for e in errors if e.code == "W570" and "Failed to read seed_manifest.json" in e.message]
        self.assertTrue(w570, f"Expected W570 for malformed seed_manifest.json. Got: {errors}")

    def test_w570_fires_when_doc_paths_missing(self):
        # Branch 3: manifest is valid JSON but has no (or empty) doc_paths.
        errors = self._run_w570(write_manifest=True, manifest_text={"other_field": "x"})
        w570 = [e for e in errors if e.code == "W570" and "missing doc_paths" in e.message]
        self.assertTrue(w570, f"Expected W570 for missing doc_paths. Got: {errors}")

    def test_w570_does_not_fire_with_valid_manifest(self):
        # Control: a well-formed manifest with non-empty doc_paths must not fire W570.
        errors = self._run_w570(write_manifest=True, manifest_text={"doc_paths": ["README.md", "docs/**"]})
        w570 = [e for e in errors if e.code == "W570"]
        self.assertEqual(w570, [], f"Did not expect W570 with a valid seed_manifest.json. Got: {w570}")


if __name__ == '__main__':
    unittest.main()
