"""``specdev update <spec> --install-only`` end to end: every piece of the host installer, through the real ``host_install.PIECES``, on three scratch hosts.

The hosts are the invented fixtures ``tests/fixtures/hosts/w`` (hand-written toolkit hooks among the host's own, and a workflow that still calls
removed commands) and ``tests/fixtures/hosts/p`` (a different house style, no toolkit hooks), and a fresh ``init`` layout (``init_project.main`` with
its subprocesses stubbed, as ``tests/unit/test_init_project_submodule.py`` does).  Every host lives under pytest's ``tmp_path`` and is a git
repository of its own; its toolkit is the live tree, by a symlink (``w``, ``p``) or by the absolute ``--repo-root`` (``init`` layout).

The command is the real one, run in this process through ``cli.main``.  Three things are replaced, none of them a piece: the pre-commit runner
(``host_install._run_pre_commit_install``, the one place pre-commit starts: no venv is built, nothing is downloaded), the venv check of the CLI, and
the global git configuration (a person's own ignore file may already cover ``settings.local.json``; the tests see only the host's rules).

What each test fixes: the status and the codes of every piece after the first run, the host's own files byte for byte outside what the installer
may write, a second run that changes no byte (every file of the host including ``.git/config`` and ``.git/info/*`` is hashed) and reports no piece as
created or refreshed, and, on ``w``, ``--adopt`` clearing the drift.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools import cli
from specdev_tools import host_install as hi

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "hosts"
SCRIPTS = REPO / "scripts"
PIECES = ["pre-commit", "merge-driver", "workflows", "wrappers", "claude-links", "ask-rules", "gitignore"]
CONFIG = ".pre-commit-config.yaml"
SETTINGS = ".claude/settings.local.json"
WORKFLOW_OF_THE_TOOLKIT = ".github/workflows/specdev-merge-check.yml"
THE_INSTALLERS_OWN_PATHS = (
    "tools/run_specdev.sh", "tools/ensure_venv.py", WORKFLOW_OF_THE_TOOLKIT, ".gitignore", ".claude/skills/", ".claude/agents/", SETTINGS,
    ".git/config", ".git/info/attributes", ".git/info/exclude",
)
"""Everything the installer may write into a host (a prefix ending in ``/`` is a folder), the pre-commit config apart: each test names it."""
SKIPPED_IN_GIT = (".git/objects", ".git/index")
"""Git's own bookkeeping that a read-only git command may rewrite; every other file under ``.git`` is hashed."""


@pytest.fixture(autouse=True)
def isolated_git_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git reads no global ignore file or configuration: the exclude line of the settings file depends on the host's own rules alone."""
    home = tmp_path / "home"
    home.mkdir()
    for name, value in (("HOME", home), ("XDG_CONFIG_HOME", home / "xdg"), ("GIT_CONFIG_GLOBAL", os.devnull), ("GIT_CONFIG_SYSTEM", os.devnull)):
        monkeypatch.setenv(name, str(value))


@pytest.fixture
def pre_commit_runs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, Path]]:
    """Replace the pre-commit runner; the list holds (binary, host root) of every call."""
    runs: list[tuple[Path, Path]] = []
    monkeypatch.setattr(hi, "_run_pre_commit_install", lambda binary, root: (runs.append((binary, root)) or (0, "installed")))
    return runs


# --- the hosts and the command ---------------------------------------------------------------------------------------------


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)


def scratch_host(tmp_path: Path, fixture: str) -> Path:
    """A git repository with the files of ``tests/fixtures/hosts/<fixture>`` in place, an empty ``spec/`` and the live toolkit by a symlink."""
    host = tmp_path / "host"
    host.mkdir()
    _git_init(host)
    (host / "spec").mkdir()
    (host / "devspec_toolkit").symlink_to(REPO, target_is_directory=True)
    source = FIXTURES / fixture
    shutil.copy(source / CONFIG, host / CONFIG)
    shutil.copytree(source / ".github", host / ".github")
    (host / ".claude").mkdir()
    shutil.copy(source / "claude_settings.local.json", host / SETTINGS)
    return host


def fresh_init_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """What ``init`` leaves: ``init_project.main`` into an empty git repository with its subprocesses (``uv``, the venv, the delegate) stubbed."""
    host = tmp_path / "host"
    host.mkdir()
    _git_init(host)
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import init_project

    monkeypatch.setattr(sys, "argv", ["init_project.py", "--target", str(host), "--toolkit-root", str(REPO)])
    with patch("init_project.run_cmd"), patch("init_project.run_install_delegate", return_value=0), patch("init_project.shutil.which", return_value="/usr/bin/uv"):
        with redirect_stdout(io.StringIO()):
            init_project.main()
    return host


def update(host: Path, *flags: str, toolkit: Path | None = None) -> dict:
    """``specdev update spec --repo-root <toolkit> --git-root <host> --install-only --json [flags]`` run in *host*; returns the ``host_install`` object."""
    toolkit = toolkit or host / "devspec_toolkit"
    argv = ["specdev-tools", "update", "spec", "--repo-root", str(toolkit), "--git-root", str(host), "--install-only", "--json", *flags]
    out, err = io.StringIO(), io.StringIO()
    previous = Path.cwd()
    os.chdir(host)
    try:
        with redirect_stdout(out), redirect_stderr(err), patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", argv):
            try:
                code = cli.main()
            except SystemExit as exit_:
                code = int(exit_.code or 0)
    finally:
        os.chdir(previous)
    assert (code or 0) == 0, out.getvalue() + err.getvalue()
    return json.loads(out.getvalue())["host_install"]


def statuses(report: dict) -> dict[str, str]:
    return {name: piece["status"] for name, piece in report["pieces"].items()}


def codes(report: dict) -> dict[str, list[str]]:
    """The finding codes of each piece that reports any."""
    return {name: [finding["code"] for finding in piece["findings"]] for name, piece in report["pieces"].items() if piece["findings"]}


def fingerprint(host: Path) -> dict[str, str]:
    """A hash of every file of the host, ``.git`` included (``.git/config``, ``.git/info/*``, the hooks); a link is hashed as its target string."""
    found: dict[str, str] = {}
    for folder, dirs, files in os.walk(host):
        relative = Path(folder).relative_to(host).as_posix()
        for name in list(dirs):
            path = Path(folder, name)
            if path.is_symlink():
                files.append(name)  # os.walk lists a link to a folder among the folders
                dirs.remove(name)
            elif (name if relative == "." else f"{relative}/{name}") in SKIPPED_IN_GIT:
                dirs.remove(name)
        for name in files:
            path = Path(folder, name)
            key = path.relative_to(host).as_posix()
            if key not in SKIPPED_IN_GIT:
                found[key] = "link:" + os.readlink(path) if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def installer_may_write(path: str) -> bool:
    return any(path == allowed or (allowed.endswith("/") and path.startswith(allowed)) for allowed in THE_INSTALLERS_OWN_PATHS)


def assert_only_the_installer_wrote(before: dict[str, str], after: dict[str, str], *also: str) -> None:
    """Nothing was deleted, and every file that is new or different is one the installer may write (or one the test names in *also*)."""
    assert not [path for path in before if path not in after], "the installer deleted a file"
    stray = {path for path, digest in after.items() if before.get(path) != digest and not installer_may_write(path) and path not in also}
    assert not stray, f"written outside what the installer may write: {sorted(stray)}"


def second_run_changes_nothing(host: Path, first: dict, **kwargs) -> dict:
    """Run the command again: no byte of the host moves, no piece is created or refreshed; returns that report."""
    before = fingerprint(host)
    second = update(host, **kwargs)
    assert fingerprint(host) == before, "a second run wrote something"
    assert not {name for name, status in statuses(second).items() if status in {hi.CREATED, hi.REFRESHED}}
    assert list(second["pieces"]) == list(first["pieces"]) == PIECES
    return second


def settings_of(host: Path) -> dict:
    return json.loads((host / SETTINGS).read_text(encoding="utf-8"))


def own_lines_outside_the_block(text: str) -> list[str]:
    before, _, after = hi.split_marked_block(text)  # ``before`` ends with the begin marker line, ``after`` starts with the end marker line
    outside = before.rstrip("\n").rsplit("\n", 1)[0] + "\n" + after.split("\n", 1)[1]
    return [line for line in outside.splitlines() if line.strip()]


# --- w ------------------------------------------------------------------------------------------------------------------------


def test_update_installs_every_piece_into_the_w_fixture_and_a_second_run_changes_nothing(tmp_path: Path, pre_commit_runs: list) -> None:
    host = scratch_host(tmp_path, "w")
    own_config = (host / CONFIG).read_bytes()
    own_workflow = (host / ".github" / "workflows" / "spec_validation.yml").read_bytes()
    own_settings = settings_of(host)
    before = fingerprint(host)

    first = update(host)
    assert list(first["pieces"]) == PIECES and first["skipped"] is None
    assert statuses(first) == {
        "pre-commit": hi.DRIFT,  # hand-written toolkit hooks are left as they are
        "merge-driver": hi.CREATED, "workflows": hi.CREATED, "wrappers": hi.CREATED, "claude-links": hi.CREATED,
        "ask-rules": hi.REFRESHED,  # the host's settings file exists: the rules are merged into it
        "gitignore": hi.CREATED,
    }
    assert codes(first) == {
        "pre-commit": ["W930", "W930"],  # the differing spec-check hook, and the template hooks the config lacks
        "workflows": ["W935", "W932", "W932", "W932", "W932"],  # no setup_command; validate-all, matrix and trace_matrix.json (twice) in the host's workflow
    }
    pre_commit = first["pieces"]["pre-commit"]["findings"]
    assert [(finding["command"], finding["file"]) for finding in pre_commit] == [("spec-check", CONFIG), ("", CONFIG)]
    retired = [finding for finding in first["pieces"]["workflows"]["findings"] if finding["code"] == "W932"]
    assert {finding["file"] for finding in retired} == {".github/workflows/spec_validation.yml"}
    assert [finding["command"] for finding in retired] == ["validate-all", "matrix", "trace_matrix.json", "trace_matrix.json"]
    assert first["pieces"]["workflows"]["findings"][0]["file"] == "spec/common/host_declarations.json"

    after = fingerprint(host)
    assert_only_the_installer_wrote(before, after)
    assert (host / CONFIG).read_bytes() == own_config, "drift leaves the hand-written hooks as they are"
    assert (host / ".github" / "workflows" / "spec_validation.yml").read_bytes() == own_workflow, "W932 only reports: the host's workflow is not rewritten"
    merged = settings_of(host)
    assert {key: value for key, value in merged.items() if key != "permissions"} == {key: value for key, value in own_settings.items() if key != "permissions"}
    assert merged["permissions"]["allow"] == own_settings["permissions"]["allow"] and merged["permissions"]["deny"] == own_settings["permissions"]["deny"]
    assert merged["permissions"]["ask"][:1] == own_settings["permissions"]["ask"] and len(merged["permissions"]["ask"]) == 1 + len(hi.ask_rules_for())
    assert (host / "tools" / "run_specdev.sh").is_file() and (host / WORKFLOW_OF_THE_TOOLKIT).is_file()
    assert (host / ".claude" / "skills" / "specdev-step").is_symlink() and ".specdev/" in (host / ".gitignore").read_text(encoding="utf-8").splitlines()
    driver = subprocess.run(["git", "config", "merge.specdev-trace-lock.driver"], cwd=host, capture_output=True, text=True).stdout.strip()
    assert driver.endswith("lock merge %O %A %B %P")
    assert SETTINGS in (host / ".git" / "info" / "exclude").read_text(encoding="utf-8"), "no ignore rule covers the settings file: it is excluded in the clone"
    assert len(pre_commit_runs) >= 1 and all(root == host for _, root in pre_commit_runs)

    second = second_run_changes_nothing(host, first)
    assert statuses(second) == {name: hi.CURRENT for name in PIECES} | {"pre-commit": hi.DRIFT}, "the drift stays reported until it is adopted"
    assert codes(second) == codes(first)

    adopted = update(host, "--adopt")
    assert statuses(adopted) == {name: hi.CURRENT for name in PIECES} | {"pre-commit": hi.REFRESHED}
    assert codes(adopted) == {"workflows": ["W935", "W932", "W932", "W932", "W932"]}, "the drift is gone; the findings about the host's own workflow are not adoptable"
    replaced = (host / CONFIG).read_text(encoding="utf-8")
    assert "id: web-format" in replaced and "id: web-unit" in replaced and "id: trailing-whitespace" in replaced, "the host's own hooks stay"
    assert "Step gate (full run)" not in replaced, "the hand-written copy is replaced by the managed block"
    assert_only_the_installer_wrote(after, fingerprint(host), CONFIG)
    final = second_run_changes_nothing(host, adopted)
    assert statuses(final) == {name: hi.CURRENT for name in PIECES}
    assert statuses(update(host, "--adopt")) == {name: hi.CURRENT for name in PIECES}, "adopting what is adopted is a no-op"


# --- p ------------------------------------------------------------------------------------------------------------------------


def test_update_installs_every_piece_into_the_p_fixture_and_a_second_run_changes_nothing(tmp_path: Path, pre_commit_runs: list) -> None:
    host = scratch_host(tmp_path, "p")
    own_config_lines = [line for line in (host / CONFIG).read_text(encoding="utf-8").splitlines() if line.strip()]
    own_workflow = (host / ".github" / "workflows" / "ci.yml").read_bytes()
    own_settings = settings_of(host)
    before = fingerprint(host)

    first = update(host)
    assert statuses(first) == {
        "pre-commit": hi.REFRESHED,  # no toolkit hooks of its own: the managed block is appended
        "merge-driver": hi.CREATED, "workflows": hi.CREATED, "wrappers": hi.CREATED, "claude-links": hi.CREATED,
        "ask-rules": hi.REFRESHED, "gitignore": hi.CREATED,
    }
    assert codes(first) == {"workflows": ["W935"]}, "nothing of p's is a retired command, and no hook of p differs from the template"
    after = fingerprint(host)
    assert_only_the_installer_wrote(before, after, CONFIG)
    assert own_lines_outside_the_block((host / CONFIG).read_text(encoding="utf-8")) == own_config_lines, "outside the marked block the config is the host's, line for line"
    assert (host / ".github" / "workflows" / "ci.yml").read_bytes() == own_workflow
    merged = settings_of(host)
    assert merged["permissions"]["allow"] == own_settings["permissions"]["allow"] and merged["permissions"]["ask"] == hi.ask_rules_for(), "p had no ask list: it gets the rules, its allow list is untouched"
    assert set(merged) == set(own_settings) == {"permissions"} and set(merged["permissions"]) == {"allow", "ask"}
    assert len(pre_commit_runs) >= 1

    second = second_run_changes_nothing(host, first)
    assert statuses(second) == {name: hi.CURRENT for name in PIECES}
    assert codes(second) == {"workflows": ["W935"]}


# --- a fresh init layout ------------------------------------------------------------------------------------------------------


def test_update_on_a_fresh_init_layout_is_a_noop_the_second_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pre_commit_runs: list) -> None:
    host = fresh_init_host(tmp_path, monkeypatch)
    assert not (host / CONFIG).exists() and not (host / ".claude").exists(), "init itself installs none of the pieces (it delegates)"
    before = fingerprint(host)

    first = update(host, toolkit=REPO)
    assert statuses(first) == {
        "pre-commit": hi.CREATED, "merge-driver": hi.CREATED, "workflows": hi.CREATED,
        "wrappers": hi.REFRESHED,  # init wrote unrendered copies; the installer renders them with the venv name
        "claude-links": hi.CREATED,
        "ask-rules": hi.CREATED,  # there is no settings file yet
        "gitignore": hi.REFRESHED,  # init wrote a .gitignore: the line is appended
    }
    assert codes(first) == {"workflows": ["W935"]}
    after = fingerprint(host)
    assert_only_the_installer_wrote(before, after, CONFIG)
    gitignore = (host / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".specdev/" in gitignore and "devspec_env/" in gitignore, "init's line stays, the installer's is added"
    assert settings_of(host) == {"permissions": {"ask": hi.ask_rules_for()}}
    assert len(pre_commit_runs) >= 1

    second = second_run_changes_nothing(host, first, toolkit=REPO)
    assert statuses(second) == {name: hi.CURRENT for name in PIECES} and codes(second) == {"workflows": ["W935"]}
