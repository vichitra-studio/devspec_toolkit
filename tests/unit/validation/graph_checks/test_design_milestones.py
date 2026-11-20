"""``matching_milestones``: the step-09 milestones a step-14 milestone computes, through containment (ruling R17)."""
from __future__ import annotations

from specdev_tools.validation.graph_checks.design_milestones import matching_milestones, unrealised_design_milestones

from ._built_support import built_context, node
from ._example_support import context_of_spec


def _schedule(milestone_id: str, *targets: str, **options):
    return node(milestone_id, "design-milestone", "plan", step="09", links=[("schedules", target) for target in targets], **options)


def _pairs(ctx) -> list[tuple[str, str]]:
    return [(design.id, roadmap.id) for design, roadmap in matching_milestones(ctx)]


def test_the_unchanged_example_computes_its_design_milestone_and_leaves_none_unrealised() -> None:
    ctx = context_of_spec()
    pairs = _pairs(ctx)
    assert [design for design, _ in pairs] == ["milestone-account-recovery"] and len({roadmap for _, roadmap in pairs}) == len(pairs) == 1
    assert unrealised_design_milestones(ctx) == []


def test_a_criterion_of_a_scheduled_node_computes_the_milestone() -> None:
    nodes = [node("fr-1", "fr", children=["ac-1"]), node("ac-1", "criterion", parent="fr-1"), _schedule("dm-1", "fr-1")]
    ctx = built_context(nodes, {"tc-1": "ac-1"})
    assert _pairs(ctx) == [("dm-1", "ms-m")] and unrealised_design_milestones(ctx) == []


def test_a_node_refined_itself_computes_the_milestone() -> None:
    ctx = built_context([node("fr-1", "fr"), _schedule("dm-1", "fr-1")], {"tc-1": "fr-1"})
    assert _pairs(ctx) == [("dm-1", "ms-m")]


def test_a_scheduled_node_that_nothing_refines_leaves_the_milestone_unrealised() -> None:
    nodes = [node("fr-1", "fr", children=["ac-1"]), node("ac-1", "criterion", parent="fr-1"), node("fr-2", "fr"), _schedule("dm-1", "fr-1")]
    ctx = built_context(nodes, {"tc-1": "fr-2"})
    assert _pairs(ctx) == [] and [item.id for item in unrealised_design_milestones(ctx)] == ["dm-1"]


def test_a_node_above_the_scheduled_one_does_not_count() -> None:
    """Containment goes down: a criterion that refines the FR does not realise a milestone that schedules one criterion of it."""
    nodes = [node("fr-1", "fr", children=["ac-1"]), node("ac-1", "criterion", parent="fr-1"), _schedule("dm-1", "ac-1")]
    assert _pairs(built_context(nodes, {"tc-1": "fr-1"})) == []


def test_a_not_applicable_or_parked_criterion_does_not_count() -> None:
    nodes = [
        node("fr-1", "fr", children=["ac-1"]), node("ac-1", "criterion", parent="fr-1"), _schedule("dm-1", "fr-1"),
        node("tc-gone", "task-criterion", "plan", step="14", lifecycle="not_applicable", links=[("refines", "ac-1")]),
        node("tc-parked", "task-criterion", "plan", step="14", scope="later", links=[("refines", "fr-1")]),
    ]
    ctx = built_context(nodes)
    assert _pairs(ctx) == [] and [item.id for item in unrealised_design_milestones(ctx)] == ["dm-1"]


def test_a_design_milestone_out_of_play_is_in_no_pair() -> None:
    ctx = built_context([node("fr-1", "fr"), _schedule("dm-1", "fr-1", lifecycle="not_applicable")], {"tc-1": "fr-1"})
    assert _pairs(ctx) == []


def test_each_design_milestone_pairs_with_each_roadmap_milestone_that_computes_it_in_the_order_of_the_listing() -> None:
    nodes = [
        node("fr-1", "fr"), node("fr-2", "fr"), _schedule("dm-b", "fr-1", "fr-2"), _schedule("dm-a", "fr-1"),
        node("ms-2", "roadmap-milestone", "plan", step="14", children=["task-2"]),
        node("task-2", "task", "plan", step="14", parent="ms-2", children=["tc-2"]),
        node("tc-2", "task-criterion", "plan", step="14", parent="task-2", links=[("refines", "fr-2")]),
    ]
    ctx = built_context(nodes, {"tc-1": "fr-1"})
    assert _pairs(ctx) == [("dm-a", "ms-m"), ("dm-b", "ms-2"), ("dm-b", "ms-m")]
