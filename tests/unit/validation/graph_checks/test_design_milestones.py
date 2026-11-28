"""``matching_milestones`` and ``unrefined_scheduled``: the step-09 milestones a step-14 milestone computes, through containment (ruling R17), and the scheduled nodes no task criterion refines (ruling R18)."""
from __future__ import annotations

from dataclasses import replace

from specdev_tools.graph.build import build_graph
from specdev_tools.validation.graph_checks.design_milestones import matching_milestones, unrealised_design_milestones, unrefined_scheduled

from ._built_support import built_context, node
from ._example_support import context_of_spec
from unit.graph._synth import EXAMPLE_SPEC, ROOT

_DECLS = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls


def _schedule(milestone_id: str, *targets: str, step: str = "09", **options):
    return node(milestone_id, "design-milestone", "plan", step=step, links=[("schedules", target) for target in targets], **options)


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


def _plan_criterion(criterion_id: str, target: str, **options):
    """A task criterion nested under a task of the roadmap milestone ``ms-m`` that ``built_context`` makes (so only its own state decides)."""
    return node(criterion_id, "task-criterion", "plan", step="14", parent="task-t", links=[("refines", target)], **options)


def test_a_not_applicable_or_parked_criterion_does_not_count() -> None:
    nodes = [
        node("fr-1", "fr", children=["ac-1"]), node("ac-1", "criterion", parent="fr-1"), _schedule("dm-1", "fr-1"),
        _plan_criterion("tc-gone", "ac-1", lifecycle="not_applicable"), _plan_criterion("tc-parked", "fr-1", scope="later"),
    ]
    ctx = built_context(nodes)
    assert _pairs(ctx) == [] and [item.id for item in unrealised_design_milestones(ctx)] == ["dm-1"]
    assert _pairs(built_context([*nodes[:3], _plan_criterion("tc-live", "ac-1")])) == [("dm-1", "ms-m")]


def test_a_criterion_that_refines_through_a_renamed_id_counts() -> None:
    renamed = replace(node("ac-1", "criterion", parent="fr-1"), aliases=("ac-old",))
    nodes = [node("fr-1", "fr", children=["ac-1"]), renamed, _schedule("dm-1", "fr-1")]
    assert _pairs(built_context(nodes, {"tc-1": "ac-old"})) == [("dm-1", "ms-m")]


def test_a_parked_roadmap_milestone_still_pairs() -> None:
    nodes = [
        node("fr-1", "fr"), _schedule("dm-1", "fr-1"),
        node("ms-parked", "roadmap-milestone", "plan", step="14", scope="later", children=["task-p"]),
        node("task-p", "task", "plan", step="14", parent="ms-parked", children=["tc-p"]),
        node("tc-p", "task-criterion", "plan", step="14", parent="task-p", links=[("refines", "fr-1")]),
    ]
    assert _pairs(built_context(nodes)) == [("dm-1", "ms-parked")]


def test_every_unrealised_milestone_is_listed() -> None:
    nodes = [node("fr-1", "fr"), node("fr-2", "fr"), _schedule("dm-a", "fr-1"), _schedule("dm-b", "fr-2"), _schedule("dm-c", "fr-1", "fr-2")]
    ctx = built_context(nodes, {"tc-1": "fr-2"})
    assert [item.id for item in unrealised_design_milestones(ctx)] == ["dm-a"] and _pairs(ctx) == [("dm-b", "ms-m"), ("dm-c", "ms-m")]
    assert [item.id for item in unrealised_design_milestones(built_context(nodes))] == ["dm-a", "dm-b", "dm-c"]


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


def test_roadmap_milestones_come_in_the_order_of_the_listing_not_of_their_ids() -> None:
    """Step 10 lists before step 14 whatever the ids: the pairs of one design milestone follow the listing."""
    nodes = [
        node("fr-1", "fr"), _schedule("dm-1", "fr-1"),
        node("ms-z", "roadmap-milestone", "plan", step="10", children=["task-z"]),
        node("task-z", "task", "plan", step="10", parent="ms-z", children=["tc-z"]),
        node("tc-z", "task-criterion", "plan", step="10", parent="task-z", links=[("refines", "fr-1")]),
    ]
    assert _pairs(built_context(nodes, {"tc-1": "fr-1"})) == [("dm-1", "ms-z"), ("dm-1", "ms-m")]


def test_the_design_milestones_come_in_the_order_of_the_listing_whatever_the_input_order() -> None:
    """The listing is step, then id: ``dm-z`` of step 08 comes before ``dm-a`` of step 09, and the input order changes nothing."""
    nodes = [node("fr-1", "fr"), _schedule("dm-a", "fr-1"), _schedule("dm-z", "fr-1", step="08")]
    forward, backward = built_context(nodes, {"tc-1": "fr-1"}), built_context(list(reversed(nodes)), {"tc-1": "fr-1"})
    assert _pairs(forward) == _pairs(backward) == [("dm-z", "ms-m"), ("dm-a", "ms-m")]


def _unrefined(ctx) -> list[tuple[str, str]]:
    return [(design.id, scheduled.id) for design, scheduled in unrefined_scheduled(ctx)]


def test_the_unchanged_example_leaves_no_scheduled_node_unrefined() -> None:
    """``fr-password-reset`` is refined through ``ac-password-reset-3``; ``risk-reset-link-takeover`` is a risk, which nothing refines."""
    assert unrefined_scheduled(context_of_spec()) == []


def test_a_scheduled_node_no_criterion_refines_is_given_with_its_design_milestone() -> None:
    nodes = [node("fr-1", "fr", children=["ac-1"]), node("ac-1", "criterion", parent="fr-1"), node("fr-2", "fr"), _schedule("dm-1", "fr-2", "fr-1")]
    assert _unrefined(built_context(nodes, {"tc-1": "ac-1"}, decls=_DECLS)) == [("dm-1", "fr-2")]


def test_a_scheduled_risk_component_or_environment_never_appears() -> None:
    nodes = [
        node("fr-1", "fr"), node("risk-1", "risk"), node("comp-1", "component"), node("env-1", "environment"),
        _schedule("dm-1", "fr-1", "risk-1", "comp-1", "env-1"),
    ]
    assert _unrefined(built_context(nodes, {"tc-1": "fr-1"}, decls=_DECLS)) == []


def test_a_design_milestone_in_no_pair_gives_nothing() -> None:
    nodes = [node("fr-1", "fr"), node("fr-2", "fr"), _schedule("dm-1", "fr-1", "fr-2")]
    ctx = built_context(nodes, decls=_DECLS)
    assert unrefined_scheduled(ctx) == [] and [item.id for item in unrealised_design_milestones(ctx)] == ["dm-1"]


def test_a_parked_or_not_applicable_criterion_does_not_refine_for_it() -> None:
    nodes = [
        node("fr-1", "fr"), node("fr-2", "fr"), node("fr-3", "fr"), _schedule("dm-1", "fr-1", "fr-2", "fr-3"),
        _plan_criterion("tc-gone", "fr-2", lifecycle="not_applicable"), _plan_criterion("tc-parked", "fr-3", scope="later"),
    ]
    assert _unrefined(built_context(nodes, {"tc-1": "fr-1"}, decls=_DECLS)) == [("dm-1", "fr-2"), ("dm-1", "fr-3")]


def test_a_node_scheduled_by_two_milestones_is_given_for_each_in_the_order_of_the_listing() -> None:
    nodes = [node("fr-1", "fr"), node("fr-2", "fr"), node("fr-3", "fr"), _schedule("dm-b", "fr-3", "fr-2", "fr-1"), _schedule("dm-a", "fr-2", "fr-1", "fr-2")]
    ctx = built_context(list(reversed(nodes)), {"tc-1": "fr-1"}, decls=_DECLS)
    assert _unrefined(ctx) == [("dm-a", "fr-2"), ("dm-b", "fr-3"), ("dm-b", "fr-2")]


def test_matching_milestones_pairs_a_design_milestone_with_the_roadmap_milestone_of_its_refining_criterion() -> None:
    ctx = built_context([node("fr-1", "fr"), _schedule("dm-1", "fr-1")], {"tc-1": "fr-1"})
    assert _pairs(ctx) == [("dm-1", "ms-m")]


def test_a_design_milestone_no_criterion_refines_has_no_pair() -> None:
    ctx = built_context([node("fr-1", "fr"), node("fr-2", "fr"), _schedule("dm-1", "fr-1")], {"tc-1": "fr-2"})
    assert _pairs(ctx) == []


def test_a_scheduled_node_out_of_play_is_not_given_but_a_deprecated_one_is() -> None:
    """A node of ``scope`` later or out, or ``not_applicable``, is not planned, so no criterion is owed for it; a deprecated node is in play."""
    nodes = [
        node("fr-1", "fr"), node("fr-2", "fr", scope="later"), node("fr-3", "fr", lifecycle="not_applicable"), node("fr-4", "fr", lifecycle="deprecated"),
        node("fr-5", "fr", scope="out"), _schedule("dm-1", "fr-1", "fr-2", "fr-3", "fr-4", "fr-5"),
    ]
    assert _unrefined(built_context(nodes, {"tc-1": "fr-1"}, decls=_DECLS)) == [("dm-1", "fr-4")]


def test_a_schedules_link_to_no_node_gives_nothing_and_does_not_raise() -> None:
    nodes = [node("fr-1", "fr"), node("fr-2", "fr"), _schedule("dm-1", "fr-1", "fr-nowhere", "fr-2")]
    assert _unrefined(built_context(nodes, {"tc-1": "fr-1"}, decls=_DECLS)) == [("dm-1", "fr-2")]


def test_a_design_milestone_in_two_pairs_gives_each_unrefined_node_once() -> None:
    """``dm-1`` is computed by ``ms-m`` (through ``fr-1``) and by ``ms-2`` (through ``fr-2``): its one unrefined node, ``fr-3``, is given once."""
    nodes = [
        node("fr-1", "fr"), node("fr-2", "fr"), node("fr-3", "fr"), _schedule("dm-1", "fr-1", "fr-2", "fr-3"),
        node("ms-2", "roadmap-milestone", "plan", step="14", children=["task-2"]),
        node("task-2", "task", "plan", step="14", parent="ms-2", children=["tc-2"]),
        node("tc-2", "task-criterion", "plan", step="14", parent="task-2", links=[("refines", "fr-2")]),
    ]
    ctx = built_context(nodes, {"tc-1": "fr-1"}, decls=_DECLS)
    assert len(_pairs(ctx)) == 2 and _unrefined(ctx) == [("dm-1", "fr-3")]


def test_a_criterion_whose_plan_file_names_a_node_that_is_no_roadmap_milestone_makes_no_pair() -> None:
    """``milestone_of`` gives the id a plan file names as it is written; only a roadmap milestone can pair with a design milestone."""
    odd = replace(_plan_criterion("tc-odd", "fr-1"), milestone="fr-2")
    ctx = built_context([node("fr-1", "fr"), node("fr-2", "fr"), _schedule("dm-1", "fr-1"), odd])
    assert _pairs(ctx) == [] and [item.id for item in unrealised_design_milestones(ctx)] == ["dm-1"]
