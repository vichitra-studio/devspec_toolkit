"""Deleting the root path ``.`` is refused cleanly: no traceback, the file is unchanged."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.core.json_utils import JsonUtilsError, json_delete, json_patch_batch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tests" / "fixtures" / "graph_example" / "spec" / "04_fr_list.json"


@pytest.fixture
def target(tmp_path: Path) -> Path:
    path = tmp_path / "04_fr_list.json"
    shutil.copyfile(SOURCE, path)
    return path


def _ops(tmp_path: Path) -> Path:
    path = tmp_path / "ops.json"
    path.write_text(json.dumps([{"op": "delete", "path": "."}]), encoding="utf-8")
    return path


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "json", *args, "--repo-root", str(ROOT)],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )


def _assert_clean_refusal(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "AttributeError" not in result.stderr
    assert "whole document" in result.stderr + result.stdout


def test_library_delete_of_root_refuses(target: Path) -> None:
    before = target.read_bytes()
    with pytest.raises(JsonUtilsError, match="whole document"):
        json_delete(str(target), ".", repo_root=str(ROOT), validate=True)
    assert target.read_bytes() == before


def test_library_batch_delete_of_root_refuses(tmp_path: Path, target: Path) -> None:
    before = target.read_bytes()
    with pytest.raises(JsonUtilsError, match="whole document"):
        json_patch_batch(str(target), str(_ops(tmp_path)), repo_root=str(ROOT))
    assert target.read_bytes() == before


def test_cli_delete_of_root_refuses(target: Path) -> None:
    before = target.read_bytes()
    _assert_clean_refusal(_cli("delete", str(target), "."))
    assert target.read_bytes() == before


def test_cli_batch_delete_of_root_refuses(tmp_path: Path, target: Path) -> None:
    before = target.read_bytes()
    _assert_clean_refusal(_cli("patch", str(target), "--batch", str(_ops(tmp_path))))
    assert target.read_bytes() == before


def test_patch_that_replaces_the_document_with_a_list_refuses_and_names_the_command(target: Path) -> None:
    before = target.read_bytes()
    result = _cli("patch", str(target), ".", "[1, 2]")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "`json patch`" in result.stderr + result.stdout
    assert "not a JSON object after this edit" in result.stderr + result.stdout
    assert target.read_bytes() == before


def test_edit_of_a_document_that_is_a_list_refuses_without_a_traceback(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text('[{"a": 1}]\n', encoding="utf-8")
    result = _cli("patch", str(path), ".[0].a", "2")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "not a JSON object." in result.stderr + result.stdout
    assert path.read_text(encoding="utf-8") == '[{"a": 1}]\n'
