"""``node status ... not_applicable``: accepted for a closed milestone's step-14 nodes, refused for every other node."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.lifecycle import LifecycleRefusedError, set_lifecycle
from unit.lifecycle._support import MILESTONE, closed_record, edit_row, example_spec, toolkit_root

TASK = "task-implement-password-reset-confirm"
CRITERION = "tc-confirm-expired-token"
ITEM = "PWRESET_CONFIRM_EXPIRED_01"


def _status(spec: Path, node: str) -> None:
    set_lifecycle(build_graph(str(spec), toolkit_root()), str(spec), toolkit_root(), node, "not_applicable")


def _close(spec: Path) -> None:
    def edit(row: dict) -> None:
        row.update(status="done", close=closed_record())

    edit_row(spec, edit)


@pytest.mark.parametrize("node", [MILESTONE, TASK, CRITERION])
def test_a_historical_step_14_node_of_a_closed_milestone_takes_not_applicable(tmp_path: Path, node: str) -> None:
    spec = example_spec(tmp_path)
    _close(spec)
    _status(spec, node)
    assert build_graph(str(spec), toolkit_root()).by_id[node].lifecycle == "not_applicable"


@pytest.mark.parametrize("node", [MILESTONE, TASK, CRITERION])
def test_the_step_14_nodes_of_an_open_milestone_refuse_it(tmp_path: Path, node: str) -> None:
    spec = example_spec(tmp_path)
    with pytest.raises(LifecycleRefusedError) as raised:
        _status(spec, node)
    assert raised.value.error.code == "E705"


@pytest.mark.parametrize("node", ["cap-account-recovery", "fr-password-reset", ITEM])
def test_other_nodes_refuse_it_even_when_the_milestone_is_closed(tmp_path: Path, node: str) -> None:
    spec = example_spec(tmp_path)
    _close(spec)
    with pytest.raises(LifecycleRefusedError) as raised:
        _status(spec, node)
    assert raised.value.error.code == "E705" and "deprecated" in raised.value.error.message
    assert build_graph(str(spec), toolkit_root()).by_id[node].lifecycle == "active"
