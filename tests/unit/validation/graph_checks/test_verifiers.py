"""The verifier rules (E742 unused, E743 missing, WI-M6b-07): the use of a verifier, the nodes a verifier must name, history, lifecycle and order."""
from __future__ import annotations

import json
from dataclasses import replace
from functools import cache

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import KindDecl, LinkDecl
from specdev_tools.graph.model import Node, SpecShape
from specdev_tools.validation.graph_checks import run_graph_checks
from specdev_tools.validation.graph_checks.context import GraphCheckContext, bind_seams
from specdev_tools.validation.graph_checks.refinement import check_refinement
from specdev_tools.validation.graph_checks.verifiers import check_verifier_rules, missing_verifiers
from unit.graph._synth import EXAMPLE_SPEC, HASH_SEEDS, ROOT, run_python_seeded

from .graph_builder import STEP_RANKS, closed_milestone, row, spec as build_spec


@cache
def _real_decls() -> dict[str, KindDecl]:
    return build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls


def _spec(*nodes: Node, decls: dict[str, KindDecl] | None = None) -> GraphCheckContext:
    """A context over *nodes* with the registry's declarations (or *decls*) and the steps the message names."""
    context = build_spec(*nodes)
    context.graph.decls = _real_decls() if decls is None else decls
    context.graph.shape = SpecShape(step_ranks=STEP_RANKS, kind_steps={"fixture": ("08",), "job": ("12",)})
    return context


def _found(context: GraphCheckContext) -> list[tuple[str, str | None]]:
    return [(error.code, error.node_id) for error in check_verifier_rules(context, "merge")]


def _criterion(verified_by: list[str], **links: list[str]) -> Node:
    return row("tc-1", "task-criterion", parent="task-1", verified_by=verified_by, **links)


def _base(*nodes: Node) -> list[Node]:
    """An FR with one criterion verified by a fixture, and a task."""
    return [row("fr-a", "fr"), row("ac-a-1", "criterion", parent="fr-a"), row("fix-ac", "fixture", verifies=["ac-a-1"]), row("task-1", "task"), *nodes]


# --- E742: unused ----------------------------------------------------------------------------------------------------


def test_unused_fixture_gives_exactly_one_e742_and_no_e740() -> None:
    context = _spec(*_base(row("fix-spare", "fixture", verifies=["ac-a-1"])))
    assert _found(context) == [("E742", "fix-ac"), ("E742", "fix-spare")]
    assert "fix-spare" not in [error.node_id for error in run_graph_checks(context, "merge", only={"E740"})]


def test_unused_job_gives_e742() -> None:
    assert ("E742", "job-1") in _found(_spec(*_base(row("job-1", "job"))))


def test_job_used_through_realises_gives_no_e742() -> None:
    context = _spec(*_base(row("gate-1", "gate"), row("job-1", "job", realises=["gate-1"])))
    assert ("E742", "job-1") not in _found(context)


def test_fixture_used_through_verified_by_gives_no_e742() -> None:
    assert ("E742", "fix-ac") not in _found(_spec(*_base(_criterion(["fix-ac"], refines=["ac-a-1"]))))


def test_removal_fixture_used_through_removal_criterion_gives_no_e742() -> None:
    nodes = [row("fix-gone", "fixture", removes=["fr-gone"]), row("task-1", "task"), _criterion(["fix-gone"], removes=["fr-gone"])]
    assert _found(_spec(*nodes)) == []
    assert _found(_spec(nodes[0])) == [("E742", "fix-gone")]


def test_job_used_only_through_depends_on_gives_e742() -> None:
    nodes = _base(row("gate-1", "gate"), row("job-1", "job", realises=["gate-1"]), row("job-2", "job", depends_on=["job-1"]))
    assert [item for item in _found(_spec(*nodes)) if item[0] == "E742"] == [("E742", "fix-ac"), ("E742", "job-2")]


def test_job_verifying_in_play_nfr_gives_no_e742() -> None:
    nodes = _base(row("nfr-1", "nfr"), row("job-1", "job", verifies=["nfr-1"]))
    assert ("E742", "job-1") not in _found(_spec(*nodes))


def test_job_with_neither_realises_nor_verifies_gives_e742() -> None:
    out_of_play = row("nfr-1", "nfr", scope="out")
    assert ("E742", "job-1") in _found(_spec(*_base(out_of_play, row("job-1", "job", verifies=["nfr-1"]))))
    assert ("E742", "job-2") in _found(_spec(*_base(row("job-2", "job"))))


def test_record_users_seam_counts_a_record_as_use() -> None:
    context = _spec(*_base(row("fix-spare", "fixture", verifies=["ac-a-1"])))
    assert ("E742", "fix-spare") in _found(context)
    restore = bind_seams(record_users=lambda verifier: {"rec-1"} if verifier.id == "fix-spare" else set())
    try:
        assert ("E742", "fix-spare") not in _found(_spec(*_base(row("fix-spare", "fixture", verifies=["ac-a-1"]))))
    finally:
        restore()


def test_e742_owner_is_step_14() -> None:
    (error,) = (e for e in check_verifier_rules(_spec(*_base(row("fix-spare", "fixture"))), "merge") if e.node_id == "fix-spare")
    assert (error.code, error.owner) == ("E742", "step:14")


# --- E743: missing ---------------------------------------------------------------------------------------------------


def test_criterion_api_and_invariant_without_a_fixture_give_e743() -> None:
    nodes = [
        row("fr-a", "fr"), row("ac-a-1", "criterion", parent="fr-a"), row("api-a", "api", derives_from=["fr-a"]),
        row("inv-a", "invariant"), row("fix-1", "fixture", verifies=["fr-a"]),
    ]
    assert [item for item in _found(_spec(*nodes)) if item[0] == "E743"] == [("E743", "ac-a-1"), ("E743", "api-a"), ("E743", "inv-a")]


def test_api_error_gets_no_e743() -> None:
    nodes = [row("ac-a-1", "criterion"), row("api-a", "api"), row("err-a", "api-error", derives_from=["ac-a-1"]), row("fix-1", "fixture", verifies=["ac-a-1", "api-a"])]
    assert [item for item in _found(_spec(*nodes)) if item[0] == "E743"] == []


def test_e743_kinds_are_read_from_the_fixture_verifies_declaration() -> None:
    decls = {"fixture": KindDecl("fixture", ".fixtures", "id", False, "verifier", (), (LinkDecl("verifies", ("criterion", "rule"), False, False, ()),))}
    nodes = [row("ac-a-1", "criterion"), row("rule-a", "rule"), row("api-a", "api")]
    assert [item for item in _found(_spec(*nodes, decls=decls)) if item[0] == "E743"] == [("E743", "ac-a-1"), ("E743", "rule-a")]
    assert missing_verifiers(_spec(*nodes, decls={})) == []


def test_nfr_message_names_a_fixture_at_08_and_a_job_at_12() -> None:
    errors = [e for e in check_verifier_rules(_spec(row("nfr-1", "nfr"), row("ac-a-1", "criterion")), "merge") if e.code == "E743"]
    messages = {error.node_id: error.message for error in errors}
    assert "a fixture at step 08 or a job at step 12" in messages["nfr-1"]
    assert "a job" not in messages["ac-a-1"] and "a fixture at step 08" in messages["ac-a-1"]


def test_removal_criterion_gives_no_e745_e742_or_e743() -> None:
    nodes = [
        row("fr-a", "fr"), row("task-1", "task"), row("fix-gone", "fixture", removes=["fr-a"]),
        row("tc-remove", "task-criterion", parent="task-1", removes=["fr-a"], verified_by=["fix-gone"]),
    ]
    context = _spec(*nodes)
    assert _found(context) == []
    assert check_refinement(context, "merge") == []


def test_fr_with_criteria_is_not_flagged() -> None:
    nodes = [row("fr-a", "fr"), row("ac-a-1", "criterion", parent="fr-a"), row("fix-1", "fixture", verifies=["ac-a-1"]), row("task-1", "task"), _criterion(["fix-1"])]
    assert _found(_spec(*nodes)) == []


def test_nfr_with_no_fixture_and_no_job_gives_e743() -> None:
    assert _found(_spec(row("nfr-1", "nfr"))) == [("E743", "nfr-1")]


def test_nfr_with_job_verifies_and_no_fixture_gives_no_e743() -> None:
    nodes = [row("nfr-1", "nfr"), row("job-1", "job", verifies=["nfr-1"]), row("task-1", "task"), _criterion(["job-1"])]
    assert _found(_spec(*nodes)) == []


def test_scope_later_node_is_exempt() -> None:
    assert _found(_spec(row("nfr-1", "nfr", scope="later"), row("ac-a-1", "criterion", scope="out"))) == []


def test_threat_and_edge_case_get_no_e743() -> None:
    assert _found(_spec(row("threat-1", "threat"), row("ec-1", "edge-case"), row("rule-1", "rule"), row("fr-1", "fr"))) == []


def test_removal_fixture_never_gets_e743() -> None:
    context = _spec(row("fix-gone", "fixture", removes=["fr-gone"]), row("task-1", "task"), _criterion(["fix-gone"], removes=["fr-gone"]))
    assert missing_verifiers(context) == []


def test_manual_fixture_counts_as_verifier() -> None:
    manual = row("fix-manual", "fixture", verifies=["ac-a-1"])
    assert missing_verifiers(_spec(row("ac-a-1", "criterion"), manual)) == []


def test_removing_only_fixture_of_an_invariant_gives_e743_naming_it() -> None:
    nodes = [row("inv-a", "invariant"), row("fix-inv", "fixture", verifies=["inv-a"]), row("task-1", "task"), _criterion(["fix-inv"])]
    assert _found(_spec(*nodes)) == []
    without = [node for node in nodes if node.id != "fix-inv"]
    (error,) = check_verifier_rules(_spec(*without), "merge")
    assert (error.code, error.node_id, error.owner) == ("E743", "inv-a", "step:08")
    assert "inv-a" in error.message


def test_e743_owner_is_step_08() -> None:
    (error,) = check_verifier_rules(_spec(row("nfr-1", "nfr")), "merge")
    assert (error.code, error.owner) == ("E743", "step:08")


# --- history ---------------------------------------------------------------------------------------------------------


def _history(*, closed: bool) -> list[Node]:
    """A criterion refined by a change criterion and removed by a removal criterion, both verified by a fixture that was deleted."""
    milestone = closed_milestone("ms-1") if closed else [row("ms-1", "roadmap-milestone")]
    return [
        *milestone, row("fr-a", "fr"), row("ac-a-1", "criterion", parent="fr-a"), row("task-1", "task", parent="ms-1"),
        row("tc-1", "task-criterion", parent="task-1", refines=["ac-a-1"], verified_by=["fix-deleted"]),
        row("tc-remove", "task-criterion", parent="task-1", removes=["ac-a-1"], verified_by=["fix-deleted"]),
    ]


def test_closed_removal_fixture_deleted_gives_no_e742_e743_e745() -> None:
    context = _spec(*_history(closed=True))
    assert _found(context) == []
    assert check_refinement(context, "merge") == []


def test_open_milestone_removal_fixture_deleted_gives_the_errors() -> None:
    context = _spec(*_history(closed=False))
    assert _found(context) == [("E743", "ac-a-1")]
    assert [(error.code, error.node_id) for error in check_refinement(context, "merge")] == [("E745", "tc-1")]


def test_fixture_renamed_under_closed_criterion_gives_no_errors() -> None:
    renamed = replace(row("fix-new", "fixture", verifies=["ac-a-1"]), aliases=("fix-old",))
    nodes = [
        *closed_milestone("ms-1"), row("ac-a-1", "criterion"), renamed, row("task-1", "task", parent="ms-1"),
        row("tc-1", "task-criterion", parent="task-1", refines=["ac-a-1"], verified_by=["fix-old"]),
    ]
    context = _spec(*nodes)
    assert _found(context) == [] and check_refinement(context, "merge") == []
    unaliased = _spec(*(replace(node, aliases=()) for node in nodes))
    assert _found(unaliased) == [("E742", "fix-new")]


# --- lifecycle and order ---------------------------------------------------------------------------------------------


def test_verifier_rules_do_not_read_a_not_applicable_node() -> None:
    assert _found(_spec(row("fix-spare", "fixture", lifecycle="not_applicable"), row("ac-a-1", "criterion", lifecycle="not_applicable"))) == []
    assert _found(_spec(row("fix-spare", "fixture", lifecycle="deprecated"), row("ac-a-1", "criterion", lifecycle="deprecated"))) == [
        ("E742", "fix-spare"), ("E743", "ac-a-1"),
    ]
    holder = _criterion(["fix-1"], refines=["ac-a-1"])
    inapplicable_holder = replace(holder, lifecycle="not_applicable")
    nodes = [row("fix-1", "fixture", verifies=["ac-a-1"]), row("ac-a-1", "criterion"), row("task-1", "task")]
    assert _found(_spec(*nodes, inapplicable_holder)) == [("E742", "fix-1")]


def _scenario(reverse: bool) -> list[tuple[str, str | None]]:
    nodes = [
        row("nfr-z", "nfr"), row("fix-z", "fixture"), row("ac-m", "criterion"), row("job-a", "job"),
        row("api-b", "api"), row("fix-a", "fixture"), row("inv-c", "invariant"),
    ]
    return _found(_spec(*reversed(nodes) if reverse else nodes))


_ORDER_CODE = """
import json
from unit.validation.graph_checks.test_verifiers import _scenario
print(json.dumps(_scenario(True)))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_verifier_rules_report_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = [list(item) for item in _scenario(False)]
    assert [code for code, _ in _scenario(False)].count("E742") == 3 and len(expected) == 7
    assert json.loads(run_python_seeded(seed, _ORDER_CODE)) == expected
