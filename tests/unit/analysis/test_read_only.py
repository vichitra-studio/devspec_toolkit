"""Read-only invariant tests: hash-diff + open-mode monkeypatch."""
from __future__ import annotations

import builtins
import hashlib
import shutil
from pathlib import Path

import pytest

from specdev_tools.analysis.upstream_backlog import run


FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures" / "analysis" / "upstream_backlog"
)


def _snapshot(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _stage_spec_dir(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "spec"
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True)
    for name in ("plan_with_six_ambiguities.json", "plan_with_no_execution.json",
                 "plan_with_null_execution.json"):
        shutil.copy(FIXTURE_DIR / name, impl / name)
    return spec_dir


def test_run_does_not_mutate_spec_dir(tmp_path: Path):
    spec_dir = _stage_spec_dir(tmp_path)
    before = _snapshot(spec_dir)
    run(str(spec_dir))
    run(str(spec_dir), json_output=True)
    after = _snapshot(spec_dir)
    assert before == after


def test_open_mode_is_read_only(tmp_path: Path, monkeypatch):
    spec_dir = _stage_spec_dir(tmp_path)
    real_open = builtins.open
    forbidden = set("wa+x")

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(ch in forbidden for ch in mode):
            raise RuntimeError(f"write-mode open attempted: {file!r} mode={mode!r}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    try:
        run(str(spec_dir))
        run(str(spec_dir), json_output=True)
    except RuntimeError as exc:
        pytest.fail(f"Read-only invariant violated: {exc}")
