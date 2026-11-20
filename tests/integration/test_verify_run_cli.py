"""``specdev verify run`` through the CLI, on a git copy of the worked example with a little code."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.verify.records import records_folder, write_binding
from unit.graph._synth import ROOT, git
from unit.trace._lock_support import git_copy_of_example, run_on_example

FIXTURE = "fix-password-reset-expired-token"
RECORDS = Path("spec") / "extras" / "verification"


def _host(tmp_path: Path, command: str, guard: str = "expected line") -> Path:
    host = git_copy_of_example(tmp_path / "host")
    (host / RECORDS / "ver-password-reset-expired-token.json").unlink()
    (host / "src").mkdir()
    (host / "src" / "hello.txt").write_text("hello\n", encoding="utf-8")
    item = {"verification_id": "ver-alpha", "verifies": [FIXTURE], "stage": "dev", "commands": [command], "output_guard": guard}
    write_binding(records_folder(str(host / "spec")), str(ROOT), item)
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "binding")
    return host


def _evidence(host: Path) -> dict:
    return json.loads((host / RECORDS / "evd-alpha-dev.json").read_text())["records"][0]


def test_run_cli_exits_non_zero_on_a_failing_binding(tmp_path: Path) -> None:
    host = _host(tmp_path, "echo expected line; exit 2")
    code, out = run_on_example(host, "verify", "run", "ver-alpha")
    assert code == 1 and "FAIL ver-alpha at dev (exit 2)" in out
    assert _evidence(host)["exit_code"] == 2


def test_broken_test_fails_its_binding(tmp_path: Path) -> None:
    host = _host(tmp_path, "python3 -c \"import sys; print('collected 1 item'); sys.exit(1)\"", guard="collected 1 item")
    code, out = run_on_example(host, "verify", "run", "--all")
    assert code == 1 and "FAIL ver-alpha" in out
    assert (_evidence(host)["exit_code"], _evidence(host)["guard_matched"]) == (1, True)


def test_a_passing_run_exits_zero_and_json_lists_the_evidence(tmp_path: Path) -> None:
    host = _host(tmp_path, "echo expected line")
    code, out = run_on_example(host, "verify", "run", "ver-alpha", "--json")
    assert code == 0, out
    document = json.loads(out)
    assert (document["passed"], document["failed"], document["recorded"]) == (1, 0, True)
    assert document["results"][0]["evidence_id"] == "evd-alpha-dev" and document["results"][0]["passed"] is True


def test_no_record_writes_no_evidence_file(tmp_path: Path) -> None:
    host = _host(tmp_path, "echo expected line")
    code, out = run_on_example(host, "verify", "run", "ver-alpha", "--no-record")
    assert code == 0 and "nothing recorded" in out
    assert git(host, "status", "--porcelain") == ""


def test_milestone_selection_runs_the_bindings_of_its_verifiers(tmp_path: Path) -> None:
    host = _host(tmp_path, "echo expected line")
    code, out = run_on_example(host, "verify", "run", "--milestone", "ms-account-recovery")
    assert code == 0 and "PASS ver-alpha at dev" in out
    code, out = run_on_example(host, "verify", "run", "--milestone", "ms-nowhere")
    assert code == 1 and "E706" in out


@pytest.mark.parametrize("flags", [(), ("--all", "--milestone", "ms-account-recovery"), ("ver-alpha", "--all")])
def test_a_run_with_no_selection_or_two_is_a_usage_error(tmp_path: Path, flags: tuple[str, ...]) -> None:
    host = _host(tmp_path, "true")
    code, out = run_on_example(host, "verify", "run", *flags)
    assert code == 2 and "exactly one" in out
