"""Integration tests for tier0_checks.py individual check functions.

Tests are pure function-level (no subprocess through main(), which does not
accept an argv parameter and would require real git state for T0-11 and T0-07).

Coverage:
  - Zero-findings paths for deterministic check functions with controlled inputs.
  - T0-10 specdev-unavailable path: when 'command -v specdev' returns non-zero,
    check_t10_generated_artifacts_clean() emits exactly one P2 gap finding with
    catalog_tag='D9' and a message starting with 'T0-10 skipped'.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load tier0_checks as a module from its script path
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]  # tests/integration/pr_audit → toolkit root
    / ".claude" / "skills" / "devspec_pr_audit" / "scripts" / "tier0_checks.py"
)


def _load_tier0():
    """Import tier0_checks from its on-disk script path."""
    spec = importlib.util.spec_from_file_location("tier0_checks", _SCRIPT_PATH)
    assert spec is not None, f"Cannot load spec from {_SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_tier0 = _load_tier0()


# ---------------------------------------------------------------------------
# Zero-findings paths — deterministic check functions with empty/clean inputs
# ---------------------------------------------------------------------------


def test_t04_no_schema_files_zero_findings():
    """T0-04: empty changed_files list → no *.schema.json to check → zero findings."""
    result = _tier0.check_t04_schema_metaschema_valid([])
    assert result == [], f"Expected [], got {result}"


def test_t04_non_schema_json_files_ignored():
    """T0-04: non-.schema.json files in changed_files are skipped → zero findings."""
    result = _tier0.check_t04_schema_metaschema_valid(
        ["tools/step_order.json", "spec/04_fr_list.json", "tools/specdev_tools/cli.py"]
    )
    assert result == [], f"Expected [], got {result}"


def test_t05_no_json_files_zero_findings():
    """T0-05: empty changed_files list → no *.json to parse → zero findings."""
    result = _tier0.check_t05_json_parse_clean([])
    assert result == [], f"Expected [], got {result}"


def test_t05_only_py_files_zero_findings():
    """T0-05: only .py files in changed_files → none are JSON → zero findings."""
    result = _tier0.check_t05_json_parse_clean(
        ["tools/specdev_tools/cli.py", "tests/unit/test_something.py"]
    )
    assert result == [], f"Expected [], got {result}"


def test_t08_no_unrouted_files_zero_findings():
    """T0-08: empty unrouted list → no unrouted files to report → zero findings."""
    result = _tier0.check_t08_unrouted_files([])
    assert result == [], f"Expected [], got {result}"


def test_t09_no_triggering_files_zero_findings():
    """T0-09: empty routing + empty changed_files → no migration/schema/cli triggers → zero findings."""
    result = _tier0.check_t09_changelog_entry_present({}, [])
    assert result == [], f"Expected [], got {result}"


def test_t09_only_changelog_files_exempt_from_trigger():
    """T0-09: migration_versioning slice contains only changelog files (exempted) → zero findings.

    CHANGELOG.md and changelog/* entries in the migration_versioning slice are
    filtered out by check_t09 before deciding whether a trigger exists, so they
    do not force a changelog-entry check.
    """
    routing = {"migration_versioning": ["CHANGELOG.md", "changelog/v1.0.0.md"]}
    changed_files = ["CHANGELOG.md", "changelog/v1.0.0.md"]
    result = _tier0.check_t09_changelog_entry_present(routing, changed_files)
    assert result == [], f"Expected [], got {result}"


# ---------------------------------------------------------------------------
# T0-10: specdev-unavailable path
# ---------------------------------------------------------------------------


def test_t10_specdev_unavailable_emits_p2_finding():
    """T0-10 emits a single P2 gap finding when specdev is not found on PATH.

    When 'command -v specdev' returns non-zero, check_t10_generated_artifacts_clean()
    sets specdev_available=False and returns early with one finding:
      severity  = "P2"
      kind      = "gap"
      catalog_tag = "D9"
      message   starts with "T0-10 skipped"

    subprocess.run is patched globally (tier0 does `import subprocess; subprocess.run(...)`
    so attribute-lookup at call time resolves against the real subprocess module; patch
    at 'subprocess.run' intercepts all calls within this block).
    """
    # Simulate 'command -v specdev' returning exit code 1 (not found).
    # The function returns immediately after the first subprocess call when
    # specdev_available is False, so a single mock return value is sufficient.
    mock_not_found = MagicMock(returncode=1, stdout="", stderr="specdev: command not found")

    with patch("subprocess.run", return_value=mock_not_found):
        findings = _tier0.check_t10_generated_artifacts_clean()

    assert len(findings) == 1, (
        f"Expected exactly 1 finding for specdev-unavailable, got {len(findings)}: {findings}"
    )
    f = findings[0]
    assert f["severity"] == "P2", f"Expected P2 severity, got {f['severity']!r}"
    assert f["kind"] == "gap", f"Expected kind='gap', got {f['kind']!r}"
    assert "T0-10 skipped" in f["message"], (
        f"Expected 'T0-10 skipped' in message, got: {f['message']!r}"
    )
    assert f.get("catalog_tag") == "D9", (
        f"Expected catalog_tag='D9', got {f.get('catalog_tag')!r}"
    )
