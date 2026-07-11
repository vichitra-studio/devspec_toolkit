"""Unit tests for changelog_parser.validate_changelog — structural checks.

Covers:
  1. `breaking` must be a Python bool.
  2. No unknown top-level keys.
  3. `version` field must be valid semver and match the filename argument.
  4. `source_of_truth`/`render_target` must point to existing, non-empty files.

Also covers the "unreleased" sentinel path in load_version/validate_changelog
(loads unreleased.yaml instead of v{version}.yaml, and bypasses the semver
check in Check 3 when version == file's declared version == "unreleased").
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specdev_tools.core.changelog_parser import (
    get_toolkit_version,
    list_versions,
    validate_changelog,
)


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

FORMAT_YAML = """\
format_version: "1.0"
required_fields:
  - version
  - breaking
optional_fields:
  - description
  - steps
  - changes
change_types:
  - add_step
  - fix
migration_actions:
  - none
  - auto
"""


FORMAT_YAML_WITH_TARGETS = """\
format_version: "1.0"
required_fields:
  - version
  - breaking
optional_fields:
  - description
  - steps
  - changes
  - source_of_truth
  - render_target
change_types:
  - add_step
  - fix
migration_actions:
  - none
  - auto
"""


def _write_format(tmp_path: Path) -> None:
    (tmp_path / "format.yaml").write_text(FORMAT_YAML, encoding="utf-8")


def _write_format_with_targets(tmp_path: Path) -> None:
    (tmp_path / "format.yaml").write_text(FORMAT_YAML_WITH_TARGETS, encoding="utf-8")


def _write_version(tmp_path: Path, version: str, content: dict) -> None:
    (tmp_path / f"v{version}.yaml").write_text(
        yaml.dump(content, default_flow_style=False),
        encoding="utf-8",
    )


def _write_unreleased(tmp_path: Path, content: dict) -> None:
    (tmp_path / "unreleased.yaml").write_text(
        yaml.dump(content, default_flow_style=False),
        encoding="utf-8",
    )


def _valid_base(version: str = "1.0.0") -> dict:
    """A fully-valid changelog dict for the given version."""
    return {
        "version": version,
        "breaking": False,
        "description": "Test release.",
    }


# ---------------------------------------------------------------------------
# Check 1 — `breaking` must be a Python bool
# ---------------------------------------------------------------------------

class TestBreakingMustBeBool:
    def test_passing_case_bool_false(self, tmp_path):
        _write_format(tmp_path)
        _write_version(tmp_path, "1.0.0", _valid_base())
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []

    def test_passing_case_bool_true(self, tmp_path):
        _write_format(tmp_path)
        data = _valid_base()
        data["breaking"] = True
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []

    def test_failing_case_string(self, tmp_path):
        _write_format(tmp_path)
        data = _valid_base()
        data["breaking"] = "yes"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        breaking_errors = [e for e in errors if "breaking" in e.message and "boolean" in e.message]
        assert len(breaking_errors) == 1
        assert "str" in breaking_errors[0].message

    def test_failing_case_integer(self, tmp_path):
        _write_format(tmp_path)
        # YAML integers are not bools; write raw YAML to avoid yaml.dump coercion
        raw_yaml = (
            "version: '1.0.0'\n"
            "breaking: 1\n"
        )
        (tmp_path / "v1.0.0.yaml").write_text(raw_yaml, encoding="utf-8")
        errors = validate_changelog(tmp_path, "1.0.0")
        breaking_errors = [e for e in errors if "breaking" in e.message and "boolean" in e.message]
        assert len(breaking_errors) == 1
        assert "int" in breaking_errors[0].message

    def test_failing_case_breaking_absent(self, tmp_path):
        """When 'breaking' is absent, load_version raises ValueError — E520 surfaced."""
        _write_format(tmp_path)
        raw_yaml = (
            "version: '1.0.0'\n"
        )
        (tmp_path / "v1.0.0.yaml").write_text(raw_yaml, encoding="utf-8")
        errors = validate_changelog(tmp_path, "1.0.0")
        # Must surface an E520 and must NOT crash
        assert len(errors) >= 1
        assert all(e.code == "E520" for e in errors)
        # Must NOT also emit a bool-type error (field is absent, not wrong type)
        bool_errors = [e for e in errors if "breaking" in e.message and "boolean" in e.message]
        assert bool_errors == []


# ---------------------------------------------------------------------------
# Check 2 — No unknown top-level keys
# ---------------------------------------------------------------------------

class TestNoUnknownTopLevelKeys:
    def test_passing_case_all_known(self, tmp_path):
        _write_format(tmp_path)
        _write_version(tmp_path, "1.0.0", _valid_base())
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []

    def test_failing_case_single_unknown_key(self, tmp_path):
        _write_format(tmp_path)
        data = _valid_base()
        data["mystery_field"] = "surprise"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        unknown_errors = [e for e in errors if "Unknown top-level key" in e.message]
        assert len(unknown_errors) == 1
        assert "mystery_field" in unknown_errors[0].message

    def test_failing_case_multiple_unknown_keys(self, tmp_path):
        _write_format(tmp_path)
        data = _valid_base()
        data["field_a"] = "x"
        data["field_b"] = "y"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        unknown_errors = [e for e in errors if "Unknown top-level key" in e.message]
        assert len(unknown_errors) == 2
        keys_mentioned = {e.message for e in unknown_errors}
        assert any("field_a" in m for m in keys_mentioned)
        assert any("field_b" in m for m in keys_mentioned)


# ---------------------------------------------------------------------------
# Check 3 — `version` must be valid semver and match filename argument
# ---------------------------------------------------------------------------

class TestVersionField:
    def test_passing_case_valid_and_matching(self, tmp_path):
        _write_format(tmp_path)
        _write_version(tmp_path, "1.0.0", _valid_base("1.0.0"))
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []

    def test_failing_case_non_semver(self, tmp_path):
        _write_format(tmp_path)
        raw_yaml = (
            "version: not-a-version\n"
            "breaking: false\n"
        )
        (tmp_path / "vnot-a-version.yaml").write_text(raw_yaml, encoding="utf-8")
        errors = validate_changelog(tmp_path, "not-a-version")
        semver_errors = [e for e in errors if "semantic version" in e.message]
        assert len(semver_errors) == 1

    def test_failing_case_mismatch_with_filename(self, tmp_path):
        _write_format(tmp_path)
        # File is named v1.0.0.yaml but content says version 2.0.0
        data = _valid_base("2.0.0")
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        mismatch_errors = [e for e in errors if "does not match filename" in e.message]
        assert len(mismatch_errors) == 1
        assert "2.0.0" in mismatch_errors[0].message
        assert "1.0.0" in mismatch_errors[0].message

    def test_failing_case_non_semver_suppresses_mismatch(self, tmp_path):
        """A non-semver version value emits the semver error but NOT a mismatch error."""
        _write_format(tmp_path)
        raw_yaml = (
            "version: 'bad'\n"
            "breaking: false\n"
        )
        (tmp_path / "v1.0.0.yaml").write_text(raw_yaml, encoding="utf-8")
        errors = validate_changelog(tmp_path, "1.0.0")
        semver_errors = [e for e in errors if "semantic version" in e.message]
        mismatch_errors = [e for e in errors if "does not match filename" in e.message]
        assert len(semver_errors) == 1
        assert mismatch_errors == []

    def test_failing_case_version_absent(self, tmp_path):
        """When 'version' is absent, load_version raises ValueError — E520 surfaced."""
        _write_format(tmp_path)
        raw_yaml = (
            "breaking: false\n"
        )
        (tmp_path / "v1.0.0.yaml").write_text(raw_yaml, encoding="utf-8")
        errors = validate_changelog(tmp_path, "1.0.0")
        # Must surface an E520 and must NOT crash
        assert len(errors) >= 1
        assert all(e.code == "E520" for e in errors)
        # Must NOT also emit a semver or mismatch error (field is absent)
        semver_errors = [e for e in errors if "semantic version" in e.message]
        mismatch_errors = [e for e in errors if "does not match filename" in e.message]
        assert semver_errors == []
        assert mismatch_errors == []


# ---------------------------------------------------------------------------
# Unreleased sentinel — load_version()/validate_changelog() special-case
# version == "unreleased" to load unreleased.yaml, bypassing semver check
# ---------------------------------------------------------------------------

class TestUnreleasedSentinel:
    def test_passing_case_loads_unreleased_yaml(self, tmp_path):
        _write_format(tmp_path)
        data = {
            "version": "unreleased",
            "breaking": False,
            "description": "Work in progress.",
        }
        _write_unreleased(tmp_path, data)
        errors = validate_changelog(tmp_path, "unreleased")
        assert errors == []

    def test_semver_check_bypassed_for_unreleased_sentinel(self, tmp_path):
        """version == 'unreleased' must NOT trip the semver-format error."""
        _write_format(tmp_path)
        data = {
            "version": "unreleased",
            "breaking": True,
        }
        _write_unreleased(tmp_path, data)
        errors = validate_changelog(tmp_path, "unreleased")
        semver_errors = [e for e in errors if "semantic version" in e.message]
        assert semver_errors == []
        assert errors == []

    def test_failing_case_unreleased_yaml_missing(self, tmp_path):
        """No unreleased.yaml on disk: E520 surfaced, not a crash."""
        _write_format(tmp_path)
        errors = validate_changelog(tmp_path, "unreleased")
        assert len(errors) >= 1
        assert all(e.code == "E520" for e in errors)

    def test_versioned_lookup_unaffected_by_sentinel(self, tmp_path):
        """A normal semver version must still resolve to v{version}.yaml, not unreleased.yaml."""
        _write_format(tmp_path)
        _write_version(tmp_path, "1.0.0", _valid_base("1.0.0"))
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []


# ---------------------------------------------------------------------------
# Check 4 — source_of_truth/render_target must point to existing,
# non-empty files (resolved relative to changelog_dir.parent)
# ---------------------------------------------------------------------------

class TestSourceOfTruthRenderTarget:
    def test_passing_case_both_targets_exist_and_non_empty(self, tmp_path):
        _write_format_with_targets(tmp_path)
        (tmp_path / "source.yaml").write_text("source: data\n", encoding="utf-8")
        (tmp_path / "rendered.md").write_text("# Rendered\n", encoding="utf-8")
        data = _valid_base()
        data["source_of_truth"] = f"{tmp_path.name}/source.yaml"
        data["render_target"] = f"{tmp_path.name}/rendered.md"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []

    def test_failing_case_source_of_truth_missing_file(self, tmp_path):
        _write_format_with_targets(tmp_path)
        data = _valid_base()
        data["source_of_truth"] = f"{tmp_path.name}/does_not_exist.yaml"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        missing_errors = [e for e in errors if "points to a missing file" in e.message]
        assert len(missing_errors) == 1
        assert "source_of_truth" in missing_errors[0].message

    def test_failing_case_render_target_empty_file(self, tmp_path):
        _write_format_with_targets(tmp_path)
        (tmp_path / "rendered.md").write_text("", encoding="utf-8")
        data = _valid_base()
        data["render_target"] = f"{tmp_path.name}/rendered.md"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        empty_errors = [e for e in errors if "points to an empty file" in e.message]
        assert len(empty_errors) == 1
        assert "render_target" in empty_errors[0].message

    def test_passing_case_fields_absent_no_check_run(self, tmp_path):
        """When source_of_truth/render_target are absent, Check 4 is a no-op."""
        _write_format_with_targets(tmp_path)
        _write_version(tmp_path, "1.0.0", _valid_base())
        errors = validate_changelog(tmp_path, "1.0.0")
        assert errors == []

    def test_failing_case_not_in_allowed_keys_emits_unknown_key_not_check4(self, tmp_path):
        """If source_of_truth isn't declared in format.yaml's optional_fields,
        Check 4 skips it entirely and Check 2 flags it as an unknown key instead."""
        _write_format(tmp_path)  # FORMAT_YAML without source_of_truth/render_target
        data = _valid_base()
        data["source_of_truth"] = "nonexistent/path.yaml"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        unknown_errors = [e for e in errors if "Unknown top-level key" in e.message]
        missing_errors = [e for e in errors if "points to a missing file" in e.message]
        assert len(unknown_errors) == 1
        assert missing_errors == []

    def test_failing_case_source_of_truth_not_a_string(self, tmp_path):
        """A non-string value (e.g. an int) trips the 'must be a non-empty string path' branch."""
        _write_format_with_targets(tmp_path)
        data = _valid_base()
        data["source_of_truth"] = 123
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        shape_errors = [e for e in errors if "must be a non-empty string path" in e.message]
        assert len(shape_errors) == 1
        assert "source_of_truth" in shape_errors[0].message
        # Must not also fall through to the missing/non-file/empty branches
        missing_errors = [e for e in errors if "points to a missing file" in e.message]
        assert missing_errors == []

    def test_failing_case_render_target_blank_string(self, tmp_path):
        """A whitespace-only string trips the 'must be a non-empty string path' branch."""
        _write_format_with_targets(tmp_path)
        data = _valid_base()
        data["render_target"] = "   "
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        shape_errors = [e for e in errors if "must be a non-empty string path" in e.message]
        assert len(shape_errors) == 1
        assert "render_target" in shape_errors[0].message

    def test_failing_case_source_of_truth_points_to_directory(self, tmp_path):
        """A target path that exists but is a directory (not a regular file) trips the
        'points to a non-file path' branch."""
        _write_format_with_targets(tmp_path)
        (tmp_path / "a_directory").mkdir()
        data = _valid_base()
        data["source_of_truth"] = f"{tmp_path.name}/a_directory"
        _write_version(tmp_path, "1.0.0", data)
        errors = validate_changelog(tmp_path, "1.0.0")
        non_file_errors = [e for e in errors if "points to a non-file path" in e.message]
        assert len(non_file_errors) == 1
        assert "source_of_truth" in non_file_errors[0].message

    def test_check4_oserror_appends_e520(self, tmp_path, monkeypatch):
        """An OSError raised mid-check (not just a bare missing/empty/non-file
        condition) must be converted to a structured E520, not propagate."""
        _write_format_with_targets(tmp_path)
        (tmp_path / "source.yaml").write_text("source: data\n", encoding="utf-8")
        data = _valid_base()
        data["source_of_truth"] = f"{tmp_path.name}/source.yaml"
        _write_version(tmp_path, "1.0.0", data)

        real_exists = Path.exists

        def flaky_exists(self):
            if self.name == "source.yaml":
                raise OSError(13, "Permission denied")
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", flaky_exists)
        errors = validate_changelog(tmp_path, "1.0.0")
        assert any(e.code == "E520" and "source_of_truth" in e.message for e in errors)


# ---------------------------------------------------------------------------
# OSError hardening — exists()/iterdir()/stat() calls across the module must
# degrade to each function's already-documented failure mode (raise
# FileNotFoundError, or return None/[]) instead of letting a bare OSError
# (e.g. PermissionError from an unreadable parent directory) propagate.
# ---------------------------------------------------------------------------

class TestOSErrorHardening:
    def test_load_format_oserror_becomes_filenotfounderror_via_validate(self, tmp_path, monkeypatch):
        """load_format()'s internal exists() OSError must surface as a
        structured E520 through validate_changelog(), not crash."""
        _write_format(tmp_path)
        _write_version(tmp_path, "1.0.0", _valid_base())

        real_exists = Path.exists

        def flaky_exists(self):
            if self.name == "format.yaml":
                raise OSError(13, "Permission denied")
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", flaky_exists)
        errors = validate_changelog(tmp_path, "1.0.0")
        assert any(e.code == "E520" and "format" in e.message.lower() for e in errors)

    def test_load_format_raises_filenotfounderror_not_oserror(self, tmp_path, monkeypatch):
        """Direct callers of load_format() (not just validate_changelog) must
        see the documented FileNotFoundError, not a raw OSError."""
        from specdev_tools.core.changelog_parser import load_format

        real_exists = Path.exists

        def flaky_exists(self):
            if self.name == "format.yaml":
                raise OSError(13, "Permission denied")
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", flaky_exists)
        try:
            load_format(tmp_path)
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_load_version_raises_filenotfounderror_not_oserror(self, tmp_path, monkeypatch):
        """Direct callers of load_version() (e.g. get_changes_between) must
        see the documented FileNotFoundError, not a raw OSError."""
        from specdev_tools.core.changelog_parser import load_version

        real_exists = Path.exists

        def flaky_exists(self):
            if self.name == "v1.0.0.yaml":
                raise OSError(13, "Permission denied")
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", flaky_exists)
        try:
            load_version(tmp_path, "1.0.0")
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_list_versions_oserror_returns_empty_list(self, tmp_path, monkeypatch):
        """list_versions() already returns [] when the directory doesn't
        exist; an OSError mid-scan must degrade the same way, not crash."""
        (tmp_path / "v1.0.0.yaml").write_text("version: '1.0.0'\nbreaking: false\n", encoding="utf-8")

        real_iterdir = Path.iterdir

        def flaky_iterdir(self):
            if self == tmp_path:
                raise OSError(13, "Permission denied")
            return real_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", flaky_iterdir)
        assert list_versions(tmp_path) == []

    def test_get_toolkit_version_oserror_returns_none(self, tmp_path, monkeypatch):
        """get_toolkit_version() already returns None when pyproject.toml is
        missing; an OSError on the existence check must degrade the same
        way, not crash."""
        real_exists = Path.exists

        def flaky_exists(self):
            if self.name == "pyproject.toml":
                raise OSError(13, "Permission denied")
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", flaky_exists)
        assert get_toolkit_version(tmp_path) is None
