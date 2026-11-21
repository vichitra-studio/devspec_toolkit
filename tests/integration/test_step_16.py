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

    def test_invalid_bad_enum(self):
        # Expect failure due to bad enum
        path = os.path.join(self.fixtures_dir, "invalid_bad_enum.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (bad enum) should fail validation")
        self.assertTrue(any(e.code == "E530" for e in errors), f"Expected E530. Got: {errors}")

    def test_valid_metadata_item_without_proof(self):
        # A metadata item needs no proof link: a plan item stores one link, `realises`.
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
    
    def test_valid_with_semantic_review(self):
        # Valid fixture with semantic_review populated and verdict=verified should pass
        path = os.path.join(self.fixtures_dir, "valid_with_semantic_review.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid semantic_review fixture should pass. Errors: {errors}")

    def test_e304_roadmap_task_uncovered(self):
        # E304: roadmap has implement-logout but checklist only covers implement-login
        path = os.path.join(self.step16_dir, "e304_roadmap", "impl_context", "ms_test_plan.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "E304 fixture should fail validation")
        self.assertTrue(
            any(e.code == "E304" for e in errors),
            f"Expected E304 error. Got: {errors}"
        )

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

    def test_impl_context_16c_dispatch_chains_up_through_the_16a_checks(self):
        """Content-based dispatch: an impl_context/ artifact with review.verdict routes to the 16c validator,
        which runs the 16a checks too: the remediation-link warning (W584) of 16a fires for a reviewed plan."""
        data = self._doc_plan_example()
        data["review"] = {
            "verdict": "needs_work",
            "findings": [{"id": "finding-one", "type": "bug", "severity": "minor", "description": "A finding.",
                          "remediation_task": {"task_id": "fix-1", "checklist_ids": ["NO_SUCH_ITEM"]},
                          "metadata": {"source": "reviewer", "impact": "none"}}],
        }
        from specdev_tools.core.step_paths import refine_impl_context_substep

        self.assertEqual(refine_impl_context_substep("16a", data), "16c")
        errors = self._validate_plan_data(data)
        link_errors = [e for e in errors if e.code == "W584" and "NO_SUCH_ITEM" in e.message]
        self.assertEqual(len(link_errors), 1, f"Expected the 16a remediation-link warning through the 16c route. Got: {errors}")

    def test_impl_context_16a_dispatch_stays_16a_for_plan_only_artifact(self):
        """An impl_context/ artifact with no review.verdict stays on the 16a path (default); execution records do not change the route."""
        from specdev_tools.core.step_paths import refine_impl_context_substep

        plan_only = {
            "$schema": "vc:16-impl-context",
            "plan": {},
        }
        plan_plus_empty_exec = {
            "$schema": "vc:16-impl-context",
            "plan": {},
            "execution": {"records": []},
            "review": {},
        }
        self.assertEqual(refine_impl_context_substep("16a", plan_only), "16a")
        self.assertEqual(refine_impl_context_substep("16a", plan_plus_empty_exec), "16a")
        # Non-impl_context steps are never refined
        self.assertEqual(refine_impl_context_substep("04", plan_only), "04")
        self.assertEqual(refine_impl_context_substep("unknown", plan_only), "unknown")

    def test_impl_context_16a_dispatch_e2e_routes_through_16a_validator(self):
        """End-to-end counterpart to the refiner-only 16a dispatch test.

        Writes a plan-only artifact (no
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
        """Chain-up (16c -> 16a -> base) must not cause base checks to fire multiple times on the same artifact.

        Only 16a calls the base validator, so a base-level error (here E530) appears exactly once in the list
        returned by 16c.
        """
        from specdev_tools.validation.validators.step_16c import validate_step_16c

        data = self._doc_plan_example()
        data["plan"]["spec_alignment"]["checklist"][0]["type"] = "not-a-type"
        data["review"] = {"verdict": "verified"}

        with tempfile.TemporaryDirectory() as td:
            impl_context_dir = Path(td) / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_chainup.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            errors = validate_step_16c(data, self.repo_root, str(fixture_path))

        e530_errors = [e for e in errors if e.code == "E530" and "not-a-type" in e.message]
        self.assertEqual(
            len(e530_errors), 1,
            f"Chain-up must fire the base-level E530 exactly once. Got {len(e530_errors)}. Full errors: {errors}",
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
                            "realises": ["tc-x"],
                            "description": "Login feature",
                            "type": "behavior",
                            "layer": "api",
                            "implementation": {
                                "files_touched": ["src/auth.py"],
                                "actions": []
                            }
                        },
                        {
                            "id": "CHK_W603_VAL",
                            "realises": ["tc-x"],
                            "description": "Validate login",
                            "type": "validation",
                            "layer": "tests"
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
                            "realises": ["tc-x"],
                            "description": "Login feature",
                            "type": "behavior",
                            "layer": "api",
                            "implementation": {
                                "files_touched": ["src/auth.py", "src/utils.py"],
                                "actions": []
                            }
                        },
                        {
                            "id": "CHK_W603_OK_VAL",
                            "realises": ["tc-x"],
                            "description": "Validate login",
                            "type": "validation",
                            "layer": "tests"
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
                    "checklist": [{"id": "CHK", "realises": ["tc-x"], "description": "d", "type": "not-a-valid-enum", "layer": "api"}],
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
                        "realises": ["tc-x"],
                        "description": "implement x",
                        "type": "behavior",
                        "layer": "api",
                        "implementation": {
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
                    "realises": ["tc-x"],
                    "description": "work",
                    "type": "behavior",
                    "layer": "api",
                    "implementation": {
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
