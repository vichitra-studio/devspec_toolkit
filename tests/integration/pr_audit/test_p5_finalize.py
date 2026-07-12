"""Integration tests for p5_finalize.py — WI-1 acceptance criteria.

AC1: Empty findings[] + no fix_plan.json → exit 0, SUMMARY.md written with "0 tasks."
AC2: Real zero-findings run (20260625-112746-3423097, copy to tmp) → exit 0.
AC3: Non-empty findings[] + no fix_plan.json → exit 1, clear error.
AC4: Manifest status="blocked" → p5_finalize exits 1 (G3 guard).
AC5: Non-empty findings[] + valid fix_plan.json → exit 0, SUMMARY.md has "## Next steps"
     footer (WI-12 AC2); zero-findings run has NO "## Next steps" footer.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load p5_finalize as a module from its script path (not on sys.path)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]  # tests/integration/pr_audit → devspec_toolkit root
    / ".claude" / "skills" / "devspec_pr_audit" / "scripts" / "p5_finalize.py"
)


def _load_p5():
    """Import p5_finalize from its on-disk script path."""
    spec = importlib.util.spec_from_file_location("p5_finalize", _SCRIPT_PATH)
    assert spec is not None, f"Cannot load spec from {_SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_p5 = _load_p5()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_EMPTY_FINDINGS = {
    "round": 1,
    "scope": "test",
    "generated_at": 1700000000,
    "findings": [],
}

_ONE_FINDING = {
    "round": 1,
    "scope": "test",
    "generated_at": 1700000000,
    "findings": [
        {
            "kind": "bug",
            "location": "tools/specdev_tools/cli.py:1",
            "signature": "test-sig-001",
            "message": "Test bug for WI-1 AC3",
            "severity": "P1",
        }
    ],
}

_MINIMAL_MANIFEST = {
    "run_id": "test-run-001",
    "head_sha": "aabbccdd1234",
    "base_sha": "11223344aabb",
    "branch": "bugs/1.1.1",
    "phases_completed": [0, 1, 2, 3, 4],
    "phase_trace": [],
    "tier0_overrides": [],
    "slices_in_scope": [],
    "out_of_scope_files": [],
    "created_at": 1700000000,
    "updated_at": 1700000000,
    "meta_findings": [],
    "status": "OK",
}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_run_dir(tmp_path: Path, *, findings: dict, manifest: dict | None = None) -> Path:
    """Create a minimal run directory with findings.json + manifest.json."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "findings.json", findings)
    _write_json(run_dir / "manifest.json", manifest or _MINIMAL_MANIFEST)
    return run_dir


# ---------------------------------------------------------------------------
# AC1 — empty findings, no fix_plan → exit 0, SUMMARY.md has "0 tasks"
# ---------------------------------------------------------------------------

def test_ac1_empty_findings_no_fix_plan(tmp_path):
    """AC1: empty findings[] + no fix_plan.json → exit 0, SUMMARY.md written without footer."""
    run_dir = _make_run_dir(tmp_path, findings=_EMPTY_FINDINGS)

    rc = _p5.main(["--run-dir", str(run_dir)])

    assert rc == 0, f"Expected exit 0, got {rc}"
    summary_path = run_dir / "SUMMARY.md"
    assert summary_path.exists(), "SUMMARY.md was not written"
    content = summary_path.read_text(encoding="utf-8")
    assert "0 tasks" in content, f"Expected '0 tasks' in SUMMARY.md, got:\n{content[:400]}"
    assert "## Next steps" not in content, (
        "SUMMARY.md must NOT contain '## Next steps' when findings == 0"
    )


# ---------------------------------------------------------------------------
# AC2 — real zero-findings production run (copy to tmp) → exit 0
# ---------------------------------------------------------------------------

_REAL_RUN = (
    Path(__file__).resolve().parents[3]  # devspec_toolkit root
    / "docs" / "audit" / "runs" / "20260625-112746-3423097"
)


@pytest.mark.skipif(
    not _REAL_RUN.is_dir(),
    reason="Production run 20260625-112746-3423097 not present in this checkout",
)
def test_ac2_real_zero_findings_run(tmp_path):
    """AC2: real audit run 20260625-112746-3423097 (zero findings, no fix_plan) → exit 0."""
    run_copy = tmp_path / "real_run"
    shutil.copytree(str(_REAL_RUN), str(run_copy))
    # Remove any pre-existing SUMMARY.md (manual-bypass artifact) so the assertion
    # proves regeneration, not just that copytree copied an old file.
    (run_copy / "SUMMARY.md").unlink(missing_ok=True)

    rc = _p5.main(["--run-dir", str(run_copy)])

    assert rc == 0, f"Expected exit 0 on real run, got {rc}"
    assert (run_copy / "SUMMARY.md").exists(), "SUMMARY.md was not regenerated"


# ---------------------------------------------------------------------------
# AC3 — non-empty findings, no fix_plan → exit 1, clear error
# ---------------------------------------------------------------------------

def test_ac3_nonempty_findings_no_fix_plan(tmp_path, capsys):
    """AC3: non-empty findings[] + no fix_plan.json → exit 1 with clear error."""
    run_dir = _make_run_dir(tmp_path, findings=_ONE_FINDING)

    rc = _p5.main(["--run-dir", str(run_dir)])

    assert rc == 1, f"Expected exit 1, got {rc}"
    captured = capsys.readouterr()
    assert "fix_plan.json" in captured.err, (
        f"Expected 'fix_plan.json' in stderr; got:\n{captured.err}"
    )
    assert not (run_dir / "SUMMARY.md").exists(), "SUMMARY.md must NOT be written on error"


# ---------------------------------------------------------------------------
# AC4 — manifest status="blocked" → G3 guard exits 1
# ---------------------------------------------------------------------------

def test_ac4_blocked_manifest_exits_1(tmp_path, capsys):
    """AC4: manifest.status='blocked' → G3 guard returns 1, skips summary generation."""
    blocked_manifest = {**_MINIMAL_MANIFEST, "status": "blocked", "blocked_reason": "schema validation failed"}
    run_dir = _make_run_dir(tmp_path, findings=_EMPTY_FINDINGS, manifest=blocked_manifest)

    rc = _p5.main(["--run-dir", str(run_dir)])

    assert rc == 1, f"Expected exit 1 for blocked run, got {rc}"
    captured = capsys.readouterr()
    assert "blocked" in captured.err.lower(), (
        f"Expected blocked reason in stderr; got:\n{captured.err}"
    )
    assert not (run_dir / "SUMMARY.md").exists(), "SUMMARY.md must NOT be written when run is blocked"


# ---------------------------------------------------------------------------
# AC5 — findings > 0 + valid fix_plan → footer present; zero-findings → absent
# ---------------------------------------------------------------------------

_ONE_TASK_FIX_PLAN = {
    "round": 1,
    "scope": "test",
    "generated_at": 1700000000,
    "tasks": [
        {
            "id": "T1",
            "kind": "code",
            "priority": "P1",
            "file": "tools/specdev_tools/cli.py",
            "change_summary": "Fix test bug.",
            "acceptance_command": "python -m pytest tests/ -q",
            "findings": ["test-sig-001"],
        }
    ],
}


def test_ac5_next_steps_footer_present_when_findings(tmp_path):
    """AC5a (WI-12 AC2): findings > 0 + fix_plan.json → SUMMARY.md has '## Next steps' footer."""
    run_dir = _make_run_dir(tmp_path, findings=_ONE_FINDING)
    _write_json(run_dir / "fix_plan.json", _ONE_TASK_FIX_PLAN)

    rc = _p5.main(["--run-dir", str(run_dir)])

    assert rc == 0, f"Expected exit 0, got {rc}"
    content = (run_dir / "SUMMARY.md").read_text(encoding="utf-8")
    assert "## Next steps" in content, (
        "SUMMARY.md must contain '## Next steps' when findings > 0"
    )
    assert "p6_verify.py" in content, (
        "Next steps footer must reference p6_verify.py"
    )
    assert "/devspec_pr_audit" in content, (
        "Next steps footer must reference /devspec_pr_audit re-run instruction"
    )


def test_ac5_next_steps_footer_absent_when_no_findings(tmp_path):
    """AC5b (WI-12 AC2): findings == 0 → SUMMARY.md must NOT have '## Next steps' footer."""
    run_dir = _make_run_dir(tmp_path, findings=_EMPTY_FINDINGS)

    rc = _p5.main(["--run-dir", str(run_dir)])

    assert rc == 0, f"Expected exit 0, got {rc}"
    content = (run_dir / "SUMMARY.md").read_text(encoding="utf-8")
    assert "## Next steps" not in content, (
        "SUMMARY.md must NOT contain '## Next steps' when findings == 0"
    )


# ---------------------------------------------------------------------------
# WI-15: additional harness coverage
# ---------------------------------------------------------------------------

def test_malformed_findings_exits_2(tmp_path):
    """Malformed (unparseable) JSON in findings.json → _load_json calls sys.exit(2).

    This is distinct from schema-invalid (which exits 1): unparseable JSON is an
    I/O-level error caught by json.JSONDecodeError in _load_json(), which calls
    sys.exit(2) directly.  The try-block in main() re-raises SystemExit so the
    exit code propagates to the caller.
    """
    run_dir = _make_run_dir(tmp_path, findings=_EMPTY_FINDINGS)
    # Overwrite findings.json with unparseable content
    (run_dir / "findings.json").write_text("NOT VALID JSON {{{{", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _p5.main(["--run-dir", str(run_dir)])

    assert exc_info.value.code == 2, (
        f"Expected SystemExit(2) for malformed findings.json, got code={exc_info.value.code}"
    )


def test_missing_manifest_exits_1(tmp_path, capsys):
    """Missing manifest.json → main returns 1 with an error message naming manifest.json.

    findings.json is present; manifest.json is absent.  The pre-flight existence
    check (before any JSON loading) catches this and returns 1 immediately.
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "findings.json", _EMPTY_FINDINGS)
    # manifest.json intentionally not written

    rc = _p5.main(["--run-dir", str(run_dir)])

    assert rc == 1, f"Expected exit 1 for missing manifest.json, got {rc}"
    captured = capsys.readouterr()
    assert "manifest.json" in captured.err, (
        f"Expected 'manifest.json' in stderr; got:\n{captured.err}"
    )
