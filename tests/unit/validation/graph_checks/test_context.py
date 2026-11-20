"""``GraphCheckContext``: the play state of a node, the four seams, the owner of a finding and the roots it reads from (WI-M6b-01)."""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from specdev_tools.core.errors import ERROR_CODES, SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import run_git
from specdev_tools.graph.model import Graph, Node, SpecShape
from specdev_tools.graph.ownership import OwnerContext
from specdev_tools.validation.check_registry import CheckContext
from specdev_tools.validation.graph_checks import GRAPH_CHECKS, run_graph_checks
from specdev_tools.validation.graph_checks.codes import (
    CROSS_CUTTING_NOT_REFINED,
    MISSING_VERIFIER,
    NODE_DANGLING,
    NODE_ID_IN_PROSE,
    SCAFFOLD_PATH_NOT_TRACKED,
    SEED_LINK_NOT_ROUTED,
    SEED_NOT_ROUTED,
    SEED_ROUTE_UNUSED,
    TERM_NOT_USED_BY_LABEL,
    UNUSED_VERIFIER,
    VERIFIER_DOES_NOT_VERIFY_REFINED,
)
from specdev_tools.validation.graph_checks.context import GRAPH_NOT_BUILT, GraphCheckContext, Seams, bind_seams
from unit.graph._synth import EXAMPLE_SPEC, ROOT
from unit.trace._lock_support import git_copy_of_example

M6B_CODES = (
    NODE_DANGLING, TERM_NOT_USED_BY_LABEL, UNUSED_VERIFIER, MISSING_VERIFIER, CROSS_CUTTING_NOT_REFINED,
    VERIFIER_DOES_NOT_VERIFY_REFINED, SCAFFOLD_PATH_NOT_TRACKED, SEED_NOT_ROUTED, SEED_ROUTE_UNUSED, SEED_LINK_NOT_ROUTED,
    NODE_ID_IN_PROSE,
)


CHECKED_ROLES = ("obligation-system", "obligation-delivery", "context")
NOT_CHECKED_FOR_USE = ("term", "scaffold-row")  # a term is used by its label (E741), a scaffold row by its path (E746)


def _node(
    node_id: str = "n-1", *, kind: str = "fr", role: str | None = "obligation-system", step: str | None = "04",
    lifecycle: str = "active", scope: str | None = None,
) -> Node:
    return Node(node_id, kind, step, role, f"{step}.json", ".items[0]", None, (), lifecycle, scope, (), node_id)


def _context(*nodes: Node) -> GraphCheckContext:
    graph = Graph.from_nodes(list(nodes), shape=SpecShape(step_ranks={"04": 0, "08": 1}))
    return GraphCheckContext(graph=graph, lock=None, owner_context=OwnerContext(rows=()), repo_root=str(ROOT))


@pytest.fixture(scope="module")
def example() -> GraphCheckContext:
    return GraphCheckContext.from_graph(build_graph(str(EXAMPLE_SPEC), str(ROOT)), None)


@pytest.mark.parametrize(
    ("lifecycle", "scope", "in_play"),
    [
        ("active", "in", True),
        ("active", None, True),
        ("active", "later", False),
        ("active", "out", False),
        ("deprecated", "in", True),
        ("not_applicable", "in", False),
        ("not_applicable", "later", False),
    ],
)
def test_play_state_table(lifecycle: str, scope: str | None, in_play: bool) -> None:
    node = _node(lifecycle=lifecycle, scope=scope)
    assert _context(node).in_play(node) is in_play


def test_play_state_follows_the_nodes_listed_in_play() -> None:
    nodes = [_node("a", lifecycle="not_applicable"), _node("b", scope="out"), _node("c"), _node("d", lifecycle="deprecated")]
    assert [node.id for node in _context(*nodes).in_play_nodes()] == ["c", "d"]


def test_in_play_nodes_come_in_step_then_id_order() -> None:
    nodes = [_node("z", step="04"), _node("a", step="08"), _node("b", step="04")]
    assert [node.id for node in _context(*nodes).in_play_nodes()] == ["b", "z", "a"]


def test_deprecated_node_stays_in_play() -> None:
    node = _node(lifecycle="deprecated")
    context = _context(node)
    assert context.in_play(node)
    assert node in context.in_play_nodes()


@pytest.mark.parametrize(("scope", "in_scope"), [(None, True), ("in", True), ("later", False), ("out", False)])
def test_omitted_scope_reads_as_in_scope(scope: str | None, in_scope: bool) -> None:
    assert GraphCheckContext.in_scope(_node(scope=scope)) is in_scope


def test_retired_bindings_seam_stub_changes_play_state() -> None:
    verifier = _node("fx-1", kind="fixture", role="verifier", step="08")
    obligation = _node("fr-1")
    context = _context(verifier, obligation)
    assert context.in_play(verifier)
    restore = bind_seams(retired_bindings=lambda node: {"binding-1"} if node.id == "fx-1" else set())
    try:
        built_after = _context(verifier, obligation)
        assert not built_after.in_play(verifier)
        assert built_after.in_play(obligation)
        assert context.in_play(verifier), "a context built before the binding keeps the seams it was built with"
    finally:
        restore()
    assert _context(verifier).in_play(verifier)


def test_record_users_extra_verifiers_and_pin_matches_seams_have_stubs() -> None:
    node = _node("tp-1", kind="third-party", step="04")
    context = _context(node)
    assert (context.record_users(node), context.extra_verifiers(node), context.pin_matches(node)) == (set(), set(), "UNKNOWN")
    restore = bind_seams(
        record_users=lambda _node: {"rec-1"}, extra_verifiers=lambda _node: {"fr-9"}, pin_matches=lambda _node: "OK",
    )
    try:
        bound = _context(node)
        assert (bound.record_users(node), bound.extra_verifiers(node), bound.pin_matches(node)) == ({"rec-1"}, {"fr-9"}, "OK")
    finally:
        restore()
    assert _context(node).pin_matches(node) == "UNKNOWN"


def test_a_seam_that_does_not_exist_is_refused() -> None:
    with pytest.raises(TypeError):
        bind_seams(retired_bindings_typo=lambda node: set())


def test_seams_can_be_given_to_one_context_without_binding_them() -> None:
    node = _node("fx-1", kind="fixture", role="verifier", step="08")
    context = replace(_context(node), seams=Seams(retired_bindings=lambda _node: {"b"}))
    assert not context.in_play(node)
    assert _context(node).in_play(node)


@pytest.mark.parametrize(
    ("kind", "owner"),
    [("component", "step:11"), ("connection", "step:11"), ("environment", "step:12"), ("gate", "step:12"), ("secret", "step:12"),
     ("fr", "step:14"), ("threat", "step:14"), ("capability", "step:14")],
)
def test_owner_strings_from_owner_for_on_toy_registry(example: GraphCheckContext, kind: str, owner: str) -> None:
    node = example.graph.by_kind[kind][0]
    assert example.finding(NODE_DANGLING, node, "m").owner == owner


def test_furthest_step_is_filled_from_the_use_table(example: GraphCheckContext) -> None:
    furthest = example.owner_context.furthest_step
    assert {kind: furthest[kind] for kind in ("component", "environment", "gate", "secret", "fr", "threat")} == {
        "component": "11", "environment": "12", "gate": "12", "secret": "12", "fr": "14", "threat": "14",
    }


@pytest.mark.parametrize(
    ("code", "step"),
    [("E741", "step:14"), ("E742", "step:14"), ("E743", "step:08"), ("E744", "step:14"), ("E745", "step:14"),
     ("E746", "step:15"), ("E747", "step:00")],
)
def test_override_rows_give_fixed_steps(example: GraphCheckContext, code: str, step: str) -> None:
    for kind in ("fr", "component", "term"):
        assert example.finding(code, example.graph.by_kind[kind][0], "m").owner == step


@pytest.mark.parametrize("code", ["E748", "E749", "E752"])
def test_node_step_rows_give_the_step_of_the_node(example: GraphCheckContext, code: str) -> None:
    node = example.graph.by_kind["api"][0]
    assert example.finding(code, node, "m").owner == f"step:{node.step}"


def test_no_finding_of_the_eight_checks_is_owned_by_merge_check(example: GraphCheckContext) -> None:
    """No code of the checks falls to the default owner, whatever node it is about; and the checks built so far report none that does."""
    checked = [node for node in example.graph.nodes if node.role in CHECKED_ROLES]
    owners = {
        example.finding(code, node, "m").owner
        for code in M6B_CODES for node in checked
        if not (code == NODE_DANGLING and node.kind in NOT_CHECKED_FOR_USE)
    }
    assert None not in owners and "merge-check" not in owners
    assert [error.owner for error in run_graph_checks(example, "merge") if error.owner in (None, "merge-check")] == []
    assert len(GRAPH_CHECKS) == 8


def test_every_code_of_the_checks_is_registered() -> None:
    assert all(code in ERROR_CODES for code in M6B_CODES)


def test_finding_carries_file_jq_path_node_id_owner_and_target(example: GraphCheckContext) -> None:
    node = example.graph.by_kind["component"][0]
    error = example.finding(NODE_DANGLING, node, "no use", target="derives_from->cap-x")
    assert error == SpecError(
        code="E740", message="no use", file=node.file, jq_path=node.jq_path, node_id=node.id, owner="step:11",
        target="derives_from->cap-x",
    )


def test_finding_without_a_jq_path_carries_none() -> None:
    node = replace(_node(), jq_path="")
    assert _context(node).finding(NODE_DANGLING, node, "m").jq_path is None


def test_skip_when_graph_is_not_built(tmp_path: Path) -> None:
    """No registry in the toolkit root: no graph, so no context; the registered checks then skip with the one reason."""
    (tmp_path / "spec").mkdir()
    registry_context = CheckContext(repo_root=str(tmp_path), spec_dir=str(tmp_path / "spec"))
    assert GraphCheckContext.from_registry(registry_context) is None
    assert GRAPH_NOT_BUILT == "graph could not be built (see the `graph` check)"


def test_submodule_layout_finds_manifest_and_git_ls_files(tmp_path: Path) -> None:
    """The toolkit is one folder and the host repository another: the manifest is the graph's, the seeds are read at the host, git runs at the host."""
    host = git_copy_of_example(tmp_path / "host")
    spec = str(host / "spec")
    registry_context = CheckContext(repo_root=str(ROOT), spec_dir=spec, git_root=str(host), spec_root=spec)
    context = GraphCheckContext.from_registry(registry_context)
    assert context is not None
    assert os.path.realpath(context.git_root or "") == os.path.realpath(host)
    assert context.repo_root == str(ROOT) and os.path.realpath(context.spec_root or "") == os.path.realpath(spec)
    assert context.manifest["seeds"]
    assert set(context.seed_texts) == {node.id for node in context.graph.by_kind["seed"]} and all(context.seed_texts.values())
    listed = run_git(context.git_root or "", ["ls-files", "spec"]).stdout.decode().splitlines()
    assert "spec/04_fr_list.json" in listed


def test_seed_texts_are_empty_without_a_host_root(example: GraphCheckContext) -> None:
    assert example.git_root is None and example.seed_texts == {}


def test_closed_milestones_are_the_milestones_of_done_anchor_rows(example: GraphCheckContext) -> None:
    assert example.closed_milestones == set()
