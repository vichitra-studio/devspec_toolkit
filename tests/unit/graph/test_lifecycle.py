"""Tests for node lifecycle (WI-M4-06): the gate every graph consumer reads, and ``set_lifecycle`` with its refusals."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.lifecycle import LifecycleRefusedError, plan_lifecycle_change, set_lifecycle
from specdev_tools.graph.model import LIFECYCLES, NOT_APPLICABLE, Graph
from specdev_tools.graph.queries import candidates
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.graph.trace import trace_node

from ._synth import EXAMPLE_SPEC, ROOT, load_doc, make_toolkit, write_json

LIFECYCLE_SPEC = Path(__file__).parents[2] / "fixtures" / "graph" / "synthetic" / "lifecycle"
_FR = "04_fr_list.json"
_PROBE = "fr-probe"

# Each consumer of the graph, as the ids of the nodes it reads or reports on; later work items add their rows.
CONSUMERS: dict[str, Callable[[Graph], set[str]]] = {
    "resolver": lambda graph: {error.node_id for error in resolve_graph(graph) if error.node_id},
    "trace": lambda graph: {node.id for node in trace_node(graph, "ac-probe-1", ("up",)).reached},
    "candidates": lambda graph: {item.id for item in candidates(graph, "derives_from", kind="api").candidates},
}


@pytest.fixture
def toolkit(tmp_path: Path) -> Path:
    return make_toolkit(tmp_path / "tk")


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    dest = tmp_path / "spec"
    shutil.copytree(LIFECYCLE_SPEC, dest)
    return dest


def _graph(spec: Path, toolkit: Path) -> Graph:
    return build_graph(str(spec), str(toolkit))


def _with_probe_lifecycle(spec: Path, lifecycle: str) -> None:
    document = load_doc(spec, _FR)
    probe = next(item for item in document["functional_requirements"] if item["fr_id"] == _PROBE)
    probe["lifecycle"] = lifecycle
    write_json(spec, _FR, document)


def _probe_item(spec: Path) -> dict[str, Any]:
    return next(item for item in load_doc(spec, _FR)["functional_requirements"] if item["fr_id"] == _PROBE)


def test_record_lifecycle_constant_active(spec: Path, toolkit: Path) -> None:
    graph = _graph(EXAMPLE_SPEC, ROOT)
    records = [node for node in graph.nodes if node.role == "record"]
    assert records
    assert {node.lifecycle for node in records} == {"active"}

    stray = {"lifecycle": "not_applicable"}
    document = load_doc(spec, _FR)
    document["ambiguities"][0].update(stray)
    manifest = load_doc(spec, "common/seed_manifest.json")
    manifest["seeds"][0].update(stray)
    overrides = {_FR: document, "common/seed_manifest.json": manifest}
    graph = build_graph(str(spec), str(toolkit), overrides=overrides)
    gated = {node.id for node in graph.gated_nodes()}
    for node_id in ("amb-open", "seed-accounts"):
        assert graph.by_id[node_id].lifecycle == "active"
        assert node_id in gated


@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_gated_nodes_skips_only_not_applicable(spec: Path, toolkit: Path, lifecycle: str) -> None:
    _with_probe_lifecycle(spec, lifecycle)
    graph = _graph(spec, toolkit)
    assert (_PROBE in {node.id for node in graph.gated_nodes()}) is (lifecycle != NOT_APPLICABLE)
    assert _PROBE in {node.id for node in graph.live_nodes()}


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_every_consumer_honours_lifecycle(spec: Path, toolkit: Path, consumer: str, lifecycle: str) -> None:
    _with_probe_lifecycle(spec, lifecycle)
    seen = CONSUMERS[consumer](_graph(spec, toolkit))
    assert (_PROBE in seen) is (lifecycle != NOT_APPLICABLE)


@pytest.mark.parametrize("node_id", ["amb-open", "rec-note", "seed-accounts"], ids=["ambiguity", "record", "seed"])
def test_node_status_refused_on_record_and_seed_e705(spec: Path, toolkit: Path, node_id: str) -> None:
    graph = _graph(spec, toolkit)
    before = {path: path.read_bytes() for path in spec.rglob("*.json")}
    with pytest.raises(LifecycleRefusedError) as raised:
        set_lifecycle(graph, str(spec), str(toolkit), node_id, "deprecated")
    assert raised.value.error.code == "E705"
    assert {path: path.read_bytes() for path in spec.rglob("*.json")} == before


@pytest.mark.parametrize(
    ("node_id", "value"), [("fr-no-such", "deprecated"), (_PROBE, "retired")], ids=["unknown-id", "value-outside-enum"]
)
def test_status_refused_for_unknown_id_and_bad_value(spec: Path, toolkit: Path, node_id: str, value: str) -> None:
    with pytest.raises(LifecycleRefusedError) as raised:
        plan_lifecycle_change(_graph(spec, toolkit), node_id, value)
    assert raised.value.error.code == "E705"


def test_status_refused_on_duplicate_id(spec: Path, toolkit: Path) -> None:
    graph = _graph(spec, toolkit)
    with pytest.raises(LifecycleRefusedError) as raised:
        plan_lifecycle_change(graph, "fr-twin", "deprecated")
    assert raised.value.error.code == "E705"
    assert "E704" in raised.value.error.message


def test_node_status_roundtrip(spec: Path, toolkit: Path) -> None:
    original = load_doc(spec, _FR)
    deprecated = set_lifecycle(_graph(spec, toolkit), str(spec), str(toolkit), _PROBE, "deprecated")
    assert (deprecated.old, deprecated.new, deprecated.file) == ("active", "deprecated", _FR)
    assert _probe_item(spec)["lifecycle"] == "deprecated"
    assert _graph(spec, toolkit).by_id[_PROBE].lifecycle == "deprecated"

    active = set_lifecycle(_graph(spec, toolkit), str(spec), str(toolkit), _PROBE, "active")
    assert (active.old, active.new) == ("deprecated", "active")
    assert "lifecycle" not in _probe_item(spec)
    assert load_doc(spec, _FR) == original


@pytest.mark.parametrize(
    ("node_id", "file"),
    [(_PROBE, _FR), ("ac-probe-1", _FR), ("LOGIN_ITEM_01", "impl_context/ms_login_plan.json")],
    ids=["top-level", "nested", "plan-item"],
)
def test_not_applicable_accepted_for_any_node(spec: Path, toolkit: Path, node_id: str, file: str) -> None:
    change = set_lifecycle(_graph(spec, toolkit), str(spec), str(toolkit), node_id, "not_applicable")
    assert (change.new, change.file) == ("not_applicable", file)
    document = json.dumps(load_doc(spec, file))
    assert '"lifecycle": "not_applicable"' in document
    assert _graph(spec, toolkit).by_id[node_id].lifecycle == "not_applicable"
