"""End-to-end CLI subprocess test for specdev upstream-backlog.

Exercises the full `python -m specdev_tools.cli upstream-backlog` path —
argparse parsing, dispatch, stdout/stderr routing, and exit code — which
mirrors the invocation performed by `./tools/run_specdev.sh`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


TOOLKIT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = TOOLKIT_ROOT / "tests" / "fixtures" / "analysis" / "upstream_backlog"


def _run_cli(spec_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(TOOLKIT_ROOT / "tools")}
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "upstream-backlog",
         str(spec_dir), *extra],
        cwd=str(TOOLKIT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def clean_spec(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    for name in ("plan_with_six_ambiguities.json", "plan_with_no_execution.json"):
        shutil.copy(FIXTURE_DIR / name, impl / name)
    return spec_dir


@pytest.fixture
def broken_spec(clean_spec: Path) -> Path:
    shutil.copy(FIXTURE_DIR / "plan_malformed.json",
                clean_spec / "impl_context" / "plan_malformed.json")
    return clean_spec


def test_clean_run_exits_zero_and_groups_buckets(clean_spec: Path):
    r = _run_cli(clean_spec)
    assert r.returncode == 0, r.stderr
    assert "Step 09" in r.stdout
    assert "Plan-level" in r.stdout
    assert "Unclassified" in r.stdout


def test_clean_run_emits_w613_for_open_unclassified(clean_spec: Path):
    r = _run_cli(clean_spec)
    assert r.returncode == 0
    # Under --status open (default), the 2 open unclassified fire W613
    w613_lines = [ln for ln in r.stderr.splitlines()
                  if ln.startswith("W613 UPSTREAM_BACKLOG_UNCLASSIFIED")]
    assert len(w613_lines) == 2


def test_status_all_includes_resolved_unclassified(clean_spec: Path):
    r = _run_cli(clean_spec, "--status", "all")
    assert r.returncode == 0
    w613_lines = [ln for ln in r.stderr.splitlines()
                  if ln.startswith("W613 UPSTREAM_BACKLOG_UNCLASSIFIED")]
    assert len(w613_lines) == 3


def test_json_output_is_valid_with_schema_version(clean_spec: Path):
    r = _run_cli(clean_spec, "--json")
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["schema_version"] == "1"
    assert "records" in payload
    assert "warnings" in payload


def test_malformed_plan_triggers_exit_two(broken_spec: Path):
    r = _run_cli(broken_spec)
    assert r.returncode == 2
    assert "E520" in r.stderr


def test_severity_high_filters_out_lower(clean_spec: Path):
    r = _run_cli(clean_spec, "--severity", "high")
    assert r.returncode == 0
    # Only amb-new-responsive-375 is high —
    # lands in Unclassified. Plan-level (all low) must be gone; Step 09
    # (low-severity wcag-pairing-ratchet) must also be gone.
    assert "Plan-level" not in r.stdout
    assert "Step 09" not in r.stdout
    assert "Unclassified" in r.stdout
    assert "amb-new-responsive-375" in r.stdout


def test_record_level_e520_triggers_exit_two(tmp_path: Path):
    """Plan decision #12: any E520 emission sets exit_code=2, including
    record-level schema bypass (not just malformed JSON)."""
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "plan_with_record_level_e520.json",
                impl / "plan_with_record_level_e520.json")
    r = _run_cli(spec_dir)
    assert r.returncode == 2
    assert "E520" in r.stderr
    assert "missing_id" in r.stderr
    # The sibling well-formed record survives and renders.
    assert "amb-good" in r.stdout


def test_null_execution_plan_is_skipped_silently(tmp_path: Path):
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "plan_with_null_execution.json",
                impl / "plan_with_null_execution.json")
    r = _run_cli(spec_dir)
    assert r.returncode == 0, r.stderr
    assert "E520" not in r.stderr
    assert "0 records" in r.stdout
