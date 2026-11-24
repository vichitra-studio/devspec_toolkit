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

import pytest

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


@pytest.mark.parametrize(
    "path",
    [
        "tools/specdev_tools/trace/commands.py",
        "tools/specdev_tools/trace/id_write_commands.py",
        "tools/specdev_tools/lifecycle/commands.py",
    ],
)
def test_t09_a_command_module_triggers_finding(tmp_path, path):
    """T0-09: a command module of a package (commands.py, <name>_commands.py) triggers the changelog requirement.

    REPO_ROOT is temporarily redirected to tmp_path (which has no changelog
    files) so has_entry stays False and a finding is emitted.
    """
    original_repo_root = _tier0.REPO_ROOT
    _tier0.REPO_ROOT = tmp_path
    try:
        result = _tier0.check_t09_changelog_entry_present({}, [path])
    finally:
        _tier0.REPO_ROOT = original_repo_root
    assert len(result) >= 1, f"Expected >=1 finding for {path}, got {result}"
    assert result[0].get("catalog_tag") == "D11", (
        f"Expected catalog_tag='D11', got {result[0].get('catalog_tag')!r}"
    )


def test_t09_a_module_that_is_not_a_command_module_triggers_nothing(tmp_path):
    """T0-09: a module that registers no subcommand is not a CLI change."""
    original_repo_root = _tier0.REPO_ROOT
    _tier0.REPO_ROOT = tmp_path
    try:
        result = _tier0.check_t09_changelog_entry_present({}, ["tools/specdev_tools/trace/id_writes.py"])
    finally:
        _tier0.REPO_ROOT = original_repo_root
    assert result == []


def test_t09_cli_py_still_triggers_finding(tmp_path):
    """T0-09: tools/specdev_tools/cli.py still triggers the changelog requirement (regression).

    The set-membership branch (CLI_PATHS) fires for the entry point itself.
    REPO_ROOT is temporarily redirected to tmp_path (which has no changelog
    files) so has_entry stays False and a finding is emitted.
    """
    changed_files = ["tools/specdev_tools/cli.py"]
    original_repo_root = _tier0.REPO_ROOT
    _tier0.REPO_ROOT = tmp_path
    try:
        result = _tier0.check_t09_changelog_entry_present({}, changed_files)
    finally:
        _tier0.REPO_ROOT = original_repo_root
    assert len(result) >= 1, f"Expected >=1 finding for cli.py, got {result}"
    assert result[0].get("catalog_tag") == "D11", (
        f"Expected catalog_tag='D11', got {result[0].get('catalog_tag')!r}"
    )


def _t09_findings(repo_root, changed_files):
    """Run T0-09 with REPO_ROOT redirected to *repo_root* and return its findings."""
    original_repo_root = _tier0.REPO_ROOT
    _tier0.REPO_ROOT = repo_root
    try:
        return _tier0.check_t09_changelog_entry_present({}, changed_files)
    finally:
        _tier0.REPO_ROOT = original_repo_root


_T09_TRIGGER = "tools/specdev_tools/cli.py"


def _write_changelog_file(repo_root, name, text):
    """Write changelog/<name> under *repo_root* (or CHANGELOG.md at its top for name 'CHANGELOG.md')."""
    path = repo_root / name if name == "CHANGELOG.md" else repo_root / "changelog" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_t09_a_markdown_only_entry_does_not_satisfy(tmp_path):
    """T0-09: the Markdown is rendered from the YAML, so a Markdown entry alone is no entry."""
    _write_changelog_file(tmp_path, "unreleased.md", "A change that is described in text only.\n")
    _write_changelog_file(tmp_path, "CHANGELOG.md", "## [Unreleased]\n\n- A change in text only.\n")
    result = _t09_findings(tmp_path, [_T09_TRIGGER])
    assert len(result) == 1, f"Expected one finding, got {result}"
    assert result[0].get("catalog_tag") == "D11"


def test_t09_the_unreleased_yaml_skeleton_does_not_satisfy(tmp_path):
    """T0-09: the committed skeleton (`changes: []`) records nothing."""
    _write_changelog_file(tmp_path, "unreleased.yaml", 'version: "unreleased"\nbreaking: false\nchanges: []\n')
    result = _t09_findings(tmp_path, [_T09_TRIGGER])
    assert len(result) == 1, f"Expected one finding, got {result}"


def test_t09_an_unreleased_yaml_with_a_change_satisfies(tmp_path):
    """T0-09: a `changes` item in changelog/unreleased.yaml is the entry."""
    _write_changelog_file(
        tmp_path, "unreleased.yaml", 'version: "unreleased"\nbreaking: false\nchanges:\n  - type: fix\n    description: x\n'
    )
    assert _t09_findings(tmp_path, [_T09_TRIGGER]) == []


def test_t09_a_version_yaml_in_the_diff_satisfies(tmp_path):
    """T0-09: a changelog/v<X.Y.Z>.yaml that the diff changes is the entry."""
    assert _t09_findings(tmp_path, [_T09_TRIGGER, "changelog/v1.2.0.yaml"]) == []


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


# ---------------------------------------------------------------------------
# T0-10: every generator output is compared
# ---------------------------------------------------------------------------


def test_t10_redirects_every_output_flag_of_registry_generate():
    """GENERATED_OUTPUTS names every ``--*out`` flag of ``registry-generate``, so a new output cannot go undiffed."""
    from specdev_tools.cli import build_parser

    subparsers = next(a for a in build_parser()._actions if getattr(a, "choices", None) and "registry-generate" in a.choices)
    out_flags = {
        flag
        for action in subparsers.choices["registry-generate"]._actions
        for flag in action.option_strings
        if flag == "--out" or flag.endswith("-out")
    }
    assert {flag for flag, _rel in _tier0.GENERATED_OUTPUTS} == out_flags
    for _flag, rel in _tier0.GENERATED_OUTPUTS:
        assert (_tier0.REPO_ROOT / rel).is_file(), rel


def test_t10_clean_tree_has_no_generator_drift():
    """On the committed tree the five generated files equal a fresh generator run."""
    findings = _tier0.check_t10_generated_artifacts_clean()
    if any(f["message"].startswith("T0-10 skipped") for f in findings):
        pytest.skip("the check found no specdev to run")
    assert findings == []


def test_t10_clean_tree_test_skips_when_specdev_is_not_found():
    """Without ``specdev`` the clean-tree test skips; it neither fails nor passes."""
    not_found = MagicMock(returncode=1, stdout="", stderr="specdev: command not found")
    with patch("subprocess.run", return_value=not_found), pytest.raises(pytest.skip.Exception):
        test_t10_clean_tree_has_no_generator_drift()



@pytest.mark.parametrize(
    "test_text",
    [
        "import specdev_tools.trace.lockfile as lockfile\n",
        "from specdev_tools.trace.lockfile import read_lock\n",
        "from specdev_tools.trace import lockfile\n",
        "from specdev_tools.trace import (\n    attest,\n    lockfile,\n)\n",
    ],
)
def test_t11_accepts_a_module_that_a_test_imports(test_text):
    """A new module needs no ``test_<module>*.py`` when a test file imports it."""
    assert _tier0._imported_by_a_test("tools/specdev_tools/trace/lockfile.py", [test_text])


@pytest.mark.parametrize(
    "test_text",
    [
        "from specdev_tools.trace import attest\n",
        "from specdev_tools.graph import lockfile\n",
        "lockfile = 'a word in a test, not an import'\n",
    ],
)
def test_t11_does_not_accept_a_module_that_no_test_imports(test_text):
    """Another module of the package, the same name in another package and a bare word are not an import."""
    assert not _tier0._imported_by_a_test("tools/specdev_tools/trace/lockfile.py", [test_text])
