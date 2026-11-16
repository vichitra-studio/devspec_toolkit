"""Core schema definitions of the spec graph: the ambiguity item, the orphan scan, and the step base."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import get_shared_registry

_ROOT = Path(__file__).parents[3]
_SCHEMA_DIR = _ROOT / "schema"
_CORE_DIR = _SCHEMA_DIR / "core"
_COLLECTIONS = "vc:core:collections"
_REMOVED_AMBIGUITY_FIELDS = ("severity", "status", "impact", "resolved", "source", "mitigation")

# Core definitions no schema `$ref`s that are still wanted: the annotation vocabulary and `metadata`.
# `ambiguityList` is on this list until WI-M3-03 references it from the step schemas.
_ORPHAN_ALLOW_LIST = frozenset({
    ("atoms", "metadata"),
    ("graph", "xNode"),
    ("graph", "xLink"),
    ("graph", "linkVerb"),
    ("collections", "ambiguityList"),
})


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _refs(node: Any) -> Iterator[str]:
    """Yield every ``$ref`` string found anywhere under *node*."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _refs(value)


def _qualified_refs(document: dict[str, Any]) -> set[str]:
    """Every ``$ref`` of *document* as ``<schema $id>#<name>``; a local ``#/$defs/x`` is qualified with its own ``$id``."""
    own_id = document.get("$id", "")
    return {
        f"{own_id}#{ref.removeprefix('#/$defs/')}" if ref.startswith("#") else ref
        for ref in _refs(document)
    }


def _item_validator() -> Draft202012Validator:
    registry = get_shared_registry(str(_ROOT))
    return Draft202012Validator(
        {"$ref": f"{_COLLECTIONS}#ambiguityItem"},
        registry=registry.to_referencing_registry(),
    )


def _valid_item() -> dict[str, Any]:
    return {
        "id": "amb-session-timeout",
        "description": "The session timeout is not stated.",
        "about": ["fr-user-login"],
    }


def test_ambiguity_item_accepts_pd3_shape() -> None:
    item = _valid_item() | {
        "missing_kind": "criterion",
        "decision": "Thirty minutes.",
        "proposed_assumption": "Thirty minutes until answered.",
    }
    assert list(_item_validator().iter_errors(item)) == []


@pytest.mark.parametrize("field", _REMOVED_AMBIGUITY_FIELDS)
def test_ambiguity_item_rejects_removed_fields(field: str) -> None:
    item = _valid_item() | {field: "x"}
    assert list(_item_validator().iter_errors(item))


def test_ambiguity_item_requires_about() -> None:
    item = _valid_item()
    del item["about"]
    assert list(_item_validator().iter_errors(item))


def test_ambiguity_item_rejects_empty_about() -> None:
    assert list(_item_validator().iter_errors(_valid_item() | {"about": []}))


def test_ambiguity_list_declares_the_ambiguity_node() -> None:
    declared = _load(_CORE_DIR / "collections.schema.json")["$defs"]["ambiguityList"]["x-node"]
    assert {key: declared[key] for key in ("kind", "id", "role")} == {
        "kind": "ambiguity-item", "id": "id", "role": "record",
    }


def test_no_orphan_defs_in_core_schemas() -> None:
    referenced = {ref for path in _SCHEMA_DIR.rglob("*.schema.json") for ref in _qualified_refs(_load(path))}
    orphans = []
    for path in sorted(_CORE_DIR.glob("*.schema.json")):
        name = path.name.removesuffix(".schema.json")
        document = _load(path)
        for definition in document.get("$defs", {}):
            if (name, definition) in _ORPHAN_ALLOW_LIST:
                continue
            if f"{document['$id']}#{definition}" not in referenced:
                orphans.append(f"{name}#{definition}")
    assert orphans == []


def test_testing_mode_accepts_manual() -> None:
    enum = _load(_CORE_DIR / "atoms.schema.json")["$defs"]["testingMode"]["enum"]
    assert "manual" in enum


def test_step_base_has_no_ingested_fields() -> None:
    properties = _load(_CORE_DIR / "step_base.schema.json")["properties"]
    assert {"spec_refs_ingested", "seed_refs_ingested"}.isdisjoint(properties)
