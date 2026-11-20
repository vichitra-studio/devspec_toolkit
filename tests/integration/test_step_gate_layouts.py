"""``spec-check --step`` and ``--paths`` read git history and seed documents: the same scenario from three places (WI-M6a-04).

The scenario is the worked example with a broken link in step 04 (the delta ``broken_link_in_step_04``) that is not
committed: step 04 owns it, a later step sees it as a new upstream error.  It is run from the host root (as the
pre-commit hook does, with ``--git-root .``), from the folder above the host with no ``--git-root``, and in a nested
layout (``host/sub/spec``, seed documents at ``host/docs/seed``) with and without ``--git-root``.  Every layout gives
the same classification; what differs is only which notes go to stderr.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from integration._step_gate_support import (
    apply_delta,
    attest,
    commit_all,
    nested_step_gate_host,
    run_split,
    step_gate_host,
)
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES
from unit.graph._synth import ROOT, git
from unit.trace._lock_support import EXAMPLE_HOST

SCHEMA = json.loads((ROOT / "tests" / "unit" / "validation" / "step_gate_output.schema.json").read_text(encoding="utf-8"))
DELTA = ["broken_link_in_step_04"]
SEED_NOTE = "seed documents not found"
SEED_FILE = "docs/seed/seed_accounts.md"
STEP_04_FILE = "04_fr_list.json"
NESTED = "sub/spec"
SPEC = "spec"
BROKEN = [("E700", "step:04", "fr-broken-link")]

Classification = dict[str, Any]


def _brief(findings: list[dict[str, Any]]) -> list[tuple[str, str, str | None]]:
    return sorted((f["code"], f["owner"], f.get("node_id")) for f in findings)


def classification(gate: dict[str, Any]) -> Classification:
    """What the gate decided, without the gate-owned findings (which differ when a seed document cannot be found)."""
    return {
        "steps": gate["steps"],
        "blocking": _brief(gate["blocking"]),
        "own_warnings": _brief(gate["own_warnings"]),
        "upstream_debt": _brief(gate["upstream_debt"]),
        "pending": {owner: _brief(found) for owner, found in gate["pending"].items()},
        "result": gate["result"],
    }


def _run_gate(capsys: pytest.CaptureFixture[str], spec: str, flags: list[str], *gate_flags: str) -> tuple[int, Classification, str]:
    """``spec-check <spec> <flags> <gate_flags> --json``: the exit code, the classification and stderr (stdout must be one JSON document)."""
    code, out, err = run_split(capsys, "spec-check", spec, "--repo-root", str(ROOT), *flags, *gate_flags, "--json")
    payload = json.loads(out)
    jsonschema.validate(payload, SCHEMA)
    return code, classification(payload["step_gate"]), err


def _host_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[str], str]:
    host = step_gate_host(tmp_path / "host", DELTA)
    monkeypatch.chdir(host)
    return "spec", ["--spec-root", "./spec", "--git-root", "."], "spec"


def _folder_above(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[str], str]:
    step_gate_host(tmp_path / "host", DELTA)
    monkeypatch.chdir(tmp_path)
    return "host/spec", ["--spec-root", "host/spec"], "host/spec"


def _nested_with_git_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[str], str]:
    monkeypatch.chdir(nested_step_gate_host(tmp_path / "host", DELTA))
    return "sub/spec", ["--spec-root", "./sub/spec", "--git-root", "."], "sub/spec"


def _nested_without_git_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[str], str]:
    monkeypatch.chdir(nested_step_gate_host(tmp_path / "host", DELTA))
    return "sub/spec", ["--spec-root", "./sub/spec"], "sub/spec"


STEP_04 = {"steps": ["04"], "blocking": BROKEN, "own_warnings": [], "upstream_debt": [], "result": "blocked"}
STEP_05 = {"steps": ["05"], "blocking": BROKEN, "own_warnings": [], "upstream_debt": [], "result": "blocked"}


def _assert_decided(found: Classification, expected: Classification) -> None:
    assert {key: found[key] for key in expected} == expected, found


# --- --step -----------------------------------------------------------------------------------------------------

def test_step_gate_from_the_host_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    spec, flags, _prefix = _host_root(tmp_path, monkeypatch)
    for step, expected in (("04", STEP_04), ("05", STEP_05)):
        code, found, err = _run_gate(capsys, spec, flags, "--step", step)
        assert code == 1 and SEED_NOTE not in err, err
        _assert_decided(found, expected)
    assert {code for findings in found["pending"].values() for code, *_rest in findings} <= GRAPH_CHECK_CODES


def test_step_gate_from_the_folder_above_without_git_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, _prefix = _folder_above(tmp_path, monkeypatch)
    for step, expected in (("04", STEP_04), ("05", STEP_05)):
        code, found, err = _run_gate(capsys, spec, flags, "--step", step)
        assert code == 1 and SEED_NOTE not in err, err
        _assert_decided(found, expected)


def test_step_gate_nested_layout_with_git_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, _prefix = _nested_with_git_root(tmp_path, monkeypatch)
    for step, expected in (("04", STEP_04), ("05", STEP_05)):
        code, found, err = _run_gate(capsys, spec, flags, "--step", step)
        assert code == 1 and SEED_NOTE not in err, err
        _assert_decided(found, expected)


def test_step_gate_nested_layout_without_git_root_notes_the_missing_seeds_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, _prefix = _nested_without_git_root(tmp_path, monkeypatch)
    code, found, err = _run_gate(capsys, spec, flags, "--step", "05")
    assert code == 1
    _assert_decided(found, STEP_05)
    notes = [line for line in err.splitlines() if SEED_NOTE in line]
    assert len(notes) == 1 and "--git-root" in notes[0], err


def test_a_committed_error_is_debt_in_every_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    host = nested_step_gate_host(tmp_path / "host", DELTA)
    commit_all(host, "the broken link is on the branch")
    monkeypatch.chdir(host)
    code, found, _err = _run_gate(capsys, "sub/spec", ["--spec-root", "./sub/spec", "--git-root", "."], "--step", "05")
    assert code == 0 and found["upstream_debt"] == BROKEN and found["blocking"] == []


def test_a_spec_with_no_git_repository_has_no_baseline_and_every_upstream_error_is_new(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    apply_delta(host, DELTA[0])
    attest(host)
    flags = ["--spec-root", str(host / "spec"), "--git-root", str(host)]
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), "--repo-root", str(ROOT), *flags, "--step", "05")
    assert code == 1 and out.splitlines()[0].endswith("base: unavailable"), out
    assert "[04 new upstream]" in out
    code, found, _err = _run_gate(capsys, str(host / "spec"), flags, "--step", "05")
    _assert_decided(found, STEP_05)


def test_json_stays_one_document_while_notes_go_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, _prefix = _nested_without_git_root(tmp_path, monkeypatch)
    code, out, err = run_split(capsys, "spec-check", spec, "--repo-root", str(ROOT), *flags, "--step", "05", "--json")
    assert code == 1 and SEED_NOTE in err and SEED_NOTE not in out
    jsonschema.validate(json.loads(out), SCHEMA)


# --- --paths ----------------------------------------------------------------------------------------------------

def test_paths_gate_from_the_host_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    spec, flags, prefix = _host_root(tmp_path, monkeypatch)
    code, found, err = _run_gate(capsys, spec, flags, "--paths", f"{prefix}/{STEP_04_FILE}")
    assert code == 1 and SEED_NOTE not in err, err
    _assert_decided(found, STEP_04)


def test_paths_gate_from_the_folder_above_without_git_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, _prefix = _folder_above(tmp_path, monkeypatch)
    code, found, err = _run_gate(capsys, spec, flags, "--paths", f"spec/{STEP_04_FILE}")
    assert code == 1 and SEED_NOTE not in err, err
    _assert_decided(found, STEP_04)


def test_paths_gate_nested_layout_with_git_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, prefix = _nested_with_git_root(tmp_path, monkeypatch)
    code, found, err = _run_gate(capsys, spec, flags, "--paths", f"{prefix}/{STEP_04_FILE}", SEED_FILE)
    assert code == 1 and SEED_NOTE not in err and "seed document edited: run specdev stale" in err, err
    _assert_decided(found, {**STEP_04, "steps": ["00", "02", "04"]})


def test_paths_outside_the_host_root_with_git_root_leave_the_git_root_advice_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, flags, prefix = _nested_with_git_root(tmp_path, monkeypatch)
    _code, _found, err = _run_gate(capsys, spec, flags, "--paths", f"{prefix}/{STEP_04_FILE}", "../README.md")
    assert "1 path lies outside the host root and maps to no step" in err and "--git-root" not in err, err


def test_paths_gate_nested_layout_without_git_root_counts_the_paths_that_leave_the_host_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The host root is ``sub`` here: the seed document at the top of the repository lies outside it."""
    spec, flags, _prefix = _nested_without_git_root(tmp_path, monkeypatch)
    seed = str(Path.cwd() / SEED_FILE)
    code, out, err = run_split(capsys, "spec-check", spec, "--repo-root", str(ROOT), *flags, "--paths", seed)
    assert (code, out) == (0, ""), out
    assert "1 path lies outside the host root and maps to no step" in err and "--git-root" in err, err
    code, found, err = _run_gate(capsys, spec, flags, "--paths", f"sub/spec/{STEP_04_FILE}", seed, SEED_FILE)
    assert code == 1 and "2 paths lie outside the host root" in err, err
    _assert_decided(found, STEP_04)


# --- the baseline in every layout ---------------------------------------------------------------------------------

def _on_a_branch_after_committing_the_error(top: Path, spec_prefix: str) -> None:
    """The broken link of step 04 is committed on ``main``; ``feat`` is one empty commit ahead of it."""
    apply_delta(top, DELTA[0], spec_prefix)
    attest(top, spec_prefix)
    commit_all(top, "the broken link is at the base")
    git(top, "checkout", "-q", "-b", "feat")
    git(top, "commit", "-q", "--allow-empty", "-m", "a branch commit")


def _example_with_spec_at(top: Path, spec_prefix: str) -> None:
    """The worked example copied to *top* (a git repository, one commit) with its spec folder moved to *spec_prefix*."""
    shutil.copytree(EXAMPLE_HOST, top)
    if spec_prefix == ".":  # the spec folder is the repository root: its files move up
        for entry in list((top / SPEC).iterdir()):
            shutil.move(str(entry), str(top / entry.name))
        (top / SPEC).rmdir()
    elif spec_prefix != SPEC:
        (top / spec_prefix).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(top / SPEC), str(top / spec_prefix))
    git(top, "init", "-q", "-b", "main")
    commit_all(top, "worked example")


def _layout_spec_under_the_git_root(tmp_path: Path) -> tuple[Path, str, list[str]]:
    top = tmp_path / "host"
    _example_with_spec_at(top, SPEC)
    _on_a_branch_after_committing_the_error(top, SPEC)
    return top, "spec", ["--spec-root", "./spec", "--git-root", "."]


def _layout_nested_spec_with_git_root_at_the_top(tmp_path: Path) -> tuple[Path, str, list[str]]:
    top = tmp_path / "host"
    _example_with_spec_at(top, NESTED)
    _on_a_branch_after_committing_the_error(top, NESTED)
    return top, NESTED, ["--spec-root", f"./{NESTED}", "--git-root", "."]


def _layout_git_root_is_a_subfolder_of_the_repository(tmp_path: Path) -> tuple[Path, str, list[str]]:
    top = tmp_path / "host"
    _example_with_spec_at(top, NESTED)
    _on_a_branch_after_committing_the_error(top, NESTED)
    return top / "sub", "spec", ["--spec-root", "./spec", "--git-root", "."]


def _layout_spec_folder_is_the_git_root(tmp_path: Path) -> tuple[Path, str, list[str]]:
    top = tmp_path / "host"
    _example_with_spec_at(top, ".")
    _on_a_branch_after_committing_the_error(top, ".")
    return top, ".", ["--spec-root", ".", "--git-root", "."]


def _layout_spec_folder_named_through_a_symlink(tmp_path: Path) -> tuple[Path, str, list[str]]:
    top = tmp_path / "host"
    _example_with_spec_at(top, SPEC)
    _on_a_branch_after_committing_the_error(top, SPEC)
    (tmp_path / "link").symlink_to(top / SPEC, target_is_directory=True)
    return tmp_path, "link", ["--spec-root", "./link", "--git-root", "host"]


BASELINE_LAYOUTS = {
    "spec-under-git-root": _layout_spec_under_the_git_root,
    "nested-spec-git-root-at-top": _layout_nested_spec_with_git_root_at_the_top,
    "git-root-is-a-subfolder": _layout_git_root_is_a_subfolder_of_the_repository,
    "spec-folder-is-the-git-root": _layout_spec_folder_is_the_git_root,
    "spec-folder-through-a-symlink": _layout_spec_folder_named_through_a_symlink,
}


@pytest.mark.parametrize("layout", sorted(BASELINE_LAYOUTS))
def test_the_baseline_resolves_in_every_layout_and_an_error_committed_at_the_base_is_old(
    layout: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cwd, spec, flags = BASELINE_LAYOUTS[layout](tmp_path)
    monkeypatch.chdir(cwd)
    base = git(cwd / flags[flags.index("--git-root") + 1], "rev-parse", "main")
    code, out, err = run_split(capsys, "spec-check", spec, "--repo-root", str(ROOT), *flags, "--step", "05")
    assert out.splitlines()[0].endswith(f"base: main {base[:12]} (merge-base)"), (out, err)
    assert "UPSTREAM DEBT" in out and "[04 new upstream]" not in out and code == 0, (out, err)


def test_a_spec_folder_outside_the_git_root_has_no_baseline_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    top = tmp_path / "host"
    _example_with_spec_at(top, SPEC)
    outside = tmp_path / "elsewhere" / "spec"
    shutil.copytree(top / SPEC, outside)
    monkeypatch.chdir(tmp_path)
    code, out, err = run_split(
        capsys, "spec-check", str(outside), "--repo-root", str(ROOT), "--spec-root", str(outside), "--git-root", str(top), "--step", "05"
    )
    assert out.splitlines()[0].endswith("base: unavailable"), (out, err)
    assert f"the spec folder {outside} is not inside the git root {top}, so it cannot be found in the repository" in err, err
