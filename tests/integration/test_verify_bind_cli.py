"""``specdev verify bind`` through the CLI, on a git copy of the worked example."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit.graph._synth import git
from unit.trace._lock_support import git_copy_of_example, run_on_example

FIXTURE = "fix-password-reset-expired-token"
RECORD = "ver-password-reset-expired-token"
GUARD = "expired token .*passed"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return git_copy_of_example(tmp_path / "host")


def _bind(host: Path, *flags: str) -> tuple[int, str]:
    return run_on_example(host, "verify", "bind", FIXTURE, "--command", "echo expired token passed", "--guard", GUARD, *flags)


def test_bind_cli_prints_the_record_id_stage_and_reasoning(host: Path) -> None:
    code, out = _bind(host)
    assert code == 0, out
    assert f"binding {RECORD} replaced (stage dev, extras/verification/{RECORD}.json)" in out
    assert "proves: ac-password-reset-3, api-password-reset-confirm" in out
    assert "ac-password-reset-3 needs dev, api-password-reset-confirm needs dev" in out


def test_bind_cli_json_envelope(host: Path) -> None:
    code, out = _bind(host, "--json")
    assert code == 0, out
    document = json.loads(out)
    assert (document["command"], document["record_id"], document["stage"], document["replaced"]) == ("verify bind", RECORD, "dev", True)
    assert document["proves"] == ["ac-password-reset-3", "api-password-reset-confirm"]
    assert document["reasoning"][0] == {"node": "ac-password-reset-3", "stage": "dev"}


def test_bind_writes_only_the_record_file(host: Path) -> None:
    code, out = _bind(host, "--proves", "api-password-reset-confirm")
    assert code == 0, out
    assert [line.split()[-1] for line in git(host, "status", "--porcelain").splitlines()] == [f"spec/extras/verification/{RECORD}.json"]
    code, out = _bind(host, "--id", "ver-a-second-binding", "--proves", "ac-password-reset-3")
    assert code == 0, out
    changed = [line.split()[-1] for line in git(host, "status", "--porcelain").splitlines()]
    assert changed == [f"spec/extras/verification/{RECORD}.json", "spec/extras/verification/ver-a-second-binding.json"]


def test_a_refused_bind_exits_one_and_writes_nothing(host: Path) -> None:
    code, out = run_on_example(host, "verify", "bind", FIXTURE, "--command", "true")
    assert code == 1 and "E332" in out
    code, out = _bind(host, "--stage", "ci")
    assert code == 1 and "E330" in out
    assert git(host, "status", "--porcelain") == ""
