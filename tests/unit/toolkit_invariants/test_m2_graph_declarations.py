"""M2 graph declarations: every ``x-node`` / ``x-link`` the step 00-05 schemas carry.

Tests are parametrised over the M2 schema files that carry ``x-node`` today, so a schema
added to the graph is covered by adding its kinds to ``_EXPECTED_KINDS``, not by copying tests.
Letters (a)-(i) are those of section 7 of the M2 plan.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.registry import get_shared_registry
from specdev_tools.registry.annotations import (
    LinkDecl,
    NodeDecl,
    SchemaReader,
    SchemaRefs,
    collect_annotations,
    lint_annotations,
)
from specdev_tools.registry.step_order_gen import derive_step_order

_ROOT = Path(__file__).parents[3]
_SCHEMA_DIR = _ROOT / "schema"
_GRAPH = "vc:core:graph"
_M2_STEPS = frozenset({"00", "01", "02", "02a", "03", "04", "05"})
_OBLIGATION_ROLES = frozenset({"obligation-system", "obligation-delivery"})
_EXCLUDED_FROM_CONTRACT = frozenset({"status", "notes", "tags", "owner", "lifecycle", "aliases", "replaces"})

# PD-1: kind -> id field (None for the map-keyed environment), by step.
_EXPECTED_KINDS: dict[str, dict[str, str | None]] = {
    "00": {
        "scope-item": "scope_id", "risk": "risk_id", "constraint": "constraint_id",
        "assumption": "assumption_id", "stakeholder": "stakeholder_id", "need": "need_id",
        "segment": "segment_id", "metric": "metric_id",
    },
    "01": {"capability": "capability_id"},
    "02": {"component": "component_id", "connection": "connection_id", "third-party": "third_party_id"},
    "02a": {"environment": None, "gate": "gate_id", "secret": "secret_id"},
    "03": {"term": "term_id"},
    "04": {"fr": "fr_id", "criterion": "criterion_id"},
    "05": {"api": "api_id", "api-error": "error_id"},
}
_ROLE_TABLE = json.loads((_ROOT / "tests" / "fixtures" / "graph" / "kind_role_table.json").read_text())["kinds"]


def _step_of(schema_file: str) -> str:
    match = re.match(r"(\d{2}[a-z]?)_", Path(schema_file).name)
    assert match, schema_file
    return match.group(1)


def _m2_schema_files() -> list[str]:
    return sorted(
        p.name
        for p in _SCHEMA_DIR.glob("[0-9][0-9]*_*.schema.json")
        if _step_of(p.name) in _M2_STEPS and "x-node" in p.read_text()
    )


_FILES = _m2_schema_files()


@pytest.fixture(scope="module")
def decls():
    return collect_annotations(str(_ROOT))


@pytest.fixture(scope="module")
def reader() -> SchemaReader:
    return SchemaReader(SchemaRefs(get_shared_registry(str(_ROOT))))


def _nodes(decls, fname: str) -> list[NodeDecl]:
    return [n for n in decls.nodes if Path(n.schema_file).name == fname]


def _links(decls, fname: str) -> list[LinkDecl]:
    return [lk for lk in decls.links if Path(lk.schema_file).name == fname]


def _item(reader: SchemaReader, node: NodeDecl) -> tuple[Any, str]:
    """The item schema of a declared node (the ``items`` of an array, the map value otherwise)."""
    items, uri = reader.get(node.container, node.uri, "items")
    if items is None:
        items, uri = reader.get(node.container, node.uri, "additionalProperties")
    return items, uri


def _props(reader: SchemaReader, node: NodeDecl) -> dict[str, Any]:
    item, uri = _item(reader, node)
    return reader.properties(item, uri)


def _link_fields(reader: SchemaReader, props: dict[str, Any]) -> set[str]:
    return {name for name, (sub, uri) in props.items() if reader.get(sub, uri, "x-link")[0] is not None}


def _node_arrays(reader: SchemaReader, props: dict[str, Any]) -> set[str]:
    return {name for name, (sub, uri) in props.items() if reader.get(sub, uri, "x-node")[0] is not None}


def _all_declared_kinds(decls) -> set[str]:
    return {n.kind for n in decls.nodes}


def test_m2_schema_files_are_found() -> None:
    assert {"00_charter.schema.json", "01_capabilities.schema.json", "02_system_sketch.schema.json"} <= set(_FILES)


@pytest.mark.parametrize("fname", _FILES)
def test_every_kind_declares_id_role_and_contract(decls, fname: str) -> None:
    declared = {n.kind: n.value for n in _nodes(decls, fname)}
    assert set(declared) == set(_EXPECTED_KINDS[_step_of(fname)])
    for kind, value in declared.items():
        expected_id = _EXPECTED_KINDS[_step_of(fname)][kind]
        if expected_id is None:
            assert value.get("map_keyed") is True and "id" not in value, kind
        else:
            assert value.get("id") == expected_id, kind
        assert value.get("role"), kind
        assert value.get("contract"), kind


@pytest.mark.parametrize("fname", _FILES)
def test_obligation_kinds_carry_scope_and_reason_rule(decls, reader: SchemaReader, fname: str) -> None:
    for node in _nodes(decls, fname):
        if node.value.get("role") not in _OBLIGATION_ROLES:
            continue
        item, uri = _item(reader, node)
        props = reader.properties(item, uri)
        assert props["scope"][0]["$ref"] == f"{_GRAPH}#scope", node.kind
        assert props["scope_reason"][0]["$ref"] == f"{_GRAPH}#scopeReason", node.kind
        assert f"{_GRAPH}#scopeReasonRule" in reader.all_of_refs(item, uri), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_every_link_kind_is_declared_or_seed(decls, fname: str) -> None:
    known = _all_declared_kinds(decls) | {"seed"}
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        if kinds == "*":
            continue
        assert set(kinds) <= known, (link.field_name, kinds)


@pytest.mark.parametrize("fname", _FILES)
def test_no_forward_links_in_steps_00_05(decls, fname: str) -> None:
    kind_step = {n.kind: _step_of(n.schema_file) for n in decls.nodes if n.kind != "seed"}
    holder_step = _step_of(fname)
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        same_step = set(link.value.get("same_step_kinds", []))
        for kind in [] if kinds == "*" else kinds:
            if kind == "seed":
                continue
            assert kind_step[kind] <= holder_step, (link.field_name, kind)
            assert (kind_step[kind] != holder_step) or kind in same_step, (link.field_name, kind)


def test_annotation_lints_and_step_order_are_clean_on_m2_schemas(decls) -> None:
    assert lint_annotations(decls) == []
    assert _M2_STEPS & set(derive_step_order(str(_ROOT))["steps"])


@pytest.mark.parametrize("fname", _FILES)
def test_roles_match_kind_role_table(decls, fname: str) -> None:
    for node in _nodes(decls, fname):
        row = _ROLE_TABLE[node.kind]
        assert node.value["role"] == row["role"], node.kind
        assert node.value.get("coarse", False) == row.get("coarse", False), node.kind
        assert _step_of(fname) == row["step"], node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_contract_equals_computed_content_set(decls, reader: SchemaReader, fname: str) -> None:
    for node in _nodes(decls, fname):
        props = _props(reader, node)
        contract = node.value["contract"]
        id_field = node.value.get("id")
        links = _link_fields(reader, props)
        assert set(contract) <= set(props), node.kind
        assert id_field not in contract and not set(contract) & links, node.kind
        computed = set(props) - {id_field} - links - _node_arrays(reader, props) - _EXCLUDED_FROM_CONTRACT
        assert set(contract) == computed, node.kind
        assert len(contract) == len(set(contract)), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_built_true_only_on_derives_from(decls, fname: str) -> None:
    for link in _links(decls, fname):
        assert link.value.get("built", False) is (link.field_name == "derives_from"), link.field_name


@pytest.mark.parametrize("fname", _FILES)
def test_required_links_have_min_items_one(decls, reader: SchemaReader, fname: str) -> None:
    for link in _links(decls, fname):
        min_items, _ = reader.get(link.container, link.uri, "minItems")
        if link.value["required"]:
            assert min_items is not None and min_items >= 1, (link.field_name, link.path)
        else:
            assert not min_items, (link.field_name, link.path)


@pytest.mark.parametrize("fname", _FILES)
def test_replaces_optional_with_node_id_items_and_aliases_without_x_link(
    decls, reader: SchemaReader, fname: str
) -> None:
    for node in _nodes(decls, fname):
        if node.value.get("role") == "record":
            continue
        item, uri = _item(reader, node)
        props = reader.properties(item, uri)
        required = reader.get(item, uri, "required")[0] or []
        replaces, aliases = props["replaces"][0], props["aliases"][0]
        assert "replaces" not in required, node.kind
        assert replaces["x-link"]["kinds"] == "*" and replaces["x-link"]["required"] is False, node.kind
        assert replaces["items"]["$ref"] == f"{_GRAPH}#nodeId", node.kind
        assert "x-link" not in aliases, node.kind
        assert aliases["items"]["$ref"] == "vc:core:atoms#kebabId", node.kind
