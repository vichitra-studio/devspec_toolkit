"""Integration tests for the Step 16 Trinity Anchor validator.

Covers:
  - Schema validation: valid fixtures pass; invalid fixtures fail on the right signal
  - E308 (ANCHOR_SCOPE_DRIFT): scope contradiction; one roadmap task owned by two non-done milestones
  - E309 (ANCHOR_CHECKLIST_DRIFT): one plan-item id with different realises sets in two plans
                                  + checklist_id_prefix collision in milestone_index
  - W585 (ANCHOR_DRIFT_SKIP): spec_path is None — filesystem checks skipped
  - W586 (ANCHOR_VALIDATOR_WRONG_ARTIFACT): non-anchor artifact dispatched here
  - W587 (ANCHOR_DRIFT_CHECKS_STALE): non-empty milestone_index but empty drift.checks
  - W588 (ANCHOR_MILESTONE_UNREADABLE): unparseable milestone in impl_context/
  - Misfiled-anchor demotion routes to anchor validator and fires W586
  - Anchor never emits E304 (which is a 16a-plan signal)

Real filesystem only — no mocks. All tests use ``tempfile.TemporaryDirectory`` +
real JSON files + the real ``validate_file`` orchestrator. Anchor + milestone
artifacts are constructed via the shared factories in ``_anchor_factories.py``
to keep schema-evolution churn in one place.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.validate import validate_file

# tests/integration/ has no __init__.py (pytest picks tests up via rootdir
# discovery, not as a package), so relative imports don't work.  Add the
# directory to sys.path and import the factory module directly.
_INTEGRATION_DIR = Path(__file__).resolve().parent
if str(_INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_DIR))

from _anchor_factories import (  # noqa: E402  — sys.path tweak above
    make_anchor,
    make_checklist_item,
    make_legacy_milestone_entry,
    make_milestone_entry,
    make_milestone_plan,
    make_roadmap,
)


_TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = str(_TOOLKIT_ROOT)
_FIXTURES_DIR = _TOOLKIT_ROOT / "tests" / "fixtures" / "step_16"


class _AnchorTestBase(unittest.TestCase):
    """Common base — every anchor test class needs the same toolkit + fixture paths."""

    repo_root = _REPO_ROOT
    fixtures_dir = _FIXTURES_DIR

    def setUp(self):
        super().setUp()


class TestStep16AnchorSchema(_AnchorTestBase):
    """Schema-level tests using pre-built fixture files."""

    def _validate_isolated(self, fixture_name: str) -> list:
        """Validate a copy of an anchor fixture in an empty directory.

        The shared fixture directory also holds the ``impl_context/`` plan fixtures of the 16a tests, which the
        anchor validator would scan beside the anchor; a valid anchor is judged on its own.
        """
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / fixture_name
            shutil.copy(self.fixtures_dir / fixture_name, copy)
            return validate_file(self.repo_root, str(copy))

    def test_valid_anchor_minimal_passes(self):
        """Minimal valid anchor with empty milestone_index should pass."""
        errors = self._validate_isolated("valid_anchor_minimal.json")
        self.assertEqual(errors, [], f"Expected no errors. Got: {errors}")

    def test_valid_anchor_with_milestones_passes(self):
        """Anchor with populated milestone_index (a done row with a legacy-migration close, an in-flight row) passes."""
        errors = self._validate_isolated("valid_anchor_with_milestones.json")
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

    def test_invalid_anchor_missing_milestone_index_fails(self):
        """Anchor without plan.milestone_index field should fail schema validation.

        L3 (RFC Task 2.8 plan): the milestone_index is the load-bearing
        registry that drives E308 FR-ownership detection and E309
        prefix-collision detection. Schema must reject its absence with the
        specific 'milestone_index' required-property signal.
        """
        path = self.fixtures_dir / "invalid_anchor_missing_milestone_index.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "milestone_index" in e.message for e in errors),
            f"Expected E520 'milestone_index' required-property error. Got: {errors}"
        )

    def test_inner_field_failure_does_not_emit_phantom_unevaluated_companion(self):
        """Regression for the H1 noisy-companion-error issue.

        Previously the anchor schema placed ``unevaluatedProperties: false`` at
        the root *outside* the ``allOf``. When any inner-branch field failed
        validation, JSON Schema 2020-12 dropped the failing branch's
        ``properties`` annotations, and the root's ``unevaluatedProperties``
        check then flagged every legitimate top-level property
        (``artifact_role``, ``plan``) as "unexpected" — producing 2 noise
        errors on top of the 1 real one.

        After lifting ``properties``/``required`` to the root and keeping only
        the step-base ``$ref`` inside ``allOf``, a single inner failure must
        produce a single error and NOT mention ``artifact_role`` or ``plan``
        as "unevaluated". This test pins that contract so future schema edits
        cannot silently re-introduce the noise.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                ambiguities=[{
                    "id": "amb-noise-test",
                    "description": "An ambiguity with an empty about list.",
                    "about": [],
                }],
            )
            errors = validate_file(self.repo_root, str(anchor_path))

        # Exactly one error should fire — the real one for the empty about list.
        about_errors = [e for e in errors if "ambiguities/0/about" in e.message]
        self.assertEqual(
            len(about_errors), 1,
            f"Expected exactly one empty-about error. Got: {errors}"
        )
        # No phantom 'artifact_role' or 'plan' unevaluatedProperties companion.
        phantom = [
            e for e in errors
            if "Unevaluated properties" in e.message
            and ("artifact_role" in e.message or "plan" in e.message)
        ]
        self.assertEqual(
            phantom, [],
            "Inner-branch failure must not emit a phantom 'artifact_role'/'plan' "
            f"unevaluatedProperties error. Got: {errors}"
        )

    def test_invalid_anchor_missing_artifact_role_fails(self):
        """Anchor without the required artifact_role field should fail schema validation.

        ``artifact_role: "anchor"`` is const-locked and required on vc:16-anchor
        artifacts. It is the canonical signal used by ``_is_anchor()`` (field-first,
        path-fallback) to distinguish the anchor from 16a/16b/16c milestone plans.
        A missing field must fail schema validation with the specific
        'artifact_role' required-property signal — without this pin, a schema
        edit that relaxed the requirement would silently re-open the routing
        ambiguity the split was introduced to close.
        """
        path = self.fixtures_dir / "invalid_anchor_missing_artifact_role.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "artifact_role" in e.message for e in errors),
            f"Expected E520 'artifact_role' required-property error. Got: {errors}"
        )

    def test_invalid_anchor_has_review_fails(self):
        """Anchor with a top-level review section should fail (unevaluatedProperties).

        Parallel to ``test_invalid_anchor_has_execution_fails``: review is a
        milestone-plan concern (16c), not an anchor concern. ``unevaluatedProperties:
        false`` at the artifact root rejects stray ``review``. Pinning both the
        ``execution`` and ``review`` rejections keeps the two-section contract
        airtight — one test alone would allow a regression on the untested side.
        """
        path = self.fixtures_dir / "invalid_anchor_has_review.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "review" in e.message for e in errors),
            f"Expected E520 'review' unevaluatedProperties error. Got: {errors}"
        )

    def test_invalid_anchor_has_checklist_fails(self):
        """Anchor with plan.spec_alignment.checklist should fail (additionalProperties on plan).

        The anchor deliberately does not carry a per-FR checklist — that detail
        lives in each 16a milestone plan. ``plan.additionalProperties: false``
        (``schema/16_anchor.schema.json:25``) rejects any leak of
        ``spec_alignment`` into the anchor. Without this pin, a schema edit that
        allowed extra plan properties would silently re-introduce the 130-item
        bloat described in ``WIP/step16_anchor_bloat_report.md``.
        """
        path = self.fixtures_dir / "invalid_anchor_has_checklist.json"
        errors = validate_file(self.repo_root, str(path))
        self.assertTrue(
            any(e.code == "E520" and "spec_alignment" in e.message for e in errors),
            f"Expected E520 'spec_alignment' additionalProperties error. Got: {errors}"
        )


    def _validate_rows(self, rows: list[dict]) -> list:
        """Validate an anchor holding *rows* in ``milestone_index`` (with a drift check, so W587 stays quiet)."""
        with tempfile.TemporaryDirectory() as td:
            anchor_path = make_anchor(
                Path(td),
                milestone_index=rows,
                drift_checks=["Verified the row shapes against the schema (2026-11-16)"],
            )
            return validate_file(self.repo_root, str(anchor_path))

    def test_doc_example_row_validates(self):
        """The design's anchor row (DOC L1830-1833) validates with no error."""
        row = {
            "anchor_id": "anchor-ms-account-recovery",
            "about": ["ms-account-recovery"],
            "status": "in_progress",
            "checklist_id_prefix": "PWRESET",
            "summary": "Confirm endpoint in progress.",
        }
        self.assertEqual(self._validate_rows([row]), [])

    def test_row_without_status_validates(self):
        """status is optional: an author-written row carries none (it reads as pending)."""
        row = make_milestone_entry("ms-auth")
        del row["status"]
        self.assertEqual(self._validate_rows([row]), [])

    def test_deferred_without_deferral_reason_fails(self):
        """A row with status 'deferred' and no deferral_reason fails."""
        row = make_milestone_entry("ms-auth", status="deferred")
        del row["deferral_reason"]
        errors = self._validate_rows([row])
        self.assertTrue(
            any(e.code == "E520" and "deferral_reason" in e.message for e in errors),
            f"Expected E520 for the missing deferral_reason. Got: {errors}",
        )

    def test_done_without_close_fails(self):
        """A row with status 'done' and no close fails."""
        row = make_milestone_entry("ms-auth", status="done")
        del row["close"]
        errors = self._validate_rows([row])
        self.assertTrue(
            any(e.code == "E520" and "'close'" in e.message for e in errors),
            f"Expected E520 for the missing close. Got: {errors}",
        )

    def test_done_with_close_and_deferred_with_reason_pass(self):
        """The two required companions satisfy the schema."""
        rows = [
            make_milestone_entry("ms-auth", status="done"),
            make_milestone_entry("ms-session", status="deferred", checklist_id_prefix="SESSION"),
        ]
        self.assertEqual(self._validate_rows(rows), [])

    def test_legacy_migration_close_without_source_fails(self):
        """close.signed_off_by 'legacy-migration' needs close.source."""
        row = make_milestone_entry("ms-auth", status="done")
        row["close"] = {"signed_off_by": "legacy-migration"}
        errors = self._validate_rows([row])
        self.assertTrue(
            any(e.code == "E520" and "source" in e.message for e in errors),
            f"Expected E520 for the missing close.source. Got: {errors}",
        )
        row["close"]["source"] = "spec/impl_context/ms_auth_plan.json final_status"
        self.assertEqual(self._validate_rows([row]), [])

    def test_about_must_have_exactly_one_item(self):
        """about is an array of exactly one milestone id: none and two both fail."""
        for about in ([], ["ms-a", "ms-b"]):
            with self.subTest(about=about):
                row = make_milestone_entry("ms-a")
                row["about"] = about
                errors = self._validate_rows([row])
                self.assertTrue(
                    any(e.code == "E520" and "about" in e.message for e in errors),
                    f"Expected E520 for about={about}. Got: {errors}",
                )

    def test_removed_row_fields_rejected(self):
        """milestone_id, context_path and fr_refs are no longer row fields."""
        errors = self._validate_rows([make_legacy_milestone_entry("ms-auth")])
        message = " ".join(e.message for e in errors)
        for field in ("milestone_id", "context_path", "fr_refs"):
            self.assertIn(field, message)

class TestStep16AnchorE308ScopeDrift(_AnchorTestBase):
    """E308 ANCHOR_SCOPE_DRIFT — bidirectional scope check + FR/API ownership."""

    def test_e308_milestone_scope_in_contradicts_anchor_scope_out(self):
        """E308 fires when milestone scope_in item appears in anchor scope_out."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
                milestone_index=[make_milestone_entry("ms-oauth")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_oauth_plan.json", milestone="ms-oauth",
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

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
                milestone_index=[make_milestone_entry("ms-jwt")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_jwt_plan.json", milestone="ms-jwt",
                scope_in=[],
                scope_out=["jwt-token-validation"],  # contradicts anchor scope_in
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" for e in errors),
            f"Expected E308 for reverse scope contradiction. Got: {errors}"
        )

    def test_e308_scope_drift_is_case_insensitive(self):
        """E308 fires even when scope items differ only in case."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["JWT-Token-Validation"],
                scope_out=["OAuth-Flows"],
                milestone_index=[make_milestone_entry("ms-oauth")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_oauth_plan.json", milestone="ms-oauth",
                scope_in=["oauth-flows"],  # differs in case from anchor scope_out
                scope_out=[],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" for e in errors),
            f"Expected E308 for case-insensitive scope contradiction. Got: {errors}"
        )

    def _ownership_errors(self, statuses: tuple[str, str], tasks: dict[str, list[str]], realised: tuple[list[str], list[str]]):
        """Validate an anchor of two milestones (with *statuses*) whose plans realise *realised*; roadmap *tasks* give task -> criteria."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            make_roadmap(tmp_dir, tasks)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-a", status=statuses[0], checklist_id_prefix="MSA"),
                    make_milestone_entry("ms-b", status=statuses[1], checklist_id_prefix="MSB"),
                ],
                drift_checks=["Verified ownership (2026-11-16)"],
            )
            make_milestone_plan(
                impl_context_dir, "ms_a_plan.json", milestone="ms-a",
                checklist=[make_checklist_item("MSA_ONE", realised[0])],
            )
            make_milestone_plan(
                impl_context_dir, "ms_b_plan.json", milestone="ms-b",
                checklist=[make_checklist_item("MSB_ONE", realised[1])],
            )
            return validate_file(self.repo_root, str(anchor_path))

    def test_e308_ownership_arm_fires_when_two_open_milestones_realise_one_task(self):
        """E308 [ownership]: two in-flight milestones whose plan items realise criteria of one task."""
        errors = self._ownership_errors(
            ("in_progress", "pending"), {"task-login": ["tc-one", "tc-two"]}, (["tc-one"], ["tc-two"])
        )
        owned = [e for e in errors if e.code == "E308" and "[ownership]" in e.message]
        self.assertEqual(len(owned), 1, f"Expected one ownership E308. Got: {errors}")
        self.assertIn("'task-login'", owned[0].message)
        self.assertIn("'ms-a'", owned[0].message)
        self.assertIn("'ms-b'", owned[0].message)

    def test_e308_ownership_arm_silent_when_one_milestone_is_done(self):
        """A done milestone does not block the same task in an in-flight milestone."""
        errors = self._ownership_errors(
            ("done", "in_progress"), {"task-login": ["tc-one", "tc-two"]}, (["tc-one"], ["tc-two"])
        )
        self.assertEqual([e for e in errors if e.code == "E308"], [], f"Done milestone should not trigger E308. Got: {errors}")

    def test_e308_ownership_arm_silent_when_milestones_realise_different_tasks(self):
        """No E308 when each in-flight milestone realises a criterion of its own task."""
        errors = self._ownership_errors(
            ("in_progress", "in_progress"), {"task-login": ["tc-one"], "task-logout": ["tc-two"]}, (["tc-one"], ["tc-two"])
        )
        self.assertEqual([e for e in errors if e.code == "E308"], [], f"Got: {errors}")

    def test_e308_deferred_milestone_still_owns_its_task(self):
        """A deferred milestone is a postponed but still-owned commitment: the same task in an in-flight milestone is a conflict."""
        errors = self._ownership_errors(
            ("deferred", "in_progress"), {"task-login": ["tc-one", "tc-two"]}, (["tc-one"], ["tc-two"])
        )
        self.assertEqual(len([e for e in errors if e.code == "E308"]), 1, f"Got: {[e.message for e in errors]}")

    def test_e308_ownership_arm_ignores_a_criterion_the_roadmap_does_not_have(self):
        """A realised id that is no criterion of the graph takes no part (the plan check reports it), and nothing raises."""
        errors = self._ownership_errors(
            ("in_progress", "in_progress"), {"task-login": ["tc-one"]}, (["tc-missing"], ["tc-missing"])
        )
        self.assertEqual([e for e in errors if e.code == "E308"], [], f"Got: {errors}")

    def test_row_without_status_is_read_as_pending(self):
        """A row with no status is not done: it takes part in prefix checks and raises nothing else."""
        row = make_milestone_entry("ms-a", checklist_id_prefix="SAME")
        other = make_milestone_entry("ms-b", checklist_id_prefix="SAME")
        del row["status"], other["status"]
        with tempfile.TemporaryDirectory() as td:
            anchor_path = make_anchor(Path(td), milestone_index=[row, other], drift_checks=["Verified rows (2026-11-16)"])
            errors = validate_file(self.repo_root, str(anchor_path))
        self.assertEqual([e.code for e in errors], ["E309"], f"Got: {errors}")

    def test_no_e308_when_no_scope_overlap(self):
        """No E308 when milestone scope does not overlap anchor scope."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
                milestone_index=[make_milestone_entry("ms-jwt")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_jwt_plan.json", milestone="ms-jwt",
                scope_in=["jwt-token-validation"],  # matches anchor scope_in — fine
                scope_out=[],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e308 = [e for e in errors if e.code == "E308"]
        self.assertEqual(e308, [], f"Did not expect E308. Got: {e308}")


class TestStep16AnchorE309ChecklistDrift(_AnchorTestBase):
    """E309 ANCHOR_CHECKLIST_DRIFT — cross-milestone checklist ID + prefix collisions."""

    def _mapping_errors(self, first: list[str], second: list[str], *, second_id: str = "AUTH_LOGIN"):
        """Validate two plans whose items are ``AUTH_LOGIN`` realising *first* and *second_id* realising *second*."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-a", checklist_id_prefix="MSA"),
                    make_milestone_entry("ms-b", checklist_id_prefix="MSB"),
                ],
            )
            make_milestone_plan(
                impl_context_dir, "ms_a_plan.json", milestone="ms-a",
                checklist=[make_checklist_item("AUTH_LOGIN", first)],
            )
            make_milestone_plan(
                impl_context_dir, "ms_b_plan.json", milestone="ms-b",
                checklist=[make_checklist_item(second_id, second)],
            )
            return validate_file(self.repo_root, str(anchor_path))

    def test_e309_fires_when_one_item_id_has_two_realises_sets(self):
        """E309 [mapping]: one plan-item id carries different realises sets in two plans."""
        errors = self._mapping_errors(["tc-login-v1"], ["tc-login-v2"])
        mapping = [e for e in errors if e.code == "E309" and "[mapping]" in e.message]
        self.assertEqual(len(mapping), 1, f"Expected one mapping E309. Got: {errors}")
        self.assertIn("'AUTH_LOGIN'", mapping[0].message)
        self.assertIn("'tc-login-v1'", mapping[0].message)
        self.assertIn("'tc-login-v2'", mapping[0].message)

    def test_e309_silent_when_realises_sets_are_equal(self):
        """No E309 when the same plan-item id realises the same set in both plans, whatever the order."""
        errors = self._mapping_errors(["tc-a", "tc-b"], ["tc-b", "tc-a"])
        self.assertEqual([e for e in errors if e.code == "E309"], [], f"Got: {errors}")

    def test_e309_silent_when_item_ids_differ(self):
        """No E309 when the plan-item ids are unique across plans."""
        errors = self._mapping_errors(["tc-login"], ["tc-session"], second_id="AUTH_SESSION")
        self.assertEqual([e for e in errors if e.code == "E309"], [], f"Got: {errors}")

    def test_e309_fires_for_duplicate_checklist_id_prefix_in_milestone_index(self):
        """E309 fires at anchor authoring time when two milestone_index entries share checklist_id_prefix.

        H4: prompt_16 promises the anchor validator catches this; previously
        only the after-the-fact cross-plan ID collision was caught.  Scope check
        runs from anchor data alone — no impl_context/ tree needed.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-auth-v1", status="done", checklist_id_prefix="AUTH"),
                    make_milestone_entry("ms-auth-v2", status="in_progress", checklist_id_prefix="AUTH"),
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E309" and "checklist_id_prefix" in e.message for e in errors),
            f"Expected E309 for duplicate checklist_id_prefix. Got: {errors}"
        )

    def test_no_e309_when_checklist_id_prefix_is_unique(self):
        """E309 does not fire when every milestone uses a distinct checklist_id_prefix."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-a", status="in_progress", checklist_id_prefix="MSA"),
                    make_milestone_entry("ms-b", status="pending", checklist_id_prefix="MSB"),
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e309 = [e for e in errors if e.code == "E309"]
        self.assertEqual(e309, [], f"Did not expect E309 with unique prefixes. Got: {e309}")


class TestStep16AnchorGuards(_AnchorTestBase):
    """W585 / W586 guards plus the "anchor route never emits E304" contract."""

    def test_w586_non_anchor_routed_to_anchor_validator(self):
        """W586 fires when anchor validator receives a non-anchor artifact."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        # Plain impl-context artifact (no artifact_role) with no path
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

    def test_w585_spec_path_none_skips_filesystem_checks(self):
        """W585 fires when spec_path is None — filesystem checks are skipped.

        In-memory checks (E309 prefix) still run because they operate purely on
        the anchor's milestone_index data.  Only filesystem-dependent checks
        (E308 scope drift, E309 checklist mapping, W610 prefix violations) are
        skipped.

        This test constructs two rows with the same checklist_id_prefix to verify
        that the in-memory E309 fires even without spec_path, while W585 confirms
        the filesystem checks were skipped.
        """
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        data = {
            "$schema": "vc:16-anchor",
            "artifact_role": "anchor",
            "plan": {
                "summary": {"functional_summary": "Test functional summary line.", "scope_in": ["auth"], "scope_out": []},
                "ambiguities": [],
                "drift": {"checks": []},
                "milestone_index": [
                    make_milestone_entry("ms-a", checklist_id_prefix="SHARED"),
                    make_milestone_entry("ms-b", checklist_id_prefix="SHARED"),
                ],
            },
        }
        errors = validate_step_16_anchor(data, self.repo_root, spec_path=None)

        self.assertTrue(
            any(e.code == "W585" for e in errors),
            f"Expected W585 for None spec_path. Got: {errors}"
        )
        self.assertTrue(
            any(e.code == "E309" for e in errors),
            f"Expected E309 prefix collision from in-memory check. Got: {errors}"
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

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=["payments"],
                functional_summary="Anchor with stray non-milestone files.",
                milestone_index=[make_milestone_entry("ms-real")],
            )
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))

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

            # Real milestone: same AUTH_LOGIN id mapped to fr-login — by itself no E309.
            (impl_context_dir / "ms_real_plan.json").write_text(
                json.dumps({
                    "$schema": "vc:16-impl-context",
                    "id": "ms-real",
                    "milestone": "ms-real",
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

            errors = validate_step_16_anchor(anchor_data, self.repo_root, str(anchor_path))

        e308 = [e for e in errors if e.code == "E308"]
        e309 = [e for e in errors if e.code == "E309"]
        self.assertEqual(e308, [], f"Stray file must not trigger E308. Got: {e308}")
        self.assertEqual(e309, [], f"Stray file must not trigger E309. Got: {e309}")

    def test_no_e308_e309_when_no_impl_context_dir(self):
        """No E308/E309 when impl_context/ directory does not exist yet."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                functional_summary="Fresh anchor, no milestones yet.",
            )
            # No impl_context/ directory — fresh anchor

            errors = validate_file(self.repo_root, str(anchor_path))

        e_codes = {e.code for e in errors}
        self.assertNotIn("E308", e_codes, f"No E308 expected without impl_context/. Errors: {errors}")
        self.assertNotIn("E309", e_codes, f"No E309 expected without impl_context/. Errors: {errors}")

    def test_anchor_route_never_emits_e304(self):
        """L4: E304 ROADMAP_TASK_UNCOVERED is a 16a-plan signal and must never appear on the anchor route.

        Even with milestone_index entries that reference real-looking IDs, the
        anchor validator skips E304 entirely (E304 lives in step_16.py and is
        gated on _is_anchor).  A regression that re-routes the anchor through
        validate_step_16 would re-introduce false E304s; this test pins the
        contract.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-auth", status="in_progress", checklist_id_prefix="AUTH"),
                ],
                drift_checks=["Verified ms-auth scope (2026-04-15)"],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e304 = [e for e in errors if e.code == "E304"]
        self.assertEqual(e304, [], f"Anchor route must never emit E304. Got: {e304}")

    def test_plan_file_whose_milestone_names_no_anchor_row_is_w611_not_crash(self):
        """A plan naming a milestone no anchor row is about is skipped with W611 and takes no part in drift checks."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=["oauth-flows"],
                milestone_index=[make_milestone_entry("ms-auth")],
                drift_checks=["Verified scope (2026-11-16)"],
            )
            make_milestone_plan(
                impl_context_dir, "ms_ghost_plan.json", milestone="ms-ghost",
                scope_in=["oauth-flows"],  # would be E308 if the plan took part
            )
            errors = validate_file(self.repo_root, str(anchor_path))
        w611 = [e for e in errors if e.code == "W611"]
        self.assertEqual(len(w611), 1, f"Expected one W611. Got: {errors}")
        self.assertIn("ms_ghost_plan.json", w611[0].message)
        self.assertEqual([e for e in errors if e.code == "E308"], [], f"Got: {errors}")

    def test_legacy_plan_file_without_milestone_is_skipped_with_notice(self):
        """A plan with no file-level milestone key is skipped with a W608 notice (never raises, no drift finding)."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=["oauth-flows"],
                milestone_index=[make_milestone_entry("ms-auth")],
                drift_checks=["Verified scope (2026-11-16)"],
            )
            make_milestone_plan(impl_context_dir, "ms_auth_plan.json", scope_in=["oauth-flows"])
            errors = validate_file(self.repo_root, str(anchor_path))
        notices = [e for e in errors if e.code == "W608" and "ms_auth_plan.json" in e.message]
        self.assertEqual(len(notices), 1, f"Expected one W608 notice. Got: {errors}")
        self.assertIn("milestone", notices[0].message)
        self.assertEqual([e for e in errors if e.code == "E308"], [], f"Got: {errors}")

    def test_w607_and_w612_not_emitted(self):
        """W607 (context_path missing) and W612 (milestone not in the roadmap) are retired: no row field feeds them."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            (tmp_dir / "impl_context").mkdir()
            (tmp_dir / "14_roadmap.json").write_text(
                json.dumps({"$schema": "vc:14-roadmap", "id": "roadmap", "owner": "product", "milestones": []}),
                encoding="utf-8",
            )
            anchor_path = make_anchor(
                tmp_dir,
                milestone_index=[make_milestone_entry("ms-typo")],
                drift_checks=["Verified scope (2026-11-16)"],
            )
            errors = validate_file(self.repo_root, str(anchor_path))
        self.assertEqual({e.code for e in errors} & {"W607", "W612"}, set(), f"Got: {errors}")

    def test_misfiled_anchor_inside_impl_context_dir_routes_to_anchor_validator(self):
        """M5: an anchor file misplaced under impl_context/ should be demoted to the anchor route.

        Without the demotion in _refine_impl_context_substep, the file would be
        deep-validated by validate_step_16a and emit confusing 16a-specific
        errors (missing plan.status, missing spec_alignment.checklist).  After
        the fix, the anchor validator sees the file via the proper route and
        the schema-required `plan.summary.functional_summary` etc. are checked
        against vc:16-anchor instead.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            misfiled_path = impl_context_dir / "16_impl_context.json"
            misfiled_path.write_text(
                json.dumps({
                    "$schema": "vc:16-anchor",
                    "id": "anchor-test",
                    "owner": "api",
                    "created_at": "2024-01-01T00:00:00Z",
                    "artifact_role": "anchor",
                    "canonical_refs_used": [],
                    "plan": {
                        "summary": {
                            "functional_summary": "Misfiled anchor inside impl_context/.",
                            "scope_in": ["auth"],
                            "scope_out": [],
                        },
                        "ambiguities": [],
                        "drift": {"checks": []},
                        "milestone_index": [],
                    },
                }),
                encoding="utf-8",
            )

            errors = validate_file(self.repo_root, str(misfiled_path))

        # No 16a-specific errors should fire; the file is recognized as the anchor.
        # Two acceptable observable signals:
        #   - The file passes the anchor schema (artifact_role + plan are valid)
        #   - No E305 PLANNED_UNEXECUTED, no E307 BEHAVIOR_VALIDATION_PAIRING,
        #     no W581 MILESTONE_REF_MISSING — those are all 16a/16b/16c codes
        sub_step_only = {"E305", "E307", "W581", "W582"}
        emitted_sub_step = {e.code for e in errors} & sub_step_only
        self.assertEqual(
            emitted_sub_step, set(),
            f"Misfiled anchor must not emit 16a/b/c-specific codes. Got: {[e for e in errors if e.code in sub_step_only]}"
        )
        # H2: the misfiling itself must produce a load-bearing diagnostic.
        # Without W609 the anchor's drift checks silently no-op (impl_context
        # resolves to impl_context/impl_context/ which doesn't exist) and the
        # file looks "clean" despite contributing nothing to drift detection.
        w609 = [e for e in errors if e.code == "W609"]
        self.assertEqual(
            len(w609), 1,
            "Misfiled anchor inside impl_context/ must emit exactly one W609 "
            f"ANCHOR_MISFILED so the routing mismatch is discoverable. Got: {errors}"
        )
        self.assertIn(
            "16_impl_context.json", w609[0].message,
            "W609 message must name the canonical filename so the author "
            f"knows where to move the file. Got: {w609[0].message}"
        )

    def test_misfiled_anchor_with_non_anchor_filename_relies_on_artifact_role_demotion(self):
        """Misfiled anchor whose filename does not start with `16_` must still route via artifact_role.

        Filename-based routing (``_get_step_from_path``) returns ``"16"`` only
        for ``16_impl_context.json`` — any other filename in ``impl_context/``
        (``ms_foo_plan.json``, ``anchor_backup.json``, ...) returns ``"16a"``.
        Content-based demotion in ``_refine_impl_context_substep`` is the
        only signal that can rescue the routing.  Pin that path.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            misfiled_path = impl_context_dir / "anchor_backup.json"
            misfiled_path.write_text(
                json.dumps({
                    "$schema": "vc:16-anchor",
                    "id": "anchor-misfiled",
                    "owner": "api",
                    "created_at": "2024-01-01T00:00:00Z",
                    "artifact_role": "anchor",
                    "canonical_refs_used": [],
                    "plan": {
                        "summary": {
                            "functional_summary": "Backup anchor saved under impl_context/ with an arbitrary name.",
                            "scope_in": ["auth"],
                            "scope_out": [],
                        },
                        "ambiguities": [],
                        "drift": {"checks": []},
                        "milestone_index": [],
                    },
                }),
                encoding="utf-8",
            )
            errors = validate_file(self.repo_root, str(misfiled_path))

        sub_step_only = {"E305", "E307", "W581", "W582"}
        emitted_sub_step = {e.code for e in errors} & sub_step_only
        self.assertEqual(
            emitted_sub_step, set(),
            "Misfiled anchor (non-16 filename) must be demoted to the anchor route via "
            f"artifact_role. Got unexpected 16a/b/c codes: "
            f"{[e for e in errors if e.code in sub_step_only]}"
        )
        # H2: location-mismatch warning must fire even when the filename also
        # diverges from the canonical 16_impl_context.json convention — both
        # the wrong directory AND the wrong filename matter.
        w609 = [e for e in errors if e.code == "W609"]
        self.assertEqual(
            len(w609), 1,
            "Misfiled anchor (non-16 filename, inside impl_context/) must "
            f"emit exactly one W609 ANCHOR_MISFILED. Got: {errors}"
        )

    def test_no_w609_when_anchor_at_canonical_location(self):
        """W609 must NOT fire when the anchor sits at the canonical spec/16_impl_context.json path.

        Negative test for the H2 fix: pin that the misfiling diagnostic is
        scoped to files inside impl_context/.  A clean anchor at the canonical
        location must produce zero W609 noise even when other anchor-only
        warnings (W587 stale drift, etc.) fire.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[make_milestone_entry("ms-auth")],
                drift_checks=["Verified ms-auth scope_in does not overlap anchor scope_out (2026-04-16)"],
            )
            errors = validate_file(self.repo_root, str(anchor_path))

        w609 = [e for e in errors if e.code == "W609"]
        self.assertEqual(
            w609, [],
            "Anchor at canonical spec/16_impl_context.json location must not "
            f"emit W609 ANCHOR_MISFILED. Got: {w609}"
        )

    def test_misfiled_anchor_without_artifact_role_fails_schema_not_routing(self):
        """Misfiled anchor missing ``artifact_role`` must fail schema before confusing routing errors escape.

        If both the filename and the ``artifact_role`` signal are absent, the
        file routes to the 16a validator (path-based default).  Schema
        validation against ``vc:16-anchor`` is still applied because of the
        ``$schema`` URI, so E520 for the missing ``artifact_role`` must fire
        — giving the author a clear "this isn't a valid anchor" signal before
        any 16a-phase diagnostics surface.  Without this pin, a future schema
        relaxation could silently route such a file through the wrong
        validator and emit misleading ``plan.status`` / checklist errors.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            misfiled_path = impl_context_dir / "anchor_backup.json"
            misfiled_path.write_text(
                json.dumps({
                    "$schema": "vc:16-anchor",
                    "id": "anchor-misfiled-no-role",
                    "owner": "api",
                    "created_at": "2024-01-01T00:00:00Z",
                    # No artifact_role — schema-required const is absent.
                    "canonical_refs_used": [],
                    "plan": {
                        "summary": {
                            "functional_summary": "Misfiled anchor missing artifact_role.",
                            "scope_in": ["auth"],
                            "scope_out": [],
                        },
                        "ambiguities": [],
                        "drift": {"checks": []},
                        "milestone_index": [],
                    },
                }),
                encoding="utf-8",
            )
            errors = validate_file(self.repo_root, str(misfiled_path))

        self.assertTrue(
            any(e.code == "E520" and "artifact_role" in e.message for e in errors),
            f"Expected E520 'artifact_role' schema error. Got: {errors}",
        )


class TestStep16AnchorW587DriftChecksStale(_AnchorTestBase):
    """W587 ANCHOR_DRIFT_CHECKS_STALE — milestone_index populated but drift.checks empty."""

    def test_w587_fires_when_milestones_indexed_but_no_drift_checks(self):
        """W587 fires when milestone_index has entries and drift.checks is empty."""
        with tempfile.TemporaryDirectory() as td:
            anchor_path = make_anchor(
                Path(td),
                scope_in=["auth"],
                milestone_index=[make_milestone_entry("ms-auth")],
                drift_checks=[],
            )
            errors = validate_file(self.repo_root, str(anchor_path))
        self.assertTrue(
            any(e.code == "W587" for e in errors),
            f"Expected W587 for populated milestone_index + empty drift.checks. Got: {errors}"
        )

    def test_no_w587_when_drift_checks_populated(self):
        """W587 does not fire when drift.checks has at least one entry."""
        with tempfile.TemporaryDirectory() as td:
            anchor_path = make_anchor(
                Path(td),
                scope_in=["auth"],
                milestone_index=[make_milestone_entry("ms-auth")],
                drift_checks=["Verified ms-auth scope alignment (2026-04-15)"],
            )
            errors = validate_file(self.repo_root, str(anchor_path))
        w587 = [e for e in errors if e.code == "W587"]
        self.assertEqual(w587, [], f"W587 should not fire when drift.checks is populated. Got: {w587}")

    def test_no_w587_when_milestone_index_empty(self):
        """W587 does not fire on a fresh anchor with no milestones yet."""
        with tempfile.TemporaryDirectory() as td:
            anchor_path = make_anchor(Path(td), scope_in=["auth"])
            errors = validate_file(self.repo_root, str(anchor_path))
        w587 = [e for e in errors if e.code == "W587"]
        self.assertEqual(w587, [], f"W587 should not fire when milestone_index is empty. Got: {w587}")


class TestStep16AnchorW588UnreadableMilestone(_AnchorTestBase):
    """W588 ANCHOR_MILESTONE_UNREADABLE — corrupt or unparseable milestone files."""

    def test_w588_fires_on_unparseable_milestone_json(self):
        """W588 fires (with the offending filename) when a milestone file in impl_context/ is malformed JSON."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            broken_path = impl_context_dir / "ms_broken_plan.json"
            broken_path.write_text("{not: valid json,", encoding="utf-8")

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W588" and "ms_broken_plan.json" in e.message for e in errors),
            f"Expected W588 mentioning ms_broken_plan.json. Got: {errors}"
        )

    def test_w588_fires_on_a_milestone_file_that_is_not_an_object(self):
        """A plan file whose top level is not an object is reported like an unreadable one, so W611 has a cause."""
        for name, raw in (("ms_list_plan.json", b"[]"), ("ms_bytes_plan.json", b'{"a": "\xff\xfe"}')):
            with tempfile.TemporaryDirectory() as td:
                tmp_dir = Path(td)
                impl_context_dir = tmp_dir / "impl_context"
                impl_context_dir.mkdir()
                anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
                (impl_context_dir / name).write_bytes(raw)

                errors = validate_file(self.repo_root, str(anchor_path))

            self.assertTrue(
                any(e.code == "W588" and name in e.message for e in errors),
                f"Expected W588 mentioning {name}. Got: {errors}"
            )

    def test_no_w588_when_all_milestone_files_parse(self):
        """W588 does not fire when every milestone file in impl_context/ parses cleanly."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(impl_context_dir, "ms_clean_plan.json", scope_in=["auth"])

            errors = validate_file(self.repo_root, str(anchor_path))

        w588 = [e for e in errors if e.code == "W588"]
        self.assertEqual(w588, [], f"W588 should not fire when files parse. Got: {w588}")


class TestStep16AnchorW589MisSchemaedMilestone(_AnchorTestBase):
    """W589 ANCHOR_MILESTONE_MISSCHEMAED — parseable JSON in impl_context/ with wrong $schema.

    Background: the anchor validator silently skipped files in impl_context/ whose
    `$schema` wasn't `vc:16-impl-context`. That hid two common authoring mistakes:
    a missing `$schema` declaration, and an out-of-place artifact filed under
    impl_context/. W589 surfaces the mismatch so drift checks can't be bypassed
    by a typo.
    """

    def test_w589_fires_on_missing_schema_field(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            bad = impl_context_dir / "ms_no_schema_plan.json"
            bad.write_text(
                json.dumps({"plan": {"spec_alignment": {"checklist": []}}}),
                encoding="utf-8",
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W589" and "ms_no_schema_plan.json" in e.message for e in errors),
            f"Expected W589 for missing $schema. Got: {errors}",
        )

    def test_w589_fires_on_wrong_schema_uri(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            bad = impl_context_dir / "ms_wrong_schema_plan.json"
            bad.write_text(
                json.dumps({"$schema": "vc:16-anchor", "plan": {}}),
                encoding="utf-8",
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W589" and "ms_wrong_schema_plan.json" in e.message for e in errors),
            f"Expected W589 for wrong $schema. Got: {errors}",
        )

    def test_no_w589_when_schema_correct(self):
        """W589 does not fire when every file declares the expected `vc:16-impl-context`."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(impl_context_dir, "ms_clean_plan.json", scope_in=["auth"])

            errors = validate_file(self.repo_root, str(anchor_path))

        w589 = [e for e in errors if e.code == "W589"]
        self.assertEqual(w589, [], f"W589 should not fire on correct $schema. Got: {w589}")


class TestStep16AnchorW608LegacySchema(_AnchorTestBase):
    """W608 ANCHOR_LEGACY_SCHEMA — anchor path declares the pre-split milestone-plan schema.

    Background: the 0.6.0 Trinity Anchor split moved per-milestone content out
    of ``spec/16_impl_context.json`` into ``spec/impl_context/*.json`` and
    introduced ``vc:16-anchor`` for the root artifact. Host repos that
    pre-date the split still carry a legacy ``$schema: vc:16-impl-context`` at
    the anchor path — schema validation still passes (the old schema is still
    registered for milestone plans), and the anchor route's E308/E309/W587
    silently no-op because the legacy shape has no ``milestone_index``. Without
    W608 the author has no signal that a migration is needed.
    """

    def _legacy_anchor_data(self) -> dict:
        """Pre-split shape: $schema='vc:16-impl-context', carries plan.status
        and plan.summary but no artifact_role, milestone_index, or drift.
        """
        return {
            "$schema": "vc:16-impl-context",
            "id": "step-legacy-anchor",
            "owner": "system",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Legacy anchor still on the pre-split schema.",
                    "scope_in": ["auth"],
                    "scope_out": [],
                    "target_file_patterns": ["src/auth.py"],
                },
                "spec_alignment": {
                    "requirements_summary": [{"theme": "Auth", "summary": "Login"}],
                    "checklist": [],
                },
                "review_requirements": {"test_commands": ["pytest tests/"]},
            },
            "canonical_refs_used": [],
        }

    def test_w608_fires_on_legacy_schema_at_anchor_path(self):
        """W608 fires for a file at the anchor path declaring the legacy schema."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = tmp_dir / "16_impl_context.json"
            anchor_path.write_text(json.dumps(self._legacy_anchor_data()), encoding="utf-8")

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W608" for e in errors),
            f"Expected W608 for legacy schema at anchor path. Got: {errors}",
        )

    def test_w608_does_not_fire_for_new_anchor_schema(self):
        """W608 stays quiet when the anchor declares the new `vc:16-anchor` schema."""
        with tempfile.TemporaryDirectory() as td:
            anchor_path = make_anchor(Path(td), scope_in=["auth"])
            errors = validate_file(self.repo_root, str(anchor_path))
        w608 = [e for e in errors if e.code == "W608"]
        self.assertEqual(
            w608, [],
            f"W608 should not fire on vc:16-anchor artifacts. Got: {w608}",
        )

    def test_w608_does_not_fire_for_milestone_plan_inside_impl_context(self):
        """W608 only fires on the anchor route — not on legitimate milestone plans.

        A milestone plan at ``spec/impl_context/<x>.json`` legitimately declares
        ``$schema: vc:16-impl-context``. It does not route through the anchor
        validator, so W608 must stay silent.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            plan_path = make_milestone_plan(
                impl_context_dir, "ms_clean_plan.json", scope_in=["auth"]
            )
            errors = validate_file(self.repo_root, str(plan_path))
        w608 = [e for e in errors if e.code == "W608"]
        self.assertEqual(
            w608, [],
            f"W608 must not fire on legitimate milestone plans inside "
            f"impl_context/. Got: {w608}",
        )

    def test_w608_message_cites_migration_path(self):
        """W608 message must point at the migration steps so the author can act.

        Pins the actionability contract — a bare "legacy schema" hint without
        a migration path would force every host repo to hunt through docs.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            anchor_path = tmp_dir / "16_impl_context.json"
            anchor_path.write_text(json.dumps(self._legacy_anchor_data()), encoding="utf-8")
            errors = validate_file(self.repo_root, str(anchor_path))
        w608_messages = [e.message for e in errors if e.code == "W608"]
        self.assertTrue(w608_messages, "Expected at least one W608 for this legacy anchor.")
        msg = w608_messages[0]
        # Must name the new schema, the migration artifacts location, and the
        # author-facing prompt so the fix path is discoverable from the warning alone.
        self.assertIn("vc:16-anchor", msg)
        self.assertIn("spec/impl_context/", msg)
        self.assertIn("prompt_16_impl_context.md", msg)


class TestStep16AnchorW610PrefixViolation(_AnchorTestBase):
    """W610 ANCHOR_PREFIX_VIOLATION — milestone plan checklist IDs must start with declared prefix."""

    def test_w610_fires_when_checklist_id_violates_prefix(self):
        """W610 fires when a milestone plan's checklist ID doesn't start with the declared prefix."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-auth", status="in_progress", checklist_id_prefix="AUTH"),
                ],
                drift_checks=["Verified ms-auth scope (2026-04-17)"],
            )
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))

            # Milestone plan with IDs that DON'T start with "AUTH_"
            make_milestone_plan(
                impl_context_dir, "ms_auth_plan.json", milestone="ms-auth",
                scope_in=["auth"],
                checklist=[
                    make_checklist_item("BILLING_LOGIN_01", ["tc-login"]),
                ],
            )

            errors = validate_step_16_anchor(anchor_data, self.repo_root, str(anchor_path))

        w610 = [e for e in errors if e.code == "W610"]
        self.assertTrue(
            len(w610) >= 1,
            f"Expected W610 for checklist ID 'BILLING_LOGIN_01' violating prefix 'AUTH_'. Got: {errors}",
        )
        self.assertIn("BILLING_LOGIN_01", w610[0].message)
        self.assertIn("AUTH_", w610[0].message)

    def test_no_w610_when_checklist_ids_respect_prefix(self):
        """W610 does not fire when all checklist IDs properly start with the declared prefix."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-auth", status="in_progress", checklist_id_prefix="AUTH"),
                ],
                drift_checks=["Verified ms-auth scope (2026-04-17)"],
            )
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))

            make_milestone_plan(
                impl_context_dir, "ms_auth_plan.json", milestone="ms-auth",
                scope_in=["auth"],
                checklist=[
                    make_checklist_item("AUTH_LOGIN_01", ["tc-login"]),
                    make_checklist_item("AUTH_LOGIN_02", ["tc-login"]),
                ],
            )

            errors = validate_step_16_anchor(anchor_data, self.repo_root, str(anchor_path))

        w610 = [e for e in errors if e.code == "W610"]
        self.assertEqual(w610, [], f"W610 should not fire when IDs respect prefix. Got: {w610}")


class TestStep16AnchorPlanDiscovery(_AnchorTestBase):
    """W588, W589 and W611 are reported over the plan files, and ``find_plan`` decides which file is a milestone's plan."""

    def test_w588_w589_w611_are_found_through_find_plan(self):
        """One run: the plan ``find_plan`` returns takes part; an unreadable file is W588, a misschemaed one W589, a plan of no anchor row W611.

        ``ms_a1_plan.json`` is the first plan file naming ``ms-a`` (``find_plan`` returns it); ``ms_a2_plan.json`` names it too and
        would contradict the anchor scope, but is not the plan of ``ms-a`` and so takes no part in drift detection.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=["oauth-flows"],
                milestone_index=[make_milestone_entry("ms-a")],
                drift_checks=["Verified scope (2026-11-16)"],
            )
            make_milestone_plan(impl_context_dir, "ms_a1_plan.json", milestone="ms-a", scope_in=["auth"])
            make_milestone_plan(impl_context_dir, "ms_a2_plan.json", milestone="ms-a", scope_in=["oauth-flows"])
            make_milestone_plan(impl_context_dir, "ms_ghost_plan.json", milestone="ms-ghost")
            (impl_context_dir / "ms_bad_plan.json").write_text("{not json", encoding="utf-8")
            (impl_context_dir / "ms_other_plan.json").write_text(json.dumps({"$schema": "vc:other", "milestone": "ms-a"}), encoding="utf-8")
            errors = validate_file(self.repo_root, str(anchor_path))
        codes = sorted(e.code for e in errors)
        self.assertEqual(codes, ["W588", "W589", "W611"], f"Got: {errors}")
        by_code = {e.code: e.message for e in errors}
        self.assertIn("ms_bad_plan.json", by_code["W588"])
        self.assertIn("ms_other_plan.json", by_code["W589"])
        self.assertIn("ms_ghost_plan.json", by_code["W611"])


class TestStep16AnchorW611DriftSuppressed(_AnchorTestBase):
    """W611 ANCHOR_DRIFT_SUPPRESSED — all milestone files filtered, E308/E309 silently suppressed."""

    def test_w611_fires_when_all_files_misschemaed(self):
        """W611 fires when impl_context/ has files but none survive $schema filtering."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                drift_checks=["Verified scope (2026-04-17)"],
            )
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))

            # Two files, both with wrong $schema — triggers W589 for each
            (impl_context_dir / "ms_a_plan.json").write_text(
                json.dumps({"$schema": "vc:wrong", "plan": {}}), encoding="utf-8",
            )
            (impl_context_dir / "ms_b_plan.json").write_text(
                json.dumps({"$schema": "vc:also-wrong", "plan": {}}), encoding="utf-8",
            )

            errors = validate_step_16_anchor(anchor_data, self.repo_root, str(anchor_path))

        w611 = [e for e in errors if e.code == "W611"]
        self.assertEqual(len(w611), 1, f"Expected exactly one W611. Got: {errors}")
        self.assertIn("2 JSON file(s)", w611[0].message)

    def test_no_w611_when_at_least_one_valid_milestone(self):
        """W611 does not fire when at least one milestone file passes $schema filtering."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[make_milestone_entry("ms-good")],
                drift_checks=["Verified scope (2026-04-17)"],
            )
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))

            # One bad, one good
            (impl_context_dir / "ms_bad_plan.json").write_text(
                json.dumps({"$schema": "vc:wrong"}), encoding="utf-8",
            )
            make_milestone_plan(impl_context_dir, "ms_good_plan.json", scope_in=["auth"], milestone="ms-good")

            errors = validate_step_16_anchor(anchor_data, self.repo_root, str(anchor_path))

        w611 = [e for e in errors if e.code == "W611"]
        self.assertEqual(w611, [], f"W611 should not fire when valid milestones exist. Got: {w611}")

    def test_no_w611_when_impl_context_empty(self):
        """W611 does not fire when impl_context/ exists but has no JSON files (files_seen==0)."""
        from specdev_tools.validation.validators.step_16_anchor import validate_step_16_anchor

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))

            errors = validate_step_16_anchor(anchor_data, self.repo_root, str(anchor_path))

        w611 = [e for e in errors if e.code == "W611"]
        self.assertEqual(w611, [], f"W611 should not fire on empty impl_context/. Got: {w611}")


if __name__ == "__main__":
    unittest.main()
