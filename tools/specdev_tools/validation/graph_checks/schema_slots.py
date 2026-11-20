"""The schema slot of a node or of one of its leaves: what the schema of the node's file says about the value there.

Shared by the prose check (a leaf that is a fixed value) and the no-dangling advice (a kind that has a ``scope`` field).
"""
from __future__ import annotations

import json
from typing import Any

from specdev_tools.core.schema_nav import child_schema, effective_schema
from specdev_tools.graph.contract import PATH_STEP
from specdev_tools.graph.model import Graph, Node
from specdev_tools.validation.hallucination_lint import SchemaResolverCtx


def _steps(path: str) -> list[str | int]:
    """The object keys and array indexes of a jq path, in order."""
    steps: list[str | int] = []
    for name, index, quoted in PATH_STEP.findall(path):
        steps.append(name or (int(index) if index else json.loads(quoted)))
    return steps


class SchemaSlots:
    """The effective schema of a node or leaf, read from the ``$schema`` of its file; the schema of each file is loaded once."""

    def __init__(self, repo_root: str) -> None:
        self._resolver = SchemaResolverCtx(repo_root)
        self._files: dict[str, tuple[Any, Any]] = {}

    def slot(self, graph: Graph, node: Node, leaf_path: str = "") -> dict[str, Any] | None:
        """The effective schema (``$ref`` and ``allOf`` merged, conditional branches included) at *leaf_path* below *node* (the node's own item when empty); ``None`` when the schema or the slot cannot be resolved."""
        if node.file not in self._files:
            document = graph.documents.get(node.file)
            self._files[node.file] = self._resolver.load_file_schema(document) if isinstance(document, dict) else (None, None)
        schema, resolve = self._files[node.file]
        if schema is None:
            return None
        for step in _steps(node.jq_path + leaf_path):
            schema = child_schema(effective_schema(schema, resolve, include_conditionals=True), step, additional=True)
            if schema is None:
                return None
        return effective_schema(schema, resolve, include_conditionals=True)

    def has_property(self, graph: Graph, node: Node, name: str) -> bool:
        """Whether the item of *node* declares the property *name*."""
        slot = self.slot(graph, node)
        return slot is not None and name in slot.get("properties", {})
