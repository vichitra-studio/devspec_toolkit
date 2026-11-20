"""Core schema definitions of the spec graph: the ambiguity item, the orphan scan, and the step base."""
from __future__ import annotations

import json
import re
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
_AMBIGUITY_LIST_REF = f"{_COLLECTIONS}#ambiguityList"
_STEP_FILE_RE = re.compile(r"^(\d{2}a?)_")
_TRINITY_LOCATIONS = (
    ("16_anchor.schema.json", ("plan", "ambiguities")),
    ("16_impl_context.schema.json", ("plan", "ambiguities")),
    ("16_impl_context.schema.json", ("execution", "emergent_ambiguities")),
)
_REMOVED_AMBIGUITY_FIELDS = ("severity", "status", "impact", "resolved", "source", "mitigation")

# Core definitions no schema `$ref`s that are still wanted: the annotation vocabulary and `metadata`.
_ORPHAN_ALLOW_LIST = frozenset({
    ("atoms", "metadata"),
    ("graph", "xNode"),
    ("graph", "xLink"),
    ("graph", "linkVerb"),
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


def _step_schema_files() -> list[str]:
    """Step schemas that carry a top-level `ambiguities`: 00 to 15, not step 16."""
    names = []
    for path in _SCHEMA_DIR.glob("*.schema.json"):
        match = _STEP_FILE_RE.match(path.name)
        if match and match.group(1) not in ("16",):
            names.append(path.name)
    return sorted(names)


def _root_properties(schema: dict[str, Any]) -> dict[str, Any]:
    """Properties declared at the root of *schema* or in one of its top-level `allOf` branches."""
    merged = dict(schema.get("properties", {}))
    for branch in schema.get("allOf", []):
        merged |= branch.get("properties", {})
    return merged


def _property_at(schema: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    node = {"properties": _root_properties(schema)}
    for name in path:
        node = node["properties"][name]
    return node


_LOCATIONS = [(name, ("ambiguities",)) for name in _step_schema_files()] + list(_TRINITY_LOCATIONS)


@pytest.mark.parametrize(("schema_file", "path"), _LOCATIONS, ids=lambda value: str(value))
def test_ambiguities_declared_on_every_step_schema_and_trinity_location(schema_file: str, path: tuple[str, ...]) -> None:
    node = _property_at(_load(_SCHEMA_DIR / schema_file), path)
    assert node["$ref"] == _AMBIGUITY_LIST_REF


def test_ambiguity_locations_are_every_step_schema_and_the_trinity_locations() -> None:
    assert len(_LOCATIONS) == len(_step_schema_files()) + len(_TRINITY_LOCATIONS)
    assert len({name for name, _ in _LOCATIONS[:-len(_TRINITY_LOCATIONS)]}) == len(_step_schema_files())
    assert not any(name.startswith("16") for name, _ in _LOCATIONS[:-len(_TRINITY_LOCATIONS)])


@pytest.mark.parametrize("schema_file", ["16_anchor.schema.json", "16_impl_context.schema.json"])
def test_ambiguities_not_in_step_base_nor_at_plan_or_anchor_root(schema_file: str) -> None:
    step_base = _load(_CORE_DIR / "step_base.schema.json")
    assert "ambiguities" not in step_base["properties"]
    assert "ambiguities" not in _root_properties(_load(_SCHEMA_DIR / schema_file))


def test_crosscycle_item_and_ambiguity_status_removed() -> None:
    assert "crossCycleAmbiguityItem" not in _load(_CORE_DIR / "collections.schema.json")["$defs"]
    assert "ambiguityStatus" not in _load(_CORE_DIR / "atoms.schema.json")["$defs"]
    referenced = {ref for path in _SCHEMA_DIR.rglob("*.schema.json") for ref in _qualified_refs(_load(path))}
    assert {f"{_COLLECTIONS}#crossCycleAmbiguityItem", "vc:core:atoms#ambiguityStatus"}.isdisjoint(referenced)
