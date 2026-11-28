"""The multi-match warning of ``json patch`` is true: ``would be changed`` on a dry run, ``are changed`` on a write."""
from __future__ import annotations

import shutil
from pathlib import Path

from unit.graph._synth import ROOT, run_cli

SOURCE = ROOT / "tests" / "fixtures" / "graph_example" / "spec" / "04_fr_list.json"
SELECTOR = ".functional_requirements[].priority"


def _copy(tmp_path: Path) -> Path:
    path = tmp_path / "04_fr_list.json"
    shutil.copyfile(SOURCE, path)
    return path


def test_dry_run_says_would_be_changed(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    before = path.read_bytes()
    code, out = run_cli("json", "patch", str(path), SELECTOR, '"should-have"', "--dry-run", "--repo-root", str(ROOT))
    assert code == 0, out
    assert "matches 2 values; all 2 would be changed." in out
    assert "are changed" not in out
    assert path.read_bytes() == before


def test_write_says_are_changed(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    code, out = run_cli("json", "patch", str(path), SELECTOR, '"should-have"', "--repo-root", str(ROOT))
    assert code == 0, out
    assert "matches 2 values; all 2 are changed." in out
    assert "would be changed" not in out
