"""Flatten JSON Schemas into an inventory of property paths.

A path names a node of the data a schema describes: ``apis[].path`` is the ``path``
property of each entry of the ``apis`` array, ``environments{}`` is the value of a map.
Each path records the node's effective ``type`` and ``enum`` and its own ``$ref``, which is
what the schema-change rows compare. Core ``$ref`` targets are expanded in place, guarded against
cycles, and keys such as ``properties``/``items`` are read as schema keywords only at
schema level, so a property that is itself named ``description`` is kept.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CORE_PREFIX = "core/"
_SCHEMA_SUFFIX = ".schema.json"
_COMBINATORS = ("allOf", "anyOf", "oneOf")
_BRANCHES = ("if", "then", "else")
_MAP_KEYWORDS = ("additionalProperties",)

SchemaDocs = Mapping[str, dict[str, Any]]


class SchemaPathError(ValueError):
    """Raised when a schema cannot be flattened (unresolvable ``$ref``, malformed file)."""


@dataclass(frozen=True)
class PathInfo:
    """Facts of one flattened path: effective ``type``, the node's own ``$ref``, effective ``enum``."""

    type: str | None
    ref: str | None
    enum: tuple[Any, ...] | None = None


def index_by_id(docs: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map each document's ``$id`` to the document; documents without ``$id`` are skipped."""
    return {doc["$id"]: doc for doc in docs if "$id" in doc}


def _type_of(node: dict[str, Any]) -> str | None:
    """The node's ``type`` as one string; a type list becomes its sorted members joined by ``|``."""
    declared = node.get("type")
    if isinstance(declared, list):
        return "|".join(sorted(str(member) for member in declared))
    return declared if isinstance(declared, str) else None


def _enum_of(node: dict[str, Any]) -> tuple[Any, ...] | None:
    """The node's ``enum`` values in declared order, or ``None`` when it declares none."""
    declared = node.get("enum")
    return tuple(declared) if isinstance(declared, list) else None


def _lookup_fragment(doc: dict[str, Any], fragment: str, ref: str) -> dict[str, Any]:
    """Resolve a ``$ref`` fragment (empty, JSON pointer, or ``$defs`` name/anchor) inside *doc*."""
    if not fragment:
        return doc
    if fragment.startswith("/"):
        target: Any = doc
        for token in fragment[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or token not in target:
                raise SchemaPathError(f"unresolvable $ref {ref!r}")
            target = target[token]
        return target
    defs = doc.get("$defs", {})
    if fragment in defs:
        return defs[fragment]
    for definition in defs.values():
        if isinstance(definition, dict) and definition.get("$anchor") == fragment:
            return definition
    raise SchemaPathError(f"unresolvable $ref {ref!r}")


def _resolve(ref: str, doc: dict[str, Any], docs: SchemaDocs) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(owning document, target schema)`` of *ref*, read from *doc* among *docs*."""
    base, _, fragment = ref.partition("#")
    owner = doc
    if base:
        if base not in docs:
            raise SchemaPathError(f"unresolvable $ref {ref!r}: no schema with $id {base!r}")
        owner = docs[base]
    return owner, _lookup_fragment(owner, fragment, ref)


class _Walker:
    """One flattening run: accumulates paths into ``out`` while expanding refs."""

    def __init__(self, docs: SchemaDocs) -> None:
        self._docs = docs
        self.out: dict[str, PathInfo] = {}

    def walk(self, node: Any, path: str, doc: dict[str, Any], stack: tuple[str, ...]) -> None:
        """Record *node* at *path*, then descend into refs, properties, items and combinators."""
        if not isinstance(node, dict):
            return
        ref = node.get("$ref")
        target: tuple[dict[str, Any], dict[str, Any]] | None = None
        if isinstance(ref, str):
            target = _resolve(ref, doc, self._docs)
        node_type = _type_of(node) or (_type_of(target[1]) if target else None)
        node_enum = _enum_of(node) or (_enum_of(target[1]) if target else None)
        if path:
            self._record(path, PathInfo(node_type, ref if isinstance(ref, str) else None, node_enum))
        if target and isinstance(ref, str):
            key = f"{target[0].get('$id', '')}#{ref.partition('#')[2]}"
            if key not in stack:
                self.walk(target[1], path, target[0], (*stack, key))
        self._descend(node, path, doc, stack)

    def _record(self, path: str, info: PathInfo) -> None:
        """Store a path, filling a missing type, ref or enum from a later visit of the same path."""
        known = self.out.get(path)
        if known is not None:
            info = PathInfo(known.type or info.type, known.ref or info.ref, known.enum or info.enum)
        self.out[path] = info

    def _descend(self, node: dict[str, Any], path: str, doc: dict[str, Any], stack: tuple[str, ...]) -> None:
        """Walk the children of *node*: properties, array items, map values, combinators."""
        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, child in properties.items():
                self.walk(child, f"{path}.{name}" if path else name, doc, stack)
        self.walk(node.get("items"), f"{path}[]", doc, stack)
        for keyword in _MAP_KEYWORDS:
            self.walk(node.get(keyword), f"{path}{{}}", doc, stack)
        pattern_properties = node.get("patternProperties")
        if isinstance(pattern_properties, dict):
            for child in pattern_properties.values():
                self.walk(child, f"{path}{{}}", doc, stack)
        for keyword in _COMBINATORS:
            for branch in node.get(keyword, ()):
                self.walk(branch, path, doc, stack)
        for keyword in _BRANCHES:
            self.walk(node.get(keyword), path, doc, stack)


def flatten_schema(doc: dict[str, Any], docs: SchemaDocs, include_defs: bool = False) -> dict[str, PathInfo]:
    """Flatten *doc* into ``{path: PathInfo}``, expanding ``$ref`` targets found in *docs*.

    With ``include_defs`` every ``$defs`` entry is also walked at ``$defs.<name>`` (for core
    schemas, whose definitions are not reachable from a root). Raises ``SchemaPathError`` on
    an unresolvable ``$ref``.
    """
    walker = _Walker(docs)
    walker.walk(doc, "", doc, ())
    if include_defs:
        for name, definition in doc.get("$defs", {}).items():
            walker.walk(definition, f"$defs.{name}", doc, ())
    return walker.out


def schema_name(schema_dir: Path, file: Path) -> str:
    """Inventory key of a schema file: ``00_charter``, or ``core/atoms`` below ``core/``."""
    stem = file.name.removesuffix(_SCHEMA_SUFFIX)
    return f"{CORE_PREFIX}{stem}" if file.parent == schema_dir / "core" else stem


def flatten_schema_dir(schema_dir: Path) -> dict[str, dict[str, PathInfo]]:
    """Flatten every ``*.schema.json`` of *schema_dir* and its ``core/`` folder.

    Returns ``{schema name: {path: PathInfo}}``. All schema files below *schema_dir* (including
    ``infra/``) are available for ``$ref`` expansion. Raises ``SchemaPathError`` for a file that
    is not valid JSON or has an unresolvable ``$ref``.
    """
    loaded: dict[Path, dict[str, Any]] = {}
    for file in sorted(schema_dir.rglob(f"*{_SCHEMA_SUFFIX}")):
        try:
            loaded[file] = json.loads(file.read_text(encoding="utf-8"))
        except ValueError as exc:  # not UTF-8 or not JSON
            raise SchemaPathError(f"{file}: invalid JSON: {exc}") from exc
    docs = index_by_id(loaded.values())
    listed = [f for f in loaded if f.parent in (schema_dir, schema_dir / "core")]
    return {
        schema_name(schema_dir, file): flatten_schema(loaded[file], docs, include_defs=file.parent.name == "core")
        for file in listed
    }
