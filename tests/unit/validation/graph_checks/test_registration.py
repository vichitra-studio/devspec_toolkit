"""How the graph checks are registered: the ``spec-check`` entries, the rule list and the replay gap provider (WI-M6b-01)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.trace import gaps
from specdev_tools.trace.gaps import CoverageGap, coverage_gaps
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation import graph_checks
from specdev_tools.validation.check_registry import CHECK_REGISTRY
from specdev_tools.validation.graph_checks import (
    BUILTIN_GRAPH_CHECKS,
    GRAPH_CHECKS,
    install_gap_provider,
    register_graph_check,
    role_gaps,
    run_graph_checks,
    unregister_graph_check,
)
from specdev_tools.validation.graph_checks.codes import MISSING_VERIFIER, NODE_DANGLING, UNUSED_VERIFIER
from specdev_tools.validation.graph_checks.context import GraphCheckContext, Mode
from specdev_tools.validation.spec_check import run_spec_check_json  # noqa: F401  (importing it fills CHECK_REGISTRY)
from unit.graph._synth import EXAMPLE_SPEC, ROOT
from unit.trace._lock_support import gap_providers, git_copy_of_example  # noqa: F401  (gap_providers is a fixture)

CHECK_NAMES = [name for name, _rule, _check in BUILTIN_GRAPH_CHECKS]


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
    assert [name for name, _ in GRAPH_CHECKS].count("no-dangling") == 1 and [spec.name for spec in CHECK_REGISTRY].count("no-dangling") == 1


def test_a_rule_that_is_not_registered_cannot_be_removed() -> None:
    with pytest.raises(ValueError, match="is not registered"):
        unregister_graph_check("never-registered")


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


def test_gap_provider_returns_role_findings(monkeypatch: pytest.MonkeyPatch, gap_providers: object) -> None:
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
    gap_providers(role_gaps)  # type: ignore[operator]
    found = [gap for gap in coverage_gaps(graph, Lock()) if gap.node in (capability.id, fixture.id)]
    assert found == [
        CoverageGap("E740", capability.id, "14"),
        CoverageGap("E742", fixture.id, "14"),
        CoverageGap("E743", capability.id, "08"),
    ]


def test_the_gap_provider_is_installed_by_a_call_once(gap_providers: object) -> None:
    assert gaps._providers == []
    install_gap_provider()
    install_gap_provider()
    assert gaps._providers == [role_gaps]


def test_a_probe_registered_with_register_graph_check_runs_in_spec_check_and_under_the_step_gate(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    """One registration: the rule is run by ``run_graph_checks``, by plain ``spec-check`` (in its place, before ``open-items``) and by ``--step``; removed again, it is in none."""
    from integration._step_gate_support import run_split

    host = git_copy_of_example(tmp_path / "host")
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]

    def probe(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
        return [ctx.finding(NODE_DANGLING, ctx.graph.by_kind["capability"][0], mode)]

    register_graph_check("probe-check", probe)
    try:
        assert [name for name, _ in GRAPH_CHECKS][-1] == "probe-check"
        assert [spec.name for spec in CHECK_REGISTRY][-1] == "probe-check"
        _code, plain, _err = run_split(capsys, "spec-check", str(host / "spec"), *flags, "--json")
        _code, gated, _err = run_split(capsys, "spec-check", str(host / "spec"), *flags, "--step", "14", "--json")
    finally:
        unregister_graph_check("probe-check")
    assert json.loads(plain)["checks"]["probe-check"]["status"] == "FAIL"
    gate = json.loads(gated)["step_gate"]
    findings = [*gate["blocking"], *(found for pending in gate["pending"].values() for found in pending)]
    assert [found["message"] for found in findings if found["message"] == "merge"] == ["merge"]
    assert "probe-check" not in [spec.name for spec in CHECK_REGISTRY] and "probe-check" not in [name for name, _ in GRAPH_CHECKS]


def test_gap_provider_leaves_out_a_finding_owned_by_a_gate_or_without_a_node(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    node = graph.by_kind["capability"][0]

    def probe(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
        gate_owned = ctx.finding(NODE_DANGLING, node, "m")
        return [SpecError("E740", "m", node_id=node.id, owner="close-gate"), SpecError("E740", "m", owner="step:14"), gate_owned]

    monkeypatch.setattr(graph_checks, "GRAPH_CHECKS", [("probe", probe)])
    assert role_gaps(graph, Lock()) == [CoverageGap("E740", node.id, "14")]


def test_the_rules_run_in_a_process_that_imports_only_the_package() -> None:
    """The table holds the eight rules from the import on and ``run_graph_checks`` imports nothing: ``validation.spec_check`` is never loaded."""
    code = (
        "import sys\n"
        "from specdev_tools.graph.build import build_graph\n"
        "from specdev_tools.validation.graph_checks import GraphCheckContext, run_graph_checks\n"
        f"graph = build_graph({str(EXAMPLE_SPEC)!r}, {str(ROOT)!r})\n"
        f"found = run_graph_checks(GraphCheckContext.from_graph(graph, None, {str(ROOT)!r}), 'merge')\n"
        "print(len(found), 'specdev_tools.validation.spec_check' in sys.modules)\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT / "tools")}, check=True)
    assert done.stdout.split() == ["23", "False"]
