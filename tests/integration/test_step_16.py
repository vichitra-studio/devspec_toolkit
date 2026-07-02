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
        # Clear the chain-up cache so a previous test that called
        # validate_step_16{a,b,c} directly (bypassing validate_file's clear)
        # cannot pollute the current test through the module-global hash table.
        from specdev_tools.validation.validators.step_16 import _step16_cache
        _step16_cache.clear()

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

    def test_invalid_deferred_checklist_item_missing_reason(self):
        # DEVSPEC-122: checklist_status=="deferred" on a single item requires that
        # item's own deferred_reason, independent of plan.status (which stays
        # "active" here — deferring one item must not require deferring the plan).
        path = os.path.join(self.fixtures_dir, "invalid_deferred_missing_reason.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            len(errors) > 0,
            "Invalid fixture (deferred checklist item missing deferred_reason) should fail validation"
        )
        self.assertTrue(
            any("deferred_reason" in e.message for e in errors),
            f"Expected a schema error mentioning deferred_reason. Got: {errors}"
        )

    def test_invalid_wont_do_checklist_item_missing_reason(self):
        # DEVSPEC-122 follow-up: checklist_status=="wont_do" on a single item
        # requires that item's own wont_do_reason, mirroring the enforced
        # deferred_reason pattern (not the unenforced prose used elsewhere).
        path = os.path.join(self.fixtures_dir, "invalid_wont_do_missing_reason.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            len(errors) > 0,
            "Invalid fixture (wont_do checklist item missing wont_do_reason) should fail validation"
        )
        self.assertTrue(
            any("wont_do_reason" in e.message for e in errors),
            f"Expected a schema error mentioning wont_do_reason. Got: {errors}"
        )

    def test_valid_wont_do_item_with_reason_and_no_linked_test_expectation(self):
        # A wont_do item with its own wont_do_reason, and no linked_test_expectation
        # (optional for wont_do, mirroring the deferred exemption), should pass fully.
        path = os.path.join(self.fixtures_dir, "valid_wont_do_item.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        wont_do_items = [
            item for item in data["plan"]["spec_alignment"]["checklist"]
            if item.get("checklist_status") == "wont_do"
        ]
        self.assertTrue(wont_do_items, "Fixture should contain at least one wont_do checklist item")
        for item in wont_do_items:
            self.assertTrue(
                item.get("wont_do_reason"),
                f"wont_do item {item.get('id')} must carry its own wont_do_reason"
            )
            self.assertNotIn(
                "linked_test_expectation", item,
                f"wont_do item {item.get('id')} should legitimately omit linked_test_expectation in this fixture"
            )
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"valid_wont_do_item.json should pass validation. Errors: {errors}")

    def test_valid_full_covers_single_item_deferred_with_active_plan(self):
        # DEVSPEC-122 regression guard: valid_full.json defers one checklist item
        # (REQ_DB_SCHEMA) while plan.status stays "active" and other items remain
        # active/verified — confirms per-item deferral doesn't require plan-wide
        # deferred status.
        path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["plan"]["status"], "active")
        deferred_items = [
            item for item in data["plan"]["spec_alignment"]["checklist"]
            if item.get("checklist_status") == "deferred"
        ]
        self.assertTrue(deferred_items, "Fixture should contain at least one deferred checklist item")
        for item in deferred_items:
            self.assertTrue(
                item.get("deferred_reason"),
                f"Deferred item {item.get('id')} must carry its own deferred_reason"
            )
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"valid_full.json should still pass validation. Errors: {errors}")

    def test_valid_deferred_item_may_omit_linked_test_expectation(self):
        # DEVSPEC-122: linked_test_expectation was unconditionally required for every
        # checklist item, including deferred ones -- the eventual test contract isn't
        # always known before work starts. Now optional when checklist_status=="deferred".
        path = os.path.join(self.fixtures_dir, "valid_deferred_missing_linked_test_expectation.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(
            errors, [],
            f"Deferred item without linked_test_expectation should pass validation. Errors: {errors}"
        )

    def test_invalid_active_item_still_requires_linked_test_expectation(self):
        # DEVSPEC-122 regression guard: the relaxation above must not become universal --
        # an active (non-deferred) checklist item still requires linked_test_expectation.
        path = os.path.join(self.fixtures_dir, "invalid_active_missing_linked_test_expectation.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(
            len(errors) > 0,
            "Active checklist item missing linked_test_expectation should fail validation"
        )
        self.assertTrue(
            any("linked_test_expectation" in e.message for e in errors),
            f"Expected a schema error mentioning linked_test_expectation. Got: {errors}"
        )

    def test_nfr_refs_gate_skips_entirely_when_07_nfrs_absent(self):
        # Path A: 07_nfrs.json absent → nfrs_data is None → gate silently skips.
        # The fixture has no sibling 07_nfrs.json and the toolkit spec/ has none either.
        # Filter on the validator's specific message text, not the filename (which also
        # contains "nfr_refs" and would falsely match every error from this fixture).
        path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        errors = validate_file(self.repo_root, path)
        nfr_e520 = [e for e in errors if e.code == "E520" and "has no nfr_refs" in e.message]
        self.assertEqual(nfr_e520, [], f"Absent 07_nfrs.json must skip the nfr_refs gate entirely. Got: {nfr_e520}")

    def test_e520_nfr_refs_required_when_fr_has_nfrs(self):
        # Enforcement: behavior-type item for an FR that IS referenced by an NFR
        # must supply nfr_refs.  Uses the secondary search path (sibling of plan) rather
        # than the production layout; see test_e520_nfr_refs_required_production_layout
        # for the primary search path test.
        base_path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nfrs_data = {
            "$schema": "vc:07-nfrs",
            "nfrs": [
                {
                    "nfr_id": "nfr-login-perf",
                    "title": "Login response time",
                    "category": "performance",
                    "trace": [{"type": "fr", "id": "fr-core-login"}]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # 07_nfrs.json in artifact sibling dir so _load_nfrs_data finds it first
            (impl_context_dir / "07_nfrs.json").write_text(json.dumps(nfrs_data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))
        nfr_e520 = [e for e in errors if e.code == "E520" and "has no nfr_refs" in e.message]
        self.assertTrue(
            len(nfr_e520) > 0,
            f"Expected E520 for missing nfr_refs when FR has NFRs. Got: {errors}"
        )
        self.assertTrue(
            any("fr-core-login" in e.message for e in nfr_e520),
            f"Expected E520 message to name the FR. Got: {[e.message for e in nfr_e520]}"
        )

    def test_e520_nfr_refs_required_production_layout(self):
        # Enforcement: production layout — 07_nfrs.json at spec root (parent of impl_context/),
        # not as a sibling of the plan.  This is the primary search path and the main use case
        # for this gate.  Verifies _load_nfrs_data correctly ascends to the spec root when the
        # plan is nested inside impl_context/.
        base_path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nfrs_data = {
            "$schema": "vc:07-nfrs",
            "nfrs": [
                {
                    "nfr_id": "nfr-login-perf",
                    "title": "Login response time",
                    "category": "performance",
                    "trace": [{"type": "fr", "id": "fr-core-login"}]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Production layout: 07_nfrs.json lives at spec root (parent of impl_context/)
            (tmp_dir / "07_nfrs.json").write_text(json.dumps(nfrs_data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))
        nfr_e520 = [e for e in errors if e.code == "E520" and "has no nfr_refs" in e.message]
        self.assertTrue(
            len(nfr_e520) > 0,
            f"Expected E520 for missing nfr_refs (production layout). Got: {errors}"
        )
        self.assertTrue(
            any("fr-core-login" in e.message for e in nfr_e520),
            f"Expected E520 message to name the FR. Got: {[e.message for e in nfr_e520]}"
        )

    def test_nfr_refs_gate_does_not_fire_when_fr_not_in_nfrs_traces(self):
        # Path B: 07_nfrs.json is present but traces a *different* FR.
        # The checklist item's FR (fr-core-login) has no NFR trace → gate must not fire.
        # This is the core new behavior: eliminated false-positives for FRs with no NFRs.
        base_path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nfrs_data = {
            "$schema": "vc:07-nfrs",
            "nfrs": [
                {
                    "nfr_id": "nfr-checkout-perf",
                    "title": "Checkout response time",
                    "category": "performance",
                    "trace": [{"type": "fr", "id": "fr-checkout-flow"}]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (impl_context_dir / "07_nfrs.json").write_text(json.dumps(nfrs_data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))
        nfr_e520 = [e for e in errors if e.code == "E520" and "has no nfr_refs" in e.message]
        self.assertEqual(nfr_e520, [], f"FR not present in NFR traces must not trigger nfr_refs E520. Got: {nfr_e520}")

    def test_nfr_refs_gate_does_not_fire_when_nfrs_list_is_empty(self):
        # Edge case: 07_nfrs.json exists with an empty nfrs array.
        # _build_fr_ids_with_nfrs returns an empty set → no FR is in it → gate does not fire.
        base_path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nfrs_data = {"$schema": "vc:07-nfrs", "nfrs": []}
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (impl_context_dir / "07_nfrs.json").write_text(json.dumps(nfrs_data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))
        nfr_e520 = [e for e in errors if e.code == "E520" and "has no nfr_refs" in e.message]
        self.assertEqual(nfr_e520, [], f"Empty nfrs array must not trigger nfr_refs E520. Got: {nfr_e520}")

    def test_nfr_refs_gate_does_not_fire_for_non_fr_spec_ref_type(self):
        # A behavior-type item with spec_ref.type != "fr" (e.g. "api") must never trigger
        # the nfr_refs gate regardless of what 07_nfrs.json contains.
        # spec_ref_fr_id is None for non-fr types; None is never in fr_ids_with_nfrs.
        base_path = os.path.join(self.fixtures_dir, "invalid_missing_nfr_refs.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Patch the checklist item's spec_ref to type "api" so it's non-FR
        data["plan"]["spec_alignment"]["checklist"][0]["spec_ref"]["type"] = "api"
        data["plan"]["spec_alignment"]["checklist"][0]["spec_ref"]["id"] = "api-login-endpoint"
        nfrs_data = {
            "$schema": "vc:07-nfrs",
            "nfrs": [
                {
                    "nfr_id": "nfr-login-perf",
                    "title": "Login response time",
                    "category": "performance",
                    "trace": [{"type": "fr", "id": "fr-core-login"}]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            (impl_context_dir / "07_nfrs.json").write_text(json.dumps(nfrs_data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))
        nfr_e520 = [e for e in errors if e.code == "E520" and "has no nfr_refs" in e.message]
        self.assertEqual(nfr_e520, [], f"Non-FR spec_ref must not trigger nfr_refs E520. Got: {nfr_e520}")

    def test_false_positive_eliminated_proof_type_no_nfr_trace(self):
        # End-to-end proof that the false positive is fully gone at every layer (schema + validator).
        # A proof-type item with fixture_ref but no nfr_refs, whose FR is absent from 07_nfrs.json
        # traces, must produce zero errors — not just zero nfr_refs-specific errors.
        base_path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Strip nfr_refs from the item; fixture_ref remains so fixture_ref gate cannot fire.
        item = data["plan"]["spec_alignment"]["checklist"][0]
        item.pop("nfr_refs", None)
        # 07_nfrs.json is present but traces a different FR — fr-core-login is not traced.
        nfrs_data = {
            "$schema": "vc:07-nfrs",
            "nfrs": [
                {
                    "nfr_id": "nfr-checkout-perf",
                    "title": "Checkout response time",
                    "category": "performance",
                    "trace": [{"type": "fr", "id": "fr-checkout-flow"}]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_test_plan.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Production layout: 07_nfrs.json at spec root (parent of impl_context/).
            (tmp_dir / "07_nfrs.json").write_text(json.dumps(nfrs_data), encoding="utf-8")
            common_dir = tmp_dir / "common"
            common_dir.mkdir()
            (common_dir / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": ["README.md", "docs/**"]}), encoding="utf-8"
            )
            errors = validate_file(self.repo_root, str(fixture_path))
        self.assertEqual(errors, [],
            f"Valid proof-type item with no nfr_refs (FR not in NFR traces) must pass fully. Got: {errors}")

    def test_invalid_missing_fixture_ref(self):
        # Expect failure because non-deferred item has no fixture_ref
        path = os.path.join(self.fixtures_dir, "invalid_missing_fixture_ref.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing fixture_ref) should fail validation")
        self.assertTrue(any(e.code == "E520" for e in errors), f"Expected E520. Got: {errors}")
    
    def test_valid_metadata_item_without_proof(self):
        # A non-deferred metadata item legitimately omits nfr_refs and fixture_ref.
        # The fixture_ref requirement (schema allOf branch + step_16 TYPES_REQUIRING_PROOF)
        # applies only to proof-types (behavior/constraint/validation/perf/security);
        # metadata/docs/logging are exempt. Guards against a future revert of the schema branch.
        path = os.path.join(self.fixtures_dir, "valid_metadata_no_proof.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid metadata-without-proof fixture should pass. Errors: {errors}")
        self.assertFalse(any(e.code == "E520" for e in errors), f"Metadata item must not trigger E520. Got: {errors}")

    def test_types_requiring_proof_exemption_deferred_and_wont_do_zero_e520(self):
        # DEVSPEC-122 follow-up regression guard: a TYPES_REQUIRING_PROOF item
        # (behavior/constraint/validation/perf/security) that is deferred or
        # wont_do is exempt from both the nfr_refs and fixture_ref proof-of-work
        # gates (see PAUSED_OR_CANCELLED_CHECKLIST_STATUSES in step_16.py). This
        # must hold even when both fields are entirely absent -- not just when
        # one of them is present.
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["plan"]["spec_alignment"]["checklist"] = [
            {
                "id": "REQ_DEFERRED_PROOF_TYPE",
                "spec_ref": {
                    "type": "fr",
                    "id": "task-login-impl",
                    "line_range": "L1-L50",
                    "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                },
                "description": "Implement login endpoint (paused)",
                "type": "behavior",
                "layer": "api",
                "checklist_status": "deferred",
                "deferred_reason": "Blocked on upstream auth contract; resume once finalised."
            },
            {
                "id": "REQ_WONT_DO_PROOF_TYPE",
                "spec_ref": {
                    "type": "fr",
                    "id": "task-login-impl",
                    "line_range": "L1-L50",
                    "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                },
                "description": "Validate login endpoint edge cases (cancelled)",
                "type": "validation",
                "layer": "tests",
                "checklist_status": "wont_do",
                "wont_do_reason": "Superseded by unified-auth validation suite; this path will never be built."
            }
        ]
        data.pop("execution", None)
        data["review"] = {}

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

        e520_errors = [e for e in errors if e.code == "E520"]
        self.assertEqual(
            [], e520_errors,
            f"Deferred/wont_do TYPES_REQUIRING_PROOF items must not trigger E520 "
            f"even with nfr_refs and fixture_ref both absent. Got: {e520_errors}"
        )

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

    def test_wont_do_item_excluded_from_e305_planned_vs_executed(self):
        """E305 exempts wont_do items from the planned-vs-executed diff, same as
        deferred (DEVSPEC-122 follow-up): a wont_do item was never intended to
        be executed, so it should not count as an unexecuted planned item."""
        path = os.path.join(self.fixtures_dir, "invalid_unexecuted_planned.json")
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

    def test_wont_do_item_missing_milestone_ref_does_not_warn_w581(self):
        """W581 exempts wont_do items from milestone_ref, same as deferred
        (DEVSPEC-122 follow-up)."""
        checklist = [{
            "id": "CHK_01",
            "description": "Wallet routing (cancelled)",
            "type": "behavior",
            "layer": "api",
            "checklist_status": "wont_do",
            "wont_do_reason": "Superseded by unified checkout flow.",
        }]
        milestones = [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": []}]

        with tempfile.TemporaryDirectory() as td:
            path = self._make_milestone_ref_fixture(td, checklist, milestones)
            errors = validate_file(self.repo_root, path)

        w581 = [e for e in errors if e.code == "W581"]
        self.assertEqual(w581, [], f"Did not expect W581 for wont_do item. Got: {w581}")

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

    def test_e304_deferred_checklist_item_still_counts_as_coverage(self):
        """A deferred checklist item still covers its roadmap task -- paused, not absent."""
        checklist = [
            self._make_checklist_item("CHK_T1_B", "t1", milestone_ref="m1"),
        ]
        checklist[0]["checklist_status"] = "deferred"
        checklist[0]["deferred_reason"] = "Blocked on upstream contract; resume once finalised."
        del checklist[0]["linked_test_expectation"]  # optional when deferred

        roadmap_milestones = [
            {
                "milestone_id": "m1",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{"task_id": "t1"}]
            }
        ]

        impl_context = self._minimal_impl_context(checklist, milestone_ref="m1")

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        self.assertEqual(
            [], e304_errors,
            f"Deferred checklist item should still cover its task; expected no E304. Got: {e304_errors}"
        )

    def test_e304_control_active_uncovered_task_still_fires(self):
        """Control: an active (non-deferred) uncovered task must still fire E304."""
        checklist = []  # no checklist items at all -- t1 genuinely uncovered

        roadmap_milestones = [
            {
                "milestone_id": "m1",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{"task_id": "t1"}]
            }
        ]

        impl_context = self._minimal_impl_context(checklist, milestone_ref="m1")

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        self.assertTrue(
            any("t1" in e.message for e in e304_errors),
            f"Expected E304 for genuinely uncovered task 't1'. Got: {e304_errors}"
        )

    def test_e304_deferred_task_status_exempts_from_coverage(self):
        """A roadmap task marked status:"deferred" (its own status_reason, not a
        checklist item) is already the authored acknowledgment that it's
        paused -- it must not also need a checklist item to avoid E304."""
        checklist = []  # no checklist items at all -- t1 is deferred at the task layer itself

        roadmap_milestones = [
            {
                "milestone_id": "m1",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{
                    "task_id": "t1",
                    "status": "deferred",
                    "status_reason": "Blocked on upstream contract; resume once finalised.",
                }]
            }
        ]

        impl_context = self._minimal_impl_context(checklist, milestone_ref="m1")

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        self.assertEqual(
            [], e304_errors,
            f"Task-level deferred status should exempt from E304 without any checklist item. Got: {e304_errors}"
        )

    def test_e304_wont_do_task_status_exempts_from_coverage(self):
        """A roadmap task marked status:"wont_do" is permanently cancelled --
        it must not need a checklist item to avoid E304 either."""
        checklist = []

        roadmap_milestones = [
            {
                "milestone_id": "m1",
                "status": "in_progress",
                "fr_refs": [],
                "tasks": [{
                    "task_id": "t1",
                    "status": "wont_do",
                    "status_reason": "Superseded by task-implement-unified-checkout.",
                }]
            }
        ]

        impl_context = self._minimal_impl_context(checklist, milestone_ref="m1")

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        self.assertEqual(
            [], e304_errors,
            f"Task-level wont_do status should exempt from E304 without any checklist item. Got: {e304_errors}"
        )

    def test_e304_skips_deferred_milestones(self):
        """E304's milestone-fallback branch skips 'deferred' milestones, like 'done'."""
        checklist = []  # no checklist items — no coverage for either milestone

        roadmap_milestones = [
            {
                "milestone_id": "ms-deferred",
                "status": "deferred",
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

        # No milestone_ref set — exercises the fallback skip-list branch
        impl_context = self._minimal_impl_context(checklist)

        with tempfile.TemporaryDirectory() as td:
            path = self._make_e304_fixture(td, impl_context, roadmap_milestones)
            errors = validate_file(self.repo_root, path)

        e304_errors = [e for e in errors if e.code == "E304"]
        e304_messages = [e.message for e in e304_errors]

        self.assertTrue(
            any("t2" in msg for msg in e304_messages),
            f"Expected E304 for uncovered task 't2' in in_progress milestone. Got: {e304_messages}"
        )
        self.assertFalse(
            any("t1" in msg for msg in e304_messages),
            f"Did not expect E304 for task 't1' in deferred milestone. Got: {e304_messages}"
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
                "status": "active",
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
                "status": "active",
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
                        "evidence_binding": {
                            "timestamp": "2024-01-01T00:00:00Z",
                            "sha256": "a" * 64,
                            "exit_code": 0,
                            "command": "pytest tests/",
                        },
                    },
                    {
                        # Duplicate command — 16b validator flags this
                        "command": "pytest tests/",
                        "status": "passed",
                        "outcome_description": "Duplicate.",
                        "reasoning": "OK.",
                        "evidence": "1 passed",
                        "evidence_ref": "ci-002",
                        "evidence_binding": {
                            "timestamp": "2024-01-01T00:00:00Z",
                            "sha256": "b" * 64,
                            "exit_code": 0,
                            "command": "pytest tests/",
                        },
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
        from specdev_tools.validation.validate import _refine_impl_context_substep

        plan_only = {
            "$schema": "vc:16-impl-context",
            "plan": {"status": "active"},
        }
        plan_plus_empty_exec = {
            "$schema": "vc:16-impl-context",
            "plan": {"status": "active"},
            "execution": {"execution_results": []},
            "review": {},
        }
        self.assertEqual(_refine_impl_context_substep("16a", plan_only), "16a")
        self.assertEqual(_refine_impl_context_substep("16a", plan_plus_empty_exec), "16a")
        # Non-impl_context steps are never refined
        self.assertEqual(_refine_impl_context_substep("04", plan_only), "04")
        self.assertEqual(_refine_impl_context_substep("unknown", plan_only), "unknown")

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
        that the 16a-specific checklist-id-uniqueness check fires via
        dispatch — proving content refinement leaves plan-only artifacts
        on the 16a path rather than demoting to the base or promoting to
        16b/16c.
        """
        base_path = os.path.join(self.fixtures_dir, "valid_full.json")
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Induce a 16a-specific failure: duplicate checklist IDs (checked by
        # validate_step_16a, not the base validator).
        original = data["plan"]["spec_alignment"]["checklist"][0]
        duplicate = json.loads(json.dumps(original))
        duplicate["id"] = original["id"]  # force exact id collision
        data["plan"]["spec_alignment"]["checklist"].append(duplicate)
        data.pop("execution", None)
        data["review"] = {}
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

        # Duplicate checklist id is pinned by validate_step_16a (E520).
        dup_id_errors = [
            e for e in errors
            if e.code == "E520" and "duplicate checklist id" in e.message.lower()
        ]
        self.assertEqual(
            len(dup_id_errors), 1,
            f"Expected exactly one duplicate-checklist-id error from the "
            f"16a dispatch path. Got: {errors}"
        )

    def test_step_16c_chain_up_deduplicates_base_checks(self):
        """Chain-up (16c → 16b → 16a → base) must not cause base checks to
        fire multiple times on the same artifact.

        _step16_cache (MD5 on data+path) deduplicates the base pass.  Without
        it, calling validate_step_16c would re-run validate_step_16's checks
        three times — once per layer — and any base-level error (here E307)
        would appear triplicated in the returned list.  This test pins the
        cache behavior by asserting the error appears exactly once.
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

    def test_step_16c_w582_fires_when_milestone_file_lives_in_impl_context(self):
        """W582 must fire even when the 16c artifact lives inside spec/impl_context/.

        Before the _load_roadmap DRY refactor, step_16c looked for 14_roadmap.json
        as a direct sibling of the artifact — which meant 16c reviews under
        spec/impl_context/ silently skipped W582 because the roadmap is one
        directory up.  This test pins the corrected path resolution.
        """
        from specdev_tools.validation.validators.step_16c import validate_step_16c

        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-w582-impl-context-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "W582 test inside impl_context/.",
                    "scope_in": ["auth-api"],
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
                "verdict": "verified",
                "fixture_status": {
                    "implemented_interfaces": [],
                    "test_results": [],
                    "ci_status": "green",
                },
                "semantic_review": {
                    # fr-login covered, fr-logout not
                    "fr_coverage": [
                        {
                            "fr_id": "fr-login",
                            "satisfied": True,
                            "evidence_summary": "Login verified.",
                            "checklist_ids": [],
                        }
                    ],
                    "hallucinated_features": [],
                    "scope_delta": "None.",
                },
            },
            "canonical_refs_used": [],
            "milestone_ref": "ms-v1",
        }
        roadmap = {
            "milestones": [
                {
                    "milestone_id": "ms-v1",
                    "fr_refs": ["fr-login", "fr-logout"],
                    "tasks": [{"task_id": "fr-login"}, {"task_id": "fr-logout"}],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            impl_context_dir = tmp_dir / "impl_context"
            impl_context_dir.mkdir()
            fixture_path = impl_context_dir / "ms_v1_review.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            # Roadmap lives at spec-root level (one dir up from impl_context/)
            (tmp_dir / "14_roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")

            errors = validate_step_16c(data, self.repo_root, spec_path=str(fixture_path))

        w582_errors = [e for e in errors if e.code == "W582"]
        self.assertTrue(
            any("fr-logout" in e.message for e in w582_errors),
            f"Expected W582 for 'fr-logout' when 16c lives in impl_context/. "
            f"Got W582 errors: {[e.message for e in w582_errors]}"
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

    def test_w616_fires_for_deferred_item_marked_verified(self):
        """W616 fires when checklist_status='deferred' but implementation.status='verified'."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Check output",
                "evidence": {"type": "log", "content": "PASS " + ("x" * 60)}
            }
        ]
        data = self._make_evidence_test_data("CHK_W616_CONTRADICTION", actions)
        item = data["plan"]["spec_alignment"]["checklist"][0]
        item["checklist_status"] = "deferred"
        item["deferred_reason"] = "Marked deferred after verification without reconciling implementation status."

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

        w616_errors = [e for e in errors if e.code == "W616"]
        self.assertTrue(
            len(w616_errors) > 0,
            f"Expected W616 for deferred item marked verified. Got: {errors}"
        )
        self.assertTrue(
            any("CHK_W616_CONTRADICTION" in e.message for e in w616_errors),
            f"Expected W616 message to reference item id. Got: {[e.message for e in w616_errors]}"
        )

    def test_w616_control_active_verified_item_does_not_fire(self):
        """Control: an active (non-deferred) verified item must not fire W616."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Check output",
                "evidence": {"type": "log", "content": "PASS " + ("x" * 60)}
            }
        ]
        data = self._make_evidence_test_data("CHK_W616_CONTROL", actions)

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

        w616_errors = [e for e in errors if e.code == "W616"]
        self.assertEqual(
            [], w616_errors,
            f"Did not expect W616 for active verified item. Got: {w616_errors}"
        )

    def test_w616_control_deferred_pending_item_does_not_fire(self):
        """Control: a deferred item with implementation.status='pending' (not
        verified) must not fire W616 -- no contradiction to reconcile."""
        actions = []
        data = self._make_evidence_test_data("CHK_W616_PENDING", actions)
        item = data["plan"]["spec_alignment"]["checklist"][0]
        item["checklist_status"] = "deferred"
        item["deferred_reason"] = "Blocked on upstream dependency."
        item["implementation"]["status"] = "pending"

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

        w616_errors = [e for e in errors if e.code == "W616"]
        self.assertEqual(
            [], w616_errors,
            f"Did not expect W616 for deferred+pending item. Got: {w616_errors}"
        )

    def test_w616_fires_for_wont_do_item_marked_verified(self):
        """W616 also fires when checklist_status='wont_do' but implementation.status='verified'
        -- the same stale contradiction as deferred+verified, just for a permanently
        cancelled item instead of a paused one."""
        actions = [
            {
                "type": "manual_verification",
                "description": "Check output",
                "evidence": {"type": "log", "content": "PASS " + ("x" * 60)}
            }
        ]
        data = self._make_evidence_test_data("CHK_W616_WONT_DO_CONTRADICTION", actions)
        item = data["plan"]["spec_alignment"]["checklist"][0]
        item["checklist_status"] = "wont_do"
        item["wont_do_reason"] = "Superseded after verification without reconciling implementation status."

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

        w616_errors = [e for e in errors if e.code == "W616"]
        self.assertTrue(
            len(w616_errors) > 0,
            f"Expected W616 for wont_do item marked verified. Got: {errors}"
        )
        self.assertTrue(
            any("CHK_W616_WONT_DO_CONTRADICTION" in e.message for e in w616_errors),
            f"Expected W616 message to reference item id. Got: {[e.message for e in w616_errors]}"
        )

    def test_w616_control_wont_do_pending_item_does_not_fire(self):
        """Control: a wont_do item with implementation.status='pending' (not
        verified) must not fire W616 -- no contradiction to reconcile."""
        actions = []
        data = self._make_evidence_test_data("CHK_W616_WONT_DO_PENDING", actions)
        item = data["plan"]["spec_alignment"]["checklist"][0]
        item["checklist_status"] = "wont_do"
        item["wont_do_reason"] = "Superseded by a different checklist item."
        item["implementation"]["status"] = "pending"

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

        w616_errors = [e for e in errors if e.code == "W616"]
        self.assertEqual(
            [], w616_errors,
            f"Did not expect W616 for wont_do+pending item. Got: {w616_errors}"
        )

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

    # --- W603 tests ---

    def test_w603_fires_for_execution_file_outside_task_scope(self):
        """W603 fires when execution.files_touched has a file not in any checklist item's files_touched."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-w603-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
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
                "status": "active",
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
                "status": "active",
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
                "status": "active",
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
                "execution_results": [],
                "critical_evidence": {
                    "passed_test_commands": [],
                    "satisfied_checklist_ids": []
                }
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
                "status": "active",
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
                ],
                "critical_evidence": {
                    "passed_test_commands": ["pytest tests/"],
                    "satisfied_checklist_ids": []
                }
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

    def test_e302_fires_missing_passed_test_commands(self):
        """E302 fires when test command not in critical_evidence.passed_test_commands."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-e302-missing-passed",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "E302 test — missing passed_test_commands.",
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
                    {"command": "pytest tests/", "status": "passed", "output": "ok"},
                    {"command": "npm test", "status": "passed", "output": "ok"}
                ],
                "critical_evidence": {
                    "passed_test_commands": ["pytest tests/"],
                    "satisfied_checklist_ids": []
                }
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
            any("npm test" in e.message and "passed_test_commands" in e.message for e in e302_errors),
            f"Expected E302 for 'npm test' not in passed_test_commands. Got E302: {[e.message for e in e302_errors]}"
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
        passed_test_commands=None,
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
                "status": "active",
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
                "critical_evidence": {
                    "passed_test_commands": passed_test_commands or [],
                    "satisfied_checklist_ids": [],
                },
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
            passed_test_commands=["pytest tests/", "npm test"],
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
            passed_test_commands=["pytest tests/"],
        )
        errors = self._run_step16_validate(data)
        e301 = [e for e in errors if e.code == "E301" and "MISSING_PROOF_CLOSURE" in e.message]
        self.assertTrue(
            any("npm test" in e.message for e in e301),
            f"Expected E301 MISSING_PROOF_CLOSURE for 'npm test'; got: {[e.message for e in e301]}"
        )

    def test_e302_object_form_test_commands_against_passed_test_commands(self):
        """E302 fires for object-form test_commands missing from passed_test_commands when verdict=verified."""
        def build(passed_list):
            return self._base_step16_artifact(
                artifact_id="step-e302-objform",
                summary="Object-form test_commands E302 path.",
                test_commands=[
                    make_object_test_command("pytest tests/"),
                    make_object_test_command("npm test"),
                ],
                execution_results=[
                    {"command": "pytest tests/", "status": "passed", "output": "ok"},
                    {"command": "npm test", "status": "passed", "output": "ok"},
                ],
                passed_test_commands=passed_list,
                review={
                    "verdict": "verified",
                    "findings": [],
                    "fixture_status": {"ci_status": "green"},
                },
            )

        # Both commands present in passed_test_commands → no E302 from this check.
        errors_ok = self._run_step16_validate(build(["pytest tests/", "npm test"]))
        e302_missing = [
            e for e in errors_ok
            if e.code == "E302" and "passed_test_commands" in e.message
        ]
        self.assertEqual(
            e302_missing, [],
            f"Expected no E302 passed_test_commands errors when all object-form commands listed; got: {[e.message for e in e302_missing]}"
        )

        # Drop 'npm test' from passed_test_commands → E302 must fire for 'npm test'.
        errors_bad = self._run_step16_validate(build(["pytest tests/"]))
        e302_bad = [
            e for e in errors_bad
            if e.code == "E302" and "npm test" in e.message and "passed_test_commands" in e.message
        ]
        self.assertTrue(
            e302_bad,
            f"Expected E302 for 'npm test' missing from passed_test_commands; got E302 errors: {[e.message for e in errors_bad if e.code == 'E302']}"
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
                passed_test_commands=["pytest tests/"],
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
            passed_test_commands=["echo placeholder"],
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
                "status": "active",
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

    # --- crossCycleAmbiguityItem accepts optional resolved/decision ---

    def test_emergent_ambiguity_with_resolved_and_decision(self):
        """crossCycleAmbiguityItem accepts optional resolved + decision fields."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-amb-test",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {"functional_summary": "amb test.", "scope_in": ["core"], "scope_out": [], "target_file_patterns": ["src/**"]},
                "spec_alignment": {"requirements_summary": [{"theme": "Core", "summary": "x"}], "checklist": []},
                "docs_impact": {"status": "not_required", "rationale": "n/a"},
            },
            "execution": {
                "emergent_ambiguities": [
                    {
                        "id": "amb-1",
                        "description": "Ambiguity surfaced during execution",
                        "severity": "medium",
                        "resolved": True,
                        "decision": "accepted",
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
            f"resolved/decision must validate. Got: {[e.message for e in errors]}"
        )

    def test_emergent_ambiguity_still_valid_without_resolved(self):
        """crossCycleAmbiguityItem without resolved/decision still validates (fields optional)."""
        data = {
            "$schema": "vc:16-impl-context",
            "id": "step-amb-min",
            "owner": "api",
            "created_at": "2024-01-01T00:00:00Z",
            "plan": {
                "status": "active",
                "summary": {"functional_summary": "amb test.", "scope_in": ["core"], "scope_out": [], "target_file_patterns": ["src/**"]},
                "spec_alignment": {"requirements_summary": [{"theme": "Core", "summary": "x"}], "checklist": []},
                "docs_impact": {"status": "not_required", "rationale": "n/a"},
            },
            "execution": {
                "emergent_ambiguities": [
                    {"id": "amb-2", "description": "Minimal ambiguity shape", "severity": "low"}
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
                "status": "active",
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
            "status": "active",
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


if __name__ == '__main__':
    unittest.main()
