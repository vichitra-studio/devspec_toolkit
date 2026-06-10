"""Tests for specdev update — specdev_tools.update module and CLI dispatch.

Coverage:
  Unit (run_update / stamp_specdev_version / refresh_venv_installation):
    - already_current: host == toolkit → exit 0, no writes
    - no_schema_changes_no_host_version: host_version is None (new project) → diff computed, stamp only
    - no_schema_changes_restamps: versions differ, zero structural diffs → specdev_version stamped
    - schema_changes_directs_to_align: structural diffs detected → exit 1, align message
    - stamp_helper_plain_bump_no_history: is_migration=False → no migration_history entry
    - stamp_helper_migration_adds_history: is_migration=True → history entry written
    - stamp_helper_preserves_created_at: existing created_at not overwritten
    - stamp_helper_creates_file_if_absent: creates specdev_version from scratch
    - refresh_uv_absent: uv not found → (False, message with install instructions)
    - refresh_wrong_python: Python < 3.13 → (False, message about setup_devspec_env.sh)
    - refresh_uv_success: uv call succeeds → (True, message)
    - refresh_uv_failure: uv returns non-zero → (False, stderr message)
    - needs_migration_flags: _needs_migration returns correct booleans
    - dry_run_no_writes: --dry-run does not write specdev_version
    - toolkit_version_unreadable: missing pyproject.toml → exit 1, E608 message

  CLI integration (via test_update_cli.*):
    - cli_missing_spec_dir: non-existent spec_dir → exit 1
    - cli_already_current_text: already current → exit 0, human-readable output
    - cli_already_current_json: already current with --json → well-formed JSON
    - cli_needs_migration_exit1: schema diff needed → exit 1
    - cli_dry_run_no_writes: --dry-run flag propagated correctly
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers shared by unit tests
# ---------------------------------------------------------------------------

def _make_toolkit_root(tmp_path: Path, version: str) -> Path:
    """Minimal toolkit root with tools/pyproject.toml."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "pyproject.toml").write_text(
        f'[project]\nname = "specdev-tools"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    return tmp_path


def _make_spec_dir(tmp_path: Path, version: str | None) -> Path:
    """Minimal spec/ dir, optionally with specdev_version YAML."""
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    if version is not None:
        (spec / "specdev_version").write_text(
            f'toolkit_version: "{version}"\ncreated_at: "2026-01-01T00:00:00Z"\n',
            encoding="utf-8",
        )
    return spec


def _make_minimal_diff(
    *,
    steps_missing: int = 0,
    steps_needs_update: int = 0,
    steps_needs_rename: int = 0,
    paradigm_shifts: int = 0,
    steps_unknown: int = 0,
    steps_extension: int = 0,
    source_version: str | None = "0.9.0",
    target_version: str = "1.0.0",
) -> MagicMock:
    diff = MagicMock()
    diff.source_version = source_version
    diff.target_version = target_version
    diff.summary = {
        "steps_missing": steps_missing,
        "steps_needs_update": steps_needs_update,
        "steps_needs_rename": steps_needs_rename,
        "paradigm_shifts": paradigm_shifts,
        "steps_unknown": steps_unknown,
        "steps_extension": steps_extension,
    }
    return diff


# ---------------------------------------------------------------------------
# Unit: stamp_specdev_version
# ---------------------------------------------------------------------------

class TestStampSpecdevVersion:
    """Direct tests of the extracted stamp_specdev_version helper."""

    def test_creates_file_if_absent(self, tmp_path):
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = tmp_path / "spec"
        spec.mkdir()
        err = stamp_specdev_version(spec, "1.0.0", is_migration=False)
        assert err is None
        data = yaml.safe_load((spec / "specdev_version").read_text())
        assert data["toolkit_version"] == "1.0.0"

    def test_plain_bump_does_not_add_migration_history(self, tmp_path):
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = _make_spec_dir(tmp_path, "0.9.0")
        err = stamp_specdev_version(spec, "1.0.0", is_migration=False)
        assert err is None
        data = yaml.safe_load((spec / "specdev_version").read_text())
        assert data["toolkit_version"] == "1.0.0"
        assert data.get("migration_history", []) == [], (
            "Plain version bump must not append a migration_history entry"
        )

    def test_migration_adds_history_entry(self, tmp_path):
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = _make_spec_dir(tmp_path, "0.9.0")
        err = stamp_specdev_version(spec, "1.0.0", is_migration=True)
        assert err is None
        data = yaml.safe_load((spec / "specdev_version").read_text())
        history = data.get("migration_history", [])
        assert len(history) == 1, "Migration stamp must add exactly one history entry"
        assert history[0]["from"] == "0.9.0"
        assert history[0]["to"] == "1.0.0"
        assert "Migrated" in history[0]["notes"]

    def test_preserves_created_at(self, tmp_path):
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = _make_spec_dir(tmp_path, "0.9.0")
        # Override created_at to a known sentinel
        sv_file = spec / "specdev_version"
        data = yaml.safe_load(sv_file.read_text())
        data["created_at"] = "2025-01-01T00:00:00Z"
        import yaml as _yaml
        sv_file.write_text(_yaml.dump(data))

        stamp_specdev_version(spec, "1.0.0", is_migration=False)
        updated = yaml.safe_load(sv_file.read_text())
        assert updated["created_at"] == "2025-01-01T00:00:00Z", (
            "stamp_specdev_version must preserve the original created_at timestamp"
        )

    def test_returns_error_string_on_write_failure(self, tmp_path):
        from specdev_tools.generation.schema_differ import stamp_specdev_version

        # Make spec dir a file, not a directory, so the write fails
        fake_spec = tmp_path / "spec"
        fake_spec.write_text("not a dir")
        result = stamp_specdev_version(fake_spec, "1.0.0")
        assert isinstance(result, str), "Expected an error string on failure"

    def test_plain_bump_new_file_last_migration_is_null(self, tmp_path):
        """New specdev_version from a plain stamp must have last_migration: null."""
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = tmp_path / "spec"
        spec.mkdir()
        stamp_specdev_version(spec, "1.0.0", is_migration=False)
        data = yaml.safe_load((spec / "specdev_version").read_text())
        assert data["last_migration"] is None, (
            "Plain stamp on new file must write last_migration: null, "
            "matching init_project.py output"
        )

    def test_plain_bump_preserves_last_migration(self, tmp_path):
        """A plain re-stamp must not overwrite an existing last_migration value."""
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = _make_spec_dir(tmp_path, "0.9.0")
        sv_file = spec / "specdev_version"
        # Set a known last_migration sentinel
        data = yaml.safe_load(sv_file.read_text())
        data["last_migration"] = "2025-06-01T12:00:00Z"
        sv_file.write_text(yaml.dump(data))

        stamp_specdev_version(spec, "1.0.0", is_migration=False)
        updated = yaml.safe_load(sv_file.read_text())
        assert updated["last_migration"] == "2025-06-01T12:00:00Z", (
            "Plain re-stamp must preserve last_migration — only align should update it"
        )

    def test_migration_updates_last_migration(self, tmp_path):
        """An is_migration=True stamp must update last_migration to current time."""
        from specdev_tools.generation.schema_differ import stamp_specdev_version
        import yaml

        spec = _make_spec_dir(tmp_path, "0.9.0")
        sv_file = spec / "specdev_version"
        data = yaml.safe_load(sv_file.read_text())
        data["last_migration"] = "2024-01-01T00:00:00Z"
        sv_file.write_text(yaml.dump(data))

        stamp_specdev_version(spec, "1.0.0", is_migration=True)
        updated = yaml.safe_load(sv_file.read_text())
        assert updated["last_migration"] != "2024-01-01T00:00:00Z", (
            "Migration stamp must update last_migration to a new timestamp"
        )
        assert updated["last_migration"] is not None


# ---------------------------------------------------------------------------
# Unit: refresh_venv_installation
# ---------------------------------------------------------------------------

class TestRefreshVenvInstallation:

    def test_uv_absent_returns_false_with_install_instructions(self, tmp_path):
        from specdev_tools.update import refresh_venv_installation

        with patch("shutil.which", return_value=None):
            ok, msg = refresh_venv_installation(tmp_path / "tools")
        assert ok is False
        assert "uv" in msg.lower()
        assert "install" in msg.lower()

    def test_wrong_python_returns_false_with_setup_instructions(self, tmp_path):
        from specdev_tools.update import refresh_venv_installation

        # Patch sys.version_info with a plain tuple — update.py uses [:2] slicing
        # which works identically on real version_info objects and plain tuples.
        with (
            patch("shutil.which", return_value="/usr/local/bin/uv"),
            patch("sys.version_info", (3, 12, 0)),
        ):
            ok, msg = refresh_venv_installation(tmp_path / "tools")
        assert ok is False
        assert "3.12" in msg
        assert "setup_devspec_env.sh" in msg

    def test_uv_success_returns_true(self, tmp_path):
        from specdev_tools.update import refresh_venv_installation

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        with (
            patch("shutil.which", return_value="/usr/local/bin/uv"),
            patch("sys.version_info", (3, 13, 0)),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            ok, msg = refresh_venv_installation(tmp_path / "tools")
        assert ok is True
        assert "refresh" in msg.lower() or "dependencies" in msg.lower()
        # --python sys.executable must be passed so uv targets the correct venv
        # regardless of whether VIRTUAL_ENV is exported (wrapper path never sets it).
        call_args = mock_run.call_args[0][0]  # positional argv list
        assert sys.executable in call_args, (
            f"Expected --python {sys.executable!r} in uv argv, got {call_args!r}"
        )

    def test_uv_nonzero_exit_returns_false(self, tmp_path):
        from specdev_tools.update import refresh_venv_installation

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some uv error"
        with (
            patch("shutil.which", return_value="/usr/local/bin/uv"),
            patch("sys.version_info", (3, 13, 0)),
            patch("subprocess.run", return_value=mock_result),
        ):
            ok, msg = refresh_venv_installation(tmp_path / "tools")
        assert ok is False
        assert "some uv error" in msg

    def test_timeout_returns_false(self, tmp_path):
        from specdev_tools.update import refresh_venv_installation
        import subprocess as _subprocess

        with (
            patch("shutil.which", return_value="/usr/local/bin/uv"),
            patch("sys.version_info", (3, 13, 0)),
            patch("subprocess.run", side_effect=_subprocess.TimeoutExpired("uv", 120)),
        ):
            ok, msg = refresh_venv_installation(tmp_path / "tools")
        assert ok is False
        assert "timed out" in msg.lower()


# ---------------------------------------------------------------------------
# Unit: _needs_migration
# ---------------------------------------------------------------------------

class TestNeedsMigration:

    def test_empty_summary_is_false(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({}) is False

    def test_steps_missing_triggers(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"steps_missing": 1}) is True

    def test_steps_needs_update_triggers(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"steps_needs_update": 2}) is True

    def test_steps_needs_rename_triggers(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"steps_needs_rename": 1}) is True

    def test_paradigm_shifts_triggers(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"paradigm_shifts": 1}) is True

    def test_steps_unknown_does_not_trigger(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"steps_unknown": 5}) is False

    def test_steps_extension_does_not_trigger(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"steps_extension": 3}) is False

    def test_unknown_and_extension_together_do_not_trigger(self):
        from specdev_tools.update import _needs_migration
        assert _needs_migration({"steps_unknown": 2, "steps_extension": 4}) is False


# ---------------------------------------------------------------------------
# Unit: run_update
# ---------------------------------------------------------------------------

class TestRunUpdate:

    def _patch_refresh(self, ok: bool = True, msg: str = "ok"):
        return patch(
            "specdev_tools.update.refresh_venv_installation",
            return_value=(ok, msg),
        )

    def test_already_current_no_writes(self, tmp_path):
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "1.0.0")

        result = run_update(spec_dir, toolkit_root)
        assert result.exit_code == 0
        assert result.status == "already_current"
        # specdev_version must be unchanged
        import yaml
        data = yaml.safe_load((spec_dir / "specdev_version").read_text())
        assert data["toolkit_version"] == "1.0.0"

    def test_no_host_version_runs_diff_and_stamps(self, tmp_path):
        """host_version=None (new project) → run diff, stamp on no structural changes."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", None)  # no specdev_version

        diff = _make_minimal_diff(source_version=None, target_version="1.0.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 0
        assert result.status == "updated"
        import yaml
        data = yaml.safe_load((spec_dir / "specdev_version").read_text())
        assert data["toolkit_version"] == "1.0.0"

    def test_no_schema_changes_stamps_specdev_version(self, tmp_path):
        from specdev_tools.update import run_update
        import yaml

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0", target_version="1.0.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 0
        assert result.status == "updated"
        assert result.from_version == "0.9.0"
        assert result.to_version == "1.0.0"
        data = yaml.safe_load((spec_dir / "specdev_version").read_text())
        assert data["toolkit_version"] == "1.0.0"

    def test_no_schema_changes_no_migration_history(self, tmp_path):
        """Plain re-stamp must not add a migration_history entry."""
        from specdev_tools.update import run_update
        import yaml

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0", target_version="1.0.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            run_update(spec_dir, toolkit_root)

        data = yaml.safe_load((spec_dir / "specdev_version").read_text())
        assert data.get("migration_history", []) == [], (
            "Plain version bump via update must never create a migration_history entry"
        )

    def test_schema_changes_returns_exit1_with_align_message(self, tmp_path):
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_missing=2, source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 1
        assert result.status == "needs_migration"
        assert result.needs_migration is True
        assert "specdev align" in result.message
        # --repo-root must be present so the align command finds toolkit schemas
        # in submodule deployments (the primary mode described in CLAUDE.md).
        assert "--repo-root" in result.message, (
            "Remediation message must include --repo-root so align resolves schemas "
            "in submodule deployments"
        )

    def test_schema_changes_align_apply_arg_order(self, tmp_path):
        """align apply must have spec_dir before --auto (matches CLI docs convention)."""
        from specdev_tools.update import run_update
        import re

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_needs_rename=1, source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        # spec_dir should appear before --auto in the apply line
        apply_line = next(
            (l for l in result.message.splitlines() if "align apply" in l), ""
        )
        idx_spec = apply_line.find(str(spec_dir))
        idx_auto = apply_line.find("--auto")
        assert idx_spec < idx_auto, (
            f"spec_dir must precede --auto in align apply invocation; got: {apply_line!r}"
        )

    def test_paradigm_shifts_includes_align_prompts_in_message(self, tmp_path):
        """When paradigm_shifts > 0, message must include 'align prompts' guidance."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(paradigm_shifts=1, source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert "align prompts" in result.message, (
            "Paradigm shifts require AI-assisted migration; message must mention "
            "'align prompts' since 'apply --auto' cannot resolve them alone"
        )

    def test_steps_needs_rename_only_does_not_include_align_prompts(self, tmp_path):
        """Pure rename-only migration: message should NOT mention align prompts (auto-fixable)."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_needs_rename=1, source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert "align prompts" not in result.message, (
            "Rename-only migration is fully auto-fixable; message must not mention "
            "'align prompts' to avoid confusing the user"
        )

    def test_steps_needs_update_includes_align_prompts_in_message(self, tmp_path):
        """steps_needs_update may include TYPE_MISMATCH/MISSING_REQUIRED/EXTRA_FIELD diffs that
        apply_auto_fixes cannot clear (auto_fixable=False).  The message must include 'align prompts'
        so the user is not stuck in an apply-then-re-run loop with no exit."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_needs_update=1, source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 1
        assert "align prompts" in result.message, (
            "steps_needs_update may include non-auto-fixable field diffs "
            "(TYPE_MISMATCH, MISSING_REQUIRED, EXTRA_FIELD); message must mention "
            "'align prompts' so the user has a path forward beyond apply --auto"
        )

    def test_migration_finalizer_is_align_validate_not_rerun_update(self, tmp_path):
        """The migration remediation must finalize with `align validate`, NOT a re-run
        of `update`.  validate runs full post-migration validation (schema + trace
        integrity) and stamps with a migration_history entry (is_migration=True); a
        re-run of update would only re-stamp after a weaker structural-diff check
        (is_migration=False), dropping the audit trail and risking marking a
        half-migrated spec as current."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_missing=1, source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert "align validate" in result.message, (
            "Migration message must finalize with `align validate` so the version is "
            "stamped only after full post-migration validation"
        )
        # The finalizer must not be a re-run of `update` (would drop migration_history).
        assert "specdev update" not in result.message, (
            "Migration message must not direct the user to re-run `specdev update` as "
            "the finalizer — that re-stamps without a migration_history entry"
        )

    def test_only_unknown_and_extension_steps_does_not_block_stamp(self, tmp_path):
        """steps_unknown and steps_extension must never trigger migration requirement."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_unknown=3, steps_extension=2)
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 0
        assert result.status == "updated"

    def test_dry_run_does_not_write_specdev_version(self, tmp_path):
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0")
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root, dry_run=True)

        assert result.exit_code == 0
        assert result.dry_run is True
        assert "[dry-run]" in result.message
        # File must still record the old version
        import yaml
        data = yaml.safe_load((spec_dir / "specdev_version").read_text())
        assert data["toolkit_version"] == "0.9.0", (
            "dry-run must not write specdev_version"
        )

    def test_dry_run_does_not_invoke_refresh(self, tmp_path):
        """dry-run must skip the uv pip install refresh entirely."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0")
        with (
            patch("specdev_tools.update.refresh_venv_installation") as mock_refresh,
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            run_update(spec_dir, toolkit_root, dry_run=True)

        mock_refresh.assert_not_called()

    def test_unreadable_toolkit_version_returns_e608(self, tmp_path):
        from specdev_tools.update import run_update

        # No pyproject.toml → get_toolkit_version returns None
        toolkit_root = tmp_path / "tk"
        (toolkit_root / "tools").mkdir(parents=True)
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        result = run_update(spec_dir, toolkit_root)
        assert result.exit_code == 1
        assert result.status == "error"
        assert "E608" in result.message

    def test_refresh_failure_is_warning_not_error(self, tmp_path):
        """If uv is absent, update should still proceed and only warn."""
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0")
        with (
            patch(
                "specdev_tools.update.refresh_venv_installation",
                return_value=(False, "uv not found"),
            ),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 0, (
            "Refresh failure must not block a re-stamp when no schema changes exist"
        )
        assert any("uv not found" in w for w in result.warnings)

    def test_stamp_failure_propagates_error(self, tmp_path):
        """A stamp write failure in the re-stamp path surfaces as status='error'.

        Covers update.py:252-263 — when stamp_specdev_version returns a non-None
        error string, run_update must return exit_code=1, status='error', and a
        message naming the write failure (rather than reporting a false success).
        """
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0")  # no structural changes
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
            patch(
                "specdev_tools.generation.schema_differ.stamp_specdev_version",
                return_value="disk full",
            ),
        ):
            result = run_update(spec_dir, toolkit_root)

        assert result.exit_code == 1
        assert result.status == "error"
        assert "Failed to write spec/specdev_version" in result.message
        assert "disk full" in result.message

    def test_dry_run_with_needs_migration_skips_refresh(self, tmp_path):
        """dry_run=True combined with a migration-requiring diff.

        Covers update.py:188-246 under dry_run: refresh is skipped (refresh_ok
        stays None), exit_code=1 and needs_migration=True are returned, dry_run
        propagates True, and no specdev_version write occurs. Distinct from the
        re-stamp dry-run path (which returns status='would_update').
        """
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(steps_missing=1, source_version="0.9.0")
        with (
            patch("specdev_tools.update.refresh_venv_installation") as mock_refresh,
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root, dry_run=True)

        mock_refresh.assert_not_called()
        assert result.exit_code == 1
        assert result.status == "needs_migration"
        assert result.needs_migration is True
        assert result.dry_run is True
        assert result.refresh_ok is None
        # dry-run must not write
        import yaml
        data = yaml.safe_load((spec_dir / "specdev_version").read_text())
        assert data["toolkit_version"] == "0.9.0"

    def test_dry_run_restamp_reports_would_update(self, tmp_path):
        """The re-stamp dry-run path reports status='would_update', not 'updated'.

        Guards the DEVSPEC fix for finding 37715e795404: a dry-run that makes no
        write must not claim status='updated'. Distinct, observable status so
        consumers reading update_status do not mis-read a no-op as a write.
        """
        from specdev_tools.update import run_update

        toolkit_root = _make_toolkit_root(tmp_path / "tk", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "sp", "0.9.0")

        diff = _make_minimal_diff(source_version="0.9.0")  # no structural changes
        with (
            self._patch_refresh(),
            patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=diff),
        ):
            result = run_update(spec_dir, toolkit_root, dry_run=True)

        assert result.exit_code == 0
        assert result.dry_run is True
        assert result.status == "would_update"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


class _CliMixin:
    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        from specdev_tools import cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("specdev_tools.cli.check_venv", return_value=None),
            patch.object(sys, "argv", ["specdev-tools", *argv]),
        ):
            from contextlib import redirect_stdout, redirect_stderr

            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    cli.main()
                    code = 0
                except SystemExit as exc:
                    code = int(exc.code) if isinstance(exc.code, int) else 1
        return code, stdout.getvalue(), stderr.getvalue()


class TestUpdateCli(_CliMixin, unittest.TestCase):

    def test_cli_missing_spec_dir_exits_1(self):
        code, _, err = self._run_cli(
            ["update", "/nonexistent/spec/dir", "--repo-root", str(REPO_ROOT)]
        )
        self.assertEqual(code, 1)
        self.assertIn("not found", err.lower())

    def test_cli_already_current_exits_0(self, tmp_path=None):
        """already-current path: human-readable output, exit 0."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            toolkit_root = _make_toolkit_root(td_path / "tk", "1.0.0")
            spec_dir = _make_spec_dir(td_path / "sp", "1.0.0")

            code, out, _ = self._run_cli(
                ["update", str(spec_dir), "--repo-root", str(toolkit_root)]
            )
        self.assertEqual(code, 0)
        self.assertIn("Already at", out)

    def test_cli_already_current_json(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            toolkit_root = _make_toolkit_root(td_path / "tk", "1.0.0")
            spec_dir = _make_spec_dir(td_path / "sp", "1.0.0")

            code, out, _ = self._run_cli(
                ["update", str(spec_dir), "--repo-root", str(toolkit_root), "--json"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["command"], "update")
        self.assertIn("update_status", payload)
        self.assertEqual(payload["update_status"], "already_current")

    def test_cli_needs_migration_exits_1(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            toolkit_root = _make_toolkit_root(td_path / "tk", "1.0.0")
            spec_dir = _make_spec_dir(td_path / "sp", "0.9.0")

            diff = _make_minimal_diff(steps_missing=1, source_version="0.9.0")
            with (
                patch(
                    "specdev_tools.update.refresh_venv_installation",
                    return_value=(True, "ok"),
                ),
                patch(
                    "specdev_tools.generation.schema_differ.diff_spec_directory",
                    return_value=diff,
                ),
            ):
                code, out, _ = self._run_cli(
                    ["update", str(spec_dir), "--repo-root", str(toolkit_root)]
                )
        self.assertEqual(code, 1)
        self.assertIn("specdev align", out)

    def test_cli_dry_run_no_file_write(self):
        import tempfile
        import yaml

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            toolkit_root = _make_toolkit_root(td_path / "tk", "1.0.0")
            spec_dir = _make_spec_dir(td_path / "sp", "0.9.0")

            diff = _make_minimal_diff(source_version="0.9.0")
            with (
                patch(
                    "specdev_tools.update.refresh_venv_installation",
                    return_value=(True, "ok"),
                ),
                patch(
                    "specdev_tools.generation.schema_differ.diff_spec_directory",
                    return_value=diff,
                ),
            ):
                code, out, _ = self._run_cli(
                    [
                        "update",
                        str(spec_dir),
                        "--repo-root",
                        str(toolkit_root),
                        "--dry-run",
                    ]
                )

            # assertions must be inside the tempdir block
            self.assertEqual(code, 0)
            self.assertIn("[dry-run]", out)
            data = yaml.safe_load((spec_dir / "specdev_version").read_text())
            self.assertEqual(data["toolkit_version"], "0.9.0")

    def test_cli_json_needs_migration_is_fail(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            toolkit_root = _make_toolkit_root(td_path / "tk", "1.0.0")
            spec_dir = _make_spec_dir(td_path / "sp", "0.9.0")

            diff = _make_minimal_diff(steps_needs_update=1, source_version="0.9.0")
            with (
                patch(
                    "specdev_tools.update.refresh_venv_installation",
                    return_value=(True, "ok"),
                ),
                patch(
                    "specdev_tools.generation.schema_differ.diff_spec_directory",
                    return_value=diff,
                ),
            ):
                code, out, _ = self._run_cli(
                    [
                        "update",
                        str(spec_dir),
                        "--repo-root",
                        str(toolkit_root),
                        "--json",
                    ]
                )

        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "FAIL")
        self.assertGreater(payload["error_count"], 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
