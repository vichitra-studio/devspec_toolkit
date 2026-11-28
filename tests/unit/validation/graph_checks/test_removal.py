"""``links_clause``: the count of nodes that link a node and the command that lists them, the clause of the advice "remove it" (E742, E747, E748)."""
from __future__ import annotations

import json
import re
from dataclasses import replace

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import SpecShape
from specdev_tools.validation.graph_checks.removal import links_clause
from unit.graph._synth import EXAMPLE_SPEC, ROOT, run_cli

from ._built_support import STEP_RANKS, declared, graph_of, node

_DECLS = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls


def _clause(target: str, *nodes) -> str:
    graph = graph_of([node(target, "fixture"), node("fix-2", "fixture"), *(declared(item, _DECLS) for item in nodes)], decls=_DECLS, shape=SpecShape(step_ranks=STEP_RANKS))
    return links_clause(graph, target)


def test_nothing_linking_the_node_gives_no_clause() -> None:
    assert _clause("fix-1") == ""


def test_the_clause_is_the_count_of_nodes_and_the_command_that_lists_them() -> None:
    clause = _clause(
        "fix-1", node("threat-1", "threat", step="11", mitigated_by=["fix-1"]), node("ec-1", "edge-case", step="11", mitigated_by=["fix-1", "fix-2"]),
        node("job-1", "job", step="10", depends_on=["fix-1"]),
    )
    assert clause == "(3 nodes: specdev trace fix-1 --down --depth 1 lists them)"


def test_one_node_reads_in_the_singular() -> None:
    assert _clause("fix-1", node("threat-1", "threat", step="11", mitigated_by=["fix-1"])) == "(1 node: specdev trace fix-1 --down --depth 1 lists it)"


def test_a_node_in_no_step_is_counted() -> None:
    """A record belongs to no step; it is a node that links the fixture all the same (the count has no step list to leave it out of)."""
    stepless = replace(node("rec-1", "threat", mitigated_by=["fix-1"]), step=None)
    assert _clause("fix-1", stepless) == "(1 node: specdev trace fix-1 --down --depth 1 lists it)"


def test_a_link_written_with_a_retired_name_counts_and_the_same_node_twice_is_one_node() -> None:
    renamed = replace(node("fix-1", "fixture"), aliases=("fix-old",))
    graph = graph_of(
        [renamed, declared(node("ec-1", "edge-case", step="11", mitigated_by=["fix-old", "fix-1"]), _DECLS)], decls=_DECLS, shape=SpecShape(step_ranks=STEP_RANKS),
    )
    assert links_clause(graph, "fix-1") == "(1 node: specdev trace fix-1 --down --depth 1 lists it)"


_FLAGS = ("--repo-root", str(ROOT), "--spec-root", str(EXAMPLE_SPEC), "--git-root", str(ROOT))


def _listed_by_the_command(clause: str) -> int:
    """Run the command the clause names and give the number of nodes and records its ``down`` side lists."""
    command = re.search(r"specdev (trace \S+ --down --depth 1) lists", clause)
    assert command is not None, clause
    code, out = run_cli(*command.group(1).split(), *_FLAGS, "--json")
    assert code == 0, out
    return json.loads(out)["down"]["count"]


@pytest.mark.parametrize(
    "target, count",
    [
        ("seed-accounts", 11),  # a seed: nodes of steps 00 and 02
        ("fix-password-reset-expired-token", 4),  # a fixture: a threat, an edge case, a criterion's verified_by and a verification record (a node in no step)
        ("fix-password-reset-reused-token", 1),
    ],
)
def test_the_count_is_what_the_trace_command_lists(target: str, count: int) -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    clause = links_clause(graph, target)
    assert clause.startswith(f"({count} node") and _listed_by_the_command(clause) == count


def test_a_node_nothing_links_has_no_clause_and_the_command_lists_none() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    assert links_clause(graph, "job-contract-tests") == ""
    code, out = run_cli("trace", "job-contract-tests", "--down", "--depth", "1", *_FLAGS, "--json")
    assert code == 0 and json.loads(out)["down"]["count"] == 0
