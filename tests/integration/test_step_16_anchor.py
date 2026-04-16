"""Integration tests for the Step 16 Trinity Anchor validator.

Covers:
  - Schema validation: valid fixtures pass; invalid fixtures fail on the right signal
  - E308 (ANCHOR_SCOPE_DRIFT): scope contradiction + FR/API ownership conflict
  - E309 (ANCHOR_CHECKLIST_DRIFT): cross-milestone checklist ID collision
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
    make_milestone_entry,
    make_milestone_plan,
)


_TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = str(_TOOLKIT_ROOT)
_FIXTURES_DIR = _TOOLKIT_ROOT / "tests" / "fixtures" / "step_16"


class _AnchorTestBase(unittest.TestCase):
    """Common base — every anchor test class needs the same toolkit + fixture paths."""

    repo_root = _REPO_ROOT
    fixtures_dir = _FIXTURES_DIR


class TestStep16AnchorSchema(_AnchorTestBase):
    """Schema-level tests using pre-built fixture files."""

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

    def test_invalid_context_path_pattern_rejected(self):
        """milestone_index[].context_path must match ^(spec/)?impl_context/<file>.json$.

        Downstream validators (traceability_closure, anchor drift checks) read
        this path directly — a path that doesn't resolve to impl_context/ would
        silently skip the milestone from coverage. The schema pattern catches
        typos and mislocations at author time.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            (tmp_dir / "impl_context").mkdir()
            # Valid anchor shape except for the bogus context_path.
            anchor_path = make_anchor(
                tmp_dir,
                milestone_index=[
                    make_milestone_entry(
                        "ms-auth",
                        # Not under impl_context/ — pattern must reject.
                        context_path="spec/plans/ms_auth_plan.json",
                    ),
                ],
            )
            errors = validate_file(self.repo_root, str(anchor_path))
        self.assertTrue(
            any(e.code == "E520" and "context_path" in e.message for e in errors),
            f"Expected E520 rejecting non-impl_context context_path. Got: {errors}",
        )


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
            )
            make_milestone_plan(
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

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["jwt-token-validation"],
                scope_out=["oauth-flows"],
            )
            make_milestone_plan(
                impl_context_dir, "ms_jwt.json",
                scope_in=[],
                scope_out=["jwt-token-validation"],  # contradicts anchor scope_in
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" for e in errors),
            f"Expected E308 for reverse scope contradiction. Got: {errors}"
        )

    def test_e308_fr_ownership_conflict_two_in_flight_milestones(self):
        """E308 fires when the same FR is owned by two non-done milestones."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            (tmp_dir / "impl_context").mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-a", status="in_progress",
                                         fr_refs=["fr-login"], checklist_id_prefix="MSA"),
                    make_milestone_entry("ms-b", status="in_progress",
                                         fr_refs=["fr-login"], checklist_id_prefix="MSB"),
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" and "FR" in e.message for e in errors),
            f"Expected E308 with FR ownership conflict marker. Got: {errors}"
        )

    def test_e308_api_ownership_conflict_uses_api_in_message(self):
        """E308 ownership-conflict message says 'API' when the conflicting ID starts with api-."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            (tmp_dir / "impl_context").mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["api"],
                milestone_index=[
                    make_milestone_entry("ms-a", status="in_progress",
                                         fr_refs=["api-session-create"], checklist_id_prefix="MSA"),
                    make_milestone_entry("ms-b", status="pending",
                                         fr_refs=["api-session-create"], checklist_id_prefix="MSB"),
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "E308" and "API" in e.message for e in errors),
            f"Expected E308 with 'API' marker for api- ID conflict. Got: {errors}"
        )

    def test_e308_done_milestone_does_not_conflict(self):
        """A 'done' milestone does not block the same FR in an in-flight milestone."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            (tmp_dir / "impl_context").mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-done", status="done",
                                         fr_refs=["fr-login"], checklist_id_prefix="DONE"),
                    make_milestone_entry("ms-active", status="in_progress",
                                         fr_refs=["fr-login"], checklist_id_prefix="ACTIVE"),
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e308 = [e for e in errors if e.code == "E308"]
        self.assertEqual(e308, [], f"Done milestone should not trigger E308. Got: {e308}")
        # Pin that no OTHER error codes start masquerading here. If a future
        # regression re-labels the FR-ownership signal under a different code
        # (e.g. re-uses E309), this test would otherwise still appear green.
        non_w587 = [e for e in errors if e.code not in ("W587",)]
        self.assertEqual(
            non_w587, [],
            f"Only W587 (drift-checks-stale) is expected when milestone_index is "
            f"non-empty but drift.checks is empty. Got: {[e.code for e in errors]}",
        )

    def test_e308_deferred_milestone_still_conflicts(self):
        """A 'deferred' milestone still claims FR ownership — must trigger E308.

        Only 'done' milestones are exempt from ownership conflict detection (the FR
        has been delivered and may legitimately be revisited later). 'deferred'
        represents a consciously postponed but still-owned commitment, so the same
        FR in another active/pending milestone is a real contradiction.
        Validator contract pinned at step_16_anchor.py:111.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            (tmp_dir / "impl_context").mkdir()

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                milestone_index=[
                    make_milestone_entry("ms-deferred", status="deferred",
                                         fr_refs=["fr-login"], checklist_id_prefix="DEFER"),
                    make_milestone_entry("ms-active", status="in_progress",
                                         fr_refs=["fr-login"], checklist_id_prefix="ACTIVE"),
                ],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e308 = [e for e in errors if e.code == "E308" and "fr-login" in e.message]
        self.assertEqual(
            len(e308), 1,
            f"Deferred + active milestone sharing fr-login should fire exactly one "
            f"E308 FR-ownership conflict. Got: {[e.message for e in errors]}",
        )

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
            )
            make_milestone_plan(
                impl_context_dir, "ms_jwt.json",
                scope_in=["jwt-token-validation"],  # matches anchor scope_in — fine
                scope_out=[],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e308 = [e for e in errors if e.code == "E308"]
        self.assertEqual(e308, [], f"Did not expect E308. Got: {e308}")


class TestStep16AnchorE309ChecklistDrift(_AnchorTestBase):
    """E309 ANCHOR_CHECKLIST_DRIFT — cross-milestone checklist ID + prefix collisions."""

    def test_e309_same_id_different_spec_ref(self):
        """E309 fires when same checklist ID maps to different spec_ref.id across milestones."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(
                impl_context_dir, "ms_a.json",
                checklist=[make_checklist_item("AUTH_LOGIN", "fr-login-v1")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_b.json",
                # Same ID "AUTH_LOGIN" but different spec_ref.id — E309
                checklist=[make_checklist_item("AUTH_LOGIN", "fr-login-v2")],
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

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(
                impl_context_dir, "ms_a.json",
                checklist=[make_checklist_item("AUTH_LOGIN", "fr-login-v1")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_b.json",
                checklist=[make_checklist_item("AUTH_LOGIN", "fr-login-v1")],  # same — ok
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e309 = [e for e in errors if e.code == "E309"]
        self.assertEqual(e309, [], f"Did not expect E309. Got: {e309}")

    def test_no_e309_different_ids_different_spec_refs(self):
        """No E309 when checklist IDs are unique across milestones."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(
                impl_context_dir, "ms_a.json",
                checklist=[make_checklist_item("AUTH_LOGIN", "fr-login")],
            )
            make_milestone_plan(
                impl_context_dir, "ms_b.json",
                checklist=[make_checklist_item("AUTH_SESSION", "fr-session")],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e309 = [e for e in errors if e.code == "E309"]
        self.assertEqual(e309, [], f"Did not expect E309. Got: {e309}")

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
                    make_milestone_entry("ms-auth-v1", status="done",
                                         fr_refs=["fr-login"], checklist_id_prefix="AUTH"),
                    make_milestone_entry("ms-auth-v2", status="in_progress",
                                         fr_refs=["fr-mfa"], checklist_id_prefix="AUTH"),
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
                    make_milestone_entry("ms-a", status="in_progress",
                                         fr_refs=["fr-login"], checklist_id_prefix="MSA"),
                    make_milestone_entry("ms-b", status="pending",
                                         fr_refs=["fr-signup"], checklist_id_prefix="MSB"),
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

            anchor_path = make_anchor(
                tmp_dir,
                scope_in=["auth"],
                scope_out=["payments"],
                functional_summary="Anchor with stray non-milestone files.",
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
                    make_milestone_entry("ms-auth", status="in_progress",
                                         fr_refs=["fr-login"], checklist_id_prefix="AUTH"),
                ],
                drift_checks=["Verified ms-auth scope (2026-04-15)"],
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        e304 = [e for e in errors if e.code == "E304"]
        self.assertEqual(e304, [], f"Anchor route must never emit E304. Got: {e304}")

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
            broken_path = impl_context_dir / "ms_broken.json"
            broken_path.write_text("{not: valid json,", encoding="utf-8")

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W588" and "ms_broken.json" in e.message for e in errors),
            f"Expected W588 mentioning ms_broken.json. Got: {errors}"
        )

    def test_no_w588_when_all_milestone_files_parse(self):
        """W588 does not fire when every milestone file in impl_context/ parses cleanly."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(impl_context_dir, "ms_clean.json", scope_in=["auth"])

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
            bad = impl_context_dir / "ms_no_schema.json"
            bad.write_text(
                json.dumps({"plan": {"spec_alignment": {"checklist": []}}}),
                encoding="utf-8",
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W589" and "ms_no_schema.json" in e.message for e in errors),
            f"Expected W589 for missing $schema. Got: {errors}",
        )

    def test_w589_fires_on_wrong_schema_uri(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            bad = impl_context_dir / "ms_wrong_schema.json"
            bad.write_text(
                json.dumps({"$schema": "vc:16-anchor", "plan": {}}),
                encoding="utf-8",
            )

            errors = validate_file(self.repo_root, str(anchor_path))

        self.assertTrue(
            any(e.code == "W589" and "ms_wrong_schema.json" in e.message for e in errors),
            f"Expected W589 for wrong $schema. Got: {errors}",
        )

    def test_no_w589_when_schema_correct(self):
        """W589 does not fire when every file declares the expected `vc:16-impl-context`."""
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()

            anchor_path = make_anchor(tmp_dir, scope_in=["auth"])
            make_milestone_plan(impl_context_dir, "ms_clean.json", scope_in=["auth"])

            errors = validate_file(self.repo_root, str(anchor_path))

        w589 = [e for e in errors if e.code == "W589"]
        self.assertEqual(w589, [], f"W589 should not fire on correct $schema. Got: {w589}")


if __name__ == "__main__":
    unittest.main()
