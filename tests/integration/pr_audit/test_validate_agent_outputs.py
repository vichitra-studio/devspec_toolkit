"""Integration tests for validate_agent_outputs.py.

AC-absent-fix-plan: When fix_plan.json is not present, the check records
    status='skip-not-present' for that artifact and the overall run exits 0 —
    the absence of fix_plan is not a defect.  Regression lock for the existing
    CORRECT behavior.

AC-schema-invalid: When findings.json violates the vc:infra:findings schema
    the run exits 1 and _write_blocked_manifest() merges status='blocked' and
    blocked_reason into manifest.json.  This exercises the IU-15 (WI-16) write
    path that was added to validate_agent_outputs.py.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Load validate_agent_outputs as a module from its script path
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]  # tests/integration/pr_audit → toolkit root
    / ".claude" / "skills" / "devspec_pr_audit" / "scripts" / "validate_agent_outputs.py"
)


def _load_vao():
    """Import validate_agent_outputs from its on-disk script path."""
    spec = importlib.util.spec_from_file_location("validate_agent_outputs", _SCRIPT_PATH)
    assert spec is not None, f"Cannot load spec from {_SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_vao = _load_vao()

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Minimal schema-valid findings document (satisfies vc:infra:findings).
_VALID_FINDINGS: dict = {
    "round": 1,
    "scope": "test",
    "generated_at": 1700000000,
    "findings": [],
}

# Schema-INVALID findings: empty object violates required fields (round, scope,
# generated_at, findings) and additionalProperties:false bars any unknowns.
_INVALID_FINDINGS: dict = {}

# Minimal manifest with all keys required by _validate_manifest_keys().
_VALID_MANIFEST: dict = {
    "run_id": "test-run-vao-001",
    "branch": "test-branch",
    "base_sha": "abc123abc123",
    "head_sha": "def456def456",
    "phases_completed": [],
    "created_at": 1700000000,
    "updated_at": 1700000000,
}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_run_dir(tmp_path: Path, name: str = "test-run-vao") -> Path:
    """Create and return an empty run directory inside tmp_path."""
    run_dir = tmp_path / name
    run_dir.mkdir()
    return run_dir


# ---------------------------------------------------------------------------
# AC-absent-fix-plan: fix_plan.json absent → skip-not-present, exit 0
# ---------------------------------------------------------------------------


def test_absent_fix_plan_skip_not_present_and_exits_0(tmp_path):
    """Absent fix_plan.json is recorded as 'skip-not-present', not a failure; exit 0.

    Regression lock: the validate script must NOT treat a missing fix_plan.json
    as a validation defect.  Zero-findings runs legitimately omit fix_plan.json
    and must still pass this gate.
    """
    run_dir = _make_run_dir(tmp_path)
    _write_json(run_dir / "findings.json", _VALID_FINDINGS)
    _write_json(run_dir / "manifest.json", _VALID_MANIFEST)
    # fix_plan.json intentionally absent

    rc = _vao.main(["--run-dir", str(run_dir)])

    assert rc == 0, f"Expected exit 0 when fix_plan.json is absent, got {rc}"
    # Manifest must NOT have been blocked
    manifest_data = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_data.get("status") != "blocked", (
        "Manifest must NOT be blocked when fix_plan.json is merely absent"
    )


# ---------------------------------------------------------------------------
# AC-schema-invalid: schema-invalid findings.json → blocked manifest, exit 1
# ---------------------------------------------------------------------------


def test_schema_invalid_findings_triggers_blocked_manifest(tmp_path):
    """Schema-invalid findings.json → exit 1, manifest.json gets status='blocked'.

    Exercises the _write_blocked_manifest() path introduced in IU-15 (WI-16):
    when _discover_and_validate() returns any 'fail' ArtifactResult, main() calls
    _write_blocked_manifest(run_dir/manifest.json, blocked_reason) before returning 1.

    The empty dict {} violates the vc:infra:findings schema on four required fields
    (round, scope, generated_at, findings) — a reliable trigger for the fail path.
    """
    run_dir = _make_run_dir(tmp_path)
    _write_json(run_dir / "findings.json", _INVALID_FINDINGS)
    _write_json(run_dir / "manifest.json", _VALID_MANIFEST)

    rc = _vao.main(["--run-dir", str(run_dir)])

    assert rc == 1, f"Expected exit 1 for schema-invalid findings.json, got {rc}"

    # _write_blocked_manifest must have merged status and blocked_reason
    manifest_data = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_data.get("status") == "blocked", (
        f"Expected manifest status='blocked', got {manifest_data.get('status')!r}"
    )
    assert manifest_data.get("blocked_reason"), (
        "Expected a non-empty blocked_reason in manifest after schema validation failure"
    )
