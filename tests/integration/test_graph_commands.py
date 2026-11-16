"""``specdev node``, ``trace`` and ``diff`` run as subprocesses on a copy of the worked example (WI-M4-11)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit.graph._synth import ROOT, copy_example, run_specdev

_CRITERION = "ac-password-reset-3"
_PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    return copy_example(tmp_path / "spec")


def _flags(spec: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(spec), "--git-root", str(spec.parent)]


@pytest.mark.parametrize(
    "command",
    [["node"], ["node", "show"], ["node", "candidates"], ["node", "status"], ["trace"], ["diff"]],
    ids=lambda command: " ".join(command),
)
def test_help_prints_the_flags(command: list[str]) -> None:
    result = run_specdev(*command, "--help")
    assert result.returncode == 0 and result.stdout.strip()


def test_node_text_shows_where_the_node_lives(spec: Path) -> None:
    result = run_specdev("node", _CRITERION, *_flags(spec))
    assert result.returncode == 0, result.stderr
    first = result.stdout.splitlines()[0]
    assert first.startswith(_CRITERION) and "criterion" in first and "step 04" in first
    assert "04_fr_list.json" in result.stdout


def test_node_several_ids_and_an_unknown_one(spec: Path) -> None:
    result = run_specdev("node", _CRITERION, "fr-password-reset", *_flags(spec), "--json")
    assert [view["id"] for view in json.loads(result.stdout)["nodes"]] == [_CRITERION, "fr-password-reset"]
    unknown = run_specdev("node", "ac-password-rest-3", *_flags(spec))
    assert unknown.returncode == 1 and unknown.stderr.startswith("E706") and _CRITERION in unknown.stderr


def test_candidates_limit_and_query(spec: Path) -> None:
    result = run_specdev("node", "candidates", "--kind", "api", "--field", "derives_from", "--limit", "1", *_flags(spec), "--json")
    document = json.loads(result.stdout)
    assert result.returncode == 0 and len(document["candidates"]) == 1 and document["total"] >= 1
    filtered = run_specdev("node", "candidates", "--for", "api-password-reset-confirm", "--field", "derives_from", "--query", "zzzz", *_flags(spec), "--json")
    assert json.loads(filtered.stdout)["candidates"] == []


def test_candidates_of_replaces_is_e706(spec: Path) -> None:
    result = run_specdev("node", "candidates", "--kind", "api", "--field", "replaces", *_flags(spec))
    assert result.returncode == 1 and result.stderr.startswith("E706")


def test_status_writes_one_file_and_refuses_a_seed(spec: Path) -> None:
    before = {path: path.read_bytes() for path in spec.rglob("*.json")}
    refused = run_specdev("node", "status", "seed-accounts", "deprecated", *_flags(spec))
    assert refused.returncode == 1 and refused.stderr.startswith("E705") and "seed" in refused.stderr
    assert {path: path.read_bytes() for path in spec.rglob("*.json")} == before
    done = run_specdev("node", "status", _CRITERION, "not_applicable", *_flags(spec))
    assert done.returncode == 0 and done.stdout.strip() == f"{_CRITERION}: active -> not_applicable (04_fr_list.json)"
    changed = [path.name for path, data in before.items() if path.read_bytes() != data]
    assert changed == ["04_fr_list.json"]


def test_trace_up_lists_ancestors_and_never_the_entry_again(spec: Path) -> None:
    result = run_specdev("trace", _CRITERION, "--up", *_flags(spec), "--json")
    document = json.loads(result.stdout)
    assert set(document) == {"entry", "up"} and document["entry"]["id"] == _CRITERION
    reached = {node["id"] for nodes in document["up"]["groups"].values() for node in nodes}
    assert "fr-password-reset" in reached and _CRITERION not in reached


def test_trace_kinds_filter_and_depth(spec: Path) -> None:
    result = run_specdev("trace", _CRITERION, "--up", "--kinds", "fr", "--depth", "1", *_flags(spec), "--json")
    assert list(json.loads(result.stdout)["up"]["groups"]) == ["fr"]


def test_trace_recipe_16b_prints_the_pack(spec: Path) -> None:
    result = run_specdev("trace", _PLAN_ITEM, "--recipe", "16b", *_flags(spec))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith(f"pack 16b for {_PLAN_ITEM}")
    wrong = run_specdev("trace", "task-implement-password-reset-confirm", "--recipe", "16b", *_flags(spec))
    assert wrong.returncode == 1 and wrong.stderr.startswith("E707")


def test_context_scope_still_runs_and_writes_no_matrix(spec: Path) -> None:
    result = run_specdev("context", "scope", str(spec), "--entry", _CRITERION, "--repo-root", str(ROOT))
    assert result.returncode == 0 and "resolved_ids" in result.stdout
    assert not (spec / "extras" / "trace_matrix.json").exists()



@pytest.mark.parametrize(
    "command",
    [
        ["node", _CRITERION],
        ["node", "candidates", "--kind", "api", "--field", "derives_from"],
        ["node", "status", _CRITERION, "deprecated"],
        ["trace", _CRITERION],
        ["trace", _PLAN_ITEM, "--recipe", "16b"],
    ],
    ids=lambda command: " ".join(command[:2]),
)
def test_missing_spec_folder_is_e520_like_the_other_commands(tmp_path: Path, command: list[str]) -> None:
    missing = tmp_path / "no-such-spec"
    flags = ["--repo-root", str(ROOT), "--spec-root", str(missing)]
    result = run_specdev(*command, *flags)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == f"E520 UNRESOLVED_INPUT missing_spec_dir {missing}"
    envelope = json.loads(run_specdev(*command, *flags, "--json").stdout)
    assert (envelope["command"], envelope["errors"][0]["code"]) == (command[0], "E520")
    assert not missing.exists()


def _ids(groups: dict[str, list[dict[str, str]]]) -> set[str]:
    return {node["id"] for nodes in groups.values() for node in nodes}


def test_devspec_265_one_trace_call_and_one_candidates_call(spec: Path) -> None:
    """The pair the ticket asks for: one call gives the lineage and impact of a node, one gives a field's valid targets.

    ``test_trace_up_lists_ancestors_and_never_the_entry_again`` overlaps the up half only for ``fr-password-reset``.
    """
    trace = run_specdev("trace", _CRITERION, *_flags(spec), "--json")
    assert trace.returncode == 0, trace.stderr
    document = json.loads(trace.stdout)
    assert {"fr-password-reset", "cap-account-recovery", "scope-password-reset"} <= _ids(document["up"]["groups"])
    assert {"err-password-reset-confirm-token-expired", "fix-password-reset-expired-token", "threat-reset-token-replay"} <= _ids(document["down"]["groups"])

    listed = run_specdev("node", "candidates", "--kind", "api", "--field", "derives_from", *_flags(spec), "--json")
    assert listed.returncode == 0, listed.stderr
    offered = {item["id"] for item in json.loads(listed.stdout)["candidates"]}
    assert "fr-password-reset" in offered
    assert "cap-account-recovery" not in offered  # wrong kind
    assert "fix-password-reset-expired-token" not in offered  # downstream and wrong kind
