"""The no-dangling check (E740): the use table of WI-M6b-01 here, the check itself from WI-M6b-02."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.no_dangling import check_no_dangling
from specdev_tools.validation.graph_checks.use_table import EXCLUDED_VERBS, USE_TABLE, Use, use_pairs
from unit.graph._synth import EXAMPLE_SPEC, ROOT, run_specdev
from unit.trace._lock_support import git_copy_of_example

# The rows of the design's "Who uses what" table that name holders (DOC L610-L634); segment and metric ("a later
# node's link") and "every other kind" have no row and take any link that is not excluded.
_ASSUMING = {
    "api", "api-error", "capability", "component", "connection", "constraint", "criterion", "edge-case", "environment",
    "fr", "gate", "invariant", "metric", "need", "nfr", "risk", "rule", "scope-item", "secret", "segment", "stakeholder",
    "third-party", "threat",
}
_DOC_ROWS: dict[str, set[Use]] = {
    "assumption": {*(Use(kind, "assumes") for kind in _ASSUMING), Use("risk", "derives_from")},
    "need": {Use("metric", "derives_from"), Use("scope-item", "derives_from"), Use("constraint", "derives_from")},
    "stakeholder": {Use("rule", "derives_from")},
    "component": {
        Use("api", "provided_by"), Use("invariant", "constrains"), Use("nfr", "constrains"), Use("threat", "threatens"),
        Use("connection", "connects_to"), Use("gate", "derives_from"), Use("secret", "derives_from"),
    },
    "connection": {
        Use("invariant", "constrains"), Use("nfr", "constrains"), Use("threat", "threatens"), Use("secret", "derives_from"),
    },
    "third-party": {Use("api", "relies_on"), Use("nfr", "relies_on"), Use("third-party", "part_of"), Use("connection", "connects_to")},
    "environment": {Use("job", "realises")},
    "gate": {Use("job", "realises")},
    "secret": {Use("job", "realises")},
    "term": set(),
    "threat": {Use("task-criterion", "refines")},
    "edge-case": {Use("task-criterion", "refines")},
    "risk": {Use("threat", "derives_from"), Use("rule", "derives_from"), Use("design-milestone", "schedules")},
    "constraint": {
        Use(kind, "derives_from") for kind in ("third-party", "component", "environment", "gate", "secret", "rule")
    },
}


def test_use_matches_doc_rows() -> None:
    """The table is the design's rows, and every (holder kind, verb) pair of it is a link the registry declares for that target kind."""
    assert {kind: set(row) for kind, row in USE_TABLE.items()} == _DOC_ROWS
    decls = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls
    undeclared = [
        (target, use) for target, row in USE_TABLE.items() for use in row
        if not any(link.field == use.verb and link.accepts(target) for link in decls[use.holder_kind].links)
    ]
    assert undeclared == []


def test_a_kind_without_a_row_is_used_by_any_link_that_is_not_excluded() -> None:
    decls = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls
    pairs = use_pairs("capability", decls)
    assert Use("fr", "derives_from") in pairs and Use("task-criterion", "refines") in pairs
    assert {use.verb for use in pairs}.isdisjoint(EXCLUDED_VERBS)
    assert {use.holder_kind for use in pairs}.isdisjoint({"fixture", "job", "ambiguity-item", "evidence-record", "verification-record"})


# --- the check ----------------------------------------------------------------------------------------------------------

_EXAMPLE = build_graph(str(EXAMPLE_SPEC), str(ROOT))
_LINK = LinkDecl("derives_from", (), False, False, ())


def _node(node_id: str, kind: str, *, parent: str | None = None, lifecycle: str = "active", scope: str | None = None, **links: list[str]) -> Node:
    """A node of the real *kind* (role and step as the registry gives them) holding the given link fields."""
    decl = _EXAMPLE.decls[kind]
    step = _EXAMPLE.shape.kind_steps[kind][0]
    made = tuple(Link(node_id, field, target, _LINK) for field, targets in links.items() for target in targets)
    return Node(node_id, kind, step, decl.role, f"{node_id}.json", ".item", parent, (), lifecycle, scope, made, node_id)


def _context(*nodes: Node) -> GraphCheckContext:
    children: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.parent:
            children[node.parent].append(node.id)
    placed = [replace(node, children=tuple(children[node.id])) for node in nodes]
    graph = Graph.from_nodes(placed, shape=_EXAMPLE.shape)
    graph.decls = _EXAMPLE.decls
    return GraphCheckContext.from_graph(graph, None, str(ROOT))


def _dangling(*nodes: Node) -> list[str]:
    return [error.node_id for error in check_no_dangling(_context(*nodes), "merge") if error.node_id]


def test_component_used_only_by_connection_derives_from_is_dangling() -> None:
    assert "comp-a" in _dangling(_node("comp-a", "component"), _node("conn-a", "connection", derives_from=["comp-a"]))


def test_component_with_connects_to_is_used() -> None:
    assert "comp-a" not in _dangling(_node("comp-a", "component"), _node("conn-a", "connection", connects_to=["comp-a"]))


def test_invariant_with_fixture_and_no_criterion_is_dangling() -> None:
    assert _dangling(_node("inv-a", "invariant"), _node("fix-a", "fixture", verifies=["inv-a"])) == ["inv-a"]


def test_nfr_with_fixture_only_is_dangling() -> None:
    assert _dangling(_node("nfr-a", "nfr"), _node("fix-a", "fixture", verifies=["nfr-a"])) == ["nfr-a"]


def test_nfr_with_refining_criterion_is_used() -> None:
    assert _dangling(_node("nfr-a", "nfr"), _node("tc-a", "task-criterion", refines=["nfr-a"])) == []


@pytest.mark.parametrize(("lifecycle", "scope", "dangling"), [
    ("active", "later", False),
    ("active", "out", True),
    ("not_applicable", None, True),
    ("deprecated", None, False),
])
def test_a_holder_counts_as_use_unless_it_is_out_of_scope_or_not_applicable(lifecycle: str, scope: str | None, dangling: bool) -> None:
    holder = _node("fr-a", "fr", lifecycle=lifecycle, scope=scope, derives_from=["cap-a"])
    assert ("cap-a" in _dangling(_node("cap-a", "capability"), holder)) is dangling


def test_scope_later_holder_counts_as_use() -> None:
    holder = _node("fr-a", "fr", scope="later", derives_from=["cap-a"])
    assert _dangling(_node("cap-a", "capability"), holder) == []


def test_scope_out_holder_does_not_count() -> None:
    holder = _node("fr-a", "fr", scope="out", derives_from=["cap-a"])
    assert _dangling(_node("cap-a", "capability"), holder) == ["cap-a"]


def test_not_applicable_holder_does_not_count() -> None:
    holder = _node("fr-a", "fr", lifecycle="not_applicable", derives_from=["cap-a"])
    assert _dangling(_node("cap-a", "capability"), holder) == ["cap-a"]


def test_not_applicable_node_is_not_checked_and_deprecated_is() -> None:
    assert _dangling(_node("cap-a", "capability", lifecycle="not_applicable")) == []
    assert _dangling(_node("cap-a", "capability", lifecycle="deprecated")) == ["cap-a"]


def test_deprecated_node_stays_checked() -> None:
    assert _dangling(_node("nfr-a", "nfr", lifecycle="deprecated")) == ["nfr-a"]


def test_record_link_does_not_count_for_a_non_verifier() -> None:
    note = _node("amb-a", "ambiguity-item", about=["cap-a"])
    assert _dangling(_node("cap-a", "capability"), note) == ["cap-a"]


@pytest.mark.parametrize("verb", ["replaces", "removes"])
def test_the_id_history_links_do_not_count(verb: str) -> None:
    successor = _node("cap-b", "capability", **{verb: ["cap-a"]})
    assert "cap-a" in _dangling(_node("cap-a", "capability"), successor)


def test_container_rule_counts_a_used_child() -> None:
    nodes = [_node("fr-a", "fr"), _node("ac-a", "criterion", parent="fr-a"), _node("tc-a", "task-criterion", refines=["ac-a"])]
    assert _dangling(*nodes) == []
    assert _dangling(*nodes[:2]) == ["ac-a", "fr-a"]


def test_a_child_that_is_out_of_play_does_not_use_its_container() -> None:
    nodes = [_node("fr-a", "fr"), _node("ac-a", "criterion", parent="fr-a", lifecycle="not_applicable")]
    assert _dangling(*nodes) == ["fr-a"]


def test_a_containment_cycle_ends() -> None:
    assert _dangling(_node("fr-a", "fr", parent="fr-b"), _node("fr-b", "fr", parent="fr-a")) == ["fr-a", "fr-b"]


@pytest.mark.parametrize("kind", ["task", "task-criterion", "design-milestone", "anchor-row", "ambiguity-item", "term", "scaffold-row", "extension"])
def test_exempt_roles_produce_no_e740(kind: str) -> None:
    assert _dangling(_node("node-a", kind)) == []


def test_unused_fixture_produces_no_e740() -> None:
    assert _dangling(_node("fix-a", "fixture"), _node("job-a", "job")) == []


@pytest.mark.parametrize(("holder_kind", "verb", "dangling"), [
    ("task-criterion", "refines", False),
    ("job", "realises", False),
    ("task-criterion", "verified_by", True),
    ("fixture", "verifies", True),
])
def test_rule_with_review_or_command_enforcer_needs_an_inbound_link(holder_kind: str, verb: str, dangling: bool) -> None:
    """A rule has no use of its own enforcer: it is used by a criterion that refines it or a job that realises it."""
    rule = _node("rule-a", "rule")
    holder = _node("holder-a", holder_kind, **{verb: ["rule-a"]})
    assert ("rule-a" in _dangling(rule, holder)) is dangling
    assert _dangling(rule) == ["rule-a"]


@pytest.mark.parametrize(("kind", "owner"), [
    ("nfr", "step:14"), ("api-error", "step:14"), ("rule", "step:14"), ("threat", "step:14"), ("environment", "step:12"),
    ("secret", "step:12"), ("metric", "step:07"), ("capability", "step:14"),
])
def test_e740_owner_is_the_furthest_usable_step(kind: str, owner: str) -> None:
    [finding] = check_no_dangling(_context(_node("node-a", kind)), "merge")
    assert (finding.code, finding.owner, finding.node_id) == ("E740", owner, "node-a")


def test_e740_message_names_the_kind_the_way_to_use_it_and_the_way_out() -> None:
    [finding] = check_no_dangling(_context(_node("nfr-a", "nfr")), "merge")
    assert "nfr nfr-a" in finding.message and "task-criterion refines (step 14)" in finding.message
    assert finding.message.endswith("link it, schedule it, or set scope later or out")


def test_e740_findings_are_listed_in_step_order_and_carry_a_node_id() -> None:
    nodes = [_node("z-nfr", "nfr"), _node("a-threat", "threat"), _node("m-cap", "capability"), _node("b-env", "environment")]
    errors = check_no_dangling(_context(*nodes), "merge")
    assert [error.node_id for error in errors] == ["m-cap", "b-env", "z-nfr", "a-threat"]
    assert all(error.node_id and error.target is None for error in errors)


def test_a_link_written_with_an_alias_counts() -> None:
    renamed = replace(_node("cap-new", "capability"), aliases=("cap-old",))
    assert "cap-new" not in _dangling(renamed, _node("fr-a", "fr", derives_from=["cap-old"]))


def test_a_verifier_with_all_bindings_retired_is_not_a_use() -> None:
    gate = _node("gate-a", "gate")
    job = _node("job-a", "job", realises=["gate-a"])
    context = _context(gate, job)
    assert check_no_dangling(context, "merge") == []
    context.seams = replace(context.seams, retired_bindings=lambda node: {"x"} if node.id == "job-a" else set())
    assert [error.node_id for error in check_no_dangling(context, "merge")] == ["gate-a"]


# --- a fresh process sees the role gaps --------------------------------------------------------------------------------

_PROBE_CAPABILITY = "cap-probe-unused"


def _example_host_with_an_unused_capability(destination: Path) -> Path:
    host = git_copy_of_example(destination)
    capabilities = host / "spec" / "01_capabilities.json"
    document = json.loads(capabilities.read_text(encoding="utf-8"))
    document["capabilities"].append({"capability_id": _PROBE_CAPABILITY, "verb": "probe", "scope": "in", "owner": "product", "description": "Nothing uses it."})
    capabilities.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return host


@pytest.mark.parametrize("command", [("stale",), ("coverage",)], ids=["stale", "coverage"])
def test_a_fresh_process_counts_the_role_gap_of_a_node(command: tuple[str, ...], tmp_path: Path) -> None:
    """``specdev stale`` and ``specdev coverage`` import the graph checks themselves: the E740 gap of the unused capability is in their output."""
    host = _example_host_with_an_unused_capability(tmp_path / "host")
    done = run_specdev(*command, "--json", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert done.returncode == 0, done.stderr
    assert f'"{_PROBE_CAPABILITY}"' in done.stdout and '"E740"' in done.stdout


def test_building_the_command_line_parser_registers_the_gap_provider_once() -> None:
    """``stale``, ``coverage`` and ``step ready`` all run after the parser is built: that is where the provider is registered, in a process that imported nothing else."""
    code = "from specdev_tools import cli; cli.build_parser(); from specdev_tools.trace import gaps; print(len(gaps._providers))"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT / "tools")}, check=True)
    assert done.stdout.strip() == "1"
