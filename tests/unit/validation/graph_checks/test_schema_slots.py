"""``SchemaSlots``: what the schema of a node's file says about the node and its leaves (the prose check's fixed values, the no-dangling advice's ``scope`` field)."""
from __future__ import annotations

from typing import Any

import pytest

from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.graph._synth import EXAMPLE_SPEC, ROOT

from ._example_support import context_of_spec
from ._built_support import graph_of
from ._built_support import node as make_node

SKETCH = "02_system_sketch.json"


@pytest.fixture(scope="module")
def example() -> GraphCheckContext:
    return context_of_spec(EXAMPLE_SPEC)


@pytest.mark.parametrize("leaf", [".protocol", ".trust_boundary", ".auth", ".rate_limit.scope"])
def test_the_leaves_of_a_connection_resolve_although_a_conditional_branch_restates_the_array(example: GraphCheckContext, leaf: str) -> None:
    """Step 02 restates ``connections`` in a ``then`` branch with no ``items``; the declaration that has them is not lost."""
    connection = example.graph.by_id["conn-identity-to-mailrelay"]
    slot = example.slots.slot(example.graph, connection, leaf)
    assert slot is not None and ("enum" in slot or "type" in slot)
    assert "enum" in example.slots.slot(example.graph, connection, ".protocol")  # type: ignore[operator]


def test_a_leaf_the_schema_does_not_describe_has_no_slot(example: GraphCheckContext) -> None:
    fixture = example.graph.by_id["fix-password-reset-expired-token"]
    assert example.slots.slot(example.graph, fixture, ".input.method") is None


def _slots_over(raw: dict[str, Any], jq_path: str = ".item") -> tuple[Any, Any, Any]:
    """Slots whose one file ``x.json`` has the schema *raw* (no toolkit schema is read)."""
    node = make_node("n-1", "fr", file="x.json", jq_path=jq_path)
    graph = graph_of([node], {"x.json": {}})
    slots = GraphCheckContext.from_graph(graph, None).slots
    slots._files["x.json"] = (raw, lambda _node: None)
    return graph, node, slots


def test_a_property_declared_only_in_a_conditional_branch_of_the_item_counts() -> None:
    raw = {"type": "object", "properties": {"item": {"type": "object", "properties": {"a": {}}, "if": {"properties": {"a": {"const": 1}}}, "then": {"properties": {"scope": {"type": "string"}}}}}}
    graph, node, slots = _slots_over(raw)
    assert slots.has_property(graph, node, "scope") and slots.has_property(graph, node, "a") and not slots.has_property(graph, node, "other")


def test_the_schema_of_a_file_is_loaded_once(example: GraphCheckContext, monkeypatch: pytest.MonkeyPatch) -> None:
    slots = type(example.slots)(str(ROOT))
    calls: list[object] = []
    original = slots._resolver.load_raw_schema
    monkeypatch.setattr(slots._resolver, "load_raw_schema", lambda document: calls.append(document) or original(document))
    for node_id in ("conn-identity-to-mailrelay", "tp-argon2", "tp-mailrelay"):
        slots.slot(example.graph, example.graph.by_id[node_id])
    assert len(calls) == 1
