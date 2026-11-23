"""Every sort of the graph code is pinned by a test on input given in the wrong order (M4 round 5, T-2).

A listing built from a set or a dict depends on ``PYTHONHASHSEED`` or on insertion order when its sort is dropped, so each
case here gives the input in reverse order and, where the input is a set, runs under several hash seeds in a subprocess.
Each section comment names the module and the functions whose ``sorted(`` / ``.sort(`` its tests pin.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.context.scope_resolver import resolve_scope
from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.graph import queries
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import contract_view
from specdev_tools.graph.diff import diff_to_dict, group_changes, render_text
from specdev_tools.graph.recipes import RecipeError, parse_recipes

from ._synth import EXAMPLE_SPEC, HASH_SEEDS, ROOT, copy_build_spec, copy_example, make_toolkit, run_python_seeded, run_specdev_seeded, write_json
from ._builders import _TASK_FILE, _core_16b, _criterion, _diff, _docs, _fr, _raw, _set, _snapshot

_CRITERION = "ac-password-reset-3"
_FLAGS = ["--repo-root", str(ROOT), "--spec-root", str(EXAMPLE_SPEC)]


# --- graph/trace.py _unknown_names  the unknown names of --kinds / --verbs, named in name order ---------------------

@pytest.mark.parametrize("seed", HASH_SEEDS)
@pytest.mark.parametrize(("flag", "subject"), [("--kinds", "kind"), ("--verbs", "link field")])
def test_unknown_kinds_and_verbs_are_named_in_name_order_whatever_the_hash_seed(seed: int, flag: str, subject: str) -> None:
    result = run_specdev_seeded(seed, "trace", _CRITERION, flag, "zzz,mmm,qqq,aaa,kkk", *_FLAGS)
    assert result.returncode == 1 and result.stderr.startswith("E706")
    assert re.findall(rf"no {subject} '(\w+)'", result.stderr) == ["aaa", "kkk", "mmm", "qqq", "zzz"]


# --- graph/resolve.py _cycle_errors  the link fields of a cycle -----------------------------------------------------

_CYCLE_CODE = """
import json
from unit.graph._builders import _decl, _graph, _node
from specdev_tools.graph.resolve import resolve_graph
zeta, mid, alpha = (_decl(name, ["B"], ["B"]) for name in ("zeta", "mid", "alpha"))
graph = _graph([_node("a", "B", "s2", [(zeta, "b")]), _node("b", "B", "s2", [(mid, "c")]), _node("c", "B", "s2", [(alpha, "a")])])
print(json.dumps([error.message for error in resolve_graph(graph)]))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_a_cycle_through_three_link_fields_names_the_fields_in_name_order(seed: int) -> None:
    assert json.loads(run_python_seeded(seed, _CYCLE_CODE)) == ["Link cycle within step s2: a, b, c (field alpha, mid, zeta)"]


# --- graph/diff.py diff_snapshots, group_changes  the changed nodes, the new removals and the groups ----------------

_DIFF_CODE = """
import json
from unit.graph._builders import _TASK_FILE, _criterion, _diff, _docs, _fr

names = ["fr-m", "fr-c", "fr-x", "fr-a", "fr-q", "fr-e", "fr-t"]
old, new = _docs(*[_fr(n, "Old.") for n in names]), _docs(*[_fr(n, "New.") for n in names])
changed = [change.id for change in _diff(old, new).changes]

def roadmap(removes):
    criterion = {**_criterion("tc-a", "Done."), "removes": removes}
    task = {"task_id": "task-a", "description": "Do it.", "acceptance_criteria": [criterion]}
    return {_TASK_FILE: {"milestones": [{"milestone_id": "ms-a", "tasks": [task]}]}}

diff = _diff(roadmap([]), roadmap(["ac-z", "ac-m", "ac-q", "ac-a", "ac-x"]))
print(json.dumps({"changed": changed, "removes": [list(pair) for pair in diff.new_removes]}))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_changed_nodes_and_new_removals_are_listed_in_id_order_whatever_the_hash_seed(seed: int) -> None:
    got = json.loads(run_python_seeded(seed, _DIFF_CODE))
    assert got["changed"] == ["fr-a", "fr-c", "fr-e", "fr-m", "fr-q", "fr-t", "fr-x"]
    assert got["removes"] == [["tc-a", f"ac-{name}"] for name in ("a", "m", "q", "x", "z")]


def _interleaved_diff() -> Any:
    """Added nodes whose id order (a-task, ms-a, z-fr) is the reverse of the order of their ``(role, kind)`` groups."""
    task = {"task_id": "a-task", "description": "Do it.", "acceptance_criteria": []}
    old = _docs(_fr("fr-m", "Old."))
    new = {**_docs(_fr("fr-m", "Old."), _fr("z-fr", "New.")), _TASK_FILE: {"milestones": [{"milestone_id": "ms-a", "tasks": [task]}]}}
    return _diff(old, new)


def test_groups_come_in_role_then_kind_order_not_in_id_order() -> None:
    diff = _interleaved_diff()
    assert [change.id for change in diff.changes] == ["a-task", "ms-a", "z-fr"]
    expected = [("obligation-system", "fr"), ("plan", "roadmap-milestone"), ("plan", "task")]
    assert list(group_changes(diff)) == expected
    assert [(group["role"], group["kind"]) for group in diff_to_dict(diff)["groups"]] == expected
    text = render_text(diff)
    assert text.index("z-fr") < text.index("ms-a") < text.index("a-task")


# --- graph/queries.py _incoming, _view, _link_decl, nearest_suffix  the incoming counts, the aliases, the link fields and the nearest names ---

def test_incoming_counts_are_listed_by_verb_then_kind_not_in_the_order_the_links_were_built() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    assert [(item.verb, item.kind) for item in queries.node_view(graph, ["fr-password-reset"]).views[0].incoming] == [
        ("constrains", "invariant"), ("constrains", "nfr"), ("derives_from", "api"), ("schedules", "design-milestone"),
    ]
    assert [(item.verb, item.kind) for item in queries.node_view(graph, [_CRITERION]).views[0].incoming] == [
        ("derives_from", "api-error"), ("mitigated_by", "edge-case"), ("refines", "task-criterion"), ("verifies", "fixture"),
    ]


def test_the_aliases_of_a_node_are_listed_by_name_whatever_the_order_they_were_added() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    for alias in ("fr-z-old", "fr-m-old", "fr-a-old"):
        graph.alias_index[alias] = "fr-password-reset"
    graph.alias_index["cap-other-old"] = "cap-account-recovery"
    assert queries.node_view(graph, ["fr-password-reset"]).views[0].aliases == ("fr-a-old", "fr-m-old", "fr-z-old")


def test_the_link_fields_of_a_kind_are_named_in_name_order() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    assert [link.field for link in graph.decls["api"].links] != sorted(link.field for link in graph.decls["api"].links)
    with pytest.raises(queries.QueryTargetError) as raised:
        queries.candidates(graph, "refines", kind="api")
    assert str(raised.value).endswith("its link fields: assumes, depends_on, derives_from, provided_by, relies_on, replaces")


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_the_nearest_kinds_are_the_same_whatever_the_hash_seed(seed: int) -> None:
    result = run_specdev_seeded(seed, "trace", _CRITERION, "--kinds", "xr,frr", *_FLAGS)
    assert result.returncode == 1
    assert result.stderr.strip() == "E706 no kind 'frr'; nearest: fr, nfr, fixture; no kind 'xr'; nearest: fr, nfr, fixture"


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_kinds_at_the_same_distance_are_offered_in_name_order_whatever_the_hash_seed(seed: int) -> None:
    result = run_specdev_seeded(seed, "trace", _CRITERION, "--kinds", "aa", *_FLAGS)
    assert result.stderr.strip() == "E706 no kind 'aa'; nearest: api, gate, task"


# --- graph/kinds.py _parse; graph/build.py _shape, _plan  the kind names, the steps of a kind and the files of a step ---

_SHAPE_CODE = """
import json
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import load_kind_registry
from unit.graph._synth import EXAMPLE_SPEC, ROOT
graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
print(json.dumps({
    "kind_names": list(load_kind_registry(str(ROOT)).kind_names),
    "ambiguity_steps": list(graph.shape.kind_steps["ambiguity-item"]),
    "link_kinds": list(graph.decls["fr"].links[0].kinds),
}))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_kind_names_and_the_steps_of_a_kind_are_sorted_whatever_the_hash_seed(seed: int) -> None:
    got = json.loads(run_python_seeded(seed, _SHAPE_CODE))
    assert got["kind_names"] == sorted(got["kind_names"]) and len(got["kind_names"]) > 20
    assert got["ambiguity_steps"] == sorted(got["ambiguity_steps"]) and got["ambiguity_steps"][:4] == ["00", "01", "02", "02a"]
    assert got["link_kinds"] == sorted(got["link_kinds"])


def test_two_files_of_one_step_are_read_and_listed_in_path_order_not_in_registry_order(tmp_path: Path) -> None:
    """The registry names ``04_fr_list.json`` before ``04_alpha.json``; both are step 04, so the path breaks the tie."""
    toolkit = make_toolkit(tmp_path / "toolkit")
    registry = json.loads((toolkit / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))
    registry["registry"]["04_alpha.json"] = copy.deepcopy(registry["registry"]["04_fr_list.json"])
    write_json(toolkit, "tools/entry_key_registry.json", registry)
    clear_shared_caches()
    spec = copy_build_spec(tmp_path / "spec")
    write_json(spec, "04_alpha.json", {"functional_requirements": [{"fr_id": "fr-alpha", "statement": "A user can look around."}]})
    graph = build_graph(str(spec), str(toolkit))
    assert [(node.file, node.id) for node in graph.nodes if node.kind == "fr"] == [
        ("04_alpha.json", "fr-alpha"), ("04_fr_list.json", "fr-login"), ("04_fr_list.json", "fr-logout"),
    ]
    assert graph.shape.files_by_step["04"] == ("04_alpha.json", "04_fr_list.json")


# --- graph/contract.py _own_fields, _own_links, contract_view  the fields, the links and the criteria of a contract view ---

def test_a_contract_view_lists_fields_links_and_criteria_in_name_order() -> None:
    criteria = [_criterion("ac-z", "Z."), _criterion("ac-b", "B."), _criterion("ac-m", "M.")]
    requirement = _fr("fr-a", "Do a.", rationale="Because.", priority="must-have", scope="in", acceptance_criteria=criteria,
                      derives_from=["cap-z", "cap-b", "cap-m"], depends_on=["fr-z", "fr-b"])
    graph = _snapshot(_docs(requirement)).graph
    view = contract_view(graph.by_id["fr-a"], graph)
    assert list(view["fields"]) == sorted(view["fields"]) and len(view["fields"]) > 3
    assert list(view["links"]) == ["depends_on", "derives_from"]
    assert view["links"] == {"depends_on": ["fr-b", "fr-z"], "derives_from": ["cap-b", "cap-m", "cap-z"]}
    assert list(view["criteria"]) == ["ac-b", "ac-m", "ac-z"]


# --- graph/recipes.py _parse_roles, parse_recipes  the roles and the reports a wrong table names --------------------

_TABLE_CODE = """
import json
from unit.graph._builders import _core_16b, _raw, _set
from specdev_tools.graph.recipes import RecipeError, parse_recipes

def message(change):
    raw = _raw()
    change(raw)
    try:
        parse_recipes(raw)
    except RecipeError as exc:
        return exc.error.message
    return None

print(json.dumps({
    "roles": message(lambda raw: _set(_core_16b, "roles", ["zz9", "17z", "mm5", "aa1"])(raw)),
    "reports": message(lambda raw: raw["reports"].update({"zeta": {}, "mu": {}, "alpha": {}})),
}))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_a_wrong_table_names_the_unknown_roles_and_reports_in_name_order(seed: int) -> None:
    got = json.loads(run_python_seeded(seed, _TABLE_CODE))
    assert "(not 17z, aa1, mm5, zz9)" in got["roles"]
    assert "names unknown report(s) alpha, mu, zeta;" in got["reports"]


def test_the_roles_a_table_may_name_are_listed_in_name_order() -> None:
    raw = _raw()
    raw["start_kinds"] = {role: raw["start_kinds"][role] for role in sorted(raw["start_kinds"], reverse=True)}
    _set(_core_16b, "roles", ["17z"])(raw)
    with pytest.raises(RecipeError) as raised:
        parse_recipes(raw)
    assert "must list roles among 16a, 16b, 16c (not 17z)" in raised.value.error.message


# --- context/scope_resolver.py resolve_scope  the ids of a kind in resolved_ids -------------------------------------

def test_context_scope_lists_the_ids_of_a_kind_by_id_though_the_kind_spans_two_steps(tmp_path: Path) -> None:
    """``trace`` orders by step then id; the ids of one kind in ``resolved_ids`` are in id order, as in 1.1.1."""
    spec = copy_example(tmp_path / "spec")
    for name, ambiguity_id in (("01_capabilities.json", "amb-z-early"), ("04_fr_list.json", "amb-a-late")):
        document = json.loads((spec / name).read_text(encoding="utf-8"))
        document["ambiguities"] = [{"id": ambiguity_id, "description": "An open question.", "about": ["fr-password-reset"]}]
        write_json(spec, name, document)
    graph = build_graph(str(spec), str(ROOT))
    assert {graph.by_id["amb-z-early"].step, graph.by_id["amb-a-late"].step} == {"01", "04"}
    resolved = resolve_scope("fr-password-reset", str(spec), str(ROOT))["resolved_ids"]
    assert resolved["ambiguity-item"] == ["amb-a-late", "amb-z-early"]


# --- trace/replay.py  the steps and the nodes of `stale` ------------------------------------------------------------

_STALE_STEPS = ["00", "01", "02", "02a", "04", "05", "06", "07", "08", "09", "10", "11", "12", "14", "15", "16a"]
_STALE_STEP_00 = [
    "asm-member-controls-email", "con-staged-delivery", "need-fewer-reset-tickets", "metric-recovery-time",
    "metric-reset-completion-rate", "risk-reset-link-takeover", "scope-password-reset", "scope-sms-reset", "seg-registered-member",
]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_stale_lists_steps_in_step_key_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    """Steps follow the waterfall (``02a`` between ``02`` and ``04``, ``16a`` last), the nodes of a step go upward first, then by id."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    seed_doc = host / "docs" / "seed" / "seed_accounts.md"
    seed_doc.write_text(seed_doc.read_text(encoding="utf-8") + "\nThe link is also sent to a phone.\n", encoding="utf-8")
    result = run_specdev_seeded(seed, "stale", "--json", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert result.returncode == 0, result.stderr
    steps = json.loads(result.stdout)["steps"]
    assert [step["step"] for step in steps] == _STALE_STEPS
    assert [node["node"] for node in steps[0]["suspect_nodes"]] == _STALE_STEP_00


# --- trace/attest.py  the nodes `attest` blocks on and the entries `--prune` lists -----------------------------------------

@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_attest_names_the_blocking_links_in_field_then_target_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    seed_doc = host / "docs" / "seed" / "seed_accounts.md"
    seed_doc.write_text(seed_doc.read_text(encoding="utf-8") + "\nThe link is also sent to a phone.\n", encoding="utf-8")
    result = run_specdev_seeded(seed, "attest", "nfr-latency-reset-email", "--json", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert result.returncode == 1, result.stderr
    (blocked,) = json.loads(result.stdout)["blocked"]
    pairs = [(item["field"], item["target"]) for item in blocked["blockers"]]
    assert len(pairs) >= 2 and pairs == sorted(pairs)


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_attest_step_lists_its_nodes_in_replay_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    seed_doc = host / "docs" / "seed" / "seed_accounts.md"
    seed_doc.write_text(seed_doc.read_text(encoding="utf-8") + "\nThe link is also sent to a phone.\n", encoding="utf-8")
    result = run_specdev_seeded(seed, "attest", "--step", "00", "--json", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert result.returncode == 0, result.stderr
    holders = list(dict.fromkeys(link["holder"] for link in json.loads(result.stdout)["attested"]))
    assert holders == _STALE_STEP_00


# --- trace/id_writes.py  the targets, the newly suspect steps and the broken links of a write ---------------------------------

_WRITE_STEPS = ["05", "06", "07", "08", "09", "11", "14", "15", "16a"]
_WRITE_TARGETS = ["ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-request-1", "ac-password-reset-request-2"]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_write_report_lists_targets_and_newly_suspect_steps_in_step_then_id_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host), "--dry-run", "--json"]
    links = json.dumps(["ac-password-reset-request-2", "ac-password-reset-2", "ac-password-reset-1", "ac-password-reset-request-1"])
    patched = run_specdev_seeded(seed, "json", "patch", "--id", "err-password-reset-confirm-token-expired", ".derives_from", links, *flags)
    assert patched.returncode == 0, patched.stderr
    assert [target["target"] for target in json.loads(patched.stdout)["targets"]] == _WRITE_TARGETS
    deleted = run_specdev_seeded(seed, "json", "delete", "--id", _CRITERION, *flags)
    assert deleted.returncode == 0, deleted.stderr
    report = json.loads(deleted.stdout)
    assert [item["step"] for item in report["newly_suspect"]] == _WRITE_STEPS
    pairs = [(link["holder"], link["field"]) for link in report["broken"]]
    assert len(pairs) >= 2 and pairs == sorted(pairs)


# --- trace/step_create.py, trace/step_ready.py  the targets of a created step and the blockers of `step ready` ------------------------

_STEP_READY_BLOCKER_STEPS = ["06", "08"]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_step_create_lists_targets_in_step_then_id_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    """The draft lists its requirements in reverse order; the targets come out by holder id, then field and target."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    draft = tmp_path / "04_fr_list.json"
    document = json.loads((host / "spec" / "04_fr_list.json").read_text(encoding="utf-8"))
    document["functional_requirements"].reverse()
    draft.write_text(json.dumps(document), encoding="utf-8")
    (host / "spec" / "04_fr_list.json").unlink()
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    result = run_specdev_seeded(seed, "step", "create", "04", "--from", str(draft), "--dry-run", "--json", *flags)
    assert result.returncode == 0, result.stderr
    triples = [(item["holder"], item["field"], item["target"]) for item in json.loads(result.stdout)["targets"]]
    assert len(triples) >= 2 and triples == sorted(triples)


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_step_ready_blockers_are_listed_in_step_then_id_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    """Step 14 links into 06 and 08, which hold suspects after a criterion edit."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    criteria = host / "spec" / "04_fr_list.json"
    document = json.loads(criteria.read_text(encoding="utf-8"))
    document["functional_requirements"][0]["acceptance_criteria"][2]["text"] += " Also reject a token issued for another account."
    criteria.write_text(json.dumps(document), encoding="utf-8")
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    result = run_specdev_seeded(seed, "step", "ready", "14", "--json", *flags)
    assert result.returncode == 1, result.stderr
    blockers = json.loads(result.stdout)["blockers"]
    assert list(dict.fromkeys(blocker["step"] for blocker in blockers)) == _STEP_READY_BLOCKER_STEPS
    in_08 = [(blocker["node"], blocker["field"], blocker["target"]) for blocker in blockers if blocker["step"] == "08"]
    assert len(in_08) >= 2 and in_08 == sorted(in_08)


# --- rename.py  the holders a rename rewrites and the uses a label rename rewrites ---------------------------------------

@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_rename_lists_rewritten_holders_and_label_uses_in_step_then_id_order_whatever_the_hash_seed(seed: int) -> None:
    renamed = json.loads(run_specdev_seeded(
        seed, "node", "rename", _CRITERION, "ac-password-reset-3b", "--dry-run", "--json", *_FLAGS, "--git-root", str(EXAMPLE_SPEC.parent)
    ).stdout)
    assert [f"{link['holder']}.{link['field']}" for link in renamed["links"]] == [
        "err-password-reset-confirm-token-expired.derives_from", "fix-password-reset-expired-token.verifies",
        "ec-token-at-expiry-second.mitigated_by", "tc-confirm-expired-token.refines",
    ]
    assert [entry["before"]["source"] for entry in renamed["lock_entries"]] == sorted(link["holder"] for link in renamed["links"])
    labelled = json.loads(run_specdev_seeded(
        seed, "node", "rename", "--label", "term-reset-token", "recovery code", "--dry-run", "--json", *_FLAGS
    ).stdout)
    assert [use["node_id"] for use in labelled["uses"]] == [
        "ac-password-reset-2", "ac-password-reset-3", "fr-password-reset", "err-password-reset-confirm-token-expired",
        "inv-reset-token-single-use", "task-implement-password-reset-confirm",
    ]
    assert labelled["files"] == sorted(labelled["files"])


# --- trace/coverage.py  the FR rows, the criteria, the groups and the links of `coverage --by fr` ----------------------------

_EXTRA_FIXTURES = ("fix-zzz-late", "fix-mmm-middle", "fix-aaa-early")


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_coverage_rows_and_groups_are_listed_in_step_then_id_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    """The FRs, their criteria and the fixtures that verify a criterion are written in reverse id order; the listing is by step, then id."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_SPEC.parent, host)
    fr_file, fixture_file = host / "spec" / "04_fr_list.json", host / "spec" / "08_fixtures.json"
    frs = json.loads(fr_file.read_text(encoding="utf-8"))
    frs["functional_requirements"].reverse()
    for fr in frs["functional_requirements"]:
        fr["acceptance_criteria"].reverse()
    fr_file.write_text(json.dumps(frs, indent=2) + "\n", encoding="utf-8")
    fixtures = json.loads(fixture_file.read_text(encoding="utf-8"))
    fixtures["fixtures"] = [{"fixture_id": name, "verifies": [_CRITERION]} for name in _EXTRA_FIXTURES] + fixtures["fixtures"]
    fixture_file.write_text(json.dumps(fixtures, indent=2) + "\n", encoding="utf-8")
    result = run_specdev_seeded(seed, "coverage", "--by", "fr", "--json", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)["by_fr"]
    assert [row["id"] for row in rows] == ["fr-password-reset", "fr-password-reset-request"]
    assert [criterion["id"] for criterion in rows[0]["criteria"]] == ["ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-3"]
    assert [group["kind"] for group in rows[0]["groups"]] == ["capability", "api", "invariant", "nfr", "design-milestone"]
    criterion = rows[0]["criteria"][2]
    assert [group["kind"] for group in criterion["groups"]] == ["api-error", "fixture", "edge-case", "task-criterion"]
    fixture_group = next(group for group in criterion["groups"] if group["kind"] == "fixture")
    assert [link["node"] for link in fixture_group["links"]] == ["fix-aaa-early", "fix-mmm-middle", "fix-password-reset-expired-token", "fix-zzz-late"]


# --- validation/graph_checks/no_dangling.py  the E740 findings, listed in step then id order ---------------------------------

_NO_DANGLING_CODE = f"""
import json
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.no_dangling import check_no_dangling

graph = build_graph({str(EXAMPLE_SPEC)!r}, {str(ROOT)!r})

def listed(nodes):
    reordered = Graph.from_nodes(nodes, shape=graph.shape)
    reordered.decls = graph.decls
    return [error.node_id for error in check_no_dangling(GraphCheckContext.from_graph(reordered, None, {str(ROOT)!r}), "merge")]

print(json.dumps({{"forward": listed(graph.nodes), "reversed": listed(list(reversed(graph.nodes)))}}))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_no_dangling_reports_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    """The nodes come in reverse order; the findings are in step order, then by id, as with the nodes in build order."""
    got = json.loads(run_python_seeded(seed, _NO_DANGLING_CODE))
    assert got["forward"] and got["reversed"] == got["forward"]
    assert got["forward"].index("metric-reset-completion-rate") < got["forward"].index("dev") < got["forward"].index("nfr-latency-reset-email")
