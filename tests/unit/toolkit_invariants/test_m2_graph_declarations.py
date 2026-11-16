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


_STEP_FILE_RE = re.compile(r"(\d{2}[a-z]?)_")


def _step_of(schema_file: str) -> str:
    match = _STEP_FILE_RE.match(Path(schema_file).name)
    assert match, schema_file
    return match.group(1)


def _is_step_schema(schema_file: str) -> bool:
    """False for a ``schema/core`` file: a kind declared there (the ambiguity item) belongs to no step."""
    return _STEP_FILE_RE.match(Path(schema_file).name) is not None


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
    assert set(_FILES) == {
        "00_charter.schema.json",
        "01_capabilities.schema.json",
        "02_system_sketch.schema.json",
        "02a_delivery_baseline.schema.json",
        "03_glossary.schema.json",
        "04_fr_list.schema.json",
        "05_interface_contracts.schema.json",
    }


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
    kind_step = {n.kind: _step_of(n.schema_file) for n in decls.nodes if n.kind != "seed" and _is_step_schema(n.schema_file)}
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


def test_term_kind_is_context_and_only_declares_replaces_link(decls) -> None:
    fname = "03_glossary.schema.json"
    assert [n.value["role"] for n in _nodes(decls, fname)] == ["context"]
    assert [lk.field_name for lk in _links(decls, fname)] == ["replaces"]


def _same_step_edges(decls) -> set[tuple[str, str]]:
    """``(holder kind, target kind)`` for every ``same_step_kinds`` entry on a 00-05 link."""
    return {
        (holder, target)
        for link in decls.links
        if _is_step_schema(link.schema_file) and _step_of(link.schema_file) in _M2_STEPS
        for holder in link.holders
        for target in link.value.get("same_step_kinds", [])
    }


def _has_cycle(edges: set[tuple[str, str]]) -> bool:
    """True when *edges* (self-loops ignored) contain a cycle between distinct kinds."""
    graph: dict[str, set[str]] = {}
    for src, dst in edges:
        if src != dst:
            graph.setdefault(src, set()).add(dst)
    done: set[str] = set()

    def visit(kind: str, path: tuple[str, ...]) -> bool:
        if kind in path:
            return True
        if kind in done:
            return False
        if any(visit(nxt, (*path, kind)) for nxt in graph.get(kind, ())):
            return True
        done.add(kind)
        return False

    return any(visit(kind, ()) for kind in list(graph))


def test_same_step_self_loops_are_exactly_third_party_fr_api(decls) -> None:
    edges = _same_step_edges(decls)
    assert edges
    assert {src for src, dst in edges if src == dst} == {"third-party", "fr", "api"}


def test_same_step_kind_graph_has_no_cycle_between_distinct_kinds(decls) -> None:
    assert not _has_cycle(_same_step_edges(decls))
    assert _has_cycle({("a", "b"), ("b", "c"), ("c", "a")})


def test_fr_depends_on_itself_parses_against_schema() -> None:
    from specdev_tools.core.schema_validate import validate_data_against_schema

    capability = {"id": "cn:project:capability:cap-sample", "kind": "capability"}

    def fr(n: int, depends_on: list[str]) -> dict[str, Any]:
        return {
            "fr_id": f"fr-item-{n}",
            "statement": "The system shall do the thing in a testable way",
            "scope": "in",
            "derives_from": ["cap-sample"],
            "capability_ref": capability,
            "acceptance_criteria": [
                {"criterion_id": f"ac-{n}-{j}", "scope": "in", "text": "Observable outcome is verified by a test"}
                for j in (1, 2)
            ],
            "depends_on": depends_on,
        }

    doc = {
        "$schema": "vc:04-fr-list", "id": "fr-catalog", "owner": "api",
        "created_at": "2025-01-01T00:00:00Z", "canonical_refs_used": [capability],
        "functional_requirements": [fr(1, ["fr-item-1"]), fr(2, []), fr(3, [])],
    }
    assert validate_data_against_schema(str(_ROOT), doc) == []


def _registry_entries_by_kind() -> dict[str, dict[str, Any]]:
    """Every registered entry of ``tools/entry_key_registry.json`` keyed by kind, nested entries included."""
    registry = json.loads((_ROOT / "tools" / "entry_key_registry.json").read_text())["registry"]
    found: dict[str, dict[str, Any]] = {}

    def collect(entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            found[entry["kind"]] = entry
            collect(entry.get("nested", []))

    for file_entry in registry.values():
        collect(file_entry.get("arrays", []))
    return found


@pytest.mark.parametrize(
    ("kind", "id_field"),
    [(kind, field) for kinds in _EXPECTED_KINDS.values() for kind, field in kinds.items()],
)
def test_every_m2_kind_in_registry_with_id_field(kind: str, id_field: str | None) -> None:
    entry = _registry_entries_by_kind()[kind]
    if id_field is None:
        assert entry.get("map_keyed") is True and "id_field" not in entry
    else:
        assert entry["id_field"] == id_field


# Every ``x-link`` of the seven M2 schemas: (schema file, JSON pointer of the link field, sorted ``kinds`` or "*").
# Written out by hand on purpose: a change of one link's ``kinds`` list must be a deliberate change of this table.
_EXPECTED_LINK_KINDS: list[tuple[str, str, Any]] = [
    ('00_charter.schema.json', '/allOf/1/properties/scope_items/items/properties/derives_from', ['need', 'seed']),
    ('00_charter.schema.json', '/allOf/1/properties/scope_items/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/scope_items/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/assumptions/items/properties/derives_from', ['seed']),
    ('00_charter.schema.json', '/allOf/1/properties/assumptions/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/risks/items/properties/derives_from', ['assumption', 'seed']),
    ('00_charter.schema.json', '/allOf/1/properties/risks/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/risks/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/stakeholders/items/properties/needs/items/properties/derives_from', ['seed']),
    ('00_charter.schema.json', '/allOf/1/properties/stakeholders/items/properties/needs/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/stakeholders/items/properties/needs/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/stakeholders/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/stakeholders/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/user_segments/items/properties/derives_from', ['seed']),
    ('00_charter.schema.json', '/allOf/1/properties/user_segments/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/user_segments/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/success_metrics/items/properties/derives_from', ['need', 'seed']),
    ('00_charter.schema.json', '/allOf/1/properties/success_metrics/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/success_metrics/items/properties/replaces', '*'),
    ('00_charter.schema.json', '/allOf/1/properties/constraints/items/properties/derives_from', ['need', 'seed']),
    ('00_charter.schema.json', '/allOf/1/properties/constraints/items/properties/assumes', ['assumption']),
    ('00_charter.schema.json', '/allOf/1/properties/constraints/items/properties/replaces', '*'),
    ('01_capabilities.schema.json', '/allOf/1/properties/capabilities/items/properties/derives_from', ['metric', 'scope-item', 'segment']),
    ('01_capabilities.schema.json', '/allOf/1/properties/capabilities/items/properties/assumes', ['assumption']),
    ('01_capabilities.schema.json', '/allOf/1/properties/capabilities/items/properties/replaces', '*'),
    ('02_system_sketch.schema.json', '/allOf/1/properties/components/items/properties/derives_from', ['capability', 'constraint']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/components/items/properties/assumes', ['assumption']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/components/items/properties/replaces', '*'),
    ('02_system_sketch.schema.json', '/allOf/1/properties/connections/items/properties/derives_from', ['component']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/connections/items/properties/connects_to', ['component', 'third-party']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/connections/items/properties/assumes', ['assumption']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/connections/items/properties/replaces', '*'),
    ('02_system_sketch.schema.json', '/allOf/1/properties/third_parties/items/properties/derives_from', ['constraint', 'seed']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/third_parties/items/properties/part_of', ['third-party']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/third_parties/items/properties/assumes', ['assumption']),
    ('02_system_sketch.schema.json', '/allOf/1/properties/third_parties/items/properties/replaces', '*'),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/environments/additionalProperties/properties/derives_from', ['constraint', 'scope-item', 'seed']),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/environments/additionalProperties/properties/assumes', ['assumption']),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/environments/additionalProperties/properties/replaces', '*'),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/ci_gates/items/properties/derives_from', ['component', 'constraint']),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/ci_gates/items/properties/assumes', ['assumption']),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/ci_gates/items/properties/replaces', '*'),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/secrets/items/properties/derives_from', ['component', 'connection', 'constraint']),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/secrets/items/properties/assumes', ['assumption']),
    ('02a_delivery_baseline.schema.json', '/allOf/1/properties/secrets/items/properties/replaces', '*'),
    ('03_glossary.schema.json', '/allOf/1/properties/terms/items/properties/replaces', '*'),
    ('04_fr_list.schema.json', '/allOf/1/properties/functional_requirements/items/properties/acceptance_criteria/items/properties/assumes', ['assumption']),
    ('04_fr_list.schema.json', '/allOf/1/properties/functional_requirements/items/properties/acceptance_criteria/items/properties/replaces', '*'),
    ('04_fr_list.schema.json', '/allOf/1/properties/functional_requirements/items/properties/derives_from', ['capability']),
    ('04_fr_list.schema.json', '/allOf/1/properties/functional_requirements/items/properties/depends_on', ['fr']),
    ('04_fr_list.schema.json', '/allOf/1/properties/functional_requirements/items/properties/assumes', ['assumption']),
    ('04_fr_list.schema.json', '/allOf/1/properties/functional_requirements/items/properties/replaces', '*'),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/errors/items/properties/derives_from', ['criterion']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/errors/items/properties/assumes', ['assumption']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/errors/items/properties/replaces', '*'),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/derives_from', ['fr']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/provided_by', ['component']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/relies_on', ['third-party']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/depends_on', ['api']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/assumes', ['assumption']),
    ('05_interface_contracts.schema.json', '/allOf/1/properties/apis/items/properties/replaces', '*'),
]


def _declared_link_kinds() -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []

    def walk(node: Any, pointer: str, fname: str) -> None:
        if isinstance(node, dict):
            if "x-link" in node:
                kinds = node["x-link"]["kinds"]
                found.append((fname, pointer, kinds if kinds == "*" else sorted(kinds)))
            for key, value in node.items():
                walk(value, f"{pointer}/{key}", fname)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}", fname)

    for fname in _FILES:
        walk(json.loads((_SCHEMA_DIR / fname).read_text(encoding="utf-8")), "", fname)
    return found


def test_every_x_link_declares_the_pinned_kinds() -> None:
    declared = _declared_link_kinds()
    expected_keys = [(f, p) for f, p, _ in _EXPECTED_LINK_KINDS]
    declared_keys = [(f, p) for f, p, _ in declared]
    assert [k for k in declared_keys if k not in expected_keys] == [], "x-link declared but not in the table"
    assert [k for k in expected_keys if k not in declared_keys] == [], "x-link in the table but not declared"
    assert sorted(declared, key=repr) == sorted(_EXPECTED_LINK_KINDS, key=repr)
