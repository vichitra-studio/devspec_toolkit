"""``specdev json read|read-multi|keys|structure --ref REF`` read the file as of a git ref (DEVSPEC-178)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.core import json_utils

FILE = "spec/00_charter.json"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=t", "-C", str(repo), *args], check=True, capture_output=True)


def _write(repo: Path, problem: str) -> None:
    (repo / FILE).write_text(json.dumps({"problem_statement": problem, "other": {"k": 1}}, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repository whose ``main`` holds problem A and whose working tree holds problem B."""
    (tmp_path / "spec").mkdir()
    _git(tmp_path, "init", "-q", "-b", "main")
    _write(tmp_path, "A")
    _git(tmp_path, "add", FILE)
    _git(tmp_path, "commit", "-q", "-m", "a")
    _write(tmp_path, "B")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["json", *args])
    code = 0
    try:
        json_utils.main()
    except SystemExit as stop:
        code = int(stop.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_read_at_ref_returns_committed_value(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _main(monkeypatch, capsys, "read", FILE, ".problem_statement", "--ref", "main")
    assert (code, out.strip()) == (0, 'A')


def test_no_ref_reads_working_tree(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _main(monkeypatch, capsys, "read", FILE, ".problem_statement")
    assert (code, out.strip()) == (0, 'B')


def test_bad_ref_exits_one_with_clear_error(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = _main(monkeypatch, capsys, "read", FILE, ".problem_statement", "--ref", "no-such-ref")
    assert code == 1 and "cannot read" in err and "no-such-ref" in err


def test_path_absent_at_ref_exits_one(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "spec" / "new.json").write_text("{}", encoding="utf-8")
    code, _, err = _main(monkeypatch, capsys, "read", "spec/new.json", ".", "--ref", "main")
    assert code == 1 and "cannot read spec/new.json at main" in err


def test_a_folder_that_is_not_a_repository_exits_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "f.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    code, _, err = _main(monkeypatch, capsys, "keys", "f.json", "--ref", "main")
    assert code == 1 and "cannot read" in err


def test_read_multi_keys_structure_accept_ref(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = _main(monkeypatch, capsys, "read-multi", FILE, ".problem_statement", ".other.k", "--ref", "main")
    assert json.loads(out) == {".problem_statement": "A", ".other.k": 1}
    _, out, _ = _main(monkeypatch, capsys, "keys", FILE, "--ref", "main")
    assert "problem_statement" in out
    _, out, _ = _main(monkeypatch, capsys, "structure", FILE, "--ref", "main")
    assert "problem_statement: str" in out


def test_ref_through_a_symlinked_folder(repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """H round 1 B1-1: a path given through a symlink to the repository still reads at the ref."""
    link = tmp_path_factory.mktemp("links") / "repo-link"
    link.symlink_to(repo, target_is_directory=True)
    code, out, err = _main(monkeypatch, capsys, "read", str(link / FILE), ".problem_statement", "--ref", "main")
    assert (code, out.strip(), err) == (0, "A", "")


def test_ref_error_names_the_file_and_ref_not_the_copy(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """H round 1 B1-8: a jq error names ``<file> at <ref>``, not the temporary copy."""
    code, _, err = _main(monkeypatch, capsys, "read", FILE, '.problem_statement | error("boom")', "--ref", "main")
    assert code == 1 and f"{FILE} at main" in err and "tmp" not in err


@pytest.mark.parametrize("command", [["patch", FILE, ".other.k", "2"], ["delete", FILE, ".other.k"]])
def test_show_file_without_dry_run_is_a_usage_error(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: list[str]) -> None:
    """H round 1 B1-9: ``--show-file`` without ``--dry-run`` exits 2 and writes nothing."""
    before = (repo / FILE).read_bytes()
    code, _, err = _main(monkeypatch, capsys, *command, "--show-file")
    assert code == 2 and "--dry-run" in err
    assert (repo / FILE).read_bytes() == before
