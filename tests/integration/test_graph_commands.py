"""``specdev node``, ``trace`` and ``diff`` run as subprocesses on a copy of the worked example (WI-M4-11)."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.core.json_utils import JsonUtilsError
from specdev_tools.graph import commands, lifecycle, queries, recipes, trace
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
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


def test_trace_kinds_filter_shows_only_the_kind_named(spec: Path) -> None:
    """The kinds only; ``--depth`` is pinned in ``test_graph_cli_flags.py`` (``test_trace_depth_limits_how_far_the_walk_goes``)."""
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


# --- a value the library refuses reaches the library (A1-3) ---------------------------------------------------------

def test_node_status_with_a_bad_value_is_e705_exit_1(spec: Path) -> None:
    before = {path: path.read_bytes() for path in spec.rglob("*.json")}
    result = run_specdev("node", "status", _CRITERION, "bogus", *_flags(spec))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == "E705 lifecycle 'bogus' is not one of active, deprecated, not_applicable"
    envelope = json.loads(run_specdev("node", "status", _CRITERION, "bogus", *_flags(spec), "--json").stdout)
    assert (envelope["command"], envelope["status"], envelope["errors"][0]["code"]) == ("node", "FAIL", "E705")
    assert {path: path.read_bytes() for path in spec.rglob("*.json")} == before


def test_trace_with_a_bad_recipe_role_is_e706_exit_1(spec: Path) -> None:
    result = run_specdev("trace", _PLAN_ITEM, "--recipe", "17z", *_flags(spec))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == "E706 no recipe role '17z'; roles: 16a, 16b, 16c"
    envelope = json.loads(run_specdev("trace", _PLAN_ITEM, "--recipe", "17z", *_flags(spec), "--json").stdout)
    assert (envelope["command"], envelope["errors"][0]["code"]) == ("trace", "E706")


def test_trace_with_an_empty_recipe_role_is_e706_not_a_plain_trace(spec: Path) -> None:
    result = run_specdev("trace", _PLAN_ITEM, "--recipe", "", *_flags(spec))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == "E706 no recipe role ''; roles: 16a, 16b, 16c"
    assert run_specdev("trace", _PLAN_ITEM, "--recipe", "", "--expand", *_flags(spec)).returncode == 1


def test_the_help_still_lists_the_values_that_are_no_longer_choices() -> None:
    assert "active, deprecated, not_applicable" in run_specdev("node", "status", "--help").stdout
    assert "16a, 16b, 16c" in run_specdev("trace", "--help").stdout


def test_node_help_says_flags_follow_the_id() -> None:
    assert "Flags follow the id" in run_specdev("node", "--help").stdout
    assert "unrecognized arguments: --json" in run_specdev("node", "--json", _CRITERION).stderr


# --- an unknown kind or link field of --kinds / --verbs (B-10) ------------------------------------------------------

@pytest.mark.parametrize(
    ("flag", "value", "message"),
    [("--kinds", "nosuch", "no kind 'nosuch'"), ("--verbs", "derive_from", "no link field 'derive_from'; nearest: derives_from")],
)
def test_trace_with_an_unknown_kind_or_verb_is_e706(spec: Path, flag: str, value: str, message: str) -> None:
    result = run_specdev("trace", _CRITERION, flag, value, *_flags(spec))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.startswith("E706") and message in result.stderr
    envelope = json.loads(run_specdev("trace", _CRITERION, flag, value, *_flags(spec), "--json").stdout)
    assert envelope["errors"][0]["code"] == "E706"
    known = run_specdev("trace", _CRITERION, "--kinds", "fr,seed", "--verbs", "derives_from,refines", *_flags(spec))
    assert known.returncode == 0, known.stderr


# --- a spec file the builder could not read (B-02, C-09) ------------------------------------------------------------

_UNREADABLE = "04_fr_list.json"
_NOTE = "could not read 04_fr_list.json; the answer may be incomplete"


@pytest.fixture
def broken(spec: Path) -> Path:
    (spec / _UNREADABLE).write_text('{"a":', encoding="utf-8")
    return spec


@pytest.mark.parametrize(
    ("command", "name"),
    [
        (["node", "cap-account-recovery"], "node"),
        (["node", "candidates", "--kind", "api", "--field", "derives_from"], "node"),
        (["trace", "cap-account-recovery"], "trace"),
        (["trace", _PLAN_ITEM, "--recipe", "16b"], "trace"),
    ],
    ids=["node", "candidates", "trace", "recipe"],
)
def test_an_unreadable_file_is_named_on_stderr_and_stdout_stays_the_answer(broken: Path, spec: Path, command: list[str], name: str) -> None:
    result = run_specdev(*command, *_flags(spec))
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == f"specdev {name}: {_NOTE}"
    assert result.stdout.strip()
    assert run_specdev(*command, *_flags(spec), "--json").stdout.lstrip().startswith("{")


def test_node_status_names_the_unreadable_file_too(broken: Path, spec: Path) -> None:
    result = run_specdev("node", "status", "cap-account-recovery", "deprecated", *_flags(spec))
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == f"specdev node: {_NOTE}"


@pytest.mark.parametrize(
    ("command", "code"),
    [
        (["node", "fr-password-reset"], "E706"),
        (["trace", "fr-password-reset"], "E706"),
        (["node", "status", "fr-password-reset", "deprecated"], "E705"),
    ],
    ids=["node", "trace", "status"],
)
def test_an_unknown_id_on_a_graph_with_unreadable_files_says_so(broken: Path, spec: Path, command: list[str], code: str) -> None:
    result = run_specdev(*command, *_flags(spec))
    assert result.returncode == 1
    finding = result.stderr.strip().splitlines()[-1]
    assert finding.startswith(code) and finding.endswith("these files could not be read, so the node may be in one of them: 04_fr_list.json")
    envelope = json.loads(run_specdev(*command, *_flags(spec), "--json").stdout)
    assert "these files could not be read" in envelope["errors"][0]["message"]


def test_a_readable_spec_prints_nothing_on_stderr_and_a_plain_unknown_id_has_no_note(spec: Path) -> None:
    assert run_specdev("node", _CRITERION, *_flags(spec)).stderr == ""
    unknown = run_specdev("node", "fr-no-such", *_flags(spec))
    assert unknown.returncode == 1 and "could not be read" not in unknown.stderr


def _refuse_the_write(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(*_args: object) -> None:
        raise JsonUtilsError("the edit would break the schema of 04_fr_list.json")

    monkeypatch.setattr(commands, "set_lifecycle", refused)


def test_a_write_the_json_tools_refuse_is_one_stderr_line_and_exit_1(spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _refuse_the_write(monkeypatch)
    code = commands.run_node(["status", _CRITERION, "deprecated", *_flags(spec)])
    captured = capsys.readouterr()
    assert code == 1 and captured.out == ""
    assert captured.err.strip() == "E705 the edit would break the schema of 04_fr_list.json"


def test_a_write_the_json_tools_refuse_under_json_is_the_envelope_on_stdout(spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _refuse_the_write(monkeypatch)
    code = commands.run_node(["status", _CRITERION, "deprecated", *_flags(spec), "--json"])
    captured = capsys.readouterr()
    assert code == 1 and captured.err == ""
    envelope = json.loads(captured.out)
    assert (envelope["command"], envelope["status"]) == ("node", "FAIL")
    assert envelope["errors"][0]["code"] == "E705"
    assert envelope["errors"][0]["message"] == "the edit would break the schema of 04_fr_list.json"


def test_a_refused_write_whose_message_carries_a_code_keeps_it(spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def refused(*_args: object) -> None:
        raise JsonUtilsError("E520 04_fr_list.json is unreadable")

    monkeypatch.setattr(commands, "set_lifecycle", refused)
    assert commands.run_node(["status", _CRITERION, "deprecated", *_flags(spec)]) == 1
    assert capsys.readouterr().err.strip() == "E520 04_fr_list.json is unreadable"


def test_a_status_the_node_already_has_writes_nothing_and_says_so(spec: Path) -> None:
    before = {path: path.read_bytes() for path in spec.rglob("*.json")}
    plain = run_specdev("node", "status", _CRITERION, "active", *_flags(spec))
    assert plain.returncode == 0 and plain.stdout.strip() == f"{_CRITERION}: already active, nothing written (04_fr_list.json)"
    as_json = run_specdev("node", "status", _CRITERION, "active", *_flags(spec), "--json")
    document = json.loads(as_json.stdout)
    assert as_json.returncode == 0 and document["old"] == document["new"] == "active"
    assert {path: path.read_bytes() for path in spec.rglob("*.json")} == before
    assert run_specdev("node", "status", _CRITERION, "deprecated", *_flags(spec)).returncode == 0
    written = (spec / "04_fr_list.json").read_bytes()
    again = run_specdev("node", "status", _CRITERION, "deprecated", *_flags(spec))
    assert again.stdout.strip() == f"{_CRITERION}: already deprecated, nothing written (04_fr_list.json)"
    assert (spec / "04_fr_list.json").read_bytes() == written


@pytest.mark.parametrize(
    ("unknown_id", "noted"), [(True, True), (False, False)], ids=["marked unknown id", "not marked, same words"]
)
def test_the_unreadable_note_follows_the_mark_of_the_raiser_not_the_words_of_the_message(unknown_id: bool, noted: bool) -> None:
    finding = make_error("E706", "no node has the id 'x'" if not unknown_id else "nothing is called 'x'")
    result = commands._with_unreadable_note(FindingError(finding, unknown_id=unknown_id), ["04_fr_list.json"])
    assert ("these files could not be read" in result.message) is noted
    assert result.message.startswith(finding.message)


@pytest.mark.parametrize(
    "raiser",
    [
        lambda graph: queries.node_view(graph, ["fr-no-such"], full=False),
        lambda graph: queries.candidates(graph, "derives_from", for_id="fr-no-such"),
        lambda graph: trace.trace_node(graph, "fr-no-such"),
        lambda graph: recipes.build_pack(graph, recipes.load_recipes(str(ROOT)), "16b", "fr-no-such"),
        lambda graph: lifecycle.plan_lifecycle_change(graph, "fr-no-such", "deprecated"),
    ],
    ids=["node", "candidates --for", "trace", "recipe start", "status"],
)
def test_every_unknown_id_refusal_is_marked(spec: Path, raiser: Callable[[Graph], object]) -> None:
    with pytest.raises(FindingError) as caught:
        raiser(build_graph(str(spec), str(ROOT)))
    assert caught.value.unknown_id


@pytest.mark.parametrize(
    "raiser",
    [
        lambda graph: queries.candidates(graph, "derives_from", kind="no-such-kind"),
        lambda graph: trace.trace_node(graph, _CRITERION, options=trace.TraceOptions(kinds=frozenset({"no-such-kind"}))),
        lambda graph: lifecycle.plan_lifecycle_change(graph, _CRITERION, "bogus"),
    ],
    ids=["kind", "trace option", "lifecycle value"],
)
def test_a_refusal_that_is_not_about_an_unknown_id_is_not_marked(spec: Path, raiser: Callable[[Graph], object]) -> None:
    with pytest.raises(FindingError) as caught:
        raiser(build_graph(str(spec), str(ROOT)))
    assert not caught.value.unknown_id
