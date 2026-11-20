"""The schema slot of a node or of one of its leaves: what the schema of the node's file says about the value there.

Shared by the prose check (a leaf that is a fixed value) and the no-dangling advice (a kind that has a ``scope`` field).
"""
from __future__ import annotations

from typing import Any

from specdev_tools.core.schema_nav import child_schema, effective_schema
from specdev_tools.graph.contract import path_steps
from specdev_tools.graph.model import Graph, Node
from specdev_tools.validation.hallucination_lint import SchemaResolverCtx


def _descend(schema: Any, resolve: Any, steps: list[str | int]) -> dict[str, Any] | None:
    """The effective schema at *steps* below *schema*, or ``None``.

    Each step is read with the conditional branches merged in; when that finds nothing further down, it is read
    again without them.  The merge lets a branch replace a property (a ``then`` that restates ``connections`` with no
    ``items``), and the restated one must not hide the declaration that has the members.
    """
    if not steps:
        return effective_schema(schema, resolve, include_conditionals=True)
    tried: list[Any] = []
    for conditionals in (True, False):
        child = child_schema(effective_schema(schema, resolve, include_conditionals=conditionals), steps[0], additional=True)
        if child is None or child in tried:
            continue
        tried.append(child)
        found = _descend(child, resolve, steps[1:])
        if found is not None:
            return found
    return None


class SchemaSlots:
    """The effective schema of a node or leaf, read from the ``$schema`` of its file; the schema of each file is loaded once."""

    def __init__(self, repo_root: str) -> None:
        self._resolver = SchemaResolverCtx(repo_root)
        self._files: dict[str, tuple[Any, Any]] = {}

    def slot(self, graph: Graph, node: Node, leaf_path: str = "") -> dict[str, Any] | None:
        """The effective schema (``$ref`` and ``allOf`` merged, conditional branches included) at *leaf_path* below *node* (the node's own item when empty); ``None`` when the schema or the slot cannot be resolved."""
        if node.file not in self._files:
            document = graph.documents.get(node.file)
            raw = self._resolver.load_raw_schema(document) if isinstance(document, dict) else None
            self._files[node.file] = (raw, self._resolver.make_resolve_fn(raw)) if raw is not None else (None, None)
        schema, resolve = self._files[node.file]
        if schema is None:
            return None
        steps = path_steps(node.jq_path + leaf_path)
        if steps is None:
            return None
        return _descend(schema, resolve, steps)

    def has_property(self, graph: Graph, node: Node, name: str) -> bool:
        """Whether the item of *node* declares the property *name*."""
        slot = self.slot(graph, node)
        return slot is not None and name in slot.get("properties", {})
