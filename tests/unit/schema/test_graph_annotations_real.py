"""Annotation rules the real step schemas must follow that the M1 lints do not check.

Each rule is parametrised over every schema file that carries an ``x-node``, so a step added to the graph
is covered without an edit. M1 dropped these lints (ANNOT-04, 06, 09); the tests live here instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.registry import get_shared_registry
from specdev_tools.registry.annotations import (
    NodeDecl,
    SchemaReader,
    SchemaRefs,
    collect_annotations,
)

_ROOT = Path(__file__).parents[3]
_SCHEMA_DIR = _ROOT / "schema"
_STAR_VERBS = frozenset({"replaces", "removes", "about"})
_LINK_VERBS = frozenset(
    json.loads((_SCHEMA_DIR / "core" / "graph.schema.json").read_text())["$defs"]["linkVerb"]["enum"]
)


def _annotated_files() -> list[str]:
    return sorted(p.name for p in _SCHEMA_DIR.glob("[0-9][0-9]*_*.schema.json") if "x-node" in p.read_text())


_FILES = _annotated_files()


@pytest.fixture(scope="module")
def decls():
    return collect_annotations(str(_ROOT))


@pytest.fixture(scope="module")
def reader() -> SchemaReader:
    return SchemaReader(SchemaRefs(get_shared_registry(str(_ROOT))))


def _properties_maps(node: Any) -> list[dict[str, Any]]:
    """Every ``properties`` mapping found anywhere under *node*."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            found.append(props)
        for value in node.values():
            found.extend(_properties_maps(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_properties_maps(value))
    return found


def _item_properties(reader: SchemaReader, node: NodeDecl) -> dict[str, Any]:
    items, uri = reader.get(node.container, node.uri, "items")
    if items is None:
        items, uri = reader.get(node.container, node.uri, "additionalProperties")
    return reader.properties(items, uri)


@pytest.mark.parametrize("fname", _FILES)
def test_contract_entries_exist_and_are_not_id_or_link(decls, reader: SchemaReader, fname: str) -> None:
    for node in (n for n in decls.nodes if Path(n.schema_file).name == fname):
        props = _item_properties(reader, node)
        links = {name for name, (sub, uri) in props.items() if reader.get(sub, uri, "x-link")[0] is not None}
        contract = node.value.get("contract", [])
        assert set(contract) <= set(props), (node.kind, sorted(set(contract) - set(props)))
        assert node.value.get("id") not in contract, node.kind
        assert not set(contract) & links, (node.kind, sorted(set(contract) & links))


@pytest.mark.parametrize("fname", _FILES)
def test_star_kinds_only_on_replaces_removes_about(decls, fname: str) -> None:
    for link in (lk for lk in decls.links if Path(lk.schema_file).name == fname):
        if link.value["kinds"] == "*":
            assert link.field_name in _STAR_VERBS, (link.field_name, link.path)


@pytest.mark.parametrize("fname", _FILES)
def test_every_verb_named_property_carries_x_link(fname: str) -> None:
    schema = json.loads((_SCHEMA_DIR / fname).read_text(encoding="utf-8"))
    for props in _properties_maps(schema):
        for name in _LINK_VERBS & set(props):
            assert "x-link" in props[name], (fname, name)
