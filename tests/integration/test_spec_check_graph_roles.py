"""``spec-check`` with the graph checks real: the eight entries on the worked example, the owners of their findings, a 1.1.1-shaped corpus, a malformed file, promotion and the summary golden."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import run_split
from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import make_error
from specdev_tools.validation.graph_checks import register_graph_check, unregister_graph_check
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES
from specdev_tools.validation.spec_check import run_spec_check as run_plain_spec_check
from unit.graph._synth import git
from unit.trace._lock_support import ROOT, git_copy_of_example

GRAPH_CHECKS = ("no-dangling", "term-use", "verifier-rules", "cross-cutting", "refinement", "scaffold-paths", "seed-routes", "prose-ids")
LEGACY = ROOT / "tests" / "fixtures" / "graph_checks" / "legacy"
GOLDEN = ROOT / "tests" / "fixtures" / "step_gate" / "spec_check_summary.golden"

STEP_14_FILE = "14_roadmap.json"
DANGLING_AT_14 = ("err-password-reset-confirm-token-expired", "nfr-latency-reset-email", "threat-reset-token-replay", "ec-token-at-expiry-second")
DANGLING_AT_12 = ("dev", "staging", "prod", "secret-mailrelay-api-key", "secret-reset-token-signing-key")


def _gate(capsys: pytest.CaptureFixture[str], host: Path, step: str) -> dict[str, Any]:
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *flags, "--step", step, "--json")
    return json.loads(out)["step_gate"]


def _e740(findings: list[dict[str, Any]]) -> set[str]:
    return {finding["node_id"] for finding in findings if finding["code"] == "E740"}


def test_half_authored_example_shows_pending_owners(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """With step 14 not authored, the nodes that only a step-14 node can use are pending under owner 14, those a job uses under 12; nothing blocks step 11."""
    complete = git_copy_of_example(tmp_path / "complete")
    complete_gate = _gate(capsys, complete, "11")
    half = git_copy_of_example(tmp_path / "half")
    (half / "spec" / STEP_14_FILE).unlink()
    half_gate = _gate(capsys, half, "11")

    assert _e740(half_gate["blocking"]) == set()
    assert set(DANGLING_AT_14) <= _e740(half_gate["pending"]["14"])
    assert set(DANGLING_AT_12) <= _e740(half_gate["pending"]["12"])
    assert _e740(half_gate["pending"]["14"]) == _e740(complete_gate["pending"]["14"])
    assert _e740(half_gate["pending"]["12"]) == _e740(complete_gate["pending"]["12"])


# --- the entries on the worked example ----------------------------------------------------------------------------------


def _spec_check_json(capsys: pytest.CaptureFixture[str], host: Path, *flags: str) -> tuple[int, dict[str, Any], str]:
    """``spec-check <host>/spec --json`` with the three root flags: ``(exit code, parsed output, stderr)``."""
    roots = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    code, out, err = run_split(capsys, "spec-check", str(host / "spec"), *roots, *flags, "--json")
    return code, json.loads(out), err


def test_new_check_entries_appear_on_the_example(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The eight entries come after trace-lock and ``third-party-pins`` (step 02's pin check), then ``milestone-numbers`` (M6c) and ``removal-rules`` (M7; their counts are not pinned here), then open-items, frozen-plans and plan-records (M8); none skips, and the counts of the eight are the example's (17, 0, 5, 1, 0, 0, 0, 0)."""
    code, report, _err = _spec_check_json(capsys, git_copy_of_example(tmp_path / "host"))
    names = list(report["checks"])
    assert names[names.index("trace-lock") + 1 : -3] == ["third-party-pins", *GRAPH_CHECKS, "milestone-numbers", "removal-rules"] and names[-3:] == ["open-items", "frozen-plans", "plan-records"]
    assert report["checks"]["milestone-numbers"]["status"] != "SKIP"
    assert {name: report["checks"][name]["status"] for name in GRAPH_CHECKS} == {
        "no-dangling": "FAIL", "term-use": "PASS", "verifier-rules": "FAIL", "cross-cutting": "FAIL",
        "refinement": "PASS", "scaffold-paths": "PASS", "seed-routes": "PASS", "prose-ids": "PASS",
    }
    assert [report["checks"][name]["error_count"] for name in GRAPH_CHECKS] == [17, 0, 5, 1, 0, 0, 0, 0]
    assert code == 1 and report["error_count"] == 24 + report["checks"]["milestone-numbers"]["error_count"]  # the eight checks are the 23 findings; the other is E608 (no specdev_version)


def test_plain_spec_check_summary_matches_golden_with_the_new_entries(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The printed summary of the example equals the golden, and the golden has a result line (no ``not built yet``) for each of the eight."""
    host = git_copy_of_example(tmp_path / "host")
    spec = str(host / "spec")
    run_plain_spec_check(str(ROOT), spec, git_root=str(host), spec_root=spec, project_canon_dir=f"{spec}/canon")
    golden = GOLDEN.read_text(encoding="utf-8")
    assert capsys.readouterr().err == golden
    assert "not built yet" not in golden
    assert all(f"] {name} " in golden for name in GRAPH_CHECKS)


# --- a 1.1.1-shaped corpus and a malformed file ---------------------------------------------------------------------------


def test_legacy_shape_corpus_reports_findings_with_owners_and_no_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """R1: a spec written in the 1.1.1 shape (trace arrays, fr_refs, fixture targets, no scope, no lock) is not skipped: every graph check runs, some report, each finding has an owner."""
    host = tmp_path / "host"
    shutil.copytree(LEGACY, host)
    git(host, "init", "-q", "-b", "main")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "legacy")
    _code, report, err = _spec_check_json(capsys, host)
    assert "Traceback" not in err
    results = {name: report["checks"][name] for name in GRAPH_CHECKS}
    assert [name for name, result in results.items() if result["status"] == "SKIP"] == []
    findings = [(name, f) for name, result in results.items() for f in result["findings"]]
    assert {f["code"] for _name, f in findings} == {"E740", "E742", "E743", "E752"} <= GRAPH_CHECK_CODES
    assert all(f["owner"] for _name, f in findings), [f for _n, f in findings if not f["owner"]]
    assert {(f["code"], f["node_id"], f["owner"]) for _n, f in findings if f["code"] == "E743"} == {
        ("E743", "ac-legacy-signin-1", "step:08"), ("E743", "api-legacy-signin", "step:08"),
    }


def test_graph_shaped_corpus_with_one_malformed_file_gives_the_m4_error_and_no_skip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The example with 07_nfrs.json cut off: the graph is built without that file, one E520 (owner step 07) says so, no graph check skips, and the NFR's own findings are gone."""
    host = git_copy_of_example(tmp_path / "host")
    (host / "spec" / "07_nfrs.json").write_text('{ "oops": \n', encoding="utf-8")
    _code, report, err = _spec_check_json(capsys, host)
    assert "Traceback" not in err
    unreadable = [f for f in report["checks"]["open-items"]["findings"] if f["code"] == "E520"]
    assert [(f["file"], f["owner"]) for f in unreadable] == [("07_nfrs.json", "step:07")]
    assert [name for name in GRAPH_CHECKS if report["checks"][name]["status"] == "SKIP"] == []
    assert "nfr-latency-reset-email" not in {f["node_id"] for name in GRAPH_CHECKS for f in report["checks"][name]["findings"]}
    assert report["checks"]["verifier-rules"]["error_count"] == 4


# --- promotion ------------------------------------------------------------------------------------------------------------


@pytest.fixture
def promotion_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
    monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
    reset_config()
    yield monkeypatch
    reset_config()


@pytest.mark.parametrize("env", [("SPECDEV_WARNINGS_AS_ERRORS", "1"), ("SPECDEV_PROMOTE_CODES", "W615")], ids=["all", "selected"])
def test_promotion_applies_to_a_new_check_result(
    env: tuple[str, str], promotion_env: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A promotable warning (W615, made up for the test) from a registered graph check is WARN as it is and FAIL with the code E615 under either promotion variable: the entry builds its result through ``check_result``."""
    warning = make_error("W615", "stand-in warning from the rule", node_id="fr-password-reset", owner="step:14")
    register_graph_check("probe-warning", lambda _ctx, _mode: [warning])
    host = git_copy_of_example(tmp_path / "host")

    try:
        reset_config()
        _code, plain, _err = _spec_check_json(capsys, host)
        assert [(plain["checks"]["probe-warning"]["status"], f["code"]) for f in plain["checks"]["probe-warning"]["findings"]] == [("WARN", "W615")]

        promotion_env.setenv(*env)
        reset_config()
        _code, promoted, _err = _spec_check_json(capsys, host)
    finally:
        unregister_graph_check("probe-warning")
    assert [(promoted["checks"]["probe-warning"]["status"], f["code"]) for f in promoted["checks"]["probe-warning"]["findings"]] == [("FAIL", "E615")]
