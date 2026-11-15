"""WI-M2-00: M2 builds on the M1 annotation interface exactly as shipped.

Pins the names M2's schemas rely on: the shared graph definitions, the
``collect_annotations`` return shape, and ``$ref``-sibling handling of ``x-node`` /
``x-link``.  A rename in M1 fails here before it breaks seven schemas.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.registry import get_shared_registry
from specdev_tools.core.schema_nav import effective_schema
from specdev_tools.registry.annotations import AnnotationDecls, SchemaRefs, collect_annotations

_ROOT = Path(__file__).parents[3]
_GRAPH_ANCHORS = ("lifecycle", "scope", "scopeReason", "scopeReasonRule")
_GRAPH_DEFINITION_NAMES = frozenset(_GRAPH_ANCHORS)


@pytest.fixture(scope="module")
def refs() -> SchemaRefs:
    return SchemaRefs(get_shared_registry(str(_ROOT)))


@pytest.mark.parametrize("anchor", _GRAPH_ANCHORS)
def test_graph_anchors_resolve_through_schema_refs(refs: SchemaRefs, anchor: str) -> None:
    hit = refs.resolve(f"vc:core:graph#{anchor}")
    assert hit is not None, f"vc:core:graph#{anchor} does not resolve"
    target, uri, _pointer = hit
    assert uri == "vc:core:graph"
    assert target["$anchor"] == anchor


def test_collect_annotations_importable_and_returns_decls() -> None:
    decls = collect_annotations(str(_ROOT))
    assert isinstance(decls, AnnotationDecls)
    assert decls.graph_present
    assert decls.registry is not None
    assert decls.nodes and decls.links


def test_effective_schema_keeps_x_node_and_x_link_beside_ref(refs: SchemaRefs) -> None:
    def resolve(node: dict) -> dict | None:
        hit = refs.resolve(node["$ref"])
        return hit[0] if hit else None

    link = {"kinds": ["assumption"], "required": False}
    merged = effective_schema({"$ref": "vc:core:graph#scope", "x-link": link}, resolve)
    assert merged["x-link"] == link
    assert merged["enum"] == ["in", "later", "out"]


def test_atoms_has_no_duplicate_graph_definitions() -> None:
    atoms = json.loads((_ROOT / "schema" / "core" / "atoms.schema.json").read_text())
    assert not _GRAPH_DEFINITION_NAMES & set(atoms.get("$defs", {}))
    anchors = {d.get("$anchor") for d in atoms.get("$defs", {}).values() if isinstance(d, dict)}
    assert not _GRAPH_DEFINITION_NAMES & anchors
