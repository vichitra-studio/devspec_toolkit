"""``specdev release prep`` through ``main([...])``: it runs the dev and CI bindings that have no valid evidence for the code tree, writes the
evidence and nothing else, runs nothing on a second pass, and exits 1 when a binding fails.

Every test works on a git copy of the worked example made release-ready (``unit.release._support``).  The one binding of the example is given
a command that passes (``PASSING``) unless a test wants it to fail.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit.graph._synth import git
from unit.lifecycle._milestone_support import cli_run
from unit.proof._support import GUARD, PASSING
from unit.release._support import release_host
from unit.verify._support import commit_all
from integration._release_support import BINDING, identity, snapshot  # noqa: F401  (the fixture ``identity``)

pytestmark = pytest.mark.usefixtures("identity")
EVIDENCE = f"spec/extras/verification/evd-{BINDING.removeprefix('ver-')}-ci.json"
FAILING = "exit 3"


def _bind(host: Path, command: str) -> None:
    """Give the one binding of the host *command* (with the guard ``GUARD``) and commit it."""
    path = host / "spec" / "extras" / "verification" / f"{BINDING}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["records"][0].update(commands=[command], output_guard=GUARD)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    commit_all(host, "bind")


def _evidence(host: Path) -> dict:
    return json.loads((host / EVIDENCE).read_text(encoding="utf-8"))["records"][0]


def test_prep_runs_unproven_bindings_and_writes_records(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    _bind(host, PASSING)
    assert not (host / EVIDENCE).exists()
    code, out, err = cli_run(host, "release", "prep")
    assert code == 0, out + err
    assert "1 binding(s) run, 1 passed, 0 failed; 0 already proven" in out and f"PASS {BINDING}" in out
    assert "nothing blocks the release" in out and "not committed" in out
    assert (host / EVIDENCE).is_file()
    assert git(host, "status", "--porcelain").split() == ["??", "spec/extras/verification/evd-password-reset-expired-token-ci.json"], "the evidence is the only change"


def test_prep_second_run_on_same_tree_runs_nothing(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    _bind(host, PASSING)
    assert cli_run(host, "release", "prep")[0] == 0
    first = (host / EVIDENCE).read_text(encoding="utf-8")
    code, out, err = cli_run(host, "release", "prep")
    assert code == 0, out + err
    assert "0 binding(s) run" in out and f"already proven: {BINDING}" in out
    assert (host / EVIDENCE).read_text(encoding="utf-8") == first, "a proven binding is not run again"
    document = json.loads(cli_run(host, "release", "prep", "--json")[1])
    assert document["run"] == [] and document["already_proven"] == [BINDING] and document["evidence"] == [] and document["failed"] == []
    commit_all(host, "evidence")
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0")
    assert code == 0 and "annotated tag created" in out, out + err


def test_prep_failure_exit_nonzero(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    _bind(host, FAILING)
    code, out, _ = cli_run(host, "release", "prep")
    assert code == 1 and f"FAIL {BINDING}" in out and "exit 3" in out
    assert _evidence(host)["exit_code"] == 3, "the failed run is recorded"
    code, out, _ = cli_run(host, "release", "prep", "--json")
    document = json.loads(out)
    assert code == 1 and document["run"] == [BINDING], "a failed binding is run again on the same tree"
    assert document["failed"] == [{"binding": BINDING, "evidence": f"evd-{BINDING.removeprefix('ver-')}-ci", "exit_code": 3, "guard_matched": False}]


def test_prep_does_not_commit(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    _bind(host, PASSING)
    head, tags, before = git(host, "rev-parse", "HEAD"), git(host, "tag"), snapshot(host)
    assert cli_run(host, "release", "prep")[0] == 0
    after = snapshot(host)
    assert git(host, "rev-parse", "HEAD") == head and git(host, "tag") == tags and after["head"] == before["head"]
    assert git(host, "diff", "--cached", "--name-only") == "", "nothing is staged"
    changed = {path for path in after["files"] if after["files"][path] != before["files"].get(path)}
    assert changed == {EVIDENCE} and after["refs"] == before["refs"], changed
