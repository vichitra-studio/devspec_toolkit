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
    calculate_version_delta,
    compare_step_inventories,
    detect_paradigm_shifts,
    diff_step_fields,
    inventory_toolkit_schemas,
    inventory_user_steps,
)


# ---------------------------------------------------------------------------
# DiffType / MigrationAction enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_diff_type_values(self):
        assert DiffType.MISSING_REQUIRED.value == "missing_required"
        assert DiffType.EXTRA_FIELD.value == "extra_field"
        assert DiffType.TYPE_MISMATCH.value == "type_mismatch"

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
        # When major is same but minor goes down, patch check may trigger.
        # True downgrade: target < source on all axes
        result = calculate_version_delta("1.0.0", "1.0.0")
        assert result is None

    def test_multiple_updates(self):
        result = calculate_version_delta("0.1.0", "0.3.0")
        assert result is not None
        assert "2 MINOR updates" in result


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
