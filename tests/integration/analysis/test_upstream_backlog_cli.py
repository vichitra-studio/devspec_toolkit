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


def test_unicode_decode_error_triggers_exit_two(tmp_path: Path):
    """_iter_plans' UnicodeDecodeError branch (an impl_context/*.json file
    containing bytes that are not valid UTF-8) must exit 2 and surface a
    stderr line naming the offending path via 'unicode_decode_error='."""
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    bad_file = impl / "plan_invalid_utf8.json"
    bad_file.write_bytes(b'{"id": "ms-bad", "execution": \xff\xfe}')
    r = _run_cli(spec_dir)
    assert r.returncode == 2
    assert "unicode_decode_error=" in r.stderr


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


@pytest.fixture
def dual_origin_spec(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "plan_with_dual_origin_ambiguities.json",
                impl / "plan_with_dual_origin_ambiguities.json")
    return spec_dir


def test_plan_ambiguities_16a_are_scanned(dual_origin_spec: Path):
    """DEVSPEC-123 regression: plan.ambiguities[] (16a) must be as visible
    to upstream-backlog as execution.emergent_ambiguities[] (16b/16c) —
    previously it was never read at all."""
    r = _run_cli(dual_origin_spec, "--status", "all", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    ids = {rec["ambiguity_id"] for rec in payload["records"]}
    assert "amb-16a-open-blocking" in ids
    assert "amb-16a-resolved-non-blocking" in ids
    assert "amb-16b-open-high" in ids
    assert "amb-16c-resolved-critical" in ids
    assert payload["summary"]["total_records"] == 4

    origins = {rec["ambiguity_id"]: rec["origin"] for rec in payload["records"]}
    assert origins["amb-16a-open-blocking"] == "plan"
    assert origins["amb-16a-resolved-non-blocking"] == "plan"
    assert origins["amb-16b-open-high"] == "execution"
    assert origins["amb-16c-resolved-critical"] == "execution"


def test_plan_ambiguities_blocking_severity_ranks_as_critical(dual_origin_spec: Path):
    """--severity critical must keep the 16a 'blocking' record (mapped to the
    critical rank) and drop the 16a 'non_blocking' one (mapped to low)."""
    r = _run_cli(dual_origin_spec, "--status", "all", "--severity", "critical", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    ids = {rec["ambiguity_id"] for rec in payload["records"]}
    assert "amb-16a-open-blocking" in ids
    assert "amb-16a-resolved-non-blocking" not in ids


def test_default_status_open_hides_resolved_and_emits_w617(dual_origin_spec: Path):
    """DEVSPEC-123: the two resolved records (one per origin) must trigger
    the W617 hidden-count notice under the default --status open."""
    r = _run_cli(dual_origin_spec)
    assert r.returncode == 0, r.stderr
    w617_lines = [ln for ln in r.stderr.splitlines()
                  if ln.startswith("W617 UPSTREAM_BACKLOG_STATUS_FILTERED")]
    assert len(w617_lines) == 1
    assert "2 record(s)" in w617_lines[0]
    assert "amb-16a-resolved-non-blocking" not in r.stdout
    assert "amb-16c-resolved-critical" not in r.stdout


def test_status_all_suppresses_w617(dual_origin_spec: Path):
    r = _run_cli(dual_origin_spec, "--status", "all")
    assert r.returncode == 0, r.stderr
    assert "W617" not in r.stderr


def test_json_summary_carries_hidden_by_status_count(dual_origin_spec: Path):
    r = _run_cli(dual_origin_spec, "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["summary"]["hidden_by_status_count"] == 2

    r_all = _run_cli(dual_origin_spec, "--status", "all", "--json")
    payload_all = json.loads(r_all.stdout)
    assert payload_all["summary"]["hidden_by_status_count"] == 0


def test_misfiled_anchor_is_skipped_not_misread_as_plan_ambiguities(tmp_path: Path):
    """DEVSPEC-123 follow-up: a Trinity Anchor (artifact_role="anchor")
    misfiled inside impl_context/ (the W609 condition) also has a
    `plan.ambiguities[]` array, but it uses the shared crossCycleAmbiguityItem
    severity scale (low/medium/high/critical), not the milestone plan's 16a
    binary blocking/non_blocking scale. Before the artifact_role guard, this
    fixture's "high" severity would have failed origin="plan" validation
    (which only accepts blocking/non_blocking) and spuriously emitted E520 for
    a perfectly schema-valid anchor. It must instead be skipped entirely."""
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "anchor_misfiled_in_impl_context.json",
                impl / "anchor_misfiled_in_impl_context.json")
    r = _run_cli(spec_dir, "--status", "all", "--json")
    assert r.returncode == 0, r.stderr
    assert "E520" not in r.stderr
    payload = json.loads(r.stdout)
    assert payload["summary"]["total_records"] == 0
    assert payload["records"] == []


def test_misfiled_anchor_with_whitespace_padded_role_is_still_skipped(tmp_path: Path):
    """validate.py's W609 ANCHOR_MISFILED check tolerates a whitespace-padded
    artifact_role via `.strip() == "anchor"` (defensive against trailing
    whitespace in an otherwise schema-invalid file). upstream-backlog's guard
    must match that same tolerance -- otherwise a file validate.py correctly
    flags as a misfiled anchor would fall through here and be misread as a
    milestone plan, spuriously emitting E520 for its crossCycleAmbiguityItem
    severities."""
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "anchor_misfiled_whitespace_role.json",
                impl / "anchor_misfiled_whitespace_role.json")
    r = _run_cli(spec_dir, "--status", "all", "--json")
    assert r.returncode == 0, r.stderr
    assert "E520" not in r.stderr
    payload = json.loads(r.stdout)
    assert payload["summary"]["total_records"] == 0
    assert payload["records"] == []
