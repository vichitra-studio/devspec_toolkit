"""Every flag and positional of ``specdev node``, ``trace`` and ``diff`` reaches the library (M4 round 5, T-1).

One case per ``add_argument`` of ``graph/commands.py``, each on an input where the flag changes the output or the exit
code, so a handler that ignores the value (or forces one) fails here.  The cases run in this process through ``run_cli``
and assert content, not only an exit code.  ``WIP/1.2.0/impl/reviews/M4/R5_fixes_1.md`` lists the flag, the line of the
handler and the mutation each test kills.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.commands import run_node
from specdev_tools.trace.lockfile import Lock, lock_path, read_lock, write_lock
from unit.trace._lock_support import EXAMPLE_HOST
from unit.graph._synth import ROOT, copy_build_spec, copy_example, git, make_toolkit, run_cli, write_json

_CRITERION = "ac-password-reset-3"
_PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"
_SKETCH = "02_system_sketch.json"
_NFR = "nfr-latency-reset-email"
_CONNECTION = "conn-identity-to-mailrelay"
_SCAFFOLD_STEP = "15"
_SCAFFOLD_FILE = "15_scaffold.json"
_FR_FILE = "04_fr_list.json"


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
    shutil.copytree(EXAMPLE_HOST / "docs", repo / "docs")  # the seed documents: without them every seed link is suspect and a hash write is E520
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


def test_node_status_is_e769_while_another_write_holds_the_lock_and_writes_nothing(spec: Path) -> None:
    from specdev_tools.trace.lockfile import with_write_lock

    before = (spec / "04_fr_list.json").read_bytes()
    with with_write_lock(str(spec)):
        code, out = run_cli("node", "status", _CRITERION, "deprecated", *_flags(spec))
    assert code == 1 and out.startswith("E769") and "another specdev write is running" in out, out
    assert (spec / "04_fr_list.json").read_bytes() == before
    assert run_cli("node", "status", _CRITERION, "deprecated", *_flags(spec))[0] == 0


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
    "node rename": (["node", "rename", _CRITERION, "ac-password-reset-3b", "--dry-run"], "links"),
    "trace walk": (["trace", _CRITERION, "--up"], "up"),
    "trace recipe": (["trace", _PLAN_ITEM, "--recipe", "16b", "--since", "HEAD~1"], "dependency_report"),
    "diff": (["diff", "HEAD~1", "HEAD"], "groups"),
    "stale": (["stale"], "steps"),
    "attest": (["attest", "--prune"], "pruned"),
    "step create": (["step", "create", _SCAFFOLD_STEP, "--dry-run", "--from"], "targets"),
    "step ready": (["step", "ready", "00"], "blockers"),
    "coverage": (["coverage"], "counts"),
}
_TEXT_START = {
    "node show": _CRITERION, "node <id>": _CRITERION, "node candidates": "api",
    "node status": f"{_CRITERION}: active -> deprecated", "node rename": f"[dry-run] would rename {_CRITERION} -> ac-password-reset-3b",
    "trace walk": "trace of ac-password-reset-3",
    "trace recipe": "pack 16b for PWRESET_CONFIRM_EXPIRED_01", "diff": "diff HEAD~1 -> HEAD",
    "stale": "stale: pending replay by step", "attest": "attest --prune: no orphan",
    "step create": "[dry-run] would create", "step ready": "step 00: ready",
    "coverage": "Link counts",
}


def _detach_scaffold(host: Path, drafts: Path, name: str = _SCAFFOLD_FILE) -> Path:
    """Move the step file *name* (default step 15) out of the host's spec folder, so ``step create`` can write it; the moved file is the draft."""
    drafts.mkdir(exist_ok=True)
    return Path(shutil.move(host / "spec" / name, drafts / name))


@pytest.mark.parametrize("name", list(_CASES))
def test_each_command_uses_the_three_root_flags_it_is_given_not_the_current_folder(name: str, host: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv, key = _CASES[name]
    if name == "step create":
        argv = [*argv, str(_detach_scaffold(host, tmp_path / "drafts"))]
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


# --- node rename: OLD NEW, --dry-run, --label ---------------------------------------------------------------------------

def _spec_bytes(spec: Path) -> dict[str, bytes]:
    return {str(path.relative_to(spec)): path.read_bytes() for path in spec.rglob("*") if path.is_file()}


def test_node_rename_is_a_subcommand_not_an_id_whatever_follows_it(spec: Path) -> None:
    """``node rename a b`` renames ``a``; it is not ``node show rename a b``, which asks for the ids ``rename``, ``a`` and ``b``."""
    code, out = run_cli("node", "rename", "ac-no-such-node", "ac-new", *_flags(spec))
    assert code == 1 and out.startswith("E706") and "'ac-no-such-node'" in out and "'rename'" not in out
    code, out = run_cli("node", "show", "rename", "ac-no-such-node", *_flags(spec))
    assert code == 1 and "'rename'" in out
    code, out = run_cli("node", "rename", "--help")
    assert code == 0 and "--dry-run" in out and "--label" in out


def test_node_rename_dry_run_writes_nothing(spec: Path) -> None:
    before = _spec_bytes(spec)
    code, out = run_cli("node", "rename", _CRITERION, "ac-password-reset-3b", "--dry-run", *_flags(spec))
    assert code == 0 and out.startswith("[dry-run] would rename") and _spec_bytes(spec) == before
    code, out = run_cli("node", "rename", _CRITERION, "ac-password-reset-3b", *_flags(spec))
    assert code == 0 and out.startswith(f"renamed {_CRITERION} -> ac-password-reset-3b") and _spec_bytes(spec) != before
    assert [view["id"] for view in _json(*run_cli("node", _CRITERION, *_flags(spec), "--json"))["nodes"]] == ["ac-password-reset-3b"]


def test_node_rename_label_renames_the_label_not_the_id(spec: Path) -> None:
    term, label = "term-reset-token", "recovery code"
    code, out = run_cli("node", "rename", term, label, *_flags(spec))
    assert code == 1 and out.startswith("E770") and "is not an id" in out
    code, out = run_cli("node", "rename", "--label", term, label, *_flags(spec))
    assert code == 0 and out.startswith(f"relabelled {term}")
    shown = _json(*run_cli("node", term, *_flags(spec), "--json"))["nodes"][0]
    assert shown["id"] == term and shown["content"]["term"] == label and shown["aliases"] == []


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
    assert [step["step"] for step in document["steps"]] == ["02", "02a", "07"]  # the re-pin of tp-mailrelay and what is built on it; the seed documents are in the host


# --- coverage: --by, --json --------------------------------------------------------------------------------------------

def test_coverage_by_fr_prints_the_matrix_of_the_frs(host: Path) -> None:
    flags = _flags(host / "spec", host)
    text = run_cli("coverage", "--by", "fr", *flags)[1]
    assert text.startswith("fr-password-reset  ") and f"  {_CRITERION}  refined: current" in text
    assert "Link counts" not in text
    document = _json(*run_cli("coverage", "--by", "fr", *flags, "--json"))
    assert set(document) == {"command", "by", "by_fr", "exempt"} and document["by"] == "fr"
    assert [row["id"] for row in document["by_fr"]] == ["fr-password-reset", "fr-password-reset-request"]
    criterion = next(item for item in document["by_fr"][0]["criteria"] if item["id"] == _CRITERION)
    assert criterion["refined"] == "current"
    fixtures = next(group for group in criterion["groups"] if group["kind"] == "fixture")
    # the host re-pins a third party in its second commit: that does not reach the fixture (before the seed documents were in the host, every seed link was suspect and so was this one)
    assert fixtures["links"] == [{"node": "fix-password-reset-expired-token", "field": "verifies", "current": True, "suspect": False, "historical": False}]


def test_coverage_json_prints_the_counts_as_json(host: Path) -> None:
    flags = _flags(host / "spec", host)
    document = _json(*run_cli("coverage", *flags, "--json"))
    assert set(document) == {"command", "counts", "criteria_refined", "exempt", "role_findings"}
    assert set(document["counts"]) == {"fr_api_coverage", "fr_fixture_coverage", "capability_fr_coverage"}
    assert document["counts"]["capability_fr_coverage"] == {"linked": 1, "total": 1, "ratio": 1.0, "unlinked": []}
    assert document["role_findings"] == {"counts": {}, "by_step": []}
    assert not run_cli("coverage", *flags)[1].lstrip().startswith("{")


# --- attest: the node, --field, --target, --step, --yes, --dry-run, --prune, --json -------------------------------------

@pytest.fixture
def full_host(tmp_path: Path) -> Path:
    """The worked example with its seed documents, in a repository whose second commit re-pins a third party."""
    repo = tmp_path / "full"
    shutil.copytree(EXAMPLE_HOST, repo)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "one")
    sketch = json.loads((repo / "spec" / _SKETCH).read_text(encoding="utf-8"))
    sketch["third_parties"][1]["pin"] = "api-v4"
    (repo / "spec" / _SKETCH).write_text(json.dumps(sketch, indent=2) + "\n", encoding="utf-8")
    return repo


def _attest_json(host: Path, *args: str, code: int = 0) -> dict[str, Any]:
    status, out = run_cli("attest", *args, *_flags(host / "spec", host), "--json")
    assert status == code, out
    return json.loads(out)


def _attested(document: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(link["holder"], link["field"], link["target"]) for link in document["attested"]]


def _lock_text(host: Path) -> str:
    return Path(lock_path(str(host / "spec"))).read_text(encoding="utf-8")


def test_attest_node_id_picks_the_node_whose_links_are_attested(full_host: Path) -> None:
    assert _attested(_attest_json(full_host, _NFR)) == [(_NFR, "relies_on", "tp-mailrelay")]
    assert _attested(_attest_json(full_host, _CONNECTION)) == [(_CONNECTION, "connects_to", "tp-mailrelay")]


def test_attest_field_keeps_only_the_links_of_that_field(full_host: Path) -> None:
    assert _attested(_attest_json(full_host, _NFR, "--field", "relies_on")) == [(_NFR, "relies_on", "tp-mailrelay")]
    assert _attest_json(full_host, _NFR, "--field", "derives_from")["attested"] == []


def test_attest_target_keeps_only_the_links_to_that_target(full_host: Path) -> None:
    assert _attested(_attest_json(full_host, _NFR, "--target", "tp-mailrelay")) == [(_NFR, "relies_on", "tp-mailrelay")]
    assert _attest_json(full_host, _NFR, "--target", "fr-password-reset")["attested"] == []


def test_attest_step_attests_the_suspect_nodes_of_that_step_only(full_host: Path) -> None:
    assert _attested(_attest_json(full_host, "--step", "07")) == [(_NFR, "relies_on", "tp-mailrelay")]
    assert _attested(_attest_json(full_host, "--step", "02")) == [(_CONNECTION, "connects_to", "tp-mailrelay")]
    assert _attest_json(full_host, "--step", "05")["attested"] == []


def test_attest_writes_only_with_yes(full_host: Path) -> None:
    before = _lock_text(full_host)
    document = _attest_json(full_host, _NFR)
    assert document["written"] is False and _lock_text(full_host) == before
    document = _attest_json(full_host, _NFR, "--yes")
    assert document["written"] is True and _lock_text(full_host) != before
    assert _nodes_in_step(full_host, "07") == []


def test_attest_dry_run_writes_nothing_even_with_yes(full_host: Path) -> None:
    before = _lock_text(full_host)
    document = _attest_json(full_host, _NFR, "--yes", "--dry-run")
    assert document["written"] is False and _attested(document) == [(_NFR, "relies_on", "tp-mailrelay")]
    assert _lock_text(full_host) == before


def test_attest_prune_removes_the_orphan_entry_and_dry_run_only_lists_it(full_host: Path) -> None:
    lock = read_lock(str(full_host / "spec"))
    orphan = replace(lock.entries[0], source=_NFR, field="relies_on", target="tp-gone")
    write_lock(str(full_host / "spec"), Lock((*lock.entries, orphan)))
    listed = json.loads(run_cli("attest", "--prune", "--dry-run", *_flags(full_host / "spec", full_host), "--json")[1])
    assert listed == {"written": False, "pruned": [{"source": _NFR, "field": "relies_on", "target": "tp-gone"}]}
    assert orphan in read_lock(str(full_host / "spec")).entries
    done = json.loads(run_cli("attest", "--prune", *_flags(full_host / "spec", full_host), "--json")[1])
    assert done["written"] is True and orphan not in read_lock(str(full_host / "spec")).entries


def test_attest_json_prints_the_document_and_text_prints_the_summary(full_host: Path) -> None:
    document = _attest_json(full_host, _NFR)
    assert set(document) == {"written", "attested", "blocked", "diffs"}
    assert set(document["attested"][0]) == {"holder", "field", "target", "reason", "cause", "old", "new"}
    text = run_cli("attest", _NFR, *_flags(full_host / "spec", full_host))[1]
    assert text.splitlines()[0] == "attest: would write 1 link on 1 node (run again with --yes to write)"
    assert "-pin: api-v3" in text and "+pin: api-v4" in text


def _nodes_in_step(host: Path, step: str) -> list[str]:
    document = json.loads(run_cli("stale", "--step", step, *_flags(host / "spec", host), "--json")[1])
    return [node["node"] for entry in document["steps"] for node in entry["suspect_nodes"]]


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


# --- lock install-driver: --driver-command and the root flags --------------------------------------------------------

def test_lock_install_driver_writes_the_command_and_the_line_for_the_spec_root_it_is_given(host: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    flags = _flags(host / "spec", host)
    document = _json(*run_cli("lock", "install-driver", "--driver-command", "/venv/bin/specdev lock merge", *flags, "--json"))
    assert document["attribute_line"] == "spec/extras/trace.lock.json merge=specdev-trace-lock"
    assert git(host, "config", "--local", "merge.specdev-trace-lock.driver") == "/venv/bin/specdev lock merge %O %A %B %P"
    assert document["attribute_line"] in (host / ".git" / "info" / "attributes").read_text(encoding="utf-8").splitlines()
    code, text = run_cli("lock", "install-driver", "--driver-command", "/venv/bin/specdev lock merge", *flags)
    assert code == 0 and text.startswith("lock merge driver installed: spec/extras/trace.lock.json merge=specdev-trace-lock")


def test_lock_install_driver_refuses_a_spec_folder_outside_the_git_root(host: Path, tmp_path: Path) -> None:
    outside = copy_example(tmp_path / "outside" / "spec")
    code, out = run_cli("lock", "install-driver", "--driver-command", "x", *_flags(outside, host))
    assert code == 1 and out.startswith("E708")


# --- json patch|insert|delete --id / --step: the id forms of the json subcommands (WI-M5-09) ---------------------------------

_FR_FILE = "04_fr_list.json"
_FR_REQUEST = "fr-password-reset-request"
_API_FILE = "05_interface_contracts.json"


@pytest.fixture
def id_host(tmp_path: Path) -> Path:
    """The worked example with its seed documents and lock, as a host folder."""
    root = tmp_path / "id_host"
    shutil.copytree(EXAMPLE_HOST, root)
    return root


def _fr_ids(host: Path) -> list[str]:
    return [item["fr_id"] for item in json.loads((host / "spec" / _FR_FILE).read_text(encoding="utf-8"))["functional_requirements"]]


def _statement(host: Path, node_id: str) -> str:
    items = json.loads((host / "spec" / _FR_FILE).read_text(encoding="utf-8"))["functional_requirements"]
    return next(item["statement"] for item in items if item["fr_id"] == node_id)


def test_json_id_names_the_node_the_write_applies_to(id_host: Path) -> None:
    flags = _flags(id_host / "spec", id_host)
    other = _statement(id_host, "fr-password-reset")
    text = "The system shall email a single-use reset link to the address of the account."
    assert run_cli("json", "patch", "--id", _FR_REQUEST, ".statement", json.dumps(text), *flags)[0] == 0
    assert (_statement(id_host, _FR_REQUEST), _statement(id_host, "fr-password-reset")) == (text, other)
    code, out = run_cli("json", "patch", "--id", "fr-password-reset", ".statement", json.dumps(other + " (reworded)"), *flags)
    assert code == 0 and _statement(id_host, "fr-password-reset").endswith("(reworded)") and _statement(id_host, _FR_REQUEST) == text
    missing = run_cli("json", "patch", "--id", "fr-nobody", ".statement", json.dumps(text), *flags)
    assert missing[0] == 1 and missing[1].startswith("E706")
    assert run_cli("json", "patch", ".statement", json.dumps(text), *flags)[0] == 2


def test_json_step_names_the_file_of_a_new_top_level_node(id_host: Path) -> None:
    flags = _flags(id_host / "spec", id_host)
    fr = {
        "statement": "The system shall let an admin revoke an outstanding reset token before it expires.", "scope": "in", "priority": "must-have",
        "capability_ref": {"id": "cn:project:capability:account-recovery", "kind": "capability", "version": "1.0.0"},
        "derives_from": ["cap-account-recovery"],
        "acceptance_criteria": [{"text": "Given a revoked token, when it is redeemed, then no password changes.", "scope": "in"}] * 2,
    }
    code, out = run_cli("json", "insert", "--step", "04", ".functional_requirements", json.dumps(fr), *flags, "--json")
    assert code == 0 and json.loads(out)["file"] == _FR_FILE and len(_fr_ids(id_host)) == 3
    unknown = run_cli("json", "insert", "--step", "99", ".functional_requirements", json.dumps(fr), *flags)
    assert unknown[0] == 1 and unknown[1].startswith("E706")
    wrong_step = run_cli("json", "insert", "--step", "05", ".functional_requirements", json.dumps(fr), *flags)
    assert wrong_step[0] == 1 and "step 05 has no node collection .functional_requirements" in wrong_step[1]
    assert run_cli("json", "insert", ".functional_requirements", json.dumps(fr), *flags)[0] == 2


def test_json_id_full_shows_the_whole_target_text(id_host: Path) -> None:
    flags = _flags(id_host / "spec", id_host)
    links = json.dumps(["fr-password-reset", _FR_REQUEST])
    short = json.loads(run_cli("json", "patch", "--id", "api-password-reset-confirm", ".derives_from", links, *flags, "--dry-run", "--json")[1])
    full = json.loads(run_cli("json", "patch", "--id", "api-password-reset-confirm", ".derives_from", links, *flags, "--dry-run", "--full", "--json")[1])
    (short_target,), (full_target,) = short["targets"], full["targets"]
    assert short_target["text"].endswith("...") and len(short_target["text"]) == 303
    assert len(full_target["text"]) > 303 and full_target["text"].startswith(short_target["text"][:-3])


def test_json_id_dry_run_writes_nothing(id_host: Path) -> None:
    flags = _flags(id_host / "spec", id_host)
    before = {path: path.read_bytes() for path in (id_host / "spec").rglob("*") if path.is_file()}
    argv = ["json", "insert", "--id", "api-password-reset-confirm", ".derives_from", json.dumps(_FR_REQUEST), *flags]
    code, out = run_cli(*argv, "--dry-run")
    assert code == 0 and out.startswith("[dry-run] would insert into api-password-reset-confirm") and "lock entry to write" in out and "lock entry written" not in out
    assert {path: path.read_bytes() for path in (id_host / "spec").rglob("*") if path.is_file()} == before
    assert json.loads(run_cli(*argv, "--dry-run", "--json")[1])["written"] is False
    assert run_cli(*argv)[0] == 0 and (id_host / "spec" / _API_FILE).read_bytes() != before[id_host / "spec" / _API_FILE]


def test_json_id_raw_takes_the_value_as_a_string(id_host: Path) -> None:
    flags = _flags(id_host / "spec", id_host)
    text = "The system shall email a single-use reset link to the address of the account."
    bare = run_cli("json", "patch", "--id", _FR_REQUEST, ".statement", text, *flags)
    assert bare[0] == 1 and bare[1].startswith("E767") and "not valid JSON" in bare[1]
    assert run_cli("json", "patch", "--id", _FR_REQUEST, ".statement", text, "--raw", *flags)[0] == 0
    assert _statement(id_host, _FR_REQUEST) == text


# --- step create: --from, --dry-run; step ready: --json (WI-M5-10, WI-M5-11) ------------------------------------------------

def test_step_create_from_reads_the_draft_file(host: Path, tmp_path: Path) -> None:
    flags = _flags(host / "spec", host)
    whole = _detach_scaffold(host, tmp_path / "drafts", _FR_FILE)
    document = json.loads(whole.read_text(encoding="utf-8"))
    first = document["functional_requirements"][0]
    extra = {**first, "fr_id": "fr-password-reset-audit", "acceptance_criteria": [{"scope": "in", "text": "Every reset is logged."}, {"scope": "in", "text": "A log line names no password."}]}
    document["functional_requirements"].append(extra)
    larger = tmp_path / "drafts" / "larger.json"
    larger.write_text(json.dumps(document), encoding="utf-8")
    full = _json(*run_cli("step", "create", "04", "--from", str(whole), "--dry-run", *flags, "--json"))
    larger_run = _json(*run_cli("step", "create", "04", "--from", str(larger), "--dry-run", *flags, "--json"))
    assert len(full["targets"]) == 2 and len(larger_run["targets"]) == 3
    code, out = run_cli("step", "create", "04", "--from", str(tmp_path / "no-such-draft.json"), *flags)
    assert code == 1 and out.startswith("E767") and "cannot read the draft" in out


def test_step_create_dry_run_writes_nothing(host: Path, tmp_path: Path) -> None:
    flags = _flags(host / "spec", host)
    draft = _detach_scaffold(host, tmp_path / "drafts")
    lock_before = _lock_text(host)
    argv = ["step", "create", _SCAFFOLD_STEP, "--from", str(draft), *flags]
    assert run_cli(*argv, "--dry-run")[0] == 0
    assert not (host / "spec" / _SCAFFOLD_FILE).exists() and _lock_text(host) == lock_before
    assert run_cli(*argv)[0] == 0 and (host / "spec" / _SCAFFOLD_FILE).exists()


def test_step_ready_json_prints_the_blockers_as_the_envelope(full_host: Path) -> None:
    flags = _flags(full_host / "spec", full_host)
    status, out = run_cli("step", "ready", "05", *flags, "--json")
    document = json.loads(out)
    assert status == 1 and document["command"] == "step ready" and document["status"] == "FAIL" and document["error_count"] == 1
    assert document["errors"][0]["code"] == "E773" and document["step"] == "05" and document["ready"] is False
    assert document["replay_first"] == "02" and document["upstream"] == ["00", "02", "04"]
    assert [(b["step"], b["reason"], b["node"], b["field"], b["target"]) for b in document["blockers"]] == [("02", "suspect", _CONNECTION, "connects_to", "tp-mailrelay")]
    status, out = run_cli("step", "ready", "04", *flags, "--json")
    assert status == 0 and json.loads(out)["status"] == "PASS" and json.loads(out)["blockers"] == []
