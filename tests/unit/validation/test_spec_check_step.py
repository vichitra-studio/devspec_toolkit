"""``spec-check --step`` and ``--paths``: the check registry, the step gate output and its exit codes (WI-M6a-04).

The scenarios are the worked example (a git copy, see ``tests/integration/_step_gate_support.py``) with the deltas of
``tests/fixtures/step_gate/deltas`` on top.  Layout cases (host root, folder above, nested) are in
``tests/integration/test_step_gate_layouts.py``.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from integration._step_gate_support import apply_delta, attest, commit_all, run_split, run_spec_check, step_gate_host
from specdev_tools.core.ambiguity_items import iter_ambiguity_items
from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.git_base import BaselineResult, active_baseline_provider, register_baseline_provider
from specdev_tools.graph.build import build_graph
from specdev_tools.validation.spec_check import (
    CHECK_REGISTRY,
    CheckContext,
    _check_result,
    _run_checks,
    register_check,
    run_spec_check_json,
    run_step_gate,
)
from specdev_tools.validation.spec_check import run_spec_check as run_plain_spec_check
from specdev_tools.validation.step_gate import waiting_map
from unit.graph._synth import ROOT, git
from unit.trace._lock_support import git_copy_of_example

SCHEMA = json.loads((Path(__file__).parent / "step_gate_output.schema.json").read_text(encoding="utf-8"))
GOLDEN = ROOT / "tests" / "fixtures" / "step_gate" / "spec_check_summary.golden"
PROMOTABLE_WARNING = "W615"


@pytest.fixture(autouse=True)
def _fresh_config() -> Iterator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture
def registry() -> Iterator[None]:
    """The check registry as it was, put back when the test ends."""
    saved = list(CHECK_REGISTRY)
    yield
    CHECK_REGISTRY[:] = saved


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _gate_json(host: Path, capsys: pytest.CaptureFixture[str], *flags: str) -> tuple[int, dict[str, Any]]:
    """``spec-check <flags> --json`` on *host*: the exit code and the parsed stdout (which must be one JSON document)."""
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), *flags, "--json")
    return code, json.loads(out)


def _register_finding(name: str, error: SpecError) -> None:
    register_check(name, lambda ctx: _check_result([error]))


# --- the registry -----------------------------------------------------------------------------------------------

def test_register_check_runs_once_and_keeps_order(tmp_path: Path, registry: None) -> None:
    calls: list[str] = []

    def probe(ctx: CheckContext) -> dict[str, Any]:
        calls.append(ctx.spec_dir)
        return _check_result([])

    register_check("probe-check", probe)
    host = step_gate_host(tmp_path / "host")
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    assert calls == [str(host / "spec")]
    assert list(context["checks"])[-2:] == ["open-items", "probe-check"]


def test_register_check_refuses_a_name_that_is_registered(registry: None) -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_check(CHECK_REGISTRY[0].name, lambda ctx: _check_result([]))


def test_every_check_of_the_registry_has_a_default_owner() -> None:
    steps = {"03", "08"}
    owners = {spec.name: spec.default_owner for spec in CHECK_REGISTRY}
    assert len(owners) == len(CHECK_REGISTRY) == 20
    assert all(owner == "merge-check" or owner.removeprefix("step:") in steps for owner in owners.values()), owners
    assert owners["fixtures-lint"] == "step:08"
    assert owners["glossary-drift-check"] == "step:03"


def test_toolkit_side_lint_finding_carries_merge_check(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    finding = context["checks"]["toolkit-version"]["findings"][0]
    assert (finding["code"], finding["owner"]) == ("E608", "merge-check")


def test_plain_spec_check_summary_matches_golden(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = git_copy_of_example(tmp_path / "host")
    spec = str(host / "spec")
    run_plain_spec_check(str(ROOT), spec, git_root=str(host), spec_root=spec, project_canon_dir=f"{spec}/canon")
    assert capsys.readouterr().err == GOLDEN.read_text(encoding="utf-8")


def test_baseline_run_prints_no_seed_note(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = git_copy_of_example(tmp_path / "host")
    (host / "docs" / "seed" / "seed_accounts.md").unlink()
    spec = str(host / "spec")
    _run_checks(str(ROOT), spec, git_root=str(host), spec_root=spec)
    assert "seed documents not found" in capsys.readouterr().err
    _run_checks(str(ROOT), spec, git_root=str(host), spec_root=spec, quiet=True)
    assert capsys.readouterr().err == ""


# --- the gate ---------------------------------------------------------------------------------------------------

def test_step_04_exits_zero_when_only_later_errors_exist_and_lists_them_pending(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_05"])
    code, out = run_spec_check(host, "--step", "04")
    assert code == 0, out
    assert "PENDING (2)" in out and "05: 1" in out
    assert "api-broken-link" not in out
    assert "api-broken-link" in run_spec_check(host, "--step", "04", "--detail", "all")[1]


def test_error_on_a_step_04_node_blocks_step_04(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"])
    code, out = run_spec_check(host, "--step", "04")
    assert code == 1, out
    assert "BLOCKING (1)" in out and "E700  [04 own]" in out and "fr-broken-link" in out
    assert out.rstrip().endswith("RESULT: BLOCKED")


def test_new_error_of_an_earlier_step_blocks_a_later_step_and_a_committed_one_is_debt(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"])
    code, out = run_spec_check(host, "--step", "05")
    assert code == 1 and "[04 new upstream]" in out, out
    commit_all(host, "the broken link is on the branch already")
    code, out = run_spec_check(host, "--step", "05")
    assert code == 0 and "UPSTREAM DEBT (1)" in out and "04: 1" in out, out


def test_promoted_code_blocks_in_own_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registry: None) -> None:
    _register_finding("own-warning", make_error(PROMOTABLE_WARNING, "unexercised", owner="step:04"))
    monkeypatch.setenv("SPECDEV_PROMOTE_CODES", PROMOTABLE_WARNING)
    host = step_gate_host(tmp_path / "host")
    code, out = run_spec_check(host, "--step", "04")
    assert code == 1 and "E615  [04 own]" in out, out


def test_unpromoted_code_is_an_own_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str], registry: None) -> None:
    _register_finding("own-warning", make_error(PROMOTABLE_WARNING, "unexercised", owner="step:04"))
    host = step_gate_host(tmp_path / "host")
    code, payload = _gate_json(host, capsys, "--step", "04")
    assert code == 0
    assert [w["code"] for w in payload["step_gate"]["own_warnings"]] == [PROMOTABLE_WARNING]
    assert payload["step_gate"]["blocking"] == [] and payload["status"] == "WARN"


def test_step_with_include_forward_replay_is_a_usage_error(tmp_path: Path) -> None:
    code, out = run_spec_check(step_gate_host(tmp_path / "host"), "--step", "04", "--include-forward-replay")
    assert code == 2 and "--include-forward-replay" in out


def test_step_with_paths_is_a_usage_error(tmp_path: Path) -> None:
    code, out = run_spec_check(step_gate_host(tmp_path / "host"), "--step", "04", "--paths", "spec/04_fr_list.json")
    assert code == 2 and "not allowed with" in out


@pytest.mark.parametrize("flags", [["--detail", "all"], ["--base-ref", "main"]], ids=["detail", "base-ref"])
def test_gate_options_without_a_gate_are_a_usage_error(tmp_path: Path, flags: list[str]) -> None:
    code, out = run_spec_check(step_gate_host(tmp_path / "host"), *flags)
    assert code == 2 and "apply only with --step or --paths" in out


def test_unknown_step_is_e706_exit_1(tmp_path: Path) -> None:
    code, out = run_spec_check(step_gate_host(tmp_path / "host"), "--step", "99")
    assert code == 1 and out.startswith("E706") and "known steps: 00, 01" in out


def test_json_output_validates_against_the_step_gate_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04", "open_items"])
    code, payload = _gate_json(host, capsys, "--step", "05")
    jsonschema.validate(payload, SCHEMA)
    gate = payload["step_gate"]
    assert code == 1 and gate["result"] == "blocked" and gate["steps"] == ["05"]
    assert [e["code"] for e in gate["blocking"]] == ["E700"]
    assert gate["baseline"]["mode"] == "head" and gate["baseline"]["ref"] == "main"
    assert [w["code"] for w in gate["own_warnings"]] == ["W630"]
    assert payload["status"] == "FAIL" and payload["command"] == "spec-check"


def test_json_exit_code_ignores_pending_debt_and_gate_owned_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    host = step_gate_host(tmp_path / "host", ["uncovered_capability"], commit=True)
    for name in ("broken_link_in_step_05", "missing_seed_file", "open_items"):
        apply_delta(host, name)
    for environment in ({}, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}):
        for variable, value in environment.items():
            monkeypatch.setenv(variable, value)
        code, payload = _gate_json(host, capsys, "--step", "04")
        gate = payload["step_gate"]
        assert code == 0, (environment, payload["errors"])
        assert any(e["code"].startswith("E") for e in gate["pending"]["05"])
        assert [e["code"] for e in gate["upstream_debt"]] == ["E590"]
        assert {"E520", "E608"} <= {e["code"] for e in gate["gate_owned"]}
        assert gate["result"] == "clear"
    assert "W630" in {e["code"] for found in gate["pending"].values() for e in found}


def test_several_steps_give_one_block_each_and_the_union_in_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_05"])
    code, out = run_spec_check(host, "--step", "04", "--step", "05")
    assert code == 1 and out.count("step gate: step") == 2 and out.count("RESULT:") == 2
    code, payload = _gate_json(host, capsys, "--step", "04", "--step", "05")
    jsonschema.validate(payload, SCHEMA)
    gate = payload["step_gate"]
    assert gate["steps"] == ["04", "05"] and [e["code"] for e in gate["blocking"]] == ["E700"]
    assert len(gate["pending"]["05"]) == 1


def test_waiting_item_explains_an_error_of_its_step(tmp_path: Path, registry: None, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["open_items"])
    spec = str(host / "spec")
    items = list(iter_ambiguity_items(spec))
    below = sorted(waiting_map(build_graph(spec, str(ROOT)), items)["amb-reset-seed"])
    _register_finding("synthetic", make_error("E520", "synthetic finding", owner="step:05", node_id=below[0]))
    code, out = run_spec_check(host, "--step", "05")
    assert code == 0 and "WAITING (1)" in out and "amb-reset-seed" in out.splitlines()[1], out
    _code, payload = _gate_json(host, capsys, "--step", "05")
    jsonschema.validate(payload, SCHEMA)
    assert "amb-reset-seed" in payload["step_gate"]["waiting"][0]["waiting_on"]


def test_step_05_exits_0_and_lists_w630_also_with_warnings_as_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = step_gate_host(tmp_path / "host", ["open_items"])
    for environment in ({}, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}):
        for variable, value in environment.items():
            monkeypatch.setenv(variable, value)
        code, out = run_spec_check(host, "--step", "05")
        assert code == 0, out
        assert "WARNINGS (1)" in out and "W630" in out and "amb-reset-seed" in out


def test_spec_check_lists_one_w630_for_the_legacy_plan(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["plan_ambiguity"])
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    assert [f["code"] for f in context["checks"]["open-items"]["findings"]] == ["W630"]


def test_gate_direct_call_without_pre_commit_reads_working_tree(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"])
    git(host, "add", "-A")
    apply_delta(host, "broken_link_in_step_05")
    attest(host)
    spec = str(host / "spec")
    run = run_step_gate(str(ROOT), spec, ["05"], git_root=str(host), spec_root=spec)
    broken = {e.node_id for e in run.results[0].blocking.errors if e.code == "E700"}
    assert broken == {"fr-broken-link", "api-broken-link"}


def test_step_gate_restores_the_baseline_provider_it_found(tmp_path: Path) -> None:
    def sentinel(spec_dir: Path, git_root: str) -> BaselineResult:
        return BaselineResult("unavailable")

    previous = active_baseline_provider()
    register_baseline_provider(sentinel)
    try:
        host = step_gate_host(tmp_path / "host")
        run_spec_check(host, "--step", "04")
        assert active_baseline_provider() is sentinel
    finally:
        register_baseline_provider(previous)


def test_base_ref_names_the_branch_the_baseline_is_measured_against(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host")
    git(host, "branch", "trunk")
    apply_delta(host, "broken_link_in_step_04")
    commit_all(host, "the broken link")
    _code, payload = _gate_json(host, capsys, "--step", "05")
    assert payload["step_gate"]["blocking"] == [] and payload["step_gate"]["baseline"]["mode"] == "head"
    code, payload = _gate_json(host, capsys, "--step", "05", "--base-ref", "trunk")
    gate = payload["step_gate"]
    assert code == 1 and [e["code"] for e in gate["blocking"]] == ["E700"]
    assert (gate["baseline"]["ref"], gate["baseline"]["mode"]) == ("trunk", "merge-base")


# --- --paths ----------------------------------------------------------------------------------------------------

def test_paths_with_no_mapped_path_exits_0_without_running_a_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registry: None
) -> None:
    def forbidden(ctx: CheckContext) -> dict[str, Any]:
        raise AssertionError("no check may run when no path maps to a step")

    register_check("forbidden", forbidden)
    host = step_gate_host(tmp_path / "host")
    monkeypatch.chdir(host)
    note = "no step gated: no listed path maps to a step\n"
    for paths in ([], ["README.md"], ["extras/anything.json"]):
        code, out = run_spec_check(host, "--paths", *paths)
        assert (code, out) == (0, note if paths else ""), (paths, out)


def test_paths_gate_the_steps_of_the_touched_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"])
    monkeypatch.chdir(host)
    code, out = run_spec_check(host, "--paths", "spec/04_fr_list.json", "spec/05_interface_contracts.json")
    assert code == 1 and out.count("step gate: step") == 2 and "E700  [04 own]" in out, out


def test_a_seed_edit_prints_the_dependants_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = step_gate_host(tmp_path / "host")
    monkeypatch.chdir(host)
    code, out = run_spec_check(host, "--paths", "docs/seed/seed_accounts.md")
    assert code == 0 and "seed edit: dependants become suspect; run `specdev stale`" in out
