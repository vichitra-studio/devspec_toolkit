"""Every flag and positional of ``specdev node``, ``trace`` and ``diff`` reaches the library (M4 round 5, T-1).

One case per ``add_argument`` of ``graph/commands.py``, each on an input where the flag changes the output or the exit
code, so a handler that ignores the value (or forces one) fails here.  The cases run in this process through ``run_cli``
and assert content, not only an exit code.  ``WIP/1.2.0/impl/reviews/M4/R5_fixes_1.md`` lists the flag, the line of the
handler and the mutation each test kills.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.commands import run_node
from unit.graph._synth import ROOT, copy_build_spec, copy_example, git, make_toolkit, run_cli, write_json

_CRITERION = "ac-password-reset-3"
_PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"
_SKETCH = "02_system_sketch.json"


def _flags(spec: Path, git_root: Path | None = None) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(spec), "--git-root", str(git_root or spec.parent)]


def _json(code: int, out: str) -> dict[str, Any]:
    assert code == 0, out
    document = json.loads(out)
    assert isinstance(document, dict)
    return document


def _ids(groups: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {node["id"] for nodes in groups.values() for node in nodes}


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    return copy_example(tmp_path / "spec")


@pytest.fixture
def host(tmp_path: Path) -> Path:
    """A repository on ``main`` holding the worked example in ``spec/``: two commits, the second re-pins a third party."""
    repo = tmp_path / "host"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    spec = copy_example(repo / "spec")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "one")
    sketch = json.loads((spec / _SKETCH).read_text(encoding="utf-8"))
    sketch["third_parties"][1]["pin"] = "api-v4"
    (spec / _SKETCH).write_text(json.dumps(sketch, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "two")
    return repo


# --- node show ------------------------------------------------------------------------------------------------------

def test_node_show_full_adds_the_content_of_the_child_nodes(spec: Path) -> None:
    plain = _json(*run_cli("node", "show", "fr-password-reset", *_flags(spec), "--json"))
    full = _json(*run_cli("node", "show", "fr-password-reset", "--full", *_flags(spec), "--json"))
    assert plain["nodes"][0]["content"]["acceptance_criteria"] == ["ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-3"]
    criteria = full["nodes"][0]["content"]["acceptance_criteria"]
    assert [item["criterion_id"] for item in criteria] == ["ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-3"]
    assert "single-use link" in run_cli("node", "show", "fr-password-reset", "--full", *_flags(spec))[1]
    assert "single-use link" not in run_cli("node", "show", "fr-password-reset", *_flags(spec))[1]


def test_node_show_of_several_ids_shows_each_one_in_the_order_given(spec: Path) -> None:
    ids = ["fr-password-reset", "cap-account-recovery", _CRITERION]
    document = _json(*run_cli("node", "show", *ids, *_flags(spec), "--json"))
    assert [view["id"] for view in document["nodes"]] == ids


def _duplicate_an_fr(spec: Path) -> None:
    path = spec / "04_fr_list.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["functional_requirements"].append({"fr_id": "fr-password-reset", "statement": "The system shall exist twice."})
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_node_of_a_duplicated_id_exits_1_with_the_e704_line_and_a_unique_id_exits_0(spec: Path) -> None:
    _duplicate_an_fr(spec)
    code, out = run_cli("node", "fr-password-reset", *_flags(spec))
    assert code == 1 and "E704 Duplicate node id 'fr-password-reset'" in out
    code, out = run_cli("node", "fr-password-reset", *_flags(spec), "--json")
    assert code == 1 and json.loads(out)["errors"][0]["code"] == "E704"
    code, out = run_cli("node", "show", _CRITERION, *_flags(spec))
    assert code == 0 and out.startswith(_CRITERION)


# --- node candidates --------------------------------------------------------------------------------------------------

def _candidates(spec: Path, *args: str) -> dict[str, Any]:
    return _json(*run_cli("node", "candidates", *args, *_flags(spec), "--json"))


def _offered(document: dict[str, Any]) -> list[str]:
    return [item["id"] for item in document["candidates"]]


def test_candidates_kind_and_field_choose_the_holder_and_the_link(spec: Path) -> None:
    api = _candidates(spec, "--kind", "api", "--field", "derives_from")
    assert (api["kind"], api["field"]) == ("api", "derives_from")
    assert _offered(api) == ["fr-password-reset", "fr-password-reset-request"]
    capability = _candidates(spec, "--kind", "capability", "--field", "derives_from")
    assert (capability["kind"], "scope-password-reset" in _offered(capability)) == ("capability", True)
    other_field = run_cli("node", "candidates", "--kind", "api", "--field", "assumes", *_flags(spec), "--json")
    assert _offered(_json(*other_field)) != _offered(api)


def test_candidates_for_a_node_leaves_out_what_it_already_links_to(spec: Path) -> None:
    by_kind = _offered(_candidates(spec, "--kind", "api", "--field", "derives_from"))
    for_node = _candidates(spec, "--for", "api-password-reset-confirm", "--field", "derives_from")
    assert "fr-password-reset" in by_kind and _offered(for_node) == ["fr-password-reset-request"]
    assert for_node["total"] == 1


def test_candidates_query_keeps_the_ids_or_labels_that_contain_the_text(spec: Path) -> None:
    kept = _candidates(spec, "--kind", "api", "--field", "derives_from", "--query", "request")
    assert _offered(kept) == ["fr-password-reset-request"]
    assert _candidates(spec, "--kind", "api", "--field", "derives_from", "--query", "zzzz")["candidates"] == []
    assert len(_candidates(spec, "--kind", "api", "--field", "derives_from")["candidates"]) == 2


def test_candidates_limit_cuts_the_list_and_without_it_the_whole_list_is_shown(spec: Path) -> None:
    whole = _candidates(spec, "--kind", "capability", "--field", "derives_from")
    limited = _candidates(spec, "--kind", "capability", "--field", "derives_from", "--limit", "2")
    assert whole["total"] > 2 and len(whole["candidates"]) == whole["total"]
    assert len(limited["candidates"]) == 2 and limited["total"] == whole["total"]
    assert _offered(limited) == _offered(whole)[:2]


def test_candidates_text_output_lists_the_ids_and_json_is_not_text(spec: Path) -> None:
    code, out = run_cli("node", "candidates", "--kind", "api", "--field", "derives_from", *_flags(spec))
    assert code == 0 and "fr-password-reset-request" in out and not out.lstrip().startswith("{")


# --- node status ------------------------------------------------------------------------------------------------------

def test_status_id_and_value_choose_the_node_and_the_lifecycle(spec: Path) -> None:
    code, out = run_cli("node", "status", _CRITERION, "not_applicable", *_flags(spec))
    assert (code, out.strip()) == (0, f"{_CRITERION}: active -> not_applicable (04_fr_list.json)")
    code, out = run_cli("node", "status", "fr-password-reset-request", "deprecated", *_flags(spec), "--json")
    document = json.loads(out)
    assert code == 0 and (document["node_id"], document["old"], document["new"]) == ("fr-password-reset-request", "active", "deprecated")
    written = json.loads((spec / "04_fr_list.json").read_text(encoding="utf-8"))
    by_id = {fr["fr_id"]: fr for fr in written["functional_requirements"]}
    assert by_id["fr-password-reset-request"]["lifecycle"] == "deprecated" and "lifecycle" not in by_id["fr-password-reset"]


# --- trace: the walk --------------------------------------------------------------------------------------------------

def _trace(spec: Path, *args: str) -> dict[str, Any]:
    return _json(*run_cli("trace", *args, *_flags(spec), "--json"))


def test_trace_depth_limits_how_far_the_walk_goes(spec: Path) -> None:
    whole = _trace(spec, _CRITERION, "--up")
    one = _trace(spec, _CRITERION, "--up", "--depth", "1")
    assert _ids(one["up"]["groups"]) == {"fr-password-reset"} and one["up"]["count"] == 1
    assert whole["up"]["count"] == 8 and {"fr-password-reset", "cap-account-recovery", "seed-accounts"} <= _ids(whole["up"]["groups"])
    assert _ids(_trace(spec, _CRITERION, "--down", "--depth", "1")["down"]["groups"]) < _ids(_trace(spec, _CRITERION, "--down")["down"]["groups"])


def test_trace_kinds_filter_shows_only_the_kinds_named_and_still_walks_through_the_others(spec: Path) -> None:
    only_seed = _trace(spec, _CRITERION, "--up", "--kinds", "seed")
    assert list(only_seed["up"]["groups"]) == ["seed"] and only_seed["up"]["count"] == 1
    both = _trace(spec, _CRITERION, "--up", "--kinds", "fr,seed")
    assert list(both["up"]["groups"]) == ["seed", "fr"]
    shallow = _trace(spec, _CRITERION, "--up", "--kinds", "fr,seed", "--depth", "1")
    assert list(shallow["up"]["groups"]) == ["fr"]
    assert len(_trace(spec, _CRITERION, "--up")["up"]["groups"]) == 8


def test_trace_verbs_follows_only_the_link_fields_named(spec: Path) -> None:
    every = _ids(_trace(spec, _CRITERION, "--up")["up"]["groups"])
    only = _ids(_trace(spec, _CRITERION, "--up", "--verbs", "derives_from")["up"]["groups"])
    assert "asm-member-controls-email" in every and "asm-member-controls-email" not in only
    assert only < every and "fr-password-reset" in only
    assert _ids(_trace(spec, _CRITERION, "--up", "--verbs", "assumes")["up"]["groups"]) <= every - only | {"fr-password-reset"}


def test_trace_no_containment_does_not_follow_the_parent_and_child_edge(spec: Path) -> None:
    assert _trace(spec, _CRITERION, "--up", "--no-containment")["up"] == {"count": 0, "groups": {}, "records": []}
    assert _trace(spec, _CRITERION, "--up")["up"]["count"] == 8
    assert _trace(spec, "fr-password-reset", "--up", "--no-containment")["up"]["count"] < _trace(spec, "fr-password-reset", "--up")["up"]["count"]


def test_trace_up_and_down_choose_the_sides(spec: Path) -> None:
    assert set(_trace(spec, _CRITERION, "--up")) == {"entry", "up"}
    assert set(_trace(spec, _CRITERION, "--down")) == {"entry", "down"}
    assert set(_trace(spec, _CRITERION)) == {"entry", "up", "down"}
    assert set(_trace(spec, _CRITERION, "--up", "--down")) == {"entry", "up", "down"}


def test_trace_id_is_the_entry_of_the_walk_and_text_is_not_json(spec: Path) -> None:
    assert _trace(spec, "fr-password-reset", "--up")["entry"]["id"] == "fr-password-reset"
    code, out = run_cli("trace", "fr-password-reset", "--up", *_flags(spec))
    assert code == 0 and out.startswith("trace of fr-password-reset") and not out.lstrip().startswith("{")


# --- trace --recipe ---------------------------------------------------------------------------------------------------

def _pack(spec: Path, *args: str, git_root: Path | None = None) -> dict[str, Any]:
    return _json(*run_cli("trace", _PLAN_ITEM, "--recipe", *args, *_flags(spec, git_root), "--json"))


def test_recipe_role_chooses_the_pack(spec: Path) -> None:
    sixteen_b = _pack(spec, "16b")
    assert (sixteen_b["role"], sixteen_b["start"]["id"]) == ("16b", _PLAN_ITEM)
    code, out = run_cli("trace", "task-implement-password-reset-confirm", "--recipe", "16a", *_flags(spec), "--json")
    assert code == 0 and json.loads(out)["role"] == "16a" and json.loads(out)["start"]["id"] == "task-implement-password-reset-confirm"


def test_recipe_expand_adds_the_content_of_every_node_of_the_pack(spec: Path) -> None:
    def entries(document: dict[str, Any]) -> list[dict[str, Any]]:
        return [entry for section in document["sections"].values() for entry in section]

    plain, expanded = entries(_pack(spec, "16b")), entries(_pack(spec, "16b", "--expand"))
    assert plain and len(plain) == len(expanded)
    assert not any("content" in entry for entry in plain)
    with_content = {entry["id"] for entry in expanded if "content" in entry}
    assert {"ms-account-recovery", "task-implement-password-reset-confirm", "fr-password-reset"} <= with_content


def test_recipe_since_names_the_ref_the_dependency_report_compares_against(host: Path) -> None:
    spec = host / "spec"
    since_one = _pack(spec, "16b", "--since", "HEAD~1")["dependency_report"]
    assert since_one["base"] == "HEAD~1" and [(item["id"], item["changes"]) for item in since_one["changes"]] == [("tp-mailrelay", ["changed"])]
    same = _pack(spec, "16b", "--since", "HEAD")["dependency_report"]
    assert same["base"] == "HEAD" and same["changes"] == []
    default = _pack(spec, "16b")["dependency_report"]
    assert default["base"] == git(host, "rev-parse", "HEAD") and default["changes"] == []
    assert "tp-mailrelay changed since HEAD~1" in run_cli("trace", _PLAN_ITEM, "--recipe", "16b", "--since", "HEAD~1", *_flags(spec))[1]


def test_recipe_git_root_is_the_repository_the_dependency_report_reads(host: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = host / "spec"
    monkeypatch.chdir(tmp_path)
    found = _pack(spec, "16b", "--since", "HEAD~1", git_root=host)["dependency_report"]
    assert found["changes"] and found.get("unavailable") in (None, "")
    elsewhere = tmp_path / "not-a-repository"
    elsewhere.mkdir()
    missing = _pack(spec, "16b", "--since", "HEAD~1", git_root=elsewhere)["dependency_report"]
    assert missing["changes"] == [] and "E708" in json.dumps(missing)


@pytest.mark.parametrize(
    ("walk_flag", "value"),
    [("--up", None), ("--down", None), ("--depth", "2"), ("--kinds", "fr"), ("--verbs", "derives_from"), ("--no-containment", None)],
)
def test_recipe_is_rejected_with_each_flag_of_the_walk(spec: Path, walk_flag: str, value: str | None) -> None:
    extra = [walk_flag] if value is None else [walk_flag, value]
    code, out = run_cli("trace", _PLAN_ITEM, "--recipe", "16b", *extra, *_flags(spec))
    assert code == 2 and out.strip() == f"specdev trace: error: --recipe cannot be combined with {walk_flag}"


@pytest.mark.parametrize(("flag", "value"), [("--expand", None), ("--since", "HEAD")])
def test_expand_and_since_need_a_recipe(spec: Path, flag: str, value: str | None) -> None:
    extra = [flag] if value is None else [flag, value]
    code, out = run_cli("trace", _CRITERION, *extra, *_flags(spec))
    assert code == 2 and out.strip() == f"specdev trace: error: {flag} needs --recipe"


def test_recipe_with_all_the_flags_of_the_walk_names_them_all(spec: Path) -> None:
    code, out = run_cli("trace", _PLAN_ITEM, "--recipe", "16b", "--up", "--down", "--depth", "1", "--kinds", "fr", "--verbs", "derives_from", "--no-containment", *_flags(spec))
    assert code == 2 and out.strip() == "specdev trace: error: --recipe cannot be combined with --up, --down, --depth, --kinds, --verbs, --no-containment"
    code, out = run_cli("trace", _CRITERION, "--expand", "--since", "HEAD", *_flags(spec))
    assert code == 2 and out.strip() == "specdev trace: error: --expand, --since needs --recipe"


# --- diff -------------------------------------------------------------------------------------------------------------

def test_diff_ref_a_is_the_older_ref_and_ref_b_the_newer(host: Path) -> None:
    flags = _flags(host / "spec", host)
    forward = _json(*run_cli("diff", "HEAD~1", "HEAD", *flags, "--json"))
    backward = _json(*run_cli("diff", "HEAD", "HEAD~1", *flags, "--json"))
    same = _json(*run_cli("diff", "HEAD", "HEAD", *flags, "--json"))
    assert (forward["from"], forward["to"]) == ("HEAD~1", "HEAD") and (backward["from"], backward["to"]) == ("HEAD", "HEAD~1")
    assert (same["from"], same["to"]) == ("HEAD", "HEAD") and not same["groups"]
    assert "tp-mailrelay" in json.dumps(forward["groups"]) and "tp-mailrelay" in json.dumps(backward["groups"])
    assert run_cli("diff", "HEAD~1", "HEAD", *flags)[1].splitlines()[0] == "diff HEAD~1 -> HEAD: 1 node(s) changed"
    assert run_cli("diff", "HEAD", "HEAD~1", *flags)[1].splitlines()[0] == "diff HEAD -> HEAD~1: 1 node(s) changed"


def test_diff_ref_b_that_does_not_resolve_is_named_and_ref_a_alone_is_not_enough(host: Path) -> None:
    flags = _flags(host / "spec", host)
    code, out = run_cli("diff", "HEAD", "v-no-such", *flags)
    assert code == 1 and out.startswith("E708") and "v-no-such" in out
    code, out = run_cli("diff", "v-no-such-a", "HEAD", *flags)
    assert code == 1 and out.startswith("E708") and "v-no-such-a" in out


# --- the root flags, from a folder that is neither the toolkit, nor the spec folder, nor the repository ---------------

_CASES: dict[str, tuple[list[str], str]] = {
    "node show": (["node", "show", _CRITERION], "nodes"),
    "node <id>": (["node", _CRITERION], "nodes"),
    "node candidates": (["node", "candidates", "--kind", "api", "--field", "derives_from"], "candidates"),
    "node status": (["node", "status", _CRITERION, "deprecated"], "new"),
    "trace walk": (["trace", _CRITERION, "--up"], "up"),
    "trace recipe": (["trace", _PLAN_ITEM, "--recipe", "16b", "--since", "HEAD~1"], "dependency_report"),
    "diff": (["diff", "HEAD~1", "HEAD"], "groups"),
    "stale": (["stale"], "steps"),
}
_TEXT_START = {
    "node show": _CRITERION, "node <id>": _CRITERION, "node candidates": "api",
    "node status": f"{_CRITERION}: active -> deprecated", "trace walk": "trace of ac-password-reset-3",
    "trace recipe": "pack 16b for PWRESET_CONFIRM_EXPIRED_01", "diff": "diff HEAD~1 -> HEAD",
    "stale": "stale: pending replay by step",
}


@pytest.mark.parametrize("name", list(_CASES))
def test_each_command_uses_the_three_root_flags_it_is_given_not_the_current_folder(name: str, host: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv, key = _CASES[name]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    flags = _flags(host / "spec", host)
    code, text = run_cli(*argv, *flags)
    assert code == 0, text
    assert text.startswith(_TEXT_START[name]) or _TEXT_START[name] in text.splitlines()[0]
    assert not text.lstrip().startswith("{")
    if name == "node status":
        return  # a second run finds the lifecycle already set: see the next test
    document = _json(*run_cli(*argv, *flags, "--json"))
    assert key in document


def test_node_status_json_says_the_lifecycle_was_already_set_on_a_second_run(host: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv = ["node", "status", _CRITERION, "deprecated"]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    flags = _flags(host / "spec", host)
    assert run_cli(*argv, *flags)[0] == 0
    document = _json(*run_cli(*argv, *flags, "--json"))
    assert document["new"] == document["old"] == "deprecated"


def test_the_three_root_flags_are_accepted_by_every_command_even_where_they_are_not_read(spec: Path) -> None:
    """``node`` and the walk of ``trace`` never read git: ``--git-root`` is accepted so the default flag set never fails."""
    other = spec.parent / "nowhere"
    for argv in (["node", _CRITERION], ["trace", _CRITERION, "--up"], ["node", "candidates", "--kind", "api", "--field", "derives_from"]):
        with_flag = run_cli(*argv, "--repo-root", str(ROOT), "--spec-root", str(spec), "--git-root", str(other))
        without = run_cli(*argv, "--repo-root", str(ROOT), "--spec-root", str(spec))
        assert with_flag == without and with_flag[0] == 0


# --- stale: --step, --diff, --json ---------------------------------------------------------------------------------

def test_stale_step_keeps_only_the_suspects_that_step_holds(host: Path) -> None:
    """The host re-pinned a third party in commit two: step 07 holds a link to it, step 02 holds the connection."""
    flags = _flags(host / "spec", host)
    everything = _json(*run_cli("stale", *flags, "--json"))
    sliced = _json(*run_cli("stale", "--step", "07", *flags, "--json"))
    assert {"02", "07"} <= {step["step"] for step in everything["steps"]}
    assert [step["step"] for step in sliced["steps"]] == ["07"]
    assert {node["node"] for node in sliced["steps"][0]["suspect_nodes"]} == {"nfr-latency-reset-email"}
    text = run_cli("stale", "--step", "07", *flags)[1]
    assert "step 07:" in text and "step 02:" not in text


def test_stale_diff_adds_the_old_and_new_text_of_each_root(host: Path) -> None:
    flags = _flags(host / "spec", host)
    plain = _json(*run_cli("stale", *flags, "--json"))
    assert "diffs" not in plain
    document = _json(*run_cli("stale", "--diff", *flags, "--json"))
    diff = next(item for item in document["diffs"] if item["root"] == "tp-mailrelay")
    assert "-pin: api-v3" in diff["diff"] and "+pin: api-v4" in diff["diff"]
    text = run_cli("stale", "--diff", *flags)[1]
    assert "changed above: tp-mailrelay" in text and "-pin: api-v3" in text
    assert "changed above:" not in run_cli("stale", *flags)[1]


def test_stale_json_prints_the_suspects_by_step_and_the_totals(host: Path) -> None:
    document = _json(*run_cli("stale", *_flags(host / "spec", host), "--json"))
    assert set(document) == {"steps", "totals"}
    assert document["totals"]["suspect_links"] == sum(len(node["links"]) for step in document["steps"] for node in step["suspect_nodes"])
    assert [step["step"] for step in document["steps"]][:3] == ["00", "01", "02"]


# --- --json: the document, and the error envelope on the same flag --------------------------------------------------

@pytest.mark.parametrize(
    "argv",
    [["node", "show", "no-such-id"], ["node", "candidates", "--kind", "api", "--field", "refines"], ["node", "status", "no-such-id", "deprecated"],
     ["trace", "no-such-id"], ["trace", "no-such-id", "--recipe", "16b"]],
    ids=lambda argv: " ".join(argv[:2]),
)
def test_a_refusal_is_the_envelope_with_json_and_a_stderr_line_without(spec: Path, argv: list[str]) -> None:
    code, text = run_cli(*argv, *_flags(spec))
    assert code == 1 and text.startswith("E70") and not text.lstrip().startswith("{")
    code, out = run_cli(*argv, *_flags(spec), "--json")
    envelope = json.loads(out)
    assert code == 1 and envelope["status"] == "FAIL" and envelope["errors"][0]["code"].startswith("E70")


def test_diff_refusal_is_the_envelope_with_json_and_a_stderr_line_without(host: Path) -> None:
    flags = _flags(host / "spec", host)
    code, text = run_cli("diff", "v1", "v2", *flags)
    assert code == 1 and text.startswith("E708") and not text.lstrip().startswith("{")
    code, out = run_cli("diff", "v1", "v2", *flags, "--json")
    assert code == 1 and json.loads(out)["errors"][0]["code"] == "E708"


def test_status_validates_the_write_against_the_toolkit_named_by_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A toolkit whose FR schema allows no other lifecycle than ``active`` refuses the write; the default toolkit would accept it."""
    toolkit = make_toolkit(tmp_path / "toolkit")
    schema_path = toolkit / "schema" / "04_fr_list.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["functional_requirements"]["items"]["properties"]["lifecycle"] = {"enum": ["active"]}
    write_json(toolkit, "schema/04_fr_list.schema.json", schema)
    spec = copy_build_spec(tmp_path / "spec")
    document = json.loads((spec / "04_fr_list.json").read_text(encoding="utf-8"))
    write_json(spec, "04_fr_list.json", {"$schema": "vc:04-fr-list", **document})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    before = (spec / "04_fr_list.json").read_bytes()
    code, out = run_cli("node", "status", "fr-login", "deprecated", "--repo-root", str(toolkit), "--spec-root", str(spec))
    assert code == 1 and out.startswith("E705") and (spec / "04_fr_list.json").read_bytes() == before


# --- the default --repo-root of ``node``: the toolkit as a submodule below the current folder ----------------------------

@pytest.fixture
def submodule_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A host folder with ``devspec_toolkit/`` (the toolkit, linked) and ``spec/`` (the example); the current folder."""
    host_dir = tmp_path / "submodule-host"
    host_dir.mkdir()
    (host_dir / "devspec_toolkit").symlink_to(ROOT, target_is_directory=True)
    copy_example(host_dir / "spec")
    monkeypatch.chdir(host_dir)
    return host_dir


@pytest.mark.parametrize(
    ("argv", "start"),
    [
        (["node", _CRITERION], _CRITERION),
        (["node", "candidates", "--kind", "api", "--field", "derives_from"], "2 candidates for api.derives_from"),
        (["node", "status", _CRITERION, "deprecated"], f"{_CRITERION}: active -> deprecated"),
    ],
    ids=["show", "candidates", "status"],
)
def test_node_finds_the_toolkit_below_the_current_folder_when_repo_root_is_not_given(submodule_host: Path, argv: list[str], start: str) -> None:
    code, text = run_cli(*argv, "--spec-root", str(submodule_host / "spec"))
    assert code == 0, text
    assert text.startswith(start)


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_run_node_prints_the_help_of_node_for_a_help_flag_not_the_help_of_node_show(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    """``cli.main`` answers ``node -h`` with its own usage line, so the tokens are handed to ``run_node`` directly."""
    with pytest.raises(SystemExit) as raised:
        run_node([flag])
    out = capsys.readouterr().out
    assert raised.value.code == 0
    assert out.startswith("usage: specdev node [-h]") and "candidates" in out and "status" in out
    assert "Show nodes of the spec graph by id." not in out
