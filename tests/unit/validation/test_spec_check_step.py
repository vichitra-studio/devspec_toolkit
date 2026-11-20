"""``spec-check --step`` and ``--paths``: the check registry, the step gate output and its exit codes (WI-M6a-04).

The scenarios are the worked example (a git copy, see ``tests/integration/_step_gate_support.py``) with the deltas of
``tests/fixtures/step_gate/deltas`` on top.  Layout cases (host root, folder above, nested) are in
``tests/integration/test_step_gate_layouts.py``.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from integration._step_gate_support import apply_delta, attest, commit_all, run_split, run_spec_check, step_gate_host
from specdev_tools.core.ambiguity_items import iter_ambiguity_items
from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.step_order import load_step_order
from specdev_tools.graph.build import build_graph
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CHECK_REGISTRY, CheckContext, check_result, register_check, run_registered_checks
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES
from specdev_tools.validation.spec_check import run_checks, run_spec_check_json
from specdev_tools.validation.spec_check import run_spec_check as run_plain_spec_check
from specdev_tools.validation.step_gate import waiting_map
from specdev_tools.validation.step_gate_run import run_step_gate
from specdev_tools.validation.touched_steps import SEED_EDIT_NOTE
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


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _gate_json(host: Path, capsys: pytest.CaptureFixture[str], *flags: str) -> tuple[int, dict[str, Any]]:
    """``spec-check <flags> --json`` on *host*: the exit code and the parsed stdout (which must be one JSON document)."""
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), *flags, "--json")
    return code, json.loads(out)


def _register_finding(name: str, error: SpecError) -> None:
    register_check(name, lambda ctx: check_result([error]))


# --- the registry -----------------------------------------------------------------------------------------------

def test_register_check_runs_once_and_keeps_order(tmp_path: Path, registered_checks: None) -> None:
    calls: list[str] = []

    def probe(ctx: CheckContext) -> dict[str, Any]:
        calls.append(ctx.spec_dir)
        return check_result([])

    register_check("probe-check", probe)
    host = step_gate_host(tmp_path / "host")
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    assert calls == [str(host / "spec")]
    assert list(context["checks"])[-2:] == ["open-items", "probe-check"]


def test_register_check_refuses_a_name_that_is_registered(registered_checks: None) -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_check(CHECK_REGISTRY[0].name, lambda ctx: check_result([]))


def test_an_empty_registry_is_refused_not_clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A gate built on no check would say CLEAR: running the registry with nothing registered is a programming error."""
    monkeypatch.setattr(check_registry, "CHECK_REGISTRY", [])
    with pytest.raises(RuntimeError, match=r"no check is registered.*spec_check"):
        run_registered_checks(CheckContext(repo_root=str(ROOT), spec_dir=str(tmp_path)))


def _registered_names_of_the_block() -> list[str]:
    """The names ``validation/spec_check.py`` registers, read from the source: the first argument of each module-level ``register_check`` call, and the rules of ``BUILTIN_GRAPH_CHECKS`` at the module-level call of ``publish_graph_checks``."""
    from specdev_tools.validation import graph_checks, spec_check

    names: list[str] = []
    for node in ast.parse(Path(spec_check.__file__).read_text(encoding="utf-8")).body:
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        func = node.value.func
        if getattr(func, "id", "") == "register_check":
            arg = node.value.args[0]
            names.append(arg.value if isinstance(arg, ast.Constant) else getattr(spec_check, arg.id))
        elif getattr(func, "attr", "") == "publish_graph_checks":
            names.extend(name for name, _rule, _check in graph_checks.BUILTIN_GRAPH_CHECKS)
    return names


def test_a_fresh_cli_process_runs_every_check_of_the_registration_block(tmp_path: Path) -> None:
    """The one place a check is registered is the block of ``spec_check.py``: a new interpreter that imports the CLI and runs ``spec-check`` has all of them."""
    host = step_gate_host(tmp_path / "host")
    spec = str(host / "spec")
    program = "import sys, specdev_tools.cli as cli\nsys.argv = ['specdev', *sys.argv[1:]]\ncli.main()"
    done = subprocess.run(
        [sys.executable, "-c", program, "spec-check", spec, "--repo-root", str(ROOT), "--spec-root", spec, "--git-root", str(host), "--json"],
        cwd=str(host), capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "tools"), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    block = _registered_names_of_the_block()
    assert len(block) >= 20 and list(json.loads(done.stdout)["checks"]) == block, done.stderr[-500:]


def test_spec_check_runs_every_check_of_the_registration_block(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    assert list(context["checks"]) == _registered_names_of_the_block()


def test_every_check_of_the_registry_has_a_default_owner() -> None:
    """Every default owner is the merge check or a step of ``tools/step_order.json``; no count, so a new check does not break it."""
    known = {f"step:{step}" for step in load_step_order(str(ROOT))["steps"]}
    owners = {spec.name: spec.default_owner for spec in CHECK_REGISTRY}
    assert owners and all(owner == "merge-check" or owner in known for owner in owners.values()), owners


def test_fixtures_lint_is_owned_by_step_08() -> None:
    assert {spec.name: spec.default_owner for spec in CHECK_REGISTRY}["fixtures-lint"] == "step:08"


def test_glossary_drift_check_is_owned_by_step_03() -> None:
    assert {spec.name: spec.default_owner for spec in CHECK_REGISTRY}["glossary-drift-check"] == "step:03"


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
    run_checks(str(ROOT), spec, git_root=str(host), spec_root=spec)
    assert "seed documents not found" in capsys.readouterr().err
    run_checks(str(ROOT), spec, git_root=str(host), spec_root=spec, quiet=True)
    assert capsys.readouterr().err == ""


# --- the gate ---------------------------------------------------------------------------------------------------

def test_step_04_exits_zero_when_only_later_errors_exist_and_lists_them_pending(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_05"])
    code, out = run_spec_check(host, "--step", "04")
    assert code == 0, out
    assert re.search(r"PENDING \(\d+\)", out) and "05: 1" in out
    # the delta's own pending part is exactly one finding at step 05; the rest is the example's own W583 at step 11 (what the
    # total was before the graph checks) and the findings of the graph checks (the total moves with those)
    _code, report = _gate_json(host, capsys, "--step", "04")
    pending = report["step_gate"]["pending"]
    assert [(finding["code"], finding["node_id"]) for finding in pending["05"]] == [("E700", "api-broken-link")]
    others = [(owner, finding["code"]) for owner, found in pending.items() if owner != "05" for finding in found if finding["code"] not in GRAPH_CHECK_CODES]
    assert others == [("11", "W583")]
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


def test_promoted_code_blocks_in_own_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registered_checks: None) -> None:
    _register_finding("own-warning", make_error(PROMOTABLE_WARNING, "unexercised", owner="step:04"))
    monkeypatch.setenv("SPECDEV_PROMOTE_CODES", PROMOTABLE_WARNING)
    host = step_gate_host(tmp_path / "host")
    code, out = run_spec_check(host, "--step", "04")
    assert code == 1 and "E615  [04 own]" in out, out


def test_unpromoted_code_is_an_own_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str], registered_checks: None) -> None:
    _register_finding("own-warning", make_error(PROMOTABLE_WARNING, "unexercised", owner="step:04"))
    host = step_gate_host(tmp_path / "host")
    code, payload = _gate_json(host, capsys, "--step", "04")
    assert code == 0
    assert [w["code"] for w in payload["step_gate"]["own_warnings"]] == [PROMOTABLE_WARNING]
    assert payload["step_gate"]["blocking"] == [] and payload["status"] == "WARN"


def test_step_with_paths_is_a_usage_error(tmp_path: Path) -> None:
    code, out = run_spec_check(step_gate_host(tmp_path / "host"), "--step", "04", "--paths", "spec/04_fr_list.json")
    assert code == 2 and "not allowed with" in out


def test_detail_accepts_summary_and_all_only(tmp_path: Path) -> None:
    code, out = run_spec_check(step_gate_host(tmp_path / "host"), "--step", "04", "--detail", "bogus")
    assert code == 2 and "invalid choice: 'bogus'" in out and "summary, all" in out


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
    attest(host)  # the missing-seed delta adds a link (to its routed seed), which needs its lock entry
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


def test_waiting_item_explains_an_error_of_its_step(tmp_path: Path, registered_checks: None, capsys: pytest.CaptureFixture[str]) -> None:
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


def test_an_unreadable_ambiguity_file_switches_waiting_off_and_the_finding_blocks(
    tmp_path: Path, registered_checks: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same setup as the test above, plus a plan file the item reader cannot parse: the items read before it explain nothing."""
    host = step_gate_host(tmp_path / "host", ["open_items"])
    spec = str(host / "spec")
    below = sorted(waiting_map(build_graph(spec, str(ROOT)), list(iter_ambiguity_items(spec)))["amb-reset-seed"])
    _register_finding("synthetic", make_error("E520", "synthetic finding", owner="step:05", node_id=below[0]))
    (host / "spec" / "impl_context").mkdir(exist_ok=True)
    (host / "spec" / "impl_context" / "ms_broken_plan.json").write_text("{not json", encoding="utf-8")
    code, out, _err = run_split(capsys, "spec-check", spec, *_flags(host), "--step", "05", "--detail", "all")
    assert code == 1 and "WAITING" not in out and "BLOCKING" in out and "synthetic finding" in out, out
    assert "ms_broken_plan.json" in out, out


def test_a_promote_code_that_cannot_promote_is_warned_about_on_stderr_under_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """W630 is a valid code with no error counterpart: ``--step`` says it is ignored, as ``spec-check`` does."""
    monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W630")
    host = step_gate_host(tmp_path / "host")
    _code, _out, err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "05")
    assert "W630" in err and "not a promotable code" in err, err


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
    run = run_step_gate(str(ROOT), spec, steps=["05"], git_root=str(host), spec_root=spec)
    broken = {e.node_id for e in run.results[0].blocking.errors if e.code == "E700"}
    assert broken == {"fr-broken-link", "api-broken-link"}


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registered_checks: None
) -> None:
    def forbidden(ctx: CheckContext) -> dict[str, Any]:
        raise AssertionError("no check may run when no path maps to a step")

    register_check("forbidden", forbidden)
    host = step_gate_host(tmp_path / "host")
    monkeypatch.chdir(host)
    note = "no step gated: no listed path maps to a step that has an artifact\n"
    for paths in ([], ["README.md"], ["extras/anything.json"]):
        code, out = run_spec_check(host, "--paths", *paths)
        assert (code, out) == (0, note if paths else ""), (paths, out)


def test_a_path_that_maps_to_a_step_whose_file_is_gone_is_not_gated_and_the_note_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registered_checks: None
) -> None:
    """``--step`` gates a step with no artifact (and notes it); ``--paths`` drops it, and the note is true: the path DID map."""
    host = step_gate_host(tmp_path / "host")
    (host / "spec" / "06_invariants.json").unlink()
    monkeypatch.chdir(host)
    code, out = run_spec_check(host, "--paths", "spec/06_invariants.json")
    assert (code, out) == (0, "no step gated: no listed path maps to a step that has an artifact\n"), out
    code, out = run_spec_check(host, "--step", "06")
    assert code == 0 and "step 06 has no artifact in" in out and "RESULT: CLEAR" in out, out


def test_paths_gate_the_steps_of_the_touched_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"])
    monkeypatch.chdir(host)
    code, out = run_spec_check(host, "--paths", "spec/04_fr_list.json", "spec/05_interface_contracts.json")
    assert code == 1 and out.count("step gate: step") == 2 and "E700  [04 own]" in out, out


def test_a_seed_edit_prints_the_dependants_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = step_gate_host(tmp_path / "host")
    monkeypatch.chdir(host)
    code, out = run_spec_check(host, "--paths", "docs/seed/seed_accounts.md")
    assert code == 0 and SEED_EDIT_NOTE in out
