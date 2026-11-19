"""A spec folder that is not directly under the repository root (``host/sub/spec``, seeds at ``host/docs/seed``), M5 round 3 (H1-2).

The host root derived from ``--spec-root`` is then ``host/sub``, where no seed document is.  The lock never takes the
hash of a seed that was not found: every command that writes hashes refuses with E520 and writes nothing; the read
commands go on and say once on stderr which seeds were not found; ``lock install-driver`` writes the line that matches
the lock file, relative to the git top level.  With ``--git-root`` the same commands work.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT, git, run_cli
from unit.trace._lock_support import EXAMPLE_HOST

FR = "fr-password-reset-request"
SEED = "seed-accounts"
SEED_PATH = "docs/seed/seed_accounts.md"
ACCEPTANCE = '{"criterion_id": "ac-password-reset-request-3", "scope": "in", "text": "Given x, when y, then z."}'

WRITERS = {
    "attest-step": ["attest", "--step", "00", "--yes"],
    "attest-step-dry-run": ["attest", "--step", "00", "--yes", "--dry-run"],
    "attest-node": ["attest", "asm-member-controls-email", "--yes"],
    "json-patch-id": ["json", "patch", "--id", FR, ".statement", '"A member can ask for a reset link."'],
    "json-patch-id-dry-run": ["json", "patch", "--id", FR, ".statement", '"A member can ask for a reset link."', "--dry-run"],
    "json-insert-id": ["json", "insert", "--id", FR, ".acceptance_criteria", ACCEPTANCE],
    "json-delete-id": ["json", "delete", "--id", "PWRESET_CONFIRM_EXPIRED_01"],
    "step-create": ["step", "create", "15", "--from", "draft_15.json"],
    "step-create-dry-run": ["step", "create", "15", "--from", "draft_15.json", "--dry-run"],
}
READERS = {
    "stale": ["stale"],
    "stale-json": ["stale", "--json"],
    "coverage": ["coverage"],
    "step-ready": ["step", "ready", "05"],
    "attest-preview": ["attest", "--step", "00"],
}


@pytest.fixture
def nested(tmp_path: Path) -> Path:
    """A git copy of the worked example with the spec folder moved to ``sub/spec``; the host root is the returned folder."""
    host = tmp_path / "work" / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    (host / "sub").mkdir()
    shutil.move(str(host / "spec" / "15_scaffold.json"), str(host / "draft_15.json"))
    shutil.move(str(host / "spec"), str(host / "sub" / "spec"))
    git(host, "init", "-q", "-b", "main")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "one")
    return host


def _run(args: list[str], host: Path, *, git_root: bool) -> tuple[int, str]:
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "sub" / "spec")]
    return run_cli(*args, *flags, *(["--git-root", str(host)] if git_root else []))


def _tree(host: Path) -> tuple[str, list[str]]:
    return git(host, "status", "--porcelain", "--ignored"), sorted(p.name for p in (host / "sub" / "spec").iterdir())


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_a_writer_refuses_when_a_seed_is_not_found_and_writes_nothing(name: str, nested: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(nested)
    before = _tree(nested)
    code, out = _run(WRITERS[name], nested, git_root=False)
    assert code == 1, out
    assert out.startswith("E520"), out
    for part in (SEED, SEED_PATH, str(nested / "sub"), "--git-root"):
        assert part in out, (part, out)
    assert "missing:" not in out
    assert _tree(nested) == before == ("", before[1])


@pytest.mark.parametrize("name", ["attest-step", "json-patch-id", "step-create"])
def test_the_same_writer_works_with_git_root_and_leaves_spec_check_clean(name: str, nested: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(nested)
    code, out = _run(WRITERS[name], nested, git_root=True)
    assert code == 0, out
    assert name == "attest-step" or git(nested, "status", "--porcelain", "sub") != ""  # the clean example has nothing to attest
    errors, _context = run_spec_check_json(str(ROOT), str(nested / "sub" / "spec"), git_root=str(nested))
    assert [e.message for e in errors if e.code == "E763"] == []
    assert "missing:" not in (nested / "sub" / "spec" / "extras" / "trace.lock.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(READERS))
def test_a_reader_goes_on_and_names_the_seeds_not_found_once(name: str, nested: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(nested)
    code, out = _run(READERS[name], nested, git_root=False)
    assert code in (0, 1), out
    lines = [line for line in out.splitlines() if "seed documents not found" in line]
    assert len(lines) == 1, out
    for part in (SEED, SEED_PATH, str(nested / "sub"), "--git-root"):
        assert part in lines[0], (part, lines[0])
    assert git(nested, "status", "--porcelain") == ""
    _code, found = _run(READERS[name], nested, git_root=True)
    assert "seed documents not found" not in found


@pytest.mark.parametrize("command", ["spec-check", "validate-all", "forward-replay-check"])
def test_a_validation_command_names_the_seeds_not_found_once(command: str, nested: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(nested)
    spec = str(nested / "sub" / "spec")
    positional = [] if command == "forward-replay-check" else [spec]
    flags = [command, *positional, "--repo-root", str(ROOT), "--spec-root", spec]
    _code, out = run_cli(*flags)
    lines = [line for line in out.splitlines() if "seed documents not found" in line]
    assert len(lines) == 1, out
    for part in (SEED, SEED_PATH, str(nested / "sub"), "--git-root"):
        assert part in lines[0], (part, lines[0])
    assert "E763" in out
    _code, found = run_cli(*flags, "--git-root", str(nested))
    assert "seed documents not found" not in found and "E763" not in found, found


def test_install_driver_writes_the_line_that_matches_the_lock_file(nested: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(nested)
    code, out = _run(["lock", "install-driver", "--driver-command", "specdev lock merge"], nested, git_root=False)
    assert code == 0, out
    assert "sub/spec/extras/trace.lock.json merge=specdev-trace-lock" in out
    attributes = (nested / ".git" / "info" / "attributes").read_text(encoding="utf-8").splitlines()
    assert attributes == ["sub/spec/extras/trace.lock.json merge=specdev-trace-lock"]
    assert git(nested, "check-attr", "merge", "--", "sub/spec/extras/trace.lock.json").endswith("merge: specdev-trace-lock")
    assert _run(["lock", "install-driver", "--driver-command", "specdev lock merge"], nested, git_root=True)[0] == 0
    assert (nested / ".git" / "info" / "attributes").read_text(encoding="utf-8").splitlines() == attributes


def test_install_driver_outside_a_repository_still_refuses(tmp_path: Path) -> None:
    host = tmp_path / "plain"
    shutil.copytree(EXAMPLE_HOST, host)
    code, out = run_cli("lock", "install-driver", "--driver-command", "x", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"))
    assert code == 1 and out.startswith("E520"), out
