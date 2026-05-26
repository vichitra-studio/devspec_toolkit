"""Unit tests for changelog_parser.validate_changelog — structural checks.

Covers:
  1. `breaking` must be a Python bool.
  2. No unknown top-level keys.
  3. `version` field must be valid semver and match the filename argument.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specdev_tools.core.changelog_parser import validate_changelog


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


def _write_format(tmp_path: Path) -> None:
    (tmp_path / "format.yaml").write_text(FORMAT_YAML, encoding="utf-8")


def _write_version(tmp_path: Path, version: str, content: dict) -> None:
    (tmp_path / f"v{version}.yaml").write_text(
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
