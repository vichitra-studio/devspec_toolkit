"""``task_of``: the roadmap task that holds a task criterion."""
from __future__ import annotations

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.queries import task_of

from ._synth import EXAMPLE_SPEC, ROOT


@pytest.fixture(scope="module")
def graph():
    return build_graph(str(EXAMPLE_SPEC), str(ROOT))


def test_task_of_a_criterion_is_its_task(graph) -> None:
    task = task_of(graph, "tc-confirm-expired-token")
    assert task is not None and task.id == "task-implement-password-reset-confirm"


@pytest.mark.parametrize("node_id", ["task-implement-password-reset-confirm", "ac-password-reset-3", "tc-no-such-criterion"])
def test_task_of_anything_but_a_criterion_is_none(graph, node_id: str) -> None:
    assert task_of(graph, node_id) is None
