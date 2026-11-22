"""E884: every ``auto`` migration entry of kind ``mechanical`` names a script the toolkit defines."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from specdev_tools.core.changelog_parser import list_versions, validate_changelog
from specdev_tools.migration.registry import discover_scripts

REAL_CHANGELOG = Path(__file__).resolve().parents[3] / "changelog"


def _changelog_dir(tmp_path: Path, version: str, migration: dict) -> Path:
    shutil.copy(REAL_CHANGELOG / "format.yaml", tmp_path / "format.yaml")
    content = {
        "version": version,
        "breaking": True,
        "changes": [{"type": "fix", "description": "x", "migration": migration}],
    }
    (tmp_path / f"v{version}.yaml").write_text(yaml.dump(content), encoding="utf-8")
    return tmp_path


def _codes(errors) -> list[str]:
    return [error.code for error in errors]


def test_every_auto_mechanical_entry_of_every_changelog_names_an_existing_script():
    known = {script.id for script in discover_scripts()}
    findings = []
    for version in [*list_versions(REAL_CHANGELOG), "unreleased"]:
        findings += [e.message for e in validate_changelog(REAL_CHANGELOG, version, known)]
    assert findings == []


def test_a_kind_none_auto_entry_is_exempt(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "auto", "kind": "none"})
    assert validate_changelog(folder, "1.2.0", set()) == []


def test_e884_for_an_auto_mechanical_entry_with_no_script(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "auto", "kind": "mechanical"})
    errors = validate_changelog(folder, "1.2.0", set())
    assert _codes(errors) == ["E884"]
    assert "names no script" in errors[0].message


def test_e884_for_a_script_id_that_is_not_in_the_registry(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "auto", "kind": "mechanical", "script": "p2_nowhere"})
    errors = validate_changelog(folder, "1.2.0", {"p2_id_mint"})
    assert _codes(errors) == ["E884"]
    assert "'p2_nowhere'" in errors[0].message


def test_the_existence_check_is_skipped_when_no_known_scripts_are_given(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "auto", "kind": "mechanical", "script": "p2_nowhere"})
    assert validate_changelog(folder, "1.2.0") == []


def test_a_missing_script_key_is_found_even_without_known_scripts(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "auto", "kind": "mechanical"})
    assert _codes(validate_changelog(folder, "1.2.0")) == ["E884"]


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0", "1.1.1"])
def test_versions_up_to_1_1_1_are_exempt(tmp_path, version):
    folder = _changelog_dir(tmp_path, version, {"action": "auto", "kind": "mechanical"})
    assert validate_changelog(folder, version, set()) == []


def test_an_entry_that_is_not_auto_is_not_checked(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "ai_assisted", "kind": "mechanical"})
    assert validate_changelog(folder, "1.2.0", set()) == []


def test_an_unknown_kind_is_a_format_error(tmp_path):
    folder = _changelog_dir(tmp_path, "1.2.0", {"action": "auto", "kind": "magic"})
    assert _codes(validate_changelog(folder, "1.2.0", set())) == ["E520"]
