"""Tests for the migration runner module."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specdev_tools.generation.schema_differ import MigrationAction
from specdev_tools.migration.planner import MigrationPlan, MigrationStep
from specdev_tools.migration.runner import (
    MigrationTransaction,
    TransactionBoundary,
    execute_plan,
    group_transaction_boundaries,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(steps=None, source="0.2.2", target="0.3.0"):
    return MigrationPlan(
        steps=steps or [],
        source_version=source,
        target_version=target,
    )


def _make_step(step_id, action=MigrationAction.AUTO, template=None):
    return MigrationStep(
        step_id=step_id,
        action=action,
        template=template,
        context={"path": f"field_in_{step_id}"},
    )


def _mock_validation_result(valid=True, errors=None):
    """Create a mock that behaves like ValidationResult.

    The runner accesses `.valid` and `.errors`, so we mock those.
    """
    result = MagicMock()
    result.valid = valid
    result.errors = errors or []
    return result


# ---------------------------------------------------------------------------
# Module-level patch targets
# ---------------------------------------------------------------------------

_RUNNER_MOD = "specdev_tools.migration.runner"
_DIFFER_MOD = "specdev_tools.generation.schema_differ"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecutePlanCreatesBackup:
    """Executing a plan creates a backup directory."""

    @patch(f"{_RUNNER_MOD}.validate_post_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.validate_pre_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.log_operation")
    @patch(f"{_RUNNER_MOD}.apply_auto_fixes")
    def test_execute_plan_creates_backup(
        self, mock_auto, mock_log, mock_pre, mock_post
    ):
        mock_auto.return_value = MagicMock(fixed_count=1, skipped_count=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir()
            # Create a dummy spec file so backup has something to copy
            (spec_dir / "04_frs.json").write_text("{}", encoding="utf-8")

            toolkit_root = Path(tmpdir) / "toolkit"
            toolkit_root.mkdir()

            plan = _make_plan(steps=[_make_step("04_frs")])
            tx = execute_plan(plan, spec_dir, toolkit_root, dry_run=False)

            assert tx.backup_path is not None
            assert tx.backup_path.exists()
            assert tx.backup_path.is_dir()
            assert not tx.rolled_back


class TestExecutePlanRollbackOnFailure:
    """When a step fails, backup is restored and rolled_back is True."""

    @patch(f"{_RUNNER_MOD}.validate_pre_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.log_operation")
    @patch(f"{_RUNNER_MOD}.apply_auto_fixes")
    def test_execute_plan_rollback_on_failure(
        self, mock_auto, mock_log, mock_pre
    ):
        # Make apply_auto_fixes raise an exception to trigger failure
        mock_auto.side_effect = RuntimeError("auto-fix exploded")

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir()
            original_content = '{"original": true}'
            (spec_dir / "04_frs.json").write_text(original_content, encoding="utf-8")

            toolkit_root = Path(tmpdir) / "toolkit"
            toolkit_root.mkdir()

            plan = _make_plan(steps=[_make_step("04_frs")])
            tx = execute_plan(plan, spec_dir, toolkit_root, dry_run=False)

            assert tx.rolled_back is True
            assert len(tx.operations_failed) > 0

            # Verify the original file was restored
            restored = (spec_dir / "04_frs.json").read_text(encoding="utf-8")
            assert restored == original_content


class TestDryRunNoSideEffects:
    """dry_run=True doesn't modify any files."""

    @patch(f"{_RUNNER_MOD}.validate_pre_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.log_operation")
    def test_dry_run_no_side_effects(self, mock_log, mock_pre):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir()
            original_content = '{"dry": "run"}'
            spec_file = spec_dir / "04_frs.json"
            spec_file.write_text(original_content, encoding="utf-8")

            toolkit_root = Path(tmpdir) / "toolkit"
            toolkit_root.mkdir()

            plan = _make_plan(steps=[
                _make_step("04_frs"),
                _make_step("00_charter", action=MigrationAction.AI_ASSISTED),
            ])
            tx = execute_plan(plan, spec_dir, toolkit_root, dry_run=True)

            assert tx.dry_run is True
            assert tx.backup_path is None
            # No backup directory should have been created
            assert not (spec_dir / "migration_backups").exists()
            # File content unchanged
            assert spec_file.read_text(encoding="utf-8") == original_content
            # All steps reported as completed (dry-run mode)
            assert len(tx.operations_completed) == 2
            for op in tx.operations_completed:
                assert "[DRY RUN]" in op


class TestMultiFileTransactionAtomicity:
    """group_transaction_boundaries groups steps by step_id."""

    def test_groups_by_step_id(self):
        steps = [
            _make_step("04_frs"),
            _make_step("04_frs", action=MigrationAction.AI_ASSISTED),
            _make_step("00_charter"),
            _make_step("09_impl_plan"),
            _make_step("09_impl_plan"),
        ]
        plan = _make_plan(steps=steps)
        boundaries = group_transaction_boundaries(plan)

        assert len(boundaries) == 3

        # First boundary: 04_frs (2 steps)
        assert len(boundaries[0].steps) == 2
        assert all(s.step_id == "04_frs" for s in boundaries[0].steps)

        # Second boundary: 00_charter (1 step)
        assert len(boundaries[1].steps) == 1
        assert boundaries[1].steps[0].step_id == "00_charter"

        # Third boundary: 09_impl_plan (2 steps)
        assert len(boundaries[2].steps) == 2
        assert all(s.step_id == "09_impl_plan" for s in boundaries[2].steps)

    def test_preserves_insertion_order(self):
        """Boundaries appear in the order their step_id was first seen."""
        steps = [
            _make_step("09_impl_plan"),
            _make_step("04_frs"),
            _make_step("09_impl_plan"),
        ]
        plan = _make_plan(steps=steps)
        boundaries = group_transaction_boundaries(plan)

        assert boundaries[0].steps[0].step_id == "09_impl_plan"
        assert boundaries[1].steps[0].step_id == "04_frs"

    def test_boundary_descriptions_include_counts(self):
        steps = [
            _make_step("04_frs"),
            _make_step("04_frs", action=MigrationAction.AI_ASSISTED),
        ]
        plan = _make_plan(steps=steps)
        boundaries = group_transaction_boundaries(plan)

        assert "2 operation(s)" in boundaries[0].description
        assert "04_frs" in boundaries[0].description

    def test_empty_plan_produces_no_boundaries(self):
        plan = _make_plan(steps=[])
        boundaries = group_transaction_boundaries(plan)
        assert boundaries == []


# ---------------------------------------------------------------------------
# Transaction-boundary integration tests
# ---------------------------------------------------------------------------

class TestExecutePlanUsesTransactionBoundaries:
    """execute_plan groups steps via group_transaction_boundaries."""

    @patch(f"{_RUNNER_MOD}.validate_post_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.validate_pre_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.log_operation")
    @patch(f"{_RUNNER_MOD}.apply_auto_fixes")
    def test_all_steps_processed_via_boundaries(
        self, mock_auto, mock_log, mock_pre, mock_post
    ):
        mock_auto.return_value = MagicMock(fixed_count=1, skipped_count=0)
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir()
            (spec_dir / "04_frs.json").write_text("{}", encoding="utf-8")
            (spec_dir / "00_charter.json").write_text("{}", encoding="utf-8")
            toolkit_root = Path(tmpdir) / "toolkit"
            toolkit_root.mkdir()

            plan = _make_plan(steps=[
                _make_step("04_frs"),
                _make_step("04_frs"),
                _make_step("00_charter"),
            ])
            tx = execute_plan(plan, spec_dir, toolkit_root, dry_run=False)

            assert not tx.rolled_back
            assert len(tx.operations_completed) == 3
            assert mock_auto.call_count == 3


class TestBoundaryRollbackOnFailure:
    """Per-boundary rollback then full rollback on step failure."""

    @patch(f"{_RUNNER_MOD}.validate_pre_migration", return_value=_mock_validation_result())
    @patch(f"{_RUNNER_MOD}.log_operation")
    @patch(f"{_RUNNER_MOD}.apply_auto_fixes")
    def test_boundary_rollback(self, mock_auto, mock_log, mock_pre):
        call_count = {"n": 0}

        def auto_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise RuntimeError("step failed")
            return MagicMock(fixed_count=1, skipped_count=0)

        mock_auto.side_effect = auto_side_effect

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir()
            (spec_dir / "04_frs.json").write_text('{"original": true}', encoding="utf-8")
            (spec_dir / "09_impl_plan.json").write_text('{"original": true}', encoding="utf-8")
            toolkit_root = Path(tmpdir) / "toolkit"
            toolkit_root.mkdir()

            plan = _make_plan(steps=[
                _make_step("04_frs"),
                _make_step("09_impl_plan"),
            ])
            tx = execute_plan(plan, spec_dir, toolkit_root, dry_run=False)

            assert tx.rolled_back is True
            assert any(
                "rolled back" in msg.lower() or "Rolled back" in msg
                for msg in tx.operations_failed
            )


class TestMigrationDiffDictReconstruction:
    """execute_single_step reconstructs MigrationDiff from dict context."""

    @patch(f"{_RUNNER_MOD}.log_operation")
    @patch(f"{_RUNNER_MOD}.apply_auto_fixes")
    def test_dict_context_becomes_migration_diff(self, mock_auto, mock_log):
        from specdev_tools.generation.schema_differ import MigrationDiff

        captured = {}

        def capture_auto(**kwargs):
            captured["diff"] = kwargs.get("diff")
            return MagicMock(fixed_count=0, skipped_count=0)

        mock_auto.side_effect = capture_auto

        step = MigrationStep(
            step_id="04_frs",
            action=MigrationAction.AUTO,
            context={"migration_diff": {"source_version": "0.2.0", "target_version": "0.3.0"}},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir()
            toolkit_root = Path(tmpdir) / "toolkit"
            toolkit_root.mkdir()

            from specdev_tools.migration.runner import execute_single_step
            success, msg = execute_single_step(step, spec_dir, toolkit_root)

            assert success
            diff = captured["diff"]
            assert isinstance(diff, MigrationDiff)
            assert diff.source_version == "0.2.0"
            assert diff.target_version == "0.3.0"
