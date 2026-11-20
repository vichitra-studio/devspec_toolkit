"""How the graph checks are registered: the ``spec-check`` entries, the rule list and the replay gap provider (WI-M6b-01)."""
from __future__ import annotations

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.trace import gaps
from specdev_tools.trace.gaps import CoverageGap, coverage_gaps
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation import graph_checks
from specdev_tools.validation.check_registry import CHECK_REGISTRY
from specdev_tools.validation.graph_checks import GRAPH_CHECKS, register_graph_check, role_gaps, run_graph_checks
from specdev_tools.validation.graph_checks.codes import MISSING_VERIFIER, NODE_DANGLING, UNUSED_VERIFIER
from specdev_tools.validation.graph_checks.context import GraphCheckContext, Mode
from specdev_tools.validation.spec_check import run_spec_check_json  # noqa: F401  (importing it fills CHECK_REGISTRY)
from unit.graph._synth import EXAMPLE_SPEC, ROOT

CHECK_NAMES = ["no-dangling", "term-use", "verifier-rules", "cross-cutting", "refinement", "scaffold-paths", "seed-routes", "prose-ids"]


def test_registered_graph_checks_come_before_open_items() -> None:
    names = [spec.name for spec in CHECK_REGISTRY]
    start = names.index("no-dangling")
    assert names[start : start + len(CHECK_NAMES) + 1] == [*CHECK_NAMES, "open-items"]
    assert {spec.default_owner for spec in CHECK_REGISTRY if spec.name in CHECK_NAMES} == {"merge-check"}


def test_rules_are_registered_under_the_names_of_the_checks() -> None:
    assert [name for name, _ in GRAPH_CHECKS][: len(CHECK_NAMES)] == CHECK_NAMES


def test_a_rule_name_is_registered_once() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_graph_check("no-dangling", lambda ctx, mode: [])


def test_run_graph_checks_keeps_the_codes_of_only_and_refuses_an_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    context = GraphCheckContext.from_graph(build_graph(str(EXAMPLE_SPEC), str(ROOT)), None)
    node = context.graph.by_kind["component"][0]

    def probe(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
        return [ctx.finding(NODE_DANGLING, node, mode), ctx.finding(UNUSED_VERIFIER, node, mode)]

    monkeypatch.setattr(graph_checks, "GRAPH_CHECKS", [("probe", probe)])
    assert [error.code for error in run_graph_checks(context, "close")] == ["E740", "E742"]
    assert [error.code for error in run_graph_checks(context, "release", only={"E742"})] == ["E742"]
    with pytest.raises(ValueError, match="mode must be one of merge, close, release"):
        run_graph_checks(context, "close-gate")  # type: ignore[arg-type]


def test_gap_provider_registered_returns_role_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Findings of the role codes become gaps grouped by their owner step: an unused capability under step 14, not step 01.

    The real E740 rule is built by WI-M6b-02; this test drives the provider through a rule that reports one finding of each role code.
    """
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    capability, fixture = graph.by_kind["capability"][0], graph.by_kind["fixture"][0]

    def probe(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
        return [
            ctx.finding(NODE_DANGLING, capability, "unused"),
            ctx.finding(UNUSED_VERIFIER, fixture, "unused"),
            ctx.finding(MISSING_VERIFIER, capability, "missing"),
            ctx.finding("E741", capability, "not a role gap"),
        ]

    monkeypatch.setattr(graph_checks, "GRAPH_CHECKS", [("probe", probe)])
    assert role_gaps in gaps._providers
    found = [gap for gap in coverage_gaps(graph, Lock()) if gap.node in (capability.id, fixture.id)]
    assert found == [
        CoverageGap("E740", capability.id, "14"),
        CoverageGap("E742", fixture.id, "14"),
        CoverageGap("E743", capability.id, "08"),
    ]


def test_gap_provider_is_registered_once() -> None:
    assert gaps._providers.count(role_gaps) == 1


def test_gap_provider_leaves_out_a_finding_owned_by_a_gate_or_without_a_node(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    node = graph.by_kind["capability"][0]

    def probe(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
        gate_owned = ctx.finding(NODE_DANGLING, node, "m")
        return [SpecError("E740", "m", node_id=node.id, owner="close-gate"), SpecError("E740", "m", owner="step:14"), gate_owned]

    monkeypatch.setattr(graph_checks, "GRAPH_CHECKS", [("probe", probe)])
    assert role_gaps(graph, Lock()) == [CoverageGap("E740", node.id, "14")]
