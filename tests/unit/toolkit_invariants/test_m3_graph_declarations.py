"""M3 graph declarations: every ``x-node`` / ``x-link`` the step 06-16 schemas carry.

The model is ``test_m2_graph_declarations.py`` for steps 00-05; the helpers and fixtures are imported from it.
Tests are parametrised over the M3 schema files that carry ``x-node`` today. A step item adds its schema to the
tables below (``_EXPECTED_KINDS``, ``_EXPECTED_LINK_KINDS``) and one ``test_step_NN_...`` test with its link
fields; the generic tests then cover it with no further edit.
"""
from __future__ import annotations

from typing import Any

import pytest

from specdev_tools.registry.annotations import LinkDecl, lint_annotations

from .test_m2_graph_declarations import (  # noqa: F401  (decls and reader are pytest fixtures)
    _EXCLUDED_FROM_CONTRACT,
    _GRAPH,
    _OBLIGATION_ROLES,
    _ROLE_TABLE,
    _SCHEMA_DIR,
    _is_step_schema,
    _item,
    _link_fields,
    _links,
    _node_arrays,
    _nodes,
    _props,
    _step_of,
    declared_link_kinds,
    decls,
    reader,
)

_M3_STEPS = frozenset({"06", "07", "08", "09", "10", "11", "12", "14", "15", "16"})

# Kind -> id field, by step (PD-1 of the M3 plan).
_EXPECTED_KINDS: dict[str, dict[str, str]] = {
    "06": {"invariant": "inv_id"},
    "07": {"nfr": "nfr_id"},
    "08": {"fixture": "fixture_id"},
}

# Every ``x-link`` of the M3 schemas: (schema file, JSON pointer of the link field, sorted ``kinds`` or "*").
# Written out by hand on purpose: a change of one link's ``kinds`` list must be a deliberate change of this table.
_EXPECTED_LINK_KINDS: list[tuple[str, str, Any]] = [
    ("06_invariants.schema.json", "/allOf/1/properties/rules/items/properties/constrains", ["api", "component", "connection", "fr"]),
    ("06_invariants.schema.json", "/allOf/1/properties/rules/items/properties/assumes", ["assumption"]),
    ("06_invariants.schema.json", "/allOf/1/properties/rules/items/properties/replaces", "*"),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/constrains", ["api", "component", "connection", "fr"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/relies_on", ["third-party"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/derives_from", ["metric"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/assumes", ["assumption"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/replaces", "*"),
    ("08_fixtures.schema.json", "/properties/fixtures/items/properties/verifies", ["api", "criterion", "invariant", "nfr"]),
    ("08_fixtures.schema.json", "/properties/fixtures/items/properties/removes", "*"),
    ("08_fixtures.schema.json", "/properties/fixtures/items/properties/replaces", "*"),
]


def _m3_schema_files() -> list[str]:
    return sorted(
        p.name
        for p in _SCHEMA_DIR.glob("[0-9][0-9]*_*.schema.json")
        if _step_of(p.name) in _M3_STEPS and "x-node" in p.read_text()
    )


_FILES = _m3_schema_files()


def _link(decls_, fname: str, field: str) -> LinkDecl:
    """The one link declared under the field name *field* in schema *fname* (links named *field* in one node only)."""
    found = [lk for lk in _links(decls_, fname) if lk.field_name == field]
    assert len(found) == 1, (fname, field, found)
    return found[0]


def _assert_links(decls_, fname: str, expected: dict[str, tuple[Any, bool]]) -> None:
    """Assert the link fields of *fname* are exactly *expected*: ``{field: (kinds, required)}``."""
    actual = {lk.field_name: (lk.value["kinds"], lk.value["required"]) for lk in _links(decls_, fname)}
    normalised = {k: (v if v == "*" else sorted(v), r) for k, (v, r) in actual.items()}
    assert normalised == expected


def test_m3_schema_files_are_found() -> None:
    assert set(_FILES) == {"06_invariants.schema.json", "07_nfrs.schema.json", "08_fixtures.schema.json"}


@pytest.mark.parametrize("fname", _FILES)
def test_every_kind_declares_id_role_and_contract(decls, fname: str) -> None:
    declared = {n.kind: n.value for n in _nodes(decls, fname)}
    assert set(declared) == set(_EXPECTED_KINDS[_step_of(fname)])
    for kind, value in declared.items():
        assert value.get("id") == _EXPECTED_KINDS[_step_of(fname)][kind], kind
        assert value.get("role"), kind
        assert value.get("contract"), kind


@pytest.mark.parametrize("fname", _FILES)
def test_roles_match_kind_role_table(decls, fname: str) -> None:
    for node in _nodes(decls, fname):
        row = _ROLE_TABLE[node.kind]
        assert node.value["role"] == row["role"], node.kind
        assert node.value.get("coarse", False) == row.get("coarse", False), node.kind
        assert _step_of(fname) == row["step"], node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_obligation_kinds_carry_scope_with_default_and_reason_rule(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        if node.value["role"] not in _OBLIGATION_ROLES:
            continue
        item, uri = _item(reader, node)
        props = reader.properties(item, uri)
        assert props["scope"][0]["$ref"] == f"{_GRAPH}#scope", node.kind
        assert props["scope"][0]["default"] == "in", node.kind
        assert "scope" not in (reader.get(item, uri, "required")[0] or []), node.kind
        assert props["scope_reason"][0]["$ref"] == f"{_GRAPH}#scopeReason", node.kind
        assert f"{_GRAPH}#scopeReasonRule" in reader.all_of_refs(item, uri), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_verifier_kinds_carry_no_scope(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        if node.value["role"] != "verifier":
            continue
        props = _props(reader, node)
        assert "scope" not in props and "scope_reason" not in props, node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_every_non_record_kind_carries_lifecycle_aliases_and_replaces(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        item, uri = _item(reader, node)
        props = reader.properties(item, uri)
        required = reader.get(item, uri, "required")[0] or []
        assert props["lifecycle"][0]["$ref"] == f"{_GRAPH}#lifecycle", node.kind
        assert props["aliases"][0]["items"]["$ref"] == "vc:core:atoms#kebabId", node.kind
        assert "x-link" not in props["aliases"][0], node.kind
        assert props["replaces"][0]["items"]["$ref"] == f"{_GRAPH}#nodeId", node.kind
        assert not {"lifecycle", "aliases", "replaces"} & set(required), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_every_link_kind_is_declared_or_seed(decls, fname: str) -> None:
    known = {n.kind for n in decls.nodes} | {"seed"}
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        if kinds != "*":
            assert set(kinds) <= known, (link.field_name, kinds)


@pytest.mark.parametrize("fname", _FILES)
def test_no_forward_links(decls, fname: str) -> None:
    kind_step = {n.kind: _step_of(n.schema_file) for n in decls.nodes if n.kind != "seed" and _is_step_schema(n.schema_file)}
    holder_step = _step_of(fname)
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        same_step = set(link.value.get("same_step_kinds", []))
        for kind in [] if kinds == "*" else kinds:
            if kind == "seed":
                continue
            assert kind_step[kind] <= holder_step, (link.field_name, kind)
            assert kind_step[kind] != holder_step or kind in same_step, (link.field_name, kind)


@pytest.mark.parametrize("fname", _FILES)
def test_contract_equals_computed_content_set(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        props = _props(reader, node)
        contract = node.value["contract"]
        id_field = node.value["id"]
        links = _link_fields(reader, props)
        assert id_field not in contract and not set(contract) & links, node.kind
        computed = set(props) - {id_field} - links - _node_arrays(reader, props) - _EXCLUDED_FROM_CONTRACT
        assert set(contract) == computed, node.kind
        assert len(contract) == len(set(contract)), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_built_true_only_on_derives_from(decls, fname: str) -> None:
    for link in _links(decls, fname):
        assert link.value.get("built", False) is (link.field_name == "derives_from"), link.field_name


@pytest.mark.parametrize("fname", _FILES)
def test_required_links_have_min_items_one(decls, reader, fname: str) -> None:
    for link in _links(decls, fname):
        min_items, _ = reader.get(link.container, link.uri, "minItems")
        if link.value["required"]:
            assert min_items is not None and min_items >= 1, (link.field_name, link.path)


def test_every_x_link_declares_the_pinned_kinds() -> None:
    declared = declared_link_kinds(_FILES)
    expected = [row for row in _EXPECTED_LINK_KINDS if row[0] in _FILES]
    assert [d[:2] for d in declared if d[:2] not in [e[:2] for e in expected]] == [], "x-link declared but not in the table"
    assert [e[:2] for e in expected if e[:2] not in [d[:2] for d in declared]] == [], "x-link in the table but not declared"
    assert sorted(declared, key=repr) == sorted(expected, key=repr)


def test_annotation_lints_are_clean_on_m3_schemas(decls) -> None:
    assert lint_annotations(decls) == []


def test_step_06_invariant_declares_constrains_and_assumes_links(decls) -> None:
    fname = "06_invariants.schema.json"
    _assert_links(
        decls, fname,
        {
            "constrains": (["api", "component", "connection", "fr"], False),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
    )


def test_step_07_nfr_declares_constrains_relies_on_and_derives_from(decls) -> None:
    fname = "07_nfrs.schema.json"
    _assert_links(
        decls, fname,
        {
            "constrains": (["api", "component", "connection", "fr"], False),
            "relies_on": (["third-party"], False),
            "derives_from": (["metric"], False),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
    )
    assert _link(decls, fname, "derives_from").value["built"] is True


def test_step_08_fixture_declares_verifies_and_removes_links(decls) -> None:
    fname = "08_fixtures.schema.json"
    _assert_links(
        decls, fname,
        {
            "verifies": (["api", "criterion", "invariant", "nfr"], False),
            "removes": ("*", False),
            "replaces": ("*", False),
        },
    )
