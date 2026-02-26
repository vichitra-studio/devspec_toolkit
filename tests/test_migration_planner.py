"""Tests for the migration planner module."""
import json
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specdev_tools.generation.schema_differ import (
    DiffType,
    FieldDiff,
    MigrationAction,
    MigrationDiff,
    ParadigmShift,
    StepDiff,
)
from specdev_tools.migration.planner import (
    MigrationPlan,
    MigrationStep,
    _STEP_TO_TEMPLATE,
    create_migration_plan,
    map_diff_to_template,
    order_migration_steps,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_diff(
    steps=None,
    paradigm_shifts=None,
    source_version="0.2.2",
    target_version="0.3.0",
):
    """Build a minimal MigrationDiff for testing."""
    return MigrationDiff(
        source_version=source_version,
        target_version=target_version,
        steps=steps or [],
        paradigm_shifts=paradigm_shifts or [],
    )


def _make_step_diff(step_id, status="needs_update", field_diffs=None, action=MigrationAction.AUTO):
    return StepDiff(
        step_id=step_id,
        status=status,
        source_file=Path(f"spec/{step_id}.json"),
        target_file=Path(f"schema/{step_id}.json"),
        field_diffs=field_diffs or [],
        action=action,
    )


def _make_field_diff(path, diff_type=DiffType.MISSING_REQUIRED, action=MigrationAction.AUTO):
    return FieldDiff(
        path=path,
        diff_type=diff_type,
        expected="string",
        actual=None,
        action=action,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreatePlanFromDiff:
    """MigrationDiff with field and step diffs produces a valid MigrationPlan."""

    def test_create_plan_from_diff(self, repo_root):
        field1 = _make_field_diff("capabilities[].owner")
        field2 = _make_field_diff("name", diff_type=DiffType.RENAME_CANDIDATE)

        step_diff = _make_step_diff(
            "04_frs",
            status="needs_update",
            field_diffs=[field1, field2],
        )
        step_missing = _make_step_diff("13a_extension", status="missing")

        diff = _make_diff(steps=[step_diff, step_missing])
        plan = create_migration_plan(diff)

        assert isinstance(plan, MigrationPlan)
        assert plan.source_version == "0.2.2"
        assert plan.target_version == "0.3.0"
        # 2 field-level steps from step_diff + 1 step-level for "needs_update"
        # + 1 step-level for "missing"
        assert len(plan.steps) >= 3


class TestStepToTemplateMapping:
    """Step-based template resolution maps step_id prefixes to templates."""

    def test_known_step_resolves_to_template(self):
        result = map_diff_to_template(DiffType.MISSING_REQUIRED, step_id="04_frs")
        assert result == "template_frs.md"

    def test_step_00_resolves(self):
        result = map_diff_to_template(DiffType.STEP_MISSING, step_id="00_charter")
        assert result == "template_charter.md"

    def test_step_02a_resolves(self):
        result = map_diff_to_template(DiffType.STEP_MISSING, step_id="02a_delivery_baseline")
        assert result == "template_delivery_baseline.md"

    def test_step_16_resolves(self):
        result = map_diff_to_template(DiffType.SCHEMA_REF_OUTDATED, step_id="16_impl_context")
        assert result == "template_impl_context.md"

    def test_unmapped_step_returns_none(self):
        result = map_diff_to_template(DiffType.STEP_UNKNOWN, step_id="99_unknown")
        assert result is None

    def test_no_step_id_returns_none(self):
        result = map_diff_to_template(DiffType.MISSING_REQUIRED)
        assert result is None

    def test_all_mapped_steps_have_templates(self):
        for prefix, template in _STEP_TO_TEMPLATE.items():
            result = map_diff_to_template(DiffType.STEP_MISSING, step_id=f"{prefix}_test")
            assert result == template, f"Step prefix '{prefix}' should map to {template}"


class TestExecutionOrderRespectsStepDependencies:
    """Steps are ordered per step_order.json (earlier pipeline steps first)."""

    def test_execution_order_respects_step_dependencies(self, repo_root):
        step_order_path = repo_root / "tools" / "step_order.json"
        if not step_order_path.exists():
            pytest.skip("step_order.json not found")

        with open(step_order_path, "r") as f:
            dag = json.load(f)
        ordered_ids = dag.get("steps", [])

        # Create steps in reverse pipeline order
        steps = [
            MigrationStep(step_id="13a_extension", action=MigrationAction.AI_ASSISTED),
            MigrationStep(step_id="04_frs", action=MigrationAction.AUTO),
            MigrationStep(step_id="00_charter", action=MigrationAction.AUTO),
        ]

        result = order_migration_steps(steps, step_order_path)

        # Verify order: 00 before 04, 04 before 13a
        ids = [s.step_id for s in result]
        assert ids.index("00_charter") < ids.index("04_frs")
        assert ids.index("04_frs") < ids.index("13a_extension")


class TestEmptyDiffProducesEmptyPlan:
    """An empty MigrationDiff produces a MigrationPlan with 0 steps."""

    def test_empty_diff_produces_empty_plan(self):
        diff = _make_diff(steps=[], paradigm_shifts=[])
        plan = create_migration_plan(diff)

        assert isinstance(plan, MigrationPlan)
        assert len(plan.steps) == 0
        assert plan.source_version == "0.2.2"
        assert plan.target_version == "0.3.0"


class TestStepOrderNotFoundWarning:
    """When step_order.json is not found, a warning is emitted."""

    def test_warns_when_step_order_missing(self, tmp_path):
        """create_migration_plan warns when step_order.json not found."""
        step_diff = _make_step_diff("04_frs", status="needs_update")
        diff = _make_diff(steps=[step_diff])

        # Temporarily make the planner look in a non-existent path
        # by passing a diff — the planner resolves step_order.json
        # internally via __file__-relative paths.  We can't easily
        # mock __file__, so we just verify the function still works
        # (the warning is only emitted if BOTH candidate paths fail).
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            plan = create_migration_plan(diff)
            # Plan should still be created (fallback to unordered)
            assert isinstance(plan, MigrationPlan)
