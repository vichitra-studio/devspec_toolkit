"""Support for the tests of the graph declarations (``x-node`` and ``x-link``) the schemas carry: where to read them and the helpers that list them."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from specdev_tools.registry.annotations import (
    LinkDecl,
    NodeDecl,
    SchemaReader,
)

_ROOT = Path(__file__).parents[3]

_SCHEMA_DIR = _ROOT / "schema"

_GRAPH = "vc:core:graph"

_OBLIGATION_ROLES = frozenset({"obligation-system", "obligation-delivery"})

_EXCLUDED_FROM_CONTRACT = frozenset({"status", "notes", "tags", "owner", "lifecycle", "aliases", "replaces"})

_ROLE_TABLE = json.loads((_ROOT / "tests" / "fixtures" / "graph" / "kind_role_table.json").read_text())["kinds"]

_STEP_FILE_RE = re.compile(r"(\d{2}[a-z]?)_")

def _step_of(schema_file: str) -> str:
    match = _STEP_FILE_RE.match(Path(schema_file).name)
    assert match, schema_file
    return match.group(1)

def _is_step_schema(schema_file: str) -> bool:
    """False for a ``schema/core`` file: a kind declared there (the ambiguity item) belongs to no step."""
    return _STEP_FILE_RE.match(Path(schema_file).name) is not None

def _item(reader: SchemaReader, node: NodeDecl) -> tuple[Any, str]:
    """The item schema of a declared node (the ``items`` of an array, the map value otherwise)."""
    items, uri = reader.get(node.container, node.uri, "items")
    if items is None:
        items, uri = reader.get(node.container, node.uri, "additionalProperties")
    return items, uri

def _link_fields(reader: SchemaReader, props: dict[str, Any]) -> set[str]:
    return {name for name, (sub, uri) in props.items() if reader.get(sub, uri, "x-link")[0] is not None}

def _links(decls, fname: str) -> list[LinkDecl]:
    return [lk for lk in decls.links if Path(lk.schema_file).name == fname]

def _node_arrays(reader: SchemaReader, props: dict[str, Any]) -> set[str]:
    return {name for name, (sub, uri) in props.items() if reader.get(sub, uri, "x-node")[0] is not None}

def _nodes(decls, fname: str) -> list[NodeDecl]:
    return [n for n in decls.nodes if Path(n.schema_file).name == fname]

def _props(reader: SchemaReader, node: NodeDecl) -> dict[str, Any]:
    item, uri = _item(reader, node)
    return reader.properties(item, uri)

def declared_link_kinds(files: list[str]) -> list[tuple[str, str, Any]]:
    """``(schema file, JSON pointer, sorted kinds or "*")`` of every ``x-link`` found in the schema *files*."""
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

    for fname in files:
        walk(json.loads((_SCHEMA_DIR / fname).read_text(encoding="utf-8")), "", fname)
    return found
