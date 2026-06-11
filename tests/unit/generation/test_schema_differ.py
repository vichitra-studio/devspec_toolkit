"""Tests for specdev_tools.generation.schema_differ — migration diff engine.

Created by FIX-047 (Batch 5).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.generation.schema_differ import (
    DiffType,
    FieldDiff,
    MigrationAction,
    MigrationDiff,
    ParadigmShift,
    StepDiff,
    apply_step16_anchor_mapping,
    calculate_version_delta,
    compare_step_inventories,
    detect_paradigm_shifts,
    diff_spec_directory,
    diff_step_fields,
    format_status_report,
    inventory_toolkit_schemas,
    inventory_user_steps,
)

# Real toolkit root (…/tests/unit/generation/test_schema_differ.py → toolkit root)
_TOOLKIT_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# DiffType / MigrationAction enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_diff_type_values(self):
        assert DiffType.MISSING_REQUIRED.value == "missing_required"
        assert DiffType.EXTRA_FIELD.value == "extra_field"
        assert DiffType.TYPE_MISMATCH.value == "type_mismatch"

    def test_diff_type_schema_ref_outdated_enum_value(self):
        # SCHEMA_REF_OUTDATED is emitted when a spec file's $schema does not
        # match the expected $id (schema_differ.py:452). The step-16 anchor
        # mapping exists precisely to avoid a *spurious* one on the root
        # 16_impl_context file. Guard its string value against accidental
        # renames so the wire/serialized "schema_ref" token stays stable.
        assert DiffType.SCHEMA_REF_OUTDATED.value == "schema_ref"

    def test_migration_action_values(self):
        assert MigrationAction.AUTO.value == "auto"
        assert MigrationAction.AI_ASSISTED.value == "ai_assisted"


# ---------------------------------------------------------------------------
# calculate_version_delta
# ---------------------------------------------------------------------------

class TestCalculateVersionDelta:
    def test_same_version_returns_none(self):
        assert calculate_version_delta("0.3.0", "0.3.0") is None

    def test_none_source_returns_none(self):
        assert calculate_version_delta(None, "0.3.0") is None

    def test_major_delta(self):
        result = calculate_version_delta("0.3.0", "1.0.0")
        assert result is not None
        assert "MAJOR" in result

    def test_minor_delta(self):
        result = calculate_version_delta("0.2.0", "0.3.0")
        assert result is not None
        assert "MINOR" in result

    def test_patch_delta(self):
        result = calculate_version_delta("0.3.0", "0.3.1")
        assert result is not None
        assert "PATCH" in result

    def test_downgrade_returns_none(self):
        # True downgrade: target minor strictly below source. All deltas <= 0,
        # so calculate_version_delta falls to the else branch and returns None.
        result = calculate_version_delta("1.1.0", "1.0.0")
        assert result is None

    def test_downgrade_major_returns_none(self):
        # Downgrade along the major axis (and others) — distinct input path from
        # the same-version case; exercises negative major/minor/patch deltas.
        result = calculate_version_delta("2.1.3", "1.0.0")
        assert result is None

    def test_multiple_updates(self):
        result = calculate_version_delta("0.1.0", "0.3.0")
        assert result is not None
        assert "2 MINOR updates" in result


# ---------------------------------------------------------------------------
# format_status_report — downgrade handling
# ---------------------------------------------------------------------------

class TestFormatStatusReportDowngrade:
    """format_status_report must distinguish a downgrade (project ahead of
    toolkit) from an upgrade-needed state. On a downgrade, calculate_version_delta
    returns None; the formatter must emit an informational 'ahead of toolkit'
    line and must NOT recommend migration.
    """

    def test_downgrade_reports_ahead_not_migration(self):
        # Project on 1.2.0 referencing an older toolkit 1.0.0 → downgrade.
        diff = MigrationDiff(
            source_version="1.2.0",
            target_version="1.0.0",
            version_delta=None,  # calculate_version_delta returns None for a downgrade
        )
        out = format_status_report(diff)
        assert "ahead of" in out, (
            f"downgrade status must note the project is ahead of the toolkit; got:\n{out}"
        )
        assert "1.2.0" in out and "1.0.0" in out
        assert "Migration recommended" not in out, (
            f"a downgrade must NOT recommend migration; got:\n{out}"
        )

    def test_upgrade_still_recommends_migration(self):
        # Guard the other direction: a real upgrade must still recommend migration.
        diff = MigrationDiff(
            source_version="1.0.0",
            target_version="1.1.0",
            version_delta="1 MINOR update",
            summary={
                "steps_missing": 0,
                "steps_needs_rename": 0,
                "steps_needs_update": 0,
                "paradigm_shifts": 0,
            },
        )
        out = format_status_report(diff)
        assert "Migration recommended" in out, (
            f"an upgrade must still recommend migration; got:\n{out}"
        )

    def test_aligned_version_reports_aligned(self):
        # Same version → aligned branch, neither downgrade nor migration text.
        diff = MigrationDiff(source_version="1.1.0", target_version="1.1.0")
        out = format_status_report(diff)
        assert "aligned" in out
        assert "Migration recommended" not in out
        assert "ahead of" not in out


# ---------------------------------------------------------------------------
# inventory_user_steps
# ---------------------------------------------------------------------------

class TestInventoryUserSteps:
    def test_finds_step_files(self, tmp_path):
        (tmp_path / "00_charter.json").write_text("{}")
        (tmp_path / "04_frs.json").write_text("{}")
        (tmp_path / "not_a_step.json").write_text("{}")
        result = inventory_user_steps(tmp_path)
        assert "00_charter" in result
        assert "04_frs" in result
        assert "not_a_step" not in result

    def test_empty_dir(self, tmp_path):
        assert inventory_user_steps(tmp_path) == {}

    def test_nonexistent_dir(self, tmp_path):
        assert inventory_user_steps(tmp_path / "nope") == {}

    def test_substep_files(self, tmp_path):
        (tmp_path / "13a_completeness.json").write_text("{}")
        result = inventory_user_steps(tmp_path)
        assert "13a_completeness" in result


# ---------------------------------------------------------------------------
# inventory_toolkit_schemas
# ---------------------------------------------------------------------------

class TestInventoryToolkitSchemas:
    def test_finds_schema_files(self, tmp_path):
        (tmp_path / "00_charter.schema.json").write_text("{}")
        (tmp_path / "04_frs.schema.json").write_text("{}")
        (tmp_path / "random.json").write_text("{}")
        result = inventory_toolkit_schemas(tmp_path)
        assert "00_charter" in result
        assert "04_frs" in result
        assert "random" not in result

    def test_empty_dir(self, tmp_path):
        assert inventory_toolkit_schemas(tmp_path) == {}

    def test_nonexistent_dir(self, tmp_path):
        assert inventory_toolkit_schemas(tmp_path / "nope") == {}


# ---------------------------------------------------------------------------
# compare_step_inventories
# ---------------------------------------------------------------------------

class TestCompareStepInventories:
    def test_matching_steps_ok(self, tmp_path):
        user = {"00_charter": tmp_path / "00_charter.json"}
        toolkit = {"00_charter": tmp_path / "00_charter.schema.json"}
        diffs = compare_step_inventories(user, toolkit)
        assert len(diffs) == 1
        assert diffs[0].status == "ok"

    def test_missing_step(self, tmp_path):
        user: dict = {}
        toolkit = {"04_frs": tmp_path / "04_frs.schema.json"}
        diffs = compare_step_inventories(user, toolkit)
        assert any(d.status == "missing" for d in diffs)

    def test_unknown_user_step(self, tmp_path):
        user = {"99_custom": tmp_path / "99_custom.json"}
        toolkit: dict = {}
        diffs = compare_step_inventories(user, toolkit)
        assert any(d.status == "unknown" for d in diffs)

    def test_extension_step(self, tmp_path):
        user = {"13b_custom": tmp_path / "13b_custom.json"}
        toolkit: dict = {}
        diffs = compare_step_inventories(user, toolkit)
        assert any(d.status == "extension" for d in diffs)


# ---------------------------------------------------------------------------
# diff_step_fields
# ---------------------------------------------------------------------------

class TestDiffStepFields:
    def test_missing_required_field(self, tmp_path):
        user = tmp_path / "spec.json"
        schema = tmp_path / "spec.schema.json"
        user.write_text(json.dumps({"id": "test"}))
        schema.write_text(json.dumps({
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
            },
        }))
        diffs = diff_step_fields(user, schema)
        assert any(d.diff_type == DiffType.MISSING_REQUIRED and d.path == "name" for d in diffs)

    def test_schema_ref_outdated(self, tmp_path):
        user = tmp_path / "spec.json"
        schema = tmp_path / "spec.schema.json"
        user.write_text(json.dumps({"$schema": "old-uri", "id": "test"}))
        schema.write_text(json.dumps({
            "$id": "new-uri",
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
        }))
        diffs = diff_step_fields(user, schema)
        assert any(d.diff_type == DiffType.SCHEMA_REF_OUTDATED for d in diffs)

    def test_extra_field_when_no_additional(self, tmp_path):
        user = tmp_path / "spec.json"
        schema = tmp_path / "spec.schema.json"
        user.write_text(json.dumps({"id": "test", "extra": "foo"}))
        schema.write_text(json.dumps({
            "additionalProperties": False,
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
        }))
        diffs = diff_step_fields(user, schema)
        assert any(d.diff_type == DiffType.EXTRA_FIELD and d.path == "extra" for d in diffs)

    def test_no_diffs_when_matching(self, tmp_path):
        user = tmp_path / "spec.json"
        schema = tmp_path / "spec.schema.json"
        user.write_text(json.dumps({"$schema": "uri", "id": "test"}))
        schema.write_text(json.dumps({
            "$id": "uri",
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
        }))
        diffs = diff_step_fields(user, schema)
        assert diffs == []

    def test_invalid_user_file(self, tmp_path):
        user = tmp_path / "spec.json"
        schema = tmp_path / "spec.schema.json"
        user.write_text("NOT JSON")
        schema.write_text(json.dumps({"required": [], "properties": {}}))
        diffs = diff_step_fields(user, schema)
        assert len(diffs) == 1
        assert diffs[0].diff_type == DiffType.TYPE_MISMATCH


# ---------------------------------------------------------------------------
# detect_paradigm_shifts
# ---------------------------------------------------------------------------

class TestDetectParadigmShifts:
    def test_detects_roadmap_shift(self, tmp_path):
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (tmp_path / "roadmap.md").write_text("# Roadmap")
        shifts = detect_paradigm_shifts(spec_dir, tmp_path)
        detected = [s for s in shifts if s.detected]
        assert any("roadmap" in str(s.target_file).lower() for s in detected)

    def test_no_shifts_when_target_exists(self, tmp_path):
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (tmp_path / "roadmap.md").write_text("# Roadmap")
        (spec_dir / "14_roadmap.json").write_text("{}")
        shifts = detect_paradigm_shifts(spec_dir, tmp_path)
        detected = [s for s in shifts if s.detected]
        assert not any("roadmap" in str(s.target_file).lower() for s in detected)

    def test_no_source_no_detection(self, tmp_path):
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        shifts = detect_paradigm_shifts(spec_dir, tmp_path)
        detected = [s for s in shifts if s.detected]
        assert detected == []


# ---------------------------------------------------------------------------
# Step-16 anchor mapping (the differ "KNOWN WALL" fix)
# ---------------------------------------------------------------------------

class TestApplyStep16AnchorMapping:
    """Unit tests for the inventory transform in isolation.

    Contract source: prompts/prompt_16_impl_context.md L8 + L73 — the root
    Trinity Anchor file spec/16_impl_context.json is validated against
    vc:16-anchor; per-milestone plans (vc:16-impl-context) live under
    spec/impl_context/ and are not root steps.
    """

    def test_root_step_remapped_to_anchor_schema(self, tmp_path):
        anchor = tmp_path / "16_anchor.schema.json"
        impl_ctx = tmp_path / "16_impl_context.schema.json"
        inv = {"16_anchor": anchor, "16_impl_context": impl_ctx, "00_charter": tmp_path / "00_charter.schema.json"}
        remapped = apply_step16_anchor_mapping(inv)
        # Root step 16_impl_context now points at the ANCHOR schema file.
        assert remapped["16_impl_context"] == anchor
        # 16_anchor is no longer a root step (would otherwise be MISSING).
        assert "16_anchor" not in remapped
        # Unrelated steps untouched.
        assert remapped["00_charter"] == tmp_path / "00_charter.schema.json"

    def test_does_not_mutate_input(self, tmp_path):
        inv = {"16_anchor": tmp_path / "a", "16_impl_context": tmp_path / "b"}
        apply_step16_anchor_mapping(inv)
        assert inv == {"16_anchor": tmp_path / "a", "16_impl_context": tmp_path / "b"}

    def test_noop_when_no_anchor_schema(self, tmp_path):
        # Older toolkit without 16_anchor.schema.json — transform is a no-op.
        inv = {"00_charter": tmp_path / "c", "16_impl_context": tmp_path / "b"}
        remapped = apply_step16_anchor_mapping(inv)
        assert remapped == inv

    def test_anchor_mapping_partial_inventory_creates_impl_context(self, tmp_path):
        # Partial inventory: 16_anchor present but 16_impl_context absent.
        # The transform is NOT a no-op here — it remaps the root step
        # 16_impl_context onto the anchor schema and drops 16_anchor.
        anchor = tmp_path / "16_anchor.schema.json"
        inv = {"16_anchor": anchor, "00_charter": tmp_path / "00_charter.schema.json"}
        remapped = apply_step16_anchor_mapping(inv)
        # Root step 16_impl_context is synthesized from the anchor schema...
        assert remapped["16_impl_context"] == anchor
        # ...and 16_anchor is dropped so it is not flagged MISSING.
        assert "16_anchor" not in remapped
        # Unrelated steps are untouched.
        assert remapped["00_charter"] == tmp_path / "00_charter.schema.json"
        # Input is not mutated.
        assert inv == {"16_anchor": anchor, "00_charter": tmp_path / "00_charter.schema.json"}


def _write_good_step16_layout(spec_dir: Path) -> None:
    """Write a correct host step-16 layout: root anchor + per-milestone plan."""
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True, exist_ok=True)
    (spec_dir / "16_impl_context.json").write_text(json.dumps({
        "$schema": "vc:16-anchor",
        "id": "anchor-v1",
        "owner": "api",
        "created_at": "2026-02-08T00:00:00Z",
        "artifact_role": "anchor",
        "plan": {},
    }), encoding="utf-8")
    # Per-milestone plan — must remain invisible to the (non-recursive) root inventory.
    (impl / "ms_batch1_plan.json").write_text(json.dumps({
        "$schema": "vc:16-impl-context",
        "plan": {},
    }), encoding="utf-8")


class TestStep16DiffEndToEnd:
    """End-to-end diff_spec_directory tests against the REAL toolkit schemas.

    Both-directions guard:
      (a) a correct host layout reports zero step-16 findings;
      (b) a genuinely-wrong step-16 layout STILL flags.
    """

    def _step16(self, diff: MigrationDiff):
        return [d for d in diff.steps if d.step_id.startswith("16")]

    def test_correct_layout_zero_step16_findings(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        _write_good_step16_layout(spec)
        diff = diff_spec_directory(spec, _TOOLKIT_ROOT)
        s16 = self._step16(diff)
        # Exactly one step-16 entry, mapped to the root anchor file, status ok.
        assert [d.step_id for d in s16] == ["16_impl_context"]
        only = s16[0]
        assert only.status == "ok", (
            f"expected ok, got {only.status} with diffs "
            f"{[(f.path, f.diff_type.value) for f in (only.field_diffs or [])]}"
        )
        assert only.target_file is not None and only.target_file.name == "16_anchor.schema.json"
        # No spurious 16_anchor MISSING.
        assert not any(d.step_id == "16_anchor" for d in diff.steps)
        # Step 16 itself contributes nothing to migration pressure (other steps
        # are absent in this minimal fixture and legitimately report missing —
        # we scope the assertion to step 16, the surface under test).
        assert only.status not in ("missing", "needs_update", "needs_rename")
        assert not (only.field_diffs or [])

    def test_wrong_schema_ref_still_flags(self, tmp_path):
        """Anchor file carrying vc:16-impl-context (the per-milestone schema)
        must still flag SCHEMA_REF_OUTDATED expecting vc:16-anchor."""
        spec = tmp_path / "spec"
        spec.mkdir()
        _write_good_step16_layout(spec)
        # Corrupt the $schema on the root anchor to the wrong (per-milestone) URI.
        (spec / "16_impl_context.json").write_text(json.dumps({
            "$schema": "vc:16-impl-context",
            "id": "anchor-v1",
            "owner": "api",
            "created_at": "2026-02-08T00:00:00Z",
            "artifact_role": "anchor",
            "plan": {},
        }), encoding="utf-8")
        diff = diff_spec_directory(spec, _TOOLKIT_ROOT)
        s16 = [d for d in self._step16(diff) if d.step_id == "16_impl_context"][0]
        assert s16.status == "needs_update"
        schema_diffs = [f for f in (s16.field_diffs or []) if f.path == "$schema"]
        assert schema_diffs, "expected a $schema field diff"
        assert schema_diffs[0].expected == "vc:16-anchor"

    def test_missing_root_anchor_still_flags(self, tmp_path):
        """No root 16_impl_context.json → step missing (not silently ok)."""
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "impl_context").mkdir()
        # Only a per-milestone plan exists; no root anchor.
        (spec / "impl_context" / "ms_batch1_plan.json").write_text(json.dumps({
            "$schema": "vc:16-impl-context", "plan": {},
        }), encoding="utf-8")
        diff = diff_spec_directory(spec, _TOOLKIT_ROOT)
        s16 = [d for d in self._step16(diff) if d.step_id == "16_impl_context"][0]
        assert s16.status == "missing"
        # Still no stray 16_anchor entry.
        assert not any(d.step_id == "16_anchor" for d in diff.steps)
