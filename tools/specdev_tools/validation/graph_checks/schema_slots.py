"""The schema slot of a node or of one of its leaves: what the schema of the node's file says about the value there.

Shared by the prose check (a leaf that is a fixed value) and the no-dangling advice (a kind that has a ``scope`` field).
"""
from __future__ import annotations

from typing import Any

from specdev_tools.core.schema_nav import child_schema, effective_schema
from specdev_tools.graph.contract import path_steps
from specdev_tools.graph.model import Graph, Node
from specdev_tools.validation.hallucination_lint import SchemaResolverCtx


def _descend(schema: Any, resolve: Any, steps: list[str | int], *, raw: bool = False) -> dict[str, Any] | None:
    """The effective schema at *steps* below *schema*, or ``None``; with *raw*, the schema as written there (``$ref``, ``anyOf`` and ``oneOf`` still in it).

    Each step is read with the conditional branches merged in; when that finds nothing further down, it is read
    again without them.  A conditional branch only adds a property (it never replaces a declaration), so the second
    read matters for a name that only such a branch declares: without the branch the name is tried against
    ``patternProperties`` and ``additionalProperties``.
    """
    if not steps:
        return schema if raw else effective_schema(schema, resolve, include_conditionals=True)
    tried: list[Any] = []
    for conditionals in (True, False):
        child = child_schema(effective_schema(schema, resolve, include_conditionals=conditionals), steps[0], additional=True)
        if child is None or child in tried:
            continue
        tried.append(child)
        found = _descend(child, resolve, steps[1:], raw=raw)
        if found is not None:
            return found
    return None


_COMPOSITION = ("$ref", "$anchor", "allOf", "oneOf", "anyOf", "if", "then", "else", "properties", "required", "description")
_MAX_UNION_DEPTH = 8


def alternatives_of(schema: dict[str, Any], resolve: Any, _depth: int = 0) -> list[dict[str, Any]]:
    """The effective schemas a value of *schema* may take: one per branch of an ``anyOf`` or ``oneOf`` (``$ref`` resolved by *resolve*, nested unions flattened), or just the effective schema of *schema* when it is no union.

    ``effective_schema`` drops a union (it only gathers the properties of its branches), so a reader that asks what a
    slot FIXES (a pattern, an enum) must read the branches here.  The keywords the union node states itself (a
    ``pattern`` beside the ``anyOf``) are carried into each branch.
    """
    node = schema
    if "$ref" in node:
        resolved = resolve(node)
        if not isinstance(resolved, dict):
            return [effective_schema(schema, resolve, include_conditionals=True)]
        node = {**resolved, **{key: value for key, value in node.items() if key != "$ref"}}
    branches = [branch for keyword in ("anyOf", "oneOf") for branch in node.get(keyword, []) or [] if isinstance(branch, dict)]
    if not branches or _depth >= _MAX_UNION_DEPTH:
        return [effective_schema(node, resolve, include_conditionals=True)]
    own = {key: value for key, value in node.items() if key not in _COMPOSITION}
    return [{**own, **alternative} for branch in branches for alternative in alternatives_of(branch, resolve, _depth + 1)]


class SchemaSlots:
    """The effective schema of a node or leaf, read from the ``$schema`` of its file; the schema of each file is loaded once."""

    def __init__(self, repo_root: str) -> None:
        self._resolver = SchemaResolverCtx(repo_root)
        self._files: dict[str, tuple[Any, Any]] = {}

    def _loaded(self, graph: Graph, node: Node) -> tuple[Any, Any]:
        """The raw schema of the file of *node* and its ``$ref`` resolver (``(None, None)`` when there is none); loaded once per file."""
        if node.file not in self._files:
            document = graph.documents.get(node.file)
            raw = self._resolver.load_raw_schema(document) if isinstance(document, dict) else None
            self._files[node.file] = (raw, self._resolver.make_resolve_fn(raw)) if raw is not None else (None, None)
        return self._files[node.file]

    def slot(self, graph: Graph, node: Node, leaf_path: str = "") -> dict[str, Any] | None:
        """The effective schema (``$ref`` and ``allOf`` merged, conditional branches included) at *leaf_path* below *node* (the node's own item when empty); ``None`` when the schema or the slot cannot be resolved."""
        schema, resolve = self._loaded(graph, node)
        if schema is None:
            return None
        steps = path_steps(node.jq_path + leaf_path)
        if steps is None:
            return None
        return _descend(schema, resolve, steps)

    def alternatives(self, graph: Graph, node: Node, leaf_path: str = "") -> list[dict[str, Any]]:
        """The effective schemas a value at *leaf_path* below *node* may take (``alternatives_of``: one per branch of a union); empty when the slot cannot be resolved."""
        schema, resolve = self._loaded(graph, node)
        steps = path_steps(node.jq_path + leaf_path)
        if schema is None or steps is None:
            return []
        raw = _descend(schema, resolve, steps, raw=True)
        return [] if raw is None else alternatives_of(raw, resolve)

    def has_property(self, graph: Graph, node: Node, name: str) -> bool:
        """Whether the item of *node* declares the property *name*."""
        slot = self.slot(graph, node)
        return slot is not None and name in slot.get("properties", {})
