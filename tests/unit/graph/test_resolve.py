"""Tests for the link resolver (WI-M4-04): one graph per branch of the design's Figure 4, the hand-off cases of the
deleted E590 tests, and the ``graph`` check of ``spec-check``."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from specdev_tools.core.errors import ERROR_CODES, SpecError, make_error
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node, SpecShape
from specdev_tools.graph.ownership import OwnerContext, load_ownership_table, owner_for
from specdev_tools.graph.resolve import NULL_HOOKS, resolve_graph
from specdev_tools.validation.spec_check import run_spec_check_json

from ._synth import EXAMPLE_SPEC, ROOT, copy_example, docs_graph, load_doc, spec_check_graph_findings, write_json, write_spec

_RANKS = {"seed": -1, "s1": 0, "s2": 1, "s3": 2}


def _decl(field: str, kinds: Iterable[str], same_step: Iterable[str] = ()) -> LinkDecl:
    return LinkDecl(field=field, kinds=tuple(kinds), required=False, built=True, same_step_kinds=tuple(same_step))


def _node(
    node_id: str, kind: str, step: str | None, links: Iterable[tuple[LinkDecl, str]] = (), *,
    role: str = "obligation-system", lifecycle: str = "active",
) -> Node:
    return Node(
        id=node_id, kind=kind, step=step, role=role, file=f"{step}.json", jq_path=f".{kind}[0]", parent=None,
        children=(), lifecycle=lifecycle, scope=None, links=tuple(Link(node_id, d.field, t, d) for d, t in links),
        label="",
    )


def _graph(nodes: Sequence[Node], *, files: Mapping[str, tuple[str, ...]] | None = None) -> Graph:
    kind_steps: dict[str, set[str]] = {}
    for node in nodes:
        if node.step:
            kind_steps.setdefault(node.kind, set()).add(node.step)
    present = files if files is not None else {step: (f"{step}.json",) for steps in kind_steps.values() for step in steps}
    shape = SpecShape(
        step_ranks=_RANKS,
        kind_steps={kind: tuple(sorted(steps)) for kind, steps in kind_steps.items()},
        files_by_step=present,
    )
    return Graph.from_nodes(list(nodes), shape=shape)


def _summary(errors: Sequence[SpecError]) -> list[tuple[str, str | None, str | None]]:
    return [(error.code, error.owner, error.node_id) for error in errors]


class _RecordingHooks:
    """A stub hook: records every call and answers one marker finding per call."""

    def __init__(self) -> None:
        self.calls: list[tuple[Link, Node, Node]] = []

    def on_link(self, link: Link, source: Node, target: Node) -> list[SpecError]:
        self.calls.append((link, source, target))
        return [make_error("W720", f"marker for {source.id} -> {target.id}", owner=f"step:{source.step}", node_id=source.id)]


# --- Figure 4, one graph per branch --------------------------------------------------------------------------------

def test_missing_target_e700() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["A", "B"]), "ghost")]), _node("b", "B", "s1")])
    (error,) = resolve_graph(graph)
    assert (error.code, error.owner, error.node_id, error.file) == ("E700", "step:s2", "a", "s2.json")
    assert "ghost" in error.message and "field to" in error.message and "no node has that id" in error.message


def test_wrong_kind_e701() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "c")]), _node("c", "C", "s1"), _node("b", "B", "s1")])
    (error,) = resolve_graph(graph)
    assert (error.code, error.owner, error.node_id) == ("E701", "step:s2", "a")
    assert "'c' is a C" in error.message and "accepts: B" in error.message


def test_downstream_e702() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "b")]), _node("b", "B", "s3")])
    (error,) = resolve_graph(graph)
    assert (error.code, error.owner, error.node_id) == ("E702", "step:s2", "a")
    assert "later step" in error.message


def test_same_step_declared_ok_undeclared_e702() -> None:
    declared = _graph([_node("a", "A", "s2", [(_decl("to", ["B", "C"], ["B"]), "b")]), _node("b", "B", "s2")])
    assert resolve_graph(declared) == []
    undeclared = _graph([_node("a", "A", "s2", [(_decl("to", ["B", "C"], ["B"]), "c")]), _node("c", "C", "s2")])
    (error,) = resolve_graph(undeclared)
    assert (error.code, error.node_id) == ("E702", "a")
    assert "same step" in error.message


def test_same_step_cycle_e703_and_self_link() -> None:
    dep = _decl("depends_on", ["B"], ["B"])
    graph = _graph([
        _node("a", "B", "s2", [(dep, "b")]), _node("b", "B", "s2", [(dep, "c")]), _node("c", "B", "s2", [(dep, "a")]),
        _node("d", "B", "s2", [(dep, "d")]), _node("e", "B", "s2", [(dep, "a")]),
    ])
    errors = resolve_graph(graph)
    assert _summary(errors) == [("E703", "step:s2", "a"), ("E703", "step:s2", "d")]
    assert "a, b, c" in errors[0].message and "field depends_on" in errors[0].message
    assert errors[1].message.endswith("d (field depends_on)")


def test_steps_filter_keeps_only_the_cycles_of_those_steps() -> None:
    """A cycle stays inside one step and only holders of the wanted steps give edges, so no other step's cycle can appear."""
    dep = _decl("depends_on", ["B"], ["B"])
    graph = _graph([
        _node("a", "B", "s2", [(dep, "b")]), _node("b", "B", "s2", [(dep, "a")]),
        _node("x", "B", "s3", [(dep, "y")]), _node("y", "B", "s3", [(dep, "x")]),
    ])
    assert _summary(resolve_graph(graph)) == [("E703", "step:s2", "a"), ("E703", "step:s3", "x")]
    assert _summary(resolve_graph(graph, steps=["s3"])) == [("E703", "step:s3", "x")]
    assert resolve_graph(graph, steps=["s1"]) == []


def test_a_chain_without_a_cycle_gives_no_e703() -> None:
    dep = _decl("depends_on", ["B"], ["B"])
    graph = _graph([_node("a", "B", "s2", [(dep, "b")]), _node("b", "B", "s2", [(dep, "c")]), _node("c", "B", "s2")])
    assert resolve_graph(graph) == []


def test_deprecated_target_no_w720_in_m4() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "b")]), _node("b", "B", "s1", lifecycle="deprecated")])
    assert resolve_graph(graph) == []


def test_w720_registered_and_owned() -> None:
    assert ERROR_CODES["W720"] == "LINK_TO_DEPRECATED_NODE"
    holder = _node("a", "A", "04")
    context = OwnerContext(rows=load_ownership_table(str(ROOT)))
    assert owner_for("W720", holder, context) == "step:04"


def test_not_applicable_target_silent() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "b")]), _node("b", "B", "s1", lifecycle="not_applicable")])
    assert resolve_graph(graph) == []


def test_not_applicable_source_skipped() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "ghost")], lifecycle="not_applicable")])
    assert resolve_graph(graph) == []


def test_same_step_per_kind() -> None:
    """One field with kinds A (same-step allowed) and B (not): a same-step A resolves, a same-step B is E702."""
    field = _decl("to", ["A", "B"], ["A"])
    holder = _node("h", "H", "s2", [(field, "a")])
    assert resolve_graph(_graph([holder, _node("a", "A", "s2")])) == []
    holder_b = _node("h", "H", "s2", [(field, "b")])
    (error,) = resolve_graph(_graph([holder_b, _node("b", "B", "s2")]))
    assert (error.code, error.node_id) == ("E702", "h")


def test_record_kind_without_home_step_skips_e702() -> None:
    """A record whose kind has no home step links to a spec node, and a spec node links to it: no direction test."""
    about = _decl("about", ["A", "R"])
    graph = _graph([
        _node("rec", "R", None, [(about, "spec-a")], role="record"),
        _node("spec-a", "A", "s2", [(_decl("to", ["R"]), "rec")]),
    ])
    assert graph.by_id["rec"].step is None
    assert resolve_graph(graph) == []


def test_w720_emitted_when_stub_hook_reports_new_link() -> None:
    hooks = _RecordingHooks()
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "b")]), _node("b", "B", "s1", lifecycle="deprecated")])
    errors = resolve_graph(graph, hooks=hooks)
    assert _summary(errors) == [("W720", "step:s2", "a")]


def test_replaces_removes_skip() -> None:
    hooks = _RecordingHooks()
    holder = _node("a", "A", "s2", [(_decl("replaces", ["B"]), "ghost"), (_decl("removes", ["B"]), "ghost-2")])
    assert resolve_graph(_graph([holder]), hooks=hooks) == []
    assert hooks.calls == []


def test_record_link_skips_lock_hook() -> None:
    hooks = _RecordingHooks()
    graph = _graph([_node("rec", "R", "s2", [(_decl("about", ["B"]), "b")], role="record"), _node("b", "B", "s1")])
    assert resolve_graph(graph, hooks=hooks) == []
    assert hooks.calls == []


def test_lock_hook_stub_fires_for_spec_link() -> None:
    hooks = _RecordingHooks()
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "b")]), _node("b", "B", "s1")])
    resolve_graph(graph, hooks=hooks)
    ((link, source, target),) = hooks.calls
    assert (link.field, link.target, source.id, target.id) == ("to", "b", "a", "b")


def test_hook_is_not_called_for_a_link_the_resolver_rejects() -> None:
    hooks = _RecordingHooks()
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "ghost")])])
    assert [error.code for error in resolve_graph(graph, hooks=hooks)] == ["E700"]
    assert hooks.calls == []


def test_null_hooks_report_nothing() -> None:
    node = _node("a", "A", "s2")
    assert NULL_HOOKS.on_link(Link("a", "to", "b", _decl("to", ["B"])), node, node) == []


def test_steps_filter_limits_holders_and_cycles() -> None:
    dep = _decl("depends_on", ["B"], ["B"])
    graph = _graph([
        _node("a", "A", "s1", [(_decl("to", ["B"]), "ghost-1")]), _node("b", "A", "s2", [(_decl("to", ["B"]), "ghost-2")]),
        _node("x", "B", "s3", [(dep, "y")]), _node("y", "B", "s3", [(dep, "x")]),
    ])
    assert [error.node_id for error in resolve_graph(graph)] == ["a", "b", "x"]
    assert [error.node_id for error in resolve_graph(graph, steps=["s2"])] == ["b"]
    assert [error.code for error in resolve_graph(graph, steps=["s3"])] == ["E703"]


def test_target_found_through_the_alias_index() -> None:
    graph = _graph([_node("a", "A", "s2", [(_decl("to", ["B"]), "old-name")]), _node("b", "B", "s1")])
    graph.alias_index["old-name"] = "b"
    assert resolve_graph(graph) == []


def test_a_step_the_order_does_not_rank_is_not_constrained() -> None:
    """The ranks hold ``s1`` only: a link to or from the unranked ``zz`` is never E702, in either direction or inside ``zz``."""
    shape = SpecShape(step_ranks={"s1": 0}, kind_steps={"A": ("zz",), "B": ("s1", "zz")}, files_by_step={"s1": ("s1.json",), "zz": ("zz.json",)})
    decl = _decl("to", ["B"])
    for holder_step, target_step in (("s1", "zz"), ("zz", "s1"), ("zz", "zz")):
        graph = Graph.from_nodes([_node("a", "A", holder_step, [(decl, "b")]), _node("b", "B", target_step)], shape=shape)
        assert resolve_graph(graph) == [], (holder_step, target_step)


def test_a_graph_without_a_shape_reports_missing_and_wrong_kind_only() -> None:
    """Built from nodes alone (no step ranks), no direction can be judged and no absent step is known."""
    graph = Graph.from_nodes([_node("a", "A", "s2", [(_decl("to", ["B"]), "ghost"), (_decl("to", ["B"]), "c")]), _node("c", "C", "s3")])
    assert [error.code for error in resolve_graph(graph)] == ["E700", "E701"]


# --- the real registry ---------------------------------------------------------------------------------------------

def test_derives_from_seed_resolves_with_kind_seed() -> None:
    docs = {
        "common/seed_manifest.json": {"seeds": [{"seed_id": "seed-brief", "path": "seeds/brief.md"}]},
        "00_charter.json": {"assumptions": [{"assumption_id": "asm-a", "derives_from": ["seed-brief"]}]},
    }
    graph = docs_graph(docs)
    assert graph.by_id["seed-brief"].kind == "seed"
    assert resolve_graph(graph) == []


def test_absent_upstream_message_names_the_step() -> None:
    docs = {"05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-x"]}]}}
    (error,) = resolve_graph(docs_graph(docs))
    assert error.code == "E700"
    assert "no file of step 04 exists" in error.message
    assert "no node has that id" not in error.message
    present = {**docs, "04_fr_list.json": {"functional_requirements": []}}
    (error,) = resolve_graph(docs_graph(present))
    assert "no node has that id" in error.message and "no file of step" not in error.message


def test_a_field_over_two_steps_names_absent_steps_only_when_none_of_them_has_a_file() -> None:
    """The field accepts kinds of ``s1`` and ``s2``; ``s1`` has a file, ``s2`` has none: the target may still be in ``s1``."""
    decl = _decl("to", ["B", "C"])
    nodes = [_node("a", "A", "s3", [(decl, "ghost")]), _node("b", "B", "s1"), _node("c", "C", "s2")]
    (error,) = resolve_graph(_graph(nodes, files={"s1": ("s1.json",), "s3": ("s3.json",)}))
    assert error.message.endswith("no node has that id")
    (error,) = resolve_graph(_graph(nodes, files={"s3": ("s3.json",)}))
    assert error.message.endswith("no file of step s1, s2 exists in the spec, so the target cannot be found")


def test_a_target_in_a_file_that_could_not_be_read_says_so() -> None:
    """The file was skipped, so "no node has that id" would be false; the finding names the file and its step."""
    api = {"05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-x"]}]}}
    for unreadable in ([1, 2], "text"):
        graph = docs_graph({**api, "04_fr_list.json": unreadable})
        assert [item.file for item in graph.load_errors] == ["04_fr_list.json"]
        (error,) = resolve_graph(graph)
        assert (error.code, error.owner, error.node_id) == ("E700", "step:05", "api-a")
        assert error.message.endswith("the file 04_fr_list.json of step 04 could not be read, so the target cannot be checked")
        assert "no node has that id" not in error.message and "no file of step" not in error.message


def test_a_file_that_could_not_be_read_does_not_change_the_other_two_e700_messages() -> None:
    """Only a file of a step that holds a kind the field accepts counts: the glossary is no home of an FR."""
    docs = {
        "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-x"]}]},
        "04_fr_list.json": {"functional_requirements": []},
        "03_glossary.json": [1],
    }
    graph = docs_graph(docs)
    assert [item.file for item in graph.load_errors] == ["03_glossary.json"]
    (error,) = resolve_graph(graph)
    assert "no node has that id" in error.message and "could not be read" not in error.message
    absent = docs_graph({"05_interface_contracts.json": docs["05_interface_contracts.json"], "03_glossary.json": [1]})
    (error,) = resolve_graph(absent)
    assert "no file of step 04 exists" in error.message and "could not be read" not in error.message


def test_ambiguity_about_same_step_reports_e702() -> None:
    docs = {"04_fr_list.json": {"functional_requirements": [{"fr_id": "fr-a"}], "ambiguities": [{"id": "amb-a", "about": ["fr-a"]}]}}
    (error,) = resolve_graph(docs_graph(docs))
    assert (error.code, error.owner, error.node_id) == ("E702", "step:04", "amb-a")
    plan = {"plan": {"spec_alignment": {"checklist": [{"id": "ITEM_A"}]}}, "execution": {"emergent_ambiguities": [
        {"id": "amb-b", "about": ["ITEM_A"]}]}}
    (error,) = resolve_graph(docs_graph({"impl_context/ms_a_plan.json": plan}))
    assert (error.code, error.owner, error.node_id) == ("E702", "step:16a", "amb-b")


def test_ambiguity_about_an_earlier_step_resolves() -> None:
    docs = {
        "04_fr_list.json": {"functional_requirements": [{"fr_id": "fr-a"}]},
        "05_interface_contracts.json": {"ambiguities": [{"id": "amb-a", "about": ["fr-a"]}]},
    }
    assert resolve_graph(docs_graph(docs)) == []


def test_worked_example_has_no_resolver_errors() -> None:
    assert resolve_graph(build_graph(str(EXAMPLE_SPEC), str(ROOT))) == []


# --- the graph check of spec-check ---------------------------------------------------------------------------------

def _job(job_id: str, depends_on: list[str] | None = None) -> dict[str, Any]:
    job: dict[str, Any] = {"job_id": job_id, "steps": [{"name": "run", "command": "true"}]}
    if depends_on is not None:
        job["depends_on"] = depends_on
    return job


def test_job_depends_on_unknown_job_is_e700_via_spec_check() -> None:
    findings = spec_check_graph_findings({"12_ci_gates.json": {"jobs": [_job("job-a", ["job-ghost"])]}})
    assert [(f["code"], f["owner"], f["node_id"]) for f in findings] == [("E700", "step:12", "job-a")]


def test_job_depends_on_cycle_is_e703_via_spec_check() -> None:
    findings = spec_check_graph_findings({"12_ci_gates.json": {"jobs": [_job("job-a", ["job-b"]), _job("job-b", ["job-a"])]}})
    assert [(f["code"], f["owner"]) for f in findings] == [("E703", "step:12")]


def test_task_depends_on_cycle_is_e703_via_spec_check() -> None:
    tasks = [{"task_id": "task-a", "depends_on": ["task-b"]}, {"task_id": "task-b", "depends_on": ["task-a"]}]
    findings = spec_check_graph_findings({"14_roadmap.json": {"milestones": [{"milestone_id": "ms-a", "tasks": tasks}]}})
    assert [(f["code"], f["owner"]) for f in findings] == [("E703", "step:14")]


def test_two_holders_same_missing_target_two_e700(tmp_path: Path) -> None:
    docs = {
        "04_fr_list.json": {"functional_requirements": []},
        "05_interface_contracts.json": {"apis": [
            {"api_id": "api-a", "derives_from": ["fr-ghost"]}, {"api_id": "api-b", "derives_from": ["fr-ghost"]}]},
    }
    errors, _context = run_spec_check_json(str(ROOT), str(write_spec(tmp_path / "spec", docs)))
    assert sorted(e.node_id for e in errors if e.code == "E700") == ["api-a", "api-b"]


def test_graph_check_in_spec_check_json(tmp_path: Path) -> None:
    docs = {"05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-ghost"]}]}}
    _errors, context = run_spec_check_json(str(ROOT), str(write_spec(tmp_path / "spec", docs)))
    graph = context["checks"]["graph"]
    assert graph["status"] == "FAIL" and graph["error_count"] == 1
    (finding,) = graph["findings"]
    assert (finding["code"], finding["owner"], finding["node_id"]) == ("E700", "step:05", "api-a")


def test_graph_check_silent_for_file_validate_reports(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "04_fr_list.json").write_text("{", encoding="utf-8")
    (spec / "05_interface_contracts.json").write_text("[]", encoding="utf-8")
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    assert context["checks"]["graph"]["findings"] == []
    schema_files = {f["message"].split(":")[0] for f in context["checks"]["schema-validation"]["findings"]}
    assert {str(spec / "04_fr_list.json"), str(spec / "05_interface_contracts.json")} <= schema_files


def test_plan_item_realises_missing_id_e700_not_e530(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    plan_rel = "impl_context/ms_account_recovery_plan.json"
    plan = load_doc(spec, plan_rel)
    plan["plan"]["spec_alignment"]["checklist"][0]["realises"] = ["tc-no-such-criterion"]
    write_json(spec, plan_rel, plan)
    errors, context = run_spec_check_json(str(ROOT), str(spec))
    (finding,) = context["checks"]["graph"]["findings"]
    assert (finding["code"], finding["owner"], finding["node_id"]) == ("E700", "step:16a", "PWRESET_CONFIRM_EXPIRED_01")
    assert "tc-no-such-criterion" in finding["message"]
    assert not [e for e in errors if e.code == "E530" and "tc-no-such-criterion" in e.message]


# --- hand-off cases of the deleted E590 tests ------------------------------------------------------------------------

_HANDOFF = ROOT / "tests" / "fixtures" / "graph" / "m4_handoff_cases.json"

# kind -> (file, collection, id field) of the upstream node a hand-off case lists
_UPSTREAM = {
    "fr": ("04_fr_list.json", "functional_requirements", "fr_id"),
    "api": ("05_interface_contracts.json", "apis", "api_id"),
    "invariant": ("06_invariants.json", "rules", "inv_id"),
    "nfr": ("07_nfrs.json", "nfrs", "nfr_id"),
    "fixture": ("08_fixtures.json", "fixtures", "fixture_id"),
    "capability": ("01_capabilities.json", "capabilities", "capability_id"),
    "component": ("02_system_sketch.json", "components", "component_id"),
}
# holder -> (file, collection, id field, holder id, step)
_HOLDERS = {
    "rule": ("06_invariants.json", "rules", "inv_id", "inv-holder", "06"),
    "fixture": ("08_fixtures.json", "fixtures", "fixture_id", "fix-holder", "08"),
    "milestone": ("09_impl_plan.json", "milestones", "milestone_id", "ms-holder", "09"),
    "job": ("12_ci_gates.json", "jobs", "job_id", "job-holder", "12"),
    "scaffold": ("15_scaffold.json", "interface_map", "row_id", "row-holder", "15"),
    "threat": ("11_redteam.json", "threats", "threat_id", "threat-holder", "11"),
    "nfr": ("07_nfrs.json", "nfrs", "nfr_id", "nfr-holder", "07"),
}


class _Case(NamedTuple):
    """One hand-off case: the holder, its link field and targets, and the upstream files present (kind -> ids)."""

    holder: str
    field: str
    targets: tuple[str, ...]
    upstream: Mapping[str, tuple[str, ...]]


def _c(holder: str, field: str, targets: Sequence[str], **upstream: Sequence[str]) -> _Case:
    return _Case(holder, field, tuple(targets), {kind: tuple(ids) for kind, ids in upstream.items()})


_RULE_VALID = _c("rule", "constrains", ["fr-login", "api-auth"], fr=["fr-login"], api=["api-auth"])
_RULE_VALID_SCOPE = _c("rule", "constrains", ["api-auth", "api-users"], api=["api-auth", "api-users"])
_FIXTURE_VALID = _c(
    "fixture", "verifies", ["ac-login-1", "api-auth", "inv-session", "nfr-latency"],
    criterion=["ac-login-1"], api=["api-auth"], invariant=["inv-session"], nfr=["nfr-latency"],
)
_JOB_VALID = _c("job", "verifies", ["nfr-latency"], fr=["fr-login"], nfr=["nfr-latency"])
_SCAFFOLD_VALID = _c("scaffold", "realises", ["api-auth", "api-users"], api=["api-auth", "api-users"])
_RULE_BROKEN = _c("rule", "constrains", ["fr-unknown", "api-missing"], fr=["fr-login"], api=["api-auth"])
_RULE_BROKEN_SCOPE = _c("rule", "constrains", ["api-nonexistent"], api=["api-auth"])
_FIXTURE_BROKEN = _c(
    "fixture", "verifies", ["fr-nonexistent", "api-ghost"], fr=[], api=[], invariant=[], nfr=[],
)
_MILESTONE_BROKEN = _c("milestone", "schedules", ["cap-nonexistent"], capability=["cap-authentication"])
_JOB_BROKEN = _c("job", "verifies", ["nfr-ghost"], fr=["fr-login"], nfr=["nfr-latency"])
_SCAFFOLD_BROKEN = _c("scaffold", "realises", ["api-nonexistent"], api=["api-auth"])
_RULE_ABSENT = _c("rule", "constrains", ["fr-login", "api-auth"])
_FIXTURE_ABSENT = _c("fixture", "verifies", ["ac-login-1", "api-auth", "inv-session", "nfr-latency"])
_MILESTONE_ABSENT = _c("milestone", "schedules", ["cap-authentication"])
_JOB_ABSENT = _c("job", "verifies", ["nfr-latency"])
_SCAFFOLD_ABSENT = _c("scaffold", "realises", ["api-auth"])

_VALID: dict[int, _Case] = {
    0: _RULE_VALID, 5: _RULE_VALID_SCOPE, 7: _FIXTURE_VALID, 15: _JOB_VALID, 19: _SCAFFOLD_VALID,
    23: _RULE_VALID, 28: _RULE_VALID_SCOPE, 30: _FIXTURE_VALID, 37: _JOB_VALID, 41: _SCAFFOLD_VALID,
    46: _c("threat", "mitigated_by", ["inv-known"], invariant=["inv-known"]),
    49: _c("threat", "mitigated_by", ["fr-known"], fr=["fr-known"]),
    53: _c("threat", "mitigated_by", ["nfr-x"], nfr=["nfr-x"]),
    55: _c("threat", "mitigated_by", ["fix-x"], fixture=["fix-x"]),
    57: _c("threat", "mitigated_by", ["api-x"], api=["api-x"]),
    66: _c("threat", "threatens", ["comp-auth"], component=["comp-auth"]),
}
_MISSING: dict[int, _Case] = {
    2: _RULE_BROKEN, 6: _RULE_BROKEN_SCOPE, 9: _FIXTURE_BROKEN, 13: _MILESTONE_BROKEN, 17: _JOB_BROKEN,
    21: _SCAFFOLD_BROKEN, 25: _RULE_BROKEN, 29: _RULE_BROKEN_SCOPE, 32: _FIXTURE_BROKEN, 35: _MILESTONE_BROKEN,
    39: _JOB_BROKEN, 43: _SCAFFOLD_BROKEN,
    45: _c("threat", "mitigated_by", ["inv-unknown"], invariant=["inv-known"]),
    48: _c("threat", "mitigated_by", ["fr-ghost"], fr=["fr-known"]),
    50: _c("threat", "mitigated_by", ["cap-phantom"], capability=["cap-auth"]),
    54: _c("threat", "mitigated_by", ["nfr-ghost"], nfr=["nfr-x"]),
    56: _c("threat", "mitigated_by", ["fix-ghost"], fixture=["fix-x"]),
    58: _c("threat", "mitigated_by", ["api-ghost"], api=["api-x"]),
    59: _c("threat", "mitigated_by", ["inv-ghost"], invariant=[]),
    60: _c("threat", "mitigated_by", ["fr-ghost"], fr=[]),
    61: _c("threat", "mitigated_by", ["nfr-ghost"], nfr=[]),
    62: _c("threat", "mitigated_by", ["fix-ghost"], fixture=[]),
    63: _c("threat", "mitigated_by", ["cap-ghost"], capability=[]),
    65: _c("threat", "threatens", ["comp-nonexistent"], component=["comp-auth"]),
    67: _c("threat", "threatens", ["api-ghost"], api=[]),
    68: _c("threat", "threatens", ["comp-ghost"], component=[]),
    69: _c("threat", "mitigated_by", ["fr-does-not-exist"]),
    71: _c("task-criterion", "refines", ["fr-unknown"], fr=["fr-user-login", "fr-user-registration"]),
    72: _c("nfr", "constrains", ["fr-login", "fr-nonexistent"], fr=["fr-login", "fr-logout"]),
}
_WRONG_KIND: dict[int, _Case] = {
    11: _c("milestone", "schedules", ["cap-authentication"], capability=["cap-authentication", "cap-dashboard"]),
    33: _c("milestone", "schedules", ["cap-authentication"], capability=["cap-authentication", "cap-dashboard"]),
    52: _c("threat", "mitigated_by", ["cap-x"], capability=["cap-x"]),
}
_ABSENT: dict[int, _Case] = {
    1: _RULE_ABSENT, 8: _FIXTURE_ABSENT, 12: _MILESTONE_ABSENT, 16: _JOB_ABSENT, 20: _SCAFFOLD_ABSENT,
    22: _c("scaffold", "realises", ["api-x"]), 24: _RULE_ABSENT, 31: _FIXTURE_ABSENT, 34: _MILESTONE_ABSENT,
    38: _JOB_ABSENT, 42: _SCAFFOLD_ABSENT, 44: _c("scaffold", "realises", ["api-x"]),
    47: _c("threat", "mitigated_by", ["inv-anything"]), 51: _c("threat", "mitigated_by", ["cap-anything"]),
}
# job.verifies takes NFR ids only: these cases fed an FR id to step 12
_JOB_VERIFIES_FR = (15, 17, 37, 39)
# The old input has no 1.2.0 link field: what it left in the document, and the upstream file it listed.
_NOT_A_LINK: dict[int, dict[str, Any]] = {
    3: {"06_invariants.json": {"rules": [
        {"inv_id": "inv-auth-required"}, {"inv_id": "inv-session-valid", "trace": [{"type": "inv", "id": "inv-auth-required"}]}]}},
    4: {"06_invariants.json": {"rules": [{"inv_id": "inv-a", "trace": [{"type": "inv", "id": "inv-nonexistent"}]}]}},
    14: {
        "09_impl_plan.json": {"milestones": [{"milestone_id": "ms-beta", "capability_refs": ["cap-unknown"]}]},
        "01_capabilities.json": {"capabilities": [{"capability_id": "cap-authentication"}]},
    },
    18: {
        "12_ci_gates.json": {"jobs": [{"job_id": "job-a", "coverage_target": "fr-does-not-exist"}]},
        "04_fr_list.json": {"functional_requirements": [{"fr_id": "fr-login"}]},
        "07_nfrs.json": {"nfrs": [{"nfr_id": "nfr-latency"}]},
    },
    64: {
        "11_redteam.json": {"threats": [{"threat_id": "threat-01", "mitigations": [{"type": "doc", "id": "any-id"}]}]},
        "04_fr_list.json": {"functional_requirements": []},
        "06_invariants.json": {"rules": []},
    },
    70: {
        "14_roadmap.json": {"milestones": [{"milestone_id": "ms-a", "source_milestones": ["missing-from-step09"]}]},
        "09_impl_plan.json": {"milestones": [{"milestone_id": "ms-b"}]},
    },
}
_NOT_A_LINK |= {26: _NOT_A_LINK[3], 27: _NOT_A_LINK[4], 36: _NOT_A_LINK[14], 40: _NOT_A_LINK[18]}
_NOT_M4 = (10, 73, 74, 75)


def _holder_item(case: _Case, holder_id: str) -> dict[str, Any]:
    return {"criterion_id": holder_id, "refines": list(case.targets)} if case.holder == "task-criterion" else {
        _HOLDERS[case.holder][2]: holder_id, case.field: list(case.targets)}


def _case_docs(case: _Case) -> dict[str, Any]:
    """The documents of a hand-off case: the holder, and the upstream files with the ids they list."""
    docs: dict[str, dict[str, Any]] = {}
    if case.holder == "task-criterion":
        criterion = {"criterion_id": "tc-holder", "refines": list(case.targets)}
        task = {"task_id": "task-holder", "acceptance_criteria": [criterion]}
        docs["14_roadmap.json"] = {"milestones": [{"milestone_id": "ms-holder", "tasks": [task]}]}
    else:
        file, collection, _id_field, holder_id, _step = _HOLDERS[case.holder]
        docs[file] = {collection: [_holder_item(case, holder_id)]}
    for kind, ids in case.upstream.items():
        if kind == "criterion":
            file, collection, id_field = _UPSTREAM["fr"]
            parent = {"fr_id": "fr-parent", "acceptance_criteria": [{"criterion_id": criterion_id} for criterion_id in ids]}
            docs.setdefault(file, {}).setdefault(collection, []).append(parent)
            continue
        file, collection, id_field = _UPSTREAM[kind]
        docs.setdefault(file, {}).setdefault(collection, []).extend({id_field: node_id} for node_id in ids)
    return docs


def _holder_step(case: _Case) -> str:
    return "14" if case.holder == "task-criterion" else _HOLDERS[case.holder][4]


def _holder_node_id(case: _Case) -> str:
    return "tc-holder" if case.holder == "task-criterion" else _HOLDERS[case.holder][3]


def _upstream_ids(case: _Case) -> set[str]:
    return {node_id for ids in case.upstream.values() for node_id in ids}


def test_handoff_cases_are_each_in_exactly_one_group() -> None:
    cases = json.loads(_HANDOFF.read_text(encoding="utf-8"))["cases"]
    groups = [_VALID, _MISSING, _WRONG_KIND, _NOT_A_LINK, _ABSENT]
    seen = [index for group in groups for index in group] + list(_NOT_M4)
    assert len(cases) == 76
    assert sorted(seen) == list(range(76))
    assert all("dangling-link finding" in cases[i]["expected"] for i in _MISSING)
    assert all("absent upstream file" in cases[i]["expected"] or "absent" in cases[i]["old_test"] for i in _ABSENT)
    assert all(cases[i]["expected"].startswith("no finding") for i in _VALID)
    assert all("is not a kind of" in cases[i]["expected"] or "not a kind of" in cases[i]["expected"] for i in _WRONG_KIND)


@pytest.mark.parametrize("index", sorted(_VALID))
def test_handoff_valid_links_resolve(index: int) -> None:
    case = _VALID[index]
    graph = docs_graph(_case_docs(case))
    holder = graph.by_id[_holder_node_id(case)]
    assert [(link.field, link.target) for link in holder.links] == [(case.field, target) for target in case.targets]
    assert resolve_graph(graph) == []


@pytest.mark.parametrize("index", sorted(_MISSING))
def test_handoff_missing_target_is_e700_per_id(index: int) -> None:
    case = _MISSING[index]
    errors = resolve_graph(docs_graph(_case_docs(case)))
    missing = [target for target in case.targets if target not in _upstream_ids(case)]
    assert [error.code for error in errors] == ["E700"] * len(missing)
    assert [error.owner for error in errors] == [f"step:{_holder_step(case)}"] * len(missing)
    assert [error.node_id for error in errors] == [_holder_node_id(case)] * len(missing)
    for error, target in zip(errors, missing, strict=True):
        assert f"'{target}'" in error.message


@pytest.mark.parametrize("index", sorted(_WRONG_KIND))
def test_handoff_wrong_kind_is_e701(index: int) -> None:
    case = _WRONG_KIND[index]
    errors = resolve_graph(docs_graph(_case_docs(case)))
    assert [(error.code, error.owner) for error in errors] == [("E701", f"step:{_holder_step(case)}")]
    assert f"'{case.targets[0]}' is a capability" in errors[0].message


@pytest.mark.parametrize("index", sorted(_NOT_A_LINK))
def test_handoff_text_and_removed_fields_are_not_links(index: int) -> None:
    graph = docs_graph(_NOT_A_LINK[index])
    assert graph.nodes
    assert [link for node in graph.nodes for link in node.links] == []
    assert resolve_graph(graph) == []


@pytest.mark.parametrize("index", sorted(_ABSENT))
def test_handoff_absent_upstream_file_gives_e700(index: int) -> None:
    case = _ABSENT[index]
    errors = resolve_graph(docs_graph(_case_docs(case)))
    assert [error.code for error in errors] == ["E700"] * len(case.targets)
    assert [error.owner for error in errors] == [f"step:{_holder_step(case)}"] * len(case.targets)
    assert all("no file of step" in error.message for error in errors)


@pytest.mark.parametrize("index", _JOB_VERIFIES_FR)
def test_job_verifies_non_nfr_is_e701(index: int) -> None:
    """``job.verifies`` takes NFR ids only: an FR id that exists is E701."""
    case = _c("job", "verifies", ["fr-login"], fr=["fr-login"], nfr=["nfr-latency"])
    (error,) = resolve_graph(docs_graph(_case_docs(case)))
    assert (error.code, error.owner, error.node_id) == ("E701", "step:12", "job-holder")
    assert "'fr-login' is a fr" in error.message and "accepts: nfr" in error.message
