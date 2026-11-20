"""The readiness gate of milestone M6c (WI-M6c-01): every replacement of a thing M6c retires exists and works.

Each test runs the replacement (a function called, or a command through ``specdev_tools.cli``) on a git copy of the
worked example ``tests/fixtures/graph_example``.  The retirement bundles start only when this file is green.  Names
are the ones that shipped (``WIP/1.2.0/impl/INTERFACE_CHANGES.md``), not the ones the plan used.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import run_spec_check, run_split, step_gate_host
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.validation import graph_checks
from specdev_tools.validation.graph_checks import design_milestones, scaffold
from specdev_tools.validation.graph_checks.built import walk_derivations
from specdev_tools.validation.graph_checks.codes import SEED_ROUTE_UNUSED
from specdev_tools.validation.spec_check import run_spec_check_json
from unit.graph._synth import ROOT, load_doc, write_json
from unit.trace._lock_support import run_on_example
from unit.validation.graph_checks._example_support import context_of_spec

COUNT_NAMES = ("fr_api_coverage", "fr_fixture_coverage", "capability_fr_coverage")
COUNT_KEYS = {"linked", "total", "ratio", "unlinked"}
SEED = "seed-accounts"


def _edit(host: Path, name: str, edit: Callable[[dict[str, Any]], None]) -> None:
    """Change the parsed spec file *name* of *host* with *edit* and write it back."""
    document = load_doc(host / "spec", name)
    edit(document)
    write_json(host / "spec", name, document)


def _findings(host: Path) -> list[dict[str, Any]]:
    """Every finding of every check of ``spec-check`` on the spec folder of *host*."""
    _errors, report = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host))
    return [finding for check in report["checks"].values() for finding in check.get("findings", [])]


@pytest.fixture
def host(tmp_path: Path) -> Path:
    """The worked example as a git repository, the trace lock accepting every link."""
    return step_gate_host(tmp_path / "host")


def test_coverage_prints_the_three_counts_and_the_exempt_ids(host: Path) -> None:
    """E-052: ``specdev coverage --json`` has the three link counts, and a parked node is listed by id under ``exempt``."""
    code, out = run_on_example(host, "coverage", "--json")
    assert code == 0, out
    counts = json.loads(out)["counts"]
    assert set(counts) >= set(COUNT_NAMES)
    for name in COUNT_NAMES:
        assert set(counts[name]) == COUNT_KEYS, name
    assert counts["fr_api_coverage"]["unlinked"] == ["fr-password-reset-request"]

    def park(document: dict[str, Any]) -> None:
        requirement = document["functional_requirements"][1]
        requirement.update(scope="later", scope_reason="after the first release")

    _edit(host, "04_fr_list.json", park)
    code, out = run_on_example(host, "coverage", "--json")
    assert code == 0, out
    parked = json.loads(out)
    assert "fr-password-reset-request" in {row["id"] for row in parked["exempt"]}
    assert parked["counts"]["fr_api_coverage"]["unlinked"] == []


def test_removing_a_derives_from_holder_breaks_the_link_with_the_holder_step_as_owner(host: Path) -> None:
    """E-035/E-036: the capability the requirements derive from goes; each requirement fails with E700 owned by step 04.

    "Holder" is read as the node that holds the link (the requirement): the broken link is reported against it and
    the finding is owned by the holder's step, not by the step of the removed node.
    """
    _edit(host, "01_capabilities.json", lambda document: document.update(capabilities=[]))
    broken = [f for f in _findings(host) if f["code"] == "E700" and f["node_id"].startswith("fr-")]
    assert {f["node_id"] for f in broken} == {"fr-password-reset", "fr-password-reset-request"}
    assert {f["owner"] for f in broken} == {"step:04"}
    assert all("cap-account-recovery" in f["message"] for f in broken)


def test_a_seed_route_used_by_no_node_errors(host: Path) -> None:
    """E-065: the seed is routed to steps 00 and 02; with no node of step 02 linking it, E748 names step 02."""
    def unlink(document: dict[str, Any]) -> None:
        for third_party in document["third_parties"]:
            third_party.pop("derives_from")

    assert [f for f in _findings(host) if f["code"] == SEED_ROUTE_UNUSED] == []
    _edit(host, "02_system_sketch.json", unlink)
    (unused,) = [f for f in _findings(host) if f["code"] == SEED_ROUTE_UNUSED]
    assert (unused["node_id"], unused["owner"]) == (SEED, "step:02")


def test_spec_check_accepts_step_14(host: Path) -> None:
    """E-068: ``spec-check --step 14`` runs the step gate (the header names the step); an unknown step is the E706 refusal."""
    _code, out = run_spec_check(host, "--step", "14")
    assert out.startswith("step gate: step 14"), out
    assert "E706" not in out
    _code, refused = run_spec_check(host, "--step", "99")
    assert "E706" in refused


def test_the_checklist_modules_import_under_the_named_names(host: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The hand-offs of M3 to M6b: every name the retirement bundles rely on exists, and each one runs on the example."""
    spec = str(host / "spec")
    assert run_graph_check(spec, str(ROOT)) == []
    graph = build_graph(spec, str(ROOT))
    ctx = context_of_spec(spec, git_root=host)
    (pair,) = design_milestones.matching_milestones(ctx)
    assert pair[0].id == "milestone-account-recovery"
    assert design_milestones.unrealised_design_milestones(ctx) == []
    assert callable(graph_checks.register_graph_check)
    assert isinstance(graph_checks.run_graph_checks(ctx, "merge"), list)
    capability = next(node for node in graph.nodes if node.id == "cap-account-recovery")
    reached = {node.id for node in walk_derivations(ctx, capability, ["derives_from"])}
    assert {"fr-password-reset", "fr-password-reset-request"} <= reached
    assert hasattr(scaffold, "scaffold_scan")
    for command in (("stale",), ("coverage", "--by", "fr", "--json"), ("attest", "--step", "14", "--dry-run")):
        code, _out, err = run_split(
            capsys, *command, "--repo-root", str(ROOT), "--spec-root", spec, "--git-root", str(host)
        )
        assert code in (0, 1), (command, err)
        assert "invalid choice" not in err, command
