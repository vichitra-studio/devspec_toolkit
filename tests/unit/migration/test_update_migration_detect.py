"""``specdev update`` made migration-aware (WI-M10-12 item 3): a spec that needs a data migration is never silently re-stamped.

Each test builds a temp toolkit root (``make_toolkit`` of ``_support``) that says what the case needs (a version, the changelog
entries it lists).  The structural differ and the venv refresh are patched, as in
``tests/unit/test_update_command.py``: the host has no schema to diff and a real refresh would re-point the live venv.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from specdev_tools.migration import registry
from specdev_tools.update import run_update

from ._support import make_toolkit

CLEAN_DIFF = SimpleNamespace(summary={"steps_missing": 0, "steps_needs_update": 0, "steps_needs_rename": 0, "paradigm_shifts": 0})
SCRIPTED_ENTRY = (
    "version: {version}\nbreaking: true\nchanges:\n"
    "  - type: add_constraint\n    description: a shape that host data must be moved to\n"
    "    migration:\n      action: auto\n      kind: mechanical\n      script: {script}\n"
)
AI_ENTRY = (
    "version: {version}\nbreaking: false\nchanges:\n"
    "  - type: add_constraint\n    description: a rule an agent applies\n"
    "    migration:\n      action: ai_assisted\n      note: ask the agent\n"
)


def make_spec(tmp_path: Path, version: str | None, **extra: str) -> Path:
    spec = tmp_path / "host" / "spec"
    spec.mkdir(parents=True)
    if version is not None:
        data = {"toolkit_version": version, "created_at": "2026-01-01T00:00:00Z", "last_migration": None, "migration_history": [], **extra}
        (spec / "specdev_version").write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    (spec / "00_charter.json").write_text("{}\n", encoding="utf-8")
    return spec


def digest(spec: Path) -> dict[str, str]:
    return {str(p.relative_to(spec)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(spec.rglob("*")) if p.is_file()}


def update(spec: Path, toolkit: Path, scripts=None, **flags):
    """``run_update`` with the differ and the refresh patched and, when *scripts* is given, that script registry."""
    patches = [
        patch("specdev_tools.update.refresh_venv_installation", return_value=(True, "ok")),
        patch("specdev_tools.generation.schema_differ.diff_spec_directory", return_value=CLEAN_DIFF),
    ]
    if scripts is not None:
        patches.append(patch.object(registry, "discover_scripts", return_value=list(scripts)))
    for each in patches:
        each.start()
    try:
        return run_update(spec, toolkit, no_install=True, **flags)
    finally:
        for each in patches:
            each.stop()


def stamp_of(spec: Path) -> dict:
    return yaml.safe_load((spec / "specdev_version").read_text(encoding="utf-8"))


def test_a_1_1_1_host_with_the_1_2_0_changelog_is_needs_migration_and_writes_nothing(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    (toolkit / "changelog" / "v1.2.0.yaml").write_text(SCRIPTED_ENTRY.format(version="1.2.0", script="p2_ids"), encoding="utf-8")
    spec = make_spec(tmp_path, "1.1.1")
    before = digest(spec)
    result = update(spec, toolkit, scripts=[])  # the changelog alone decides: no script module is registered
    assert (result.exit_code, result.status, result.needs_migration) == (1, "needs_migration", True)
    assert "v1.1.1 -> v1.2.0" in result.message and "migrate host data" in result.message
    assert "specdev align apply" in result.message and "--auto" in result.message
    assert digest(spec) == before and stamp_of(spec)["toolkit_version"] == "1.1.1"


def test_the_registry_alone_makes_a_1_1_1_host_needs_migration_with_the_real_scripts(tmp_path):
    """The N1 run of the preflight: a 1.1.1 host against a 1.2.0 toolkit was re-stamped, exit 0.  Now the registry's chain blocks it."""
    toolkit = make_toolkit(tmp_path, "1.2.0")
    spec = make_spec(tmp_path, "1.1.1")
    before = digest(spec)
    result = update(spec, toolkit)
    assert (result.exit_code, result.status) == (1, "needs_migration")
    assert "migration script(s) are registered for v1.1.1 -> v1.2.0" in result.message and "p1_capture" in result.message
    assert digest(spec) == before


def test_an_unlisted_host_version_is_needs_migration(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    spec = make_spec(tmp_path, "1.1.5")
    result = update(spec, toolkit, scripts=[])
    assert (result.exit_code, result.status) == (1, "needs_migration")
    assert "v1.1.5 is not a release the changelog lists" in result.message
    assert stamp_of(spec)["toolkit_version"] == "1.1.5"


def test_a_host_with_no_stamp_keeps_todays_restamp_behaviour(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    (toolkit / "changelog" / "v1.2.0.yaml").write_text(SCRIPTED_ENTRY.format(version="1.2.0", script="p2_ids"), encoding="utf-8")
    spec = make_spec(tmp_path, None)
    result = update(spec, toolkit)
    assert (result.exit_code, result.status) == (0, "updated")
    assert stamp_of(spec)["toolkit_version"] == "1.2.0"


def test_a_1_1_0_host_updated_to_1_1_1_is_restamped(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.1.1", listed=("1.0.0", "1.1.0", "1.1.1"))
    (toolkit / "changelog" / "v1.1.1.yaml").write_text(AI_ENTRY.format(version="1.1.1"), encoding="utf-8")
    spec = make_spec(tmp_path, "1.1.0")
    result = update(spec, toolkit)  # the real registry: its only script before 1.2.0 belongs to 1.1.0
    assert (result.exit_code, result.status) == (0, "updated")
    stamp = stamp_of(spec)
    assert stamp["toolkit_version"] == "1.1.1" and stamp["migration_history"] == []


def test_a_1_0_x_host_updated_to_1_1_1_needs_the_status_ref_script(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.1.1", listed=("1.0.0", "1.1.0", "1.1.1"))
    spec = make_spec(tmp_path, "1.0.0")
    result = update(spec, toolkit)
    assert (result.exit_code, result.status) == (1, "needs_migration") and "p3_strip_status_ref" in result.message


def test_a_1_2_0_host_updated_to_a_script_free_later_version_is_restamped(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.1", listed=("1.0.0", "1.1.0", "1.1.1", "1.2.0", "1.2.1"))
    (toolkit / "changelog" / "v1.2.0.yaml").write_text(SCRIPTED_ENTRY.format(version="1.2.0", script="p2_ids"), encoding="utf-8")
    (toolkit / "changelog" / "v1.2.1.yaml").write_text(AI_ENTRY.format(version="1.2.1"), encoding="utf-8")
    spec = make_spec(tmp_path, "1.2.0")
    result = update(spec, toolkit)  # the real registry: its scripts belong to 1.1.0 and 1.2.0, none above the host's version
    assert (result.exit_code, result.status) == (0, "updated")
    stamp = stamp_of(spec)
    assert stamp["toolkit_version"] == "1.2.1" and stamp["migration_history"] == []


def test_the_remediation_names_update_no_install_dry_run_align_apply_commit_no_verify_update_adopt_the_pass_align_validate(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    spec = make_spec(tmp_path, "1.1.1")
    result = update(spec, toolkit)
    commands = [line.strip() for line in result.message.splitlines() if line.strip()[:2] in {f"{n}." for n in range(1, 10)}]
    texts = [command.split(". ", 1)[1] for command in commands]
    assert len(texts) == 7
    assert "specdev update" in texts[0] and "--no-install --dry-run" in texts[0]
    assert "align apply" in texts[1] and "--auto --dry-run" in texts[1]
    assert "align apply" in texts[2] and "--dry-run" not in texts[2]
    assert "git add" in texts[3] and "git commit --no-verify" in texts[3]
    assert "specdev update" in texts[4] and "--adopt" in texts[4]
    assert "align triage" in texts[5]
    assert "align validate" in texts[6]
    for text in texts:
        assert "--repo-root" in text or text.startswith("git ")
    assert "spec/specdev_version is left as it is" in result.message


def test_a_changelog_entry_that_is_ai_assisted_does_not_block_a_restamp(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    (toolkit / "changelog" / "v1.2.0.yaml").write_text(AI_ENTRY.format(version="1.2.0"), encoding="utf-8")
    spec = make_spec(tmp_path, "1.1.1")
    result = update(spec, toolkit, scripts=[])
    assert (result.exit_code, result.status) == (0, "updated")


@pytest.mark.parametrize("dry_run", [False, True])
def test_dry_run_reports_needs_migration_and_writes_nothing(tmp_path, dry_run):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    spec = make_spec(tmp_path, "1.1.1")
    before = digest(spec)
    result = update(spec, toolkit, dry_run=dry_run)
    assert result.status == "needs_migration" and result.exit_code == 1
    assert digest(spec) == before


def test_a_host_in_migration_status_in_progress_is_told_to_run_align_validate(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    spec = make_spec(tmp_path, "1.2.0", migration_status="in_progress")
    before = digest(spec)
    result = update(spec, toolkit)
    assert (result.exit_code, result.status) == (0, "migration_in_progress")
    assert "align validate" in result.message and "align triage" in result.message and "migration_status: in_progress" in result.message
    assert digest(spec) == before


def test_a_host_in_progress_below_the_toolkit_version_is_not_restamped_either(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.1", listed=("1.0.0", "1.1.0", "1.1.1", "1.2.0", "1.2.1"))
    spec = make_spec(tmp_path, "1.2.0", migration_status="in_progress")
    result = update(spec, toolkit)
    assert (result.exit_code, result.status) == (1, "migration_in_progress")
    assert "finish the migration first" in result.message and "align validate" in result.message
    assert stamp_of(spec)["toolkit_version"] == "1.2.0"
