"""Waiting-on classification: which open items explain which errors of a step (DOC 13.2)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from specdev_tools.core.ambiguity_items import AmbiguityItem
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.git_base import BaselineResult
from specdev_tools.core.step_order import load_step_order
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.validation.step_gate_run import _waiting_on
from specdev_tools.validation.step_gate import WaitingOn, classify_for_step, declared_owner, waiting_map

ROOT = Path(__file__).parents[3]
EXAMPLE_SPEC = ROOT / "tests" / "fixtures" / "graph_example" / "spec"
ORDER = {step: index for index, step in enumerate(load_step_order(str(ROOT))["steps"])}
SEED, CRITERION = "seed-accounts", "ac-password-reset-3"
BELOW_SEED, BELOW_CRITERION = "scope-password-reset", "fix-password-reset-expired-token"
RECORD = "ver-password-reset-expired-token"


@pytest.fixture(scope="module")
def graph() -> Graph:
    return build_graph(str(EXAMPLE_SPEC), str(ROOT))


def item(item_id: str, step: str, about: list[str]) -> AmbiguityItem:
    return AmbiguityItem(f"spec/{step}.json", step, ".ambiguities", {"id": item_id, "description": "?", "about": about}, "unified")


@pytest.fixture(scope="module")
def doc_items() -> list[AmbiguityItem]:
    """DOC 13.2: an item about the seed in step 05 and an item about a criterion in step 08."""
    return [item("amb-reset-seed", "05", [SEED]), item("amb-reset-criterion", "08", [CRITERION])]


@pytest.fixture(scope="module")
def criterion_item(doc_items: list[AmbiguityItem]) -> list[AmbiguityItem]:
    """Only the criterion item: the criterion is itself derived from the seed, so the seed item would cover it."""
    return doc_items[1:]


def error(owner: str, node_id: str | None, code: str = "E500") -> SpecError:
    return SpecError(code=code, message="m", owner=owner, node_id=node_id)


def waiting(graph: Graph, items: list[AmbiguityItem], **kwargs) -> WaitingOn:
    return WaitingOn.from_items(graph, items, **kwargs)


def gate(errors: list[SpecError], step: str, on: WaitingOn | None):
    return classify_for_step(errors, step, declared_owner, ORDER, BaselineResult("ok"), on)


def test_error_below_a_seed_about_node_is_waiting(graph: Graph, doc_items: list[AmbiguityItem]) -> None:
    found = error("step:05", BELOW_SEED)
    result = gate([found], "05", waiting(graph, doc_items))
    assert result.clear and result.waiting[0].error == found
    assert result.waiting[0].reasons == ("waiting on amb-reset-seed",)


def test_error_below_a_spec_node_about_is_waiting(graph: Graph, criterion_item: list[AmbiguityItem]) -> None:
    found = error("step:08", BELOW_CRITERION)
    result = gate([found], "08", waiting(graph, criterion_item))
    assert result.clear and result.waiting[0].reasons == ("waiting on amb-reset-criterion",)


def test_error_on_the_about_node_itself_is_blocking(graph: Graph, criterion_item: list[AmbiguityItem]) -> None:
    found = error("step:04", CRITERION)
    result = gate([found], "04", waiting(graph, criterion_item))
    assert result.blocking.own == (found,) and not result.waiting


def test_new_upstream_error_under_an_open_item_still_blocks(graph: Graph, doc_items: list[AmbiguityItem]) -> None:
    found = error("step:00", BELOW_SEED)
    result = gate([found], "05", waiting(graph, doc_items))
    assert result.blocking.new_upstream == (found,) and not result.waiting


def test_route_of_makes_the_e748_of_its_step_wait_on_an_open_item_about_the_seed(graph: Graph, doc_items: list[AmbiguityItem]) -> None:
    """The gate's own waiting context (``step_gate_run._waiting_on``) reads the route an E748 carries: step 05 waits, step 06 does not."""
    read = SimpleNamespace(error=None, items=doc_items)
    on = _waiting_on(SimpleNamespace(check_graph=graph, ambiguity_read=read))
    assert on is not None
    unused = make_error("E748", "m", node_id=SEED, owner="step:05", route=(SEED, "05"))
    assert on.reasons(unused, "05") == ("waiting on amb-reset-seed",)
    assert on.reasons(unused, "06") == ()
    assert gate([unused], "05", on).clear
    assert on.reasons(make_error("E748", "m", node_id=SEED, owner="step:05"), "05") == ()


def test_ambiguity_item_nodes_are_not_in_the_closure(graph: Graph, doc_items: list[AmbiguityItem]) -> None:
    closures = waiting_map(graph, doc_items)
    assert RECORD not in closures["amb-reset-criterion"] and RECORD not in closures["amb-reset-seed"]
    assert CRITERION not in closures["amb-reset-criterion"] and BELOW_CRITERION in closures["amb-reset-criterion"]


def test_waiting_is_off_in_merge_mode(graph: Graph, doc_items: list[AmbiguityItem]) -> None:
    on = waiting(graph, doc_items)
    found = error("step:05", BELOW_SEED)
    assert on.reasons(found, None) == ()
    assert gate([found], "05", None).blocking.own == (found,)


def test_an_item_that_is_not_open_or_names_no_node_explains_nothing(graph: Graph) -> None:
    resolved = AmbiguityItem("p.json", "16a", ".plan.ambiguities", {"id": "amb-old", "status": "resolved"}, "legacy")
    assert waiting_map(graph, [resolved, item("amb-lost", "05", ["no-such-node"])]) == {"amb-lost": frozenset()}
