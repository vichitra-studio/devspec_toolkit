"""``verify run``: what a run records, which bindings it takes, and what it leaves alone."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.verify import run as run_module
from specdev_tools.verify.code_tree import code_tree_for_host
from specdev_tools.verify.records import Evidence, records_folder, write_binding
from specdev_tools.verify.run import TIMEOUT_EXIT_CODE, run_bindings, selected_ids
from unit.graph._synth import ROOT

from unit.proof._closed import add_milestone, criterion

from ._support import commit_all, edit_doc, example_host, graph_of, write, write_json

FIXTURE = "fix-password-reset-expired-token"
CRITERION, API, TP = "ac-password-reset-3", "api-password-reset-confirm", "tp-argon2"
PASSING = "echo expected line"
GUARD = "expected line"


def _binding(binding_id: str, *, commands: tuple[str, ...] = (PASSING,), guard: str = GUARD, stage: str = "dev", verifier: str = FIXTURE) -> dict[str, Any]:
    item: dict[str, Any] = {"verification_id": binding_id, "verifies": [verifier], "stage": stage, "commands": list(commands), "output_guard": guard}
    return {**item, "proves": [CRITERION, API]} if verifier == FIXTURE else item


def _host(tmp_path: Path, *bindings: dict[str, Any]) -> Path:
    """The worked example with code under ``src/`` and the given bindings (replacing the example's own), committed."""
    host = example_host(tmp_path)
    (host / "spec" / "extras" / "verification" / "ver-password-reset-expired-token.json").unlink()
    write(host / "src" / "hello.txt", "hello\n")
    for item in bindings:
        write_binding(records_folder(str(host / "spec")), str(ROOT), item)
    commit_all(host)
    return host


def _run(host: Path, ids: list[str], **given: Any) -> list[Evidence]:
    spec = str(host / "spec")
    return run_bindings(ids, spec, records_folder(spec), str(host), repo_root=str(ROOT), **given)


def _evidence_files(host: Path) -> dict[str, dict[str, Any]]:
    folder = host / "spec" / "extras" / "verification"
    return {path.stem: json.loads(path.read_text())["records"][0] for path in sorted(folder.glob("evd-*.json"))}


def test_passing_command_writes_all_fields_and_a_second_run_overwrites_the_file(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    _run(host, ["ver-alpha"])
    stored = _evidence_files(host)
    assert list(stored) == ["evd-alpha-dev"]
    record = stored["evd-alpha-dev"]
    assert record["about"] == ["ver-alpha"] and record["type"] == "run" and record["stage"] == "dev"
    assert (record["exit_code"], record["guard_matched"]) == (0, True)
    assert record["output_hash"] == "sha256:" + hashlib.sha256(b"expected line\n").hexdigest()
    assert set(record["recorded_hashes"]) == {"ver-alpha", FIXTURE, CRITERION, API} and record["installed_versions"] == {}
    _run(host, ["ver-alpha"])
    assert list(_evidence_files(host)) == ["evd-alpha-dev"]


def test_tested_tree_equals_code_tree_for_host(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    [evidence] = _run(host, ["ver-alpha"])
    assert evidence.tested_tree == code_tree_for_host(str(host), str(host / "spec"))
    assert _evidence_files(host)["evd-alpha-dev"]["tested_tree"] == evidence.tested_tree


def test_exit_zero_with_unmatched_guard_is_guard_matched_false_and_fails(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha", guard="no such line"))
    [evidence] = _run(host, ["ver-alpha"])
    assert (evidence.exit_code, evidence.guard_matched, evidence.passed) == (0, False, False)


def test_non_zero_exit_is_recorded(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha", commands=("echo expected line; exit 3",)))
    [evidence] = _run(host, ["ver-alpha"])
    assert (evidence.exit_code, evidence.guard_matched, evidence.passed) == (3, True, False)
    assert _evidence_files(host)["evd-alpha-dev"]["exit_code"] == 3


def test_no_record_writes_nothing_and_returns_in_memory_evidence(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    [evidence] = _run(host, ["ver-alpha"], record=False)
    assert evidence.passed and evidence.evidence_id == "evd-alpha-dev"
    assert _evidence_files(host) == {}


def test_no_record_leaves_stored_evidence_untouched(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    _run(host, ["ver-alpha"])
    path = host / "spec" / "extras" / "verification" / "evd-alpha-dev.json"
    stored = path.read_bytes()
    write(host / "src" / "hello.txt", "changed\n")
    [fresh] = _run(host, ["ver-alpha"], record=False)
    assert path.read_bytes() == stored
    assert fresh.tested_tree != json.loads(stored)["records"][0]["tested_tree"]


def test_run_that_changes_a_tracked_file_warns_w351_and_records_the_post_run_tree(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha", commands=("echo expected line; echo more >> src/hello.txt",)))
    before = code_tree_for_host(str(host), str(host / "spec"))
    [evidence] = _run(host, ["ver-alpha"])
    after = code_tree_for_host(str(host), str(host / "spec"))
    assert evidence.passed and before != after and evidence.tested_tree == after
    assert [note.split(" ", 1)[0] for note in evidence.notes] == ["W351"]


def test_identical_command_and_guard_run_once(tmp_path: Path) -> None:
    counter = tmp_path / "counter.txt"
    command = f"echo expected line; echo run >> '{counter}'"
    host = _host(tmp_path, _binding("ver-alpha", commands=(command,)), _binding("ver-beta", commands=(command,)), _binding("ver-gamma", commands=(command,), guard="line"))
    results = _run(host, ["ver-alpha", "ver-beta", "ver-gamma"])
    assert counter.read_text().splitlines() == ["run", "run"]
    assert [evidence.about[0] for evidence in results] == ["ver-alpha", "ver-beta", "ver-gamma"]
    assert set(_evidence_files(host)) == {"evd-alpha-dev", "evd-beta-dev", "evd-gamma-dev"}


def _staged_host(tmp_path: Path) -> Path:
    return _host(
        tmp_path, _binding("ver-dev"), _binding("ver-ci", stage="ci"), _binding("ver-staging", stage="staging"), _binding("ver-prod", stage="prod"),
    )


def test_stage_ci_runs_dev_and_ci_not_staging(tmp_path: Path) -> None:
    host = _staged_host(tmp_path)
    ids = selected_ids(graph_of(host), every=True, milestone=None, stage="ci", only_stage=False)
    assert sorted(ids) == ["ver-ci", "ver-dev"]
    _run(host, ids, stage="ci")
    assert set(_evidence_files(host)) == {"evd-dev-ci", "evd-ci-ci"}


def test_only_stage_prod_touches_only_prod_bindings(tmp_path: Path) -> None:
    host = _staged_host(tmp_path)
    graph = graph_of(host)
    assert selected_ids(graph, every=True, milestone=None, stage="prod", only_stage=True) == ["ver-prod"]
    results = _run(host, ["ver-dev", "ver-prod"], stage="prod", only_stage=True)
    assert [evidence.about[0] for evidence in results] == ["ver-prod"] and set(_evidence_files(host)) == {"evd-prod-prod"}


def test_explicit_staging_binding_at_dev_fails(tmp_path: Path) -> None:
    host = _staged_host(tmp_path)
    with pytest.raises(FindingError) as caught:
        _run(host, ["ver-dev", "ver-staging"])
    assert caught.value.error.code == "E767" and "ver-staging" in caught.value.error.message
    assert _evidence_files(host) == {}


def test_installed_flag_overrides_the_discovered_version(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    write_json(host / "package-lock.json", {"packages": {"node_modules/argon2": {"version": "0.31.0"}}})
    write_json(host / "spec" / "common" / "host_declarations.json", {"pin_sources": {TP: [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}]}})
    commit_all(host)
    [discovered] = _run(host, ["ver-alpha"], record=False)
    [overridden] = _run(host, ["ver-alpha"], record=False, installed={TP: "9.9.9"})
    assert (dict(discovered.installed_versions), dict(overridden.installed_versions)) == ({TP: "0.31.0"}, {TP: "9.9.9"})


def test_the_evidence_of_an_api_records_the_version_of_a_third_party_its_components_connection_reaches(tmp_path: Path) -> None:
    """identity-service connects to tp-mailrelay; with the API's own relies_on gone, only that computed reliance names it."""
    host = _host(tmp_path, _binding("ver-alpha"))
    edit_doc(host, "05_interface_contracts.json", lambda document: document["apis"][0].pop("relies_on"))
    write_json(host / "package-lock.json", {"packages": {"node_modules/argon2": {"version": "0.31.0"}, "node_modules/mailrelay": {"version": "2.4.0"}}})
    write_json(host / "spec" / "common" / "host_declarations.json", {"pin_sources": {
        TP: [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}],
        "tp-mailrelay": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1mailrelay/version"}],
    }})
    commit_all(host)
    [evidence] = _run(host, ["ver-alpha"], record=False)
    assert dict(evidence.installed_versions) == {"tp-mailrelay": "2.4.0"}


def test_direct_and_computed_reliance_each_give_one_installed_version(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    write_json(host / "package-lock.json", {"packages": {"node_modules/argon2": {"version": "0.31.0"}, "node_modules/mailrelay": {"version": "2.4.0"}}})
    write_json(host / "spec" / "common" / "host_declarations.json", {"pin_sources": {
        TP: [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}],
        "tp-mailrelay": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1mailrelay/version"}],
    }})
    commit_all(host)
    [evidence] = _run(host, ["ver-alpha"], record=False)
    assert dict(evidence.installed_versions) == {TP: "0.31.0", "tp-mailrelay": "2.4.0"}


def test_first_non_zero_exit_of_two_commands_is_the_exit_code(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha", commands=("echo expected line", "exit 4", "exit 5")))
    [evidence] = _run(host, ["ver-alpha"])
    assert (evidence.exit_code, evidence.guard_matched) == (4, True)


def test_run_writes_only_under_extras_verification(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"), _binding("ver-beta", stage="ci"))

    def snapshot() -> dict[str, bytes]:
        return {str(path.relative_to(host)): path.read_bytes() for path in sorted(host.rglob("*")) if path.is_file() and ".git" not in path.parts}

    before = snapshot()
    _run(host, ["ver-alpha", "ver-beta"], stage="ci")
    after = snapshot()
    changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
    assert changed == {"spec/extras/verification/evd-alpha-ci.json", "spec/extras/verification/evd-beta-ci.json"}


def test_timeout_records_124_and_fails(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha", commands=("echo expected line; sleep 30",)))
    started = time.monotonic()
    [evidence] = _run(host, ["ver-alpha"], timeout=1)
    assert time.monotonic() - started < 15
    assert (evidence.exit_code, evidence.guard_matched, evidence.passed) == (TIMEOUT_EXIT_CODE, False, False)


def test_failing_run_replaces_an_earlier_passing_record(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    _run(host, ["ver-alpha"])
    assert _evidence_files(host)["evd-alpha-dev"]["exit_code"] == 0
    write_binding(records_folder(str(host / "spec")), str(ROOT), _binding("ver-alpha", commands=("exit 1",)))
    _run(host, ["ver-alpha"])
    assert (_evidence_files(host)["evd-alpha-dev"]["exit_code"], _evidence_files(host)["evd-alpha-dev"]["guard_matched"]) == (1, False)


def test_other_stage_files_are_independent(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"))
    _run(host, ["ver-alpha"])
    dev_file = host / "spec" / "extras" / "verification" / "evd-alpha-dev.json"
    stored = dev_file.read_bytes()
    write_binding(records_folder(str(host / "spec")), str(ROOT), _binding("ver-alpha", commands=("exit 1",)))
    _run(host, ["ver-alpha"], stage="ci")
    assert dev_file.read_bytes() == stored
    assert _evidence_files(host)["evd-alpha-ci"]["exit_code"] == 1


def test_a_guard_that_is_no_regular_expression_is_refused_before_any_command_runs(tmp_path: Path) -> None:
    """A hand-edited record with a bad guard: E332, and the command (which would leave a file behind) did not run."""
    host = _host(tmp_path, _binding("ver-alpha", commands=("touch ran-before-the-guard-check",), guard="("))
    with pytest.raises(FindingError) as caught:
        _run(host, ["ver-alpha"])
    assert caught.value.error.code == "E332"
    assert not (host / "ran-before-the-guard-check").exists()
    assert _evidence_files(host) == {}


def test_the_tree_measured_after_one_group_is_the_one_before_the_next(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two groups, three measurements of the code tree (before the first, after each), not four."""
    host = _host(tmp_path, _binding("ver-alpha"), _binding("ver-beta", commands=("echo second line",), guard="second line", verifier="fix-password-reset-reused-token"))
    measured: list[str] = []
    real = run_module.code_tree_for_host

    def counting(*args: Any) -> str:
        measured.append(real(*args))
        return measured[-1]

    monkeypatch.setattr(run_module, "code_tree_for_host", counting)
    first, second = _run(host, ["ver-alpha", "ver-beta"])
    assert len(measured) == 3 and first.tested_tree == second.tested_tree == measured[-1]


def test_milestone_takes_only_the_bindings_of_the_verifiers_its_own_criteria_name(tmp_path: Path) -> None:
    host = _host(tmp_path, _binding("ver-alpha"), _binding("ver-other", verifier="fix-only-other"))
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"].append({**doc["fixtures"][0], "fixture_id": "fix-only-other"}))
    add_milestone(host, "ms-other-work", [criterion("tc-other-work", verified_by=["fix-only-other"])], done=False)
    graph = graph_of(host)
    assert selected_ids(graph, every=False, milestone="ms-account-recovery", stage="dev", only_stage=False) == ["ver-alpha"]
    assert selected_ids(graph, every=False, milestone="ms-other-work", stage="dev", only_stage=False) == ["ver-other"]
