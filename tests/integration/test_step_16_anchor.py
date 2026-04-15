"""Integration tests for the Step 16 Trinity Anchor validator.

Covers:
  - Schema validation: valid fixtures pass, invalid fixtures fail
  - E308 (ANCHOR_SCOPE_DRIFT): scope contradiction and FR ownership conflict
  - E309 (ANCHOR_CHECKLIST_DRIFT): cross-milestone checklist ID collision
  - W580 (ANCHOR_DRIFT_SKIP / ANCHOR_VALIDATOR_WRONG_ARTIFACT): guard paths
"""
import json
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional

from specdev_tools.validation.validate import validate_file


class TestStep16AnchorSchema(unittest.TestCase):
    """Schema-level tests using pre-built fixture files."""

    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)
        self.fixtures_dir = toolkit_root / "tests" / "fixtures" / "step_16"

    def test_valid_anchor_minimal_passes(self):
        """Minimal valid anchor with empty milestone_index should pass."""
        path = self.fixtures_dir / "valid_anchor_minimal.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertEqual(errors, [], f"Expected no errors. Got: {errors}")

    def test_valid_anchor_with_milestones_passes(self):
        """Anchor with populated milestone_index and drift checks should pass."""
        path = self.fixtures_dir / "valid_anchor_with_milestones.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertEqual(errors, [], f"Expected no errors. Got: {errors}")

    def test_invalid_anchor_missing_drift_fails(self):
        """Anchor without plan.drift field should fail schema validation."""
        path = self.fixtures_dir / "invalid_anchor_missing_drift.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            len(errors) > 0,
            "Expected schema errors for missing plan.drift. Got no errors."
        )

    def test_invalid_anchor_has_execution_fails(self):
        """Anchor with forbidden execution section should fail (unevaluatedProperties)."""
        path = self.fixtures_dir / "invalid_anchor_has_execution.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            len(errors) > 0,
            "Expected schema errors for forbidden execution section. Got no errors."
        )


class TestStep16AnchorE308ScopeDrift(unittest.TestCase):
    """E308 ANCHOR_SCOPE_DRIFT tests — require filesystem setup."""

    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)

    def _make_anchor(self, tmp_dir: Path, scope_in: list, scope_out: list,
                     milestone_index: Optional[list] = None) -> Path:
        anchor = {
            "$schema": "vc:16-anchor",
            "id": "anchor-v1",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "artifact_role": "anchor",
            "canonical_refs_used": [],
            "plan": {
                "summary": {
                    "functional_summary": "Test anchor for E308 scope drift.",
                    "scope_in": scope_in,
                    "scope_out": scope_out,
                },
                "ambiguities": [],
                "drift": {"checks": []},
                "milestone_index": milestone_index or [],
            },
        }
        path = tmp_dir / "16_impl_context.json"
        path.write_text(json.dumps(anchor), encoding="utf-8")
        return path

    def _make_milestone(self, impl_context_dir: Path, filename: str,
                        scope_in: list, scope_out: list,
                        checklist: Optional[list] = None) -> None:
        ms = {
            "$schema": "vc:16-impl-context",
            "id": "ms-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Test milestone for scope drift.",
                    "scope_in": scope_in,
                    "scope_out": scope_out,
                    "target_file_patterns": ["src/**/*.py"],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Core", "summary": "Test"}],
                    "checklist": checklist or [],
                },
                "docs_impact": {
                    "status": "not-required",
                    "rationale": "No doc changes needed.",
                    "docs_touched": [],
                },
                "review_requirements": {"test_commands": ["pytest tests/"]},
            },
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": [],
        }
        (impl_context_dir / filename).write_text(json.dumps(ms), encoding="utf-8")

    def test_e308_milestone_scope_in_contradicts_anchor_scope_out(self):
        """E308 fires when milestone scope_in item appears in anchor scope_out."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
            )
            self._make_milestone(
                impl_context_dir, "ms_oauth.json",
                scope_in=["oauth-flows"],  # contradicts anchor scope_out
                scope_out=[],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" for e in errors),
            f"Expected E308 for scope_in/scope_out contradiction. Got: {errors}"
        )

    def test_e308_milestone_scope_out_contradicts_anchor_scope_in(self):
        """E308 fires when milestone scope_out item appears in anchor scope_in."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
            )
            self._make_milestone(
                impl_context_dir, "ms_jwt.json",
                scope_in=[],
                scope_out=["jwt-token-validation"],  # contradicts anchor scope_in
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" for e in errors),
            f"Expected E308 for reverse scope contradiction. Got: {errors}"
        )

    def test_e308_fr_ownership_conflict_two_active_milestones(self):
        """E308 fires when the same FR is owned by two active milestones."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=[],
                milestone_index=[
                    {
                        "milestone_id": "ms-a",
                        "context_path": "spec/impl_context/ms_a.json",
                        "status": "active",
                        "fr_refs": ["fr-login"],
                        "checklist_id_prefix": "MSA",
                        "summary": "Milestone A implements login.",
                    },
                    {
                        "milestone_id": "ms-b",
                        "context_path": "spec/impl_context/ms_b.json",
                        "status": "active",
                        "fr_refs": ["fr-login"],  # same FR — conflict
                        "checklist_id_prefix": "MSB",
                        "summary": "Milestone B also implements login.",
                    },
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" for e in errors),
            f"Expected E308 for FR ownership conflict. Got: {errors}"
        )

    def test_e308_done_milestone_does_not_conflict(self):
        """A 'done' milestone does not block the same FR in an active milestone."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=[],
                milestone_index=[
                    {
                        "milestone_id": "ms-done",
                        "context_path": "spec/impl_context/ms_done.json",
                        "status": "done",  # done — not a conflict source
                        "fr_refs": ["fr-login"],
                        "checklist_id_prefix": "DONE",
                        "summary": "Completed milestone.",
                    },
                    {
                        "milestone_id": "ms-active",
                        "context_path": "spec/impl_context/ms_active.json",
                        "status": "active",
                        "fr_refs": ["fr-login"],
                        "checklist_id_prefix": "ACTIVE",
                        "summary": "Active milestone revisiting login.",
                    },
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e308_errors = [e for e in errors if e.code == "E308"]
        self.assertEqual(e308_errors, [], f"Done milestone should not trigger E308. Got: {e308_errors}")

    def test_no_e308_when_no_scope_overlap(self):
        """No E308 when milestone scope does not overlap anchor scope."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
            )
            self._make_milestone(
                impl_context_dir, "ms_jwt.json",
                scope_in=["jwt-token-validation"],  # matches anchor scope_in — fine
                scope_out=[],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e308_errors = [e for e in errors if e.code == "E308"]
        self.assertEqual(e308_errors, [], f"Did not expect E308. Got: {e308_errors}")


class TestStep16AnchorE309ChecklistDrift(unittest.TestCase):
    """E309 ANCHOR_CHECKLIST_DRIFT — cross-milestone checklist ID conflict."""

    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)

    def _make_anchor(self, tmp_dir: Path) -> Path:
        anchor = {
            "$schema": "vc:16-anchor",
            "id": "anchor-v1",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "artifact_role": "anchor",
            "canonical_refs_used": [],
            "plan": {
                "summary": {
                    "functional_summary": "Test anchor for E309 checklist drift.",
                    "scope_in": ["auth"],
                    "scope_out": [],
                },
                "ambiguities": [],
                "drift": {"checks": []},
                "milestone_index": [],
            },
        }
        path = tmp_dir / "16_impl_context.json"
        path.write_text(json.dumps(anchor), encoding="utf-8")
        return path

    def _make_milestone_with_checklist(self, impl_context_dir: Path, filename: str,
                                       checklist: list) -> None:
        ms = {
            "$schema": "vc:16-impl-context",
            "id": "ms-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Test milestone for E309.",
                    "scope_in": ["auth"],
                    "scope_out": [],
                    "target_file_patterns": ["src/**/*.py"],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Auth", "summary": "Test"}],
                    "checklist": checklist,
                },
                "docs_impact": {
                    "status": "not-required",
                    "rationale": "No doc changes.",
                    "docs_touched": [],
                },
                "review_requirements": {"test_commands": ["pytest tests/"]},
            },
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": [],
        }
        (impl_context_dir / filename).write_text(json.dumps(ms), encoding="utf-8")

    def _checklist_item(self, item_id: str, spec_ref_id: str, item_type: str = "behavior") -> dict:
        return {
            "id": item_id,
            "spec_ref": {
                "type": "fr",
                "id": spec_ref_id,
                "line_range": "L1-L10",
                "commit_hash": "a1b2c3d4e5f61234567890123456789012345678",
            },
            "description": f"Checklist item {item_id}.",
            "type": item_type,
            "layer": "api",
            "linked_test_expectation": "pytest test_auth",
            "nfr_refs": [],
            "fixture_ref": "fixture-auth",
        }

    def test_e309_same_id_different_spec_ref(self):
        """E309 fires when same checklist ID maps to different spec_ref.id across milestones."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(tmp_dir)
            self._make_milestone_with_checklist(
                impl_context_dir, "ms_a.json",
                checklist=[self._checklist_item("AUTH_LOGIN", "fr-login-v1")],
            )
            self._make_milestone_with_checklist(
                impl_context_dir, "ms_b.json",
                # Same ID "AUTH_LOGIN" but different spec_ref.id — E309
                checklist=[self._checklist_item("AUTH_LOGIN", "fr-login-v2")],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E309" for e in errors),
            f"Expected E309 for checklist ID collision. Got: {errors}"
        )

    def test_no_e309_same_id_same_spec_ref(self):
        """No E309 when same checklist ID maps to same spec_ref.id (valid duplication)."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(tmp_dir)
            self._make_milestone_with_checklist(
                impl_context_dir, "ms_a.json",
                checklist=[self._checklist_item("AUTH_LOGIN", "fr-login-v1")],
            )
            self._make_milestone_with_checklist(
                impl_context_dir, "ms_b.json",
                checklist=[self._checklist_item("AUTH_LOGIN", "fr-login-v1")],  # same — ok
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e309_errors = [e for e in errors if e.code == "E309"]
        self.assertEqual(e309_errors, [], f"Did not expect E309. Got: {e309_errors}")

    def test_no_e309_different_ids_different_spec_refs(self):
        """No E309 when checklist IDs are unique across milestones."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = self._make_anchor(tmp_dir)
            self._make_milestone_with_checklist(
                impl_context_dir, "ms_a.json",
                checklist=[self._checklist_item("AUTH_LOGIN", "fr-login")],
            )
            self._make_milestone_with_checklist(
                impl_context_dir, "ms_b.json",
                checklist=[self._checklist_item("AUTH_SESSION", "fr-session")],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e309_errors = [e for e in errors if e.code == "E309"]
        self.assertEqual(e309_errors, [], f"Did not expect E309. Got: {e309_errors}")


class TestStep16AnchorW580Guard(unittest.TestCase):
    """W580 guard tests — wrong artifact type and missing spec_path."""

    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)

    def test_w580_non_anchor_routed_to_anchor_validator(self):
        """W580 fires when anchor validator receives a non-anchor artifact."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        # Pass a plain impl-context artifact (no artifact_role) with no path
        data = {
            "$schema": "vc:16-impl-context",
            "id": "ms-test",
            "plan": {},
        }
        errors = validate_step_16_anchor(data, self.repo_root, spec_path=None)
        self.assertTrue(
            any(e.code == "W580" for e in errors),
            f"Expected W580 for non-anchor artifact. Got: {errors}"
        )

    def test_w580_spec_path_none_skips_drift_checks(self):
        """W580 fires when spec_path is None and artifact_role is 'anchor'."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        data = {
            "$schema": "vc:16-anchor",
            "artifact_role": "anchor",
            "plan": {
                "summary": {"functional_summary": "Test."},
                "ambiguities": [],
                "drift": {"checks": []},
                "milestone_index": [],
            },
        }
        errors = validate_step_16_anchor(data, self.repo_root, spec_path=None)
        self.assertTrue(
            any(e.code == "W580" for e in errors),
            f"Expected W580 for None spec_path. Got: {errors}"
        )

    def test_no_e308_e309_when_no_impl_context_dir(self):
        """No E308/E309 when impl_context/ directory does not exist yet."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor = {
                "$schema": "vc:16-anchor",
                "id": "anchor-v1",
                "owner": "api",
                "created_at": "2024-01-01T00:00:00Z",
                "artifact_role": "anchor",
                "canonical_refs_used": [],
                "plan": {
                    "summary": {
                        "functional_summary": "Fresh anchor, no milestones yet.",
                        "scope_in": ["auth"],
                        "scope_out": [],
                    },
                    "ambiguities": [],
                    "drift": {"checks": []},
                    "milestone_index": [],
                },
            }
            anchor_path = tmp_dir / "16_impl_context.json"
            anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
            # No impl_context/ directory — fresh anchor

            errors = validate_file(self.repo_root, str(anchor_path))

        e_codes = {e.code for e in errors}
        self.assertNotIn("E308", e_codes, f"No E308 expected without impl_context/. Errors: {errors}")
        self.assertNotIn("E309", e_codes, f"No E309 expected without impl_context/. Errors: {errors}")


if __name__ == "__main__":
    unittest.main()
