"""Integration tests for the Step 16 Trinity Anchor validator.

Covers:
  - Schema validation: valid fixtures pass, invalid fixtures fail
  - E308 (ANCHOR_SCOPE_DRIFT): scope contradiction and FR ownership conflict
  - E309 (ANCHOR_CHECKLIST_DRIFT): cross-milestone checklist ID collision
  - W585 (ANCHOR_DRIFT_SKIP): spec_path is None — filesystem checks skipped
  - W586 (ANCHOR_VALIDATOR_WRONG_ARTIFACT): non-anchor artifact dispatched here
  - W587 (ANCHOR_DRIFT_CHECKS_STALE): non-empty milestone_index but empty drift.checks
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
        """Anchor without plan.drift field should fail schema validation.

        Assert on the specific signal ('drift' required-property error) so a
        different unrelated failure (e.g. missing owner) cannot satisfy this
        test — the point is to pin the drift-required contract.
        """
        path = self.fixtures_dir / "invalid_anchor_missing_drift.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "'drift'" in e.message for e in errors),
            f"Expected E520 'drift' required-property error. Got: {errors}"
        )

    def test_invalid_anchor_has_execution_fails(self):
        """Anchor with forbidden execution section should fail (unevaluatedProperties).

        Assert on the specific signal ('execution' rejected as unevaluated) so
        a different unrelated failure cannot satisfy this test — the point is
        to pin the anchor's unevaluatedProperties:false contract.
        """
        path = self.fixtures_dir / "invalid_anchor_has_execution.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "execution" in e.message for e in errors),
            f"Expected E520 'execution' unevaluatedProperties error. Got: {errors}"
        )

    def test_invalid_anchor_has_milestone_ref_fails(self):
        """Anchor with a top-level milestone_ref should fail (unevaluatedProperties).

        The anchor spans all milestones and has no single owning milestone, so
        the anchor schema deliberately does NOT declare milestone_ref. Presence
        must be rejected by `unevaluatedProperties: false` at the artifact root.
        This pins that contract so future schema edits can't silently
        re-introduce the loophole.
        """
        path = self.fixtures_dir / "invalid_anchor_has_milestone_ref.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "milestone_ref" in e.message for e in errors),
            f"Expected E520 'milestone_ref' unevaluatedProperties error. Got: {errors}"
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
                        "status": "in_progress",
                        "fr_refs": ["fr-login"],
                        "checklist_id_prefix": "MSA",
                        "summary": "Milestone A implements login.",
                    },
                    {
                        "milestone_id": "ms-b",
                        "context_path": "spec/impl_context/ms_b.json",
                        "status": "in_progress",
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
                        "status": "in_progress",
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


class TestStep16AnchorGuard(unittest.TestCase):
    """W585/W586 guard tests — wrong artifact type and missing spec_path."""

    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)

    def test_w586_non_anchor_routed_to_anchor_validator(self):
        """W586 fires when anchor validator receives a non-anchor artifact."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        # Pass a plain impl-context artifact (no artifact_role) with no path
        data = {
            "$schema": "vc:16-impl-context",
            "id": "ms-test",
            "plan": {},
        }
        errors = validate_step_16_anchor(data, self.repo_root, spec_path=None)
        self.assertTrue(
            any(e.code == "W586" for e in errors),
            f"Expected W586 for non-anchor artifact. Got: {errors}"
        )

    def test_w585_spec_path_none_skips_drift_checks(self):
        """W585 fires when spec_path is None and artifact_role is 'anchor'."""
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
            any(e.code == "W585" for e in errors),
            f"Expected W585 for None spec_path. Got: {errors}"
        )

    def test_non_milestone_file_in_impl_context_is_ignored(self):
        """A file in impl_context/ whose $schema != vc:16-impl-context must NOT
        contribute to drift detection.  Catches misfiled docs, backups, or
        non-milestone artifacts from polluting the E308/E309 registries.
        """
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor = {
                "$schema": "vc:16-anchor",
                "id": "anchor-v1",
                "owner": "api",
                "created_at": "2024-01-01T00:00:00Z",
                "artifact_role": "anchor",
                "canonical_refs_used": [],
                "plan": {
                    "summary": {
                        "functional_summary": "Anchor with stray non-milestone files.",
                        "scope_in": ["auth"],
                        "scope_out": ["payments"],
                    },
                    "ambiguities": [],
                    "drift": {"checks": []},
                    "milestone_index": [],
                },
            }
            anchor_path = tmp_dir / "16_impl_context.json"
            anchor_path.write_text(json.dumps(anchor), encoding="utf-8")

            # Stray file: schema mismatch — must be ignored.
            (impl_context_dir / "notes.json").write_text(
                json.dumps({
                    "$schema": "vc:draft-notes",
                    "plan": {
                        "summary": {
                            # Would trigger E308 if it were counted.
                            "scope_in": ["payments"],
                        },
                        "spec_alignment": {
                            "checklist": [
                                # Would trigger E309 if it were counted against a
                                # real milestone with the same checklist id.
                                {"id": "AUTH_LOGIN", "spec_ref": {"id": "fr-ghost"}}
                            ]
                        },
                    },
                }),
                encoding="utf-8",
            )

            # Real milestone: same AUTH_LOGIN id but mapped to fr-login — alone
            # this should NOT fire E309 (one-source-of-truth), and scope_in
            # does not contradict anchor scope_out.
            (impl_context_dir / "ms_real.json").write_text(
                json.dumps({
                    "$schema": "vc:16-impl-context",
                    "id": "ms-real",
                    "plan": {
                        "summary": {"scope_in": ["auth"], "scope_out": []},
                        "spec_alignment": {
                            "checklist": [
                                {"id": "AUTH_LOGIN", "spec_ref": {"id": "fr-login"}}
                            ]
                        },
                    },
                }),
                encoding="utf-8",
            )

            errors = validate_step_16_anchor(anchor, self.repo_root, str(anchor_path))

        e308 = [e for e in errors if e.code == "E308"]
        e309 = [e for e in errors if e.code == "E309"]
        self.assertEqual(e308, [], f"Stray file must not trigger E308. Got: {e308}")
        self.assertEqual(e309, [], f"Stray file must not trigger E309. Got: {e309}")

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


class TestStep16AnchorW587DriftChecksStale(unittest.TestCase):
    """W587 ANCHOR_DRIFT_CHECKS_STALE — milestone_index populated but drift.checks empty."""

    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)

    def _build_anchor(self, milestone_index: list, drift_checks: list) -> dict:
        return {
            "$schema": "vc:16-anchor",
            "id": "anchor-v1",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "artifact_role": "anchor",
            "canonical_refs_used": [],
            "plan": {
                "summary": {
                    "functional_summary": "Anchor for W587 coverage.",
                    "scope_in": ["auth"],
                    "scope_out": [],
                },
                "ambiguities": [],
                "drift": {"checks": drift_checks},
                "milestone_index": milestone_index,
            },
        }

    def _write_and_validate(self, anchor: dict) -> list:
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = tmp_dir / "16_impl_context.json"
            anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
            return validate_file(self.repo_root, str(anchor_path))

    def _ms_entry(self, milestone_id: str, fr_refs: Optional[list] = None,
                  status: str = "in_progress") -> dict:
        return {
            "milestone_id": milestone_id,
            "context_path": f"spec/impl_context/{milestone_id.replace('-', '_')}_plan.json",
            "status": status,
            "fr_refs": fr_refs or ["fr-login"],
            "checklist_id_prefix": milestone_id.upper().replace("-", "_")[:20],
            "summary": f"{milestone_id} summary line.",
        }

    def test_w587_fires_when_milestones_indexed_but_no_drift_checks(self):
        """W587 fires when milestone_index has entries and drift.checks is empty."""
        anchor = self._build_anchor(
            milestone_index=[self._ms_entry("ms-auth")],
            drift_checks=[],
        )
        errors = self._write_and_validate(anchor)
        self.assertTrue(
            any(e.code == "W587" for e in errors),
            f"Expected W587 for populated milestone_index + empty drift.checks. Got: {errors}"
        )

    def test_no_w587_when_drift_checks_populated(self):
        """W587 does not fire when drift.checks has at least one entry."""
        anchor = self._build_anchor(
            milestone_index=[self._ms_entry("ms-auth")],
            drift_checks=["Verified ms-auth scope alignment (2026-04-15)"],
        )
        errors = self._write_and_validate(anchor)
        w587 = [e for e in errors if e.code == "W587"]
        self.assertEqual(w587, [], f"W587 should not fire when drift.checks is populated. Got: {w587}")

    def test_no_w587_when_milestone_index_empty(self):
        """W587 does not fire on a fresh anchor with no milestones yet."""
        anchor = self._build_anchor(milestone_index=[], drift_checks=[])
        errors = self._write_and_validate(anchor)
        w587 = [e for e in errors if e.code == "W587"]
        self.assertEqual(w587, [], f"W587 should not fire when milestone_index is empty. Got: {w587}")


if __name__ == "__main__":
    unittest.main()
