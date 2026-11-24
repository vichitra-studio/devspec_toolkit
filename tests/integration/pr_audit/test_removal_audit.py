"""Integration tests for removal_audit.py: what it does to the Tier-0 findings file and the manifest."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]  # tests/integration/pr_audit -> toolkit root
    / ".claude" / "skills" / "devspec_pr_audit" / "scripts" / "removal_audit.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("removal_audit", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_removal = _load()


def _run(monkeypatch, run_dir: Path, deleted: list[str], *extra: str) -> int:
    monkeypatch.setattr(_removal, "load_deleted_files", lambda base, head: deleted)
    monkeypatch.setattr(sys, "argv", ["removal_audit.py", "--run-dir", str(run_dir), "--head-sha", "h", "--base-sha", "b", *extra])
    return _removal.main()


def _run_dir(tmp_path: Path) -> Path:
    (tmp_path / "p0").mkdir()
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "r", "tier0_overrides": []}), encoding="utf-8")
    return tmp_path


def test_an_unreadable_tier0_file_stops_the_run_and_is_left_as_it_is(tmp_path, monkeypatch, capsys):
    run_dir = _run_dir(tmp_path)
    tier0 = run_dir / "p0" / "tier0_findings.json"
    tier0.write_text("{not json", encoding="utf-8")
    assert _run(monkeypatch, run_dir, ["docs/old_note.md"]) == 2
    assert tier0.read_text(encoding="utf-8") == "{not json"
    assert "is unreadable" in capsys.readouterr().err


def test_an_override_counts_and_records_the_p0_removals_it_suppresses(tmp_path, monkeypatch, capsys):
    run_dir = _run_dir(tmp_path)
    code = _run(monkeypatch, run_dir, ["canon/kinds/trace_type.json", "docs/old_note.md"], "--allow-tier0-failure=removal-audit")
    assert code == 0
    out = capsys.readouterr().out
    assert "removal-audit: 1 P0 finding(s) suppressed" in out
    assert "suppressed P0 removal: canon/kinds/trace_type.json" in out
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["removal_audit_suppressed"] == ["canon/kinds/trace_type.json"]
    assert manifest["tier0_overrides"] == ["removal-audit"]
    written = json.loads((run_dir / "p0" / "tier0_findings.json").read_text(encoding="utf-8"))["findings"]
    assert [f["severity"] for f in written] == ["P2"]
