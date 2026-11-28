"""Shared readers of the worked example in ``tests/fixtures/graph_example`` (steps 00-16).

The example nodes are read through ``tools/entry_key_registry.json``, so the tests that use them follow the
schemas' ``x-link`` / ``x-entry-key`` annotations instead of a hand list of fields.
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Iterator, NamedTuple

from specdev_tools.core.entry_key_registry import iter_nodes, join_nested_path

ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "tests" / "fixtures" / "graph_example"
SPEC = EXAMPLE / "spec"
SEED_ID = "seed-accounts"


class Node(NamedTuple):
    """One entry of the example: its id, its registry kind, its stored item and the link rows of its kind."""

    node_id: str
    kind: str
    item: dict[str, Any]
    links: list[dict[str, Any]]


def load(name: str) -> dict[str, Any]:
    """Return the JSON document ``name`` (a path relative to the example's ``spec`` folder)."""
    return json.loads((SPEC / name).read_text(encoding="utf-8"))


def _entries(entries: list[dict[str, Any]], parent_path: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(full_array_path, registry_entry)`` for every entry, nested ones included."""
    for entry in entries:
        full = entry["array_path"] if parent_path is None else join_nested_path(parent_path, entry["array_path"])
        yield full, entry
        yield from _entries(entry.get("nested", []), full)


def _registry() -> dict[str, Any]:
    return json.loads((ROOT / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))["registry"]


def _registry_arrays(name: str) -> list[dict[str, Any]]:
    """The registry arrays of file ``name``; a plan file matches the glob key ``impl_context/ms_*_plan.json``."""
    registry = _registry()
    key = next(pattern for pattern in registry if fnmatch.fnmatchcase(name, pattern))
    return registry[key]["arrays"]


def nodes_of(names: tuple[str, ...]) -> list[Node]:
    """Every registry node of the given example files."""
    nodes: list[Node] = []
    for name in names:
        doc = load(name)
        for full, entry in _entries(_registry_arrays(name)):
            for item, _path, key in iter_nodes(doc, full):
                node_id = key if key is not None else item[entry["id_field"]]
                nodes.append(Node(node_id, entry["kind"], item, entry.get("links", [])))
    return nodes
