"""Synthetic toolkit and spec folders for the graph tests.

``make_toolkit`` copies the mini spec-graph toolkit (``tests/fixtures/graph/mini_toolkit``: a nested array, a map-keyed
collection, a plan file, a record file and the seed manifest) and generates its registry.  ``copy_build_spec`` copies the
spec folder ``tests/fixtures/graph/synthetic/builder`` that matches it.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.registry.generate import generate_registry

ROOT = Path(__file__).parents[3]
MINI_TOOLKIT = ROOT / "tests" / "fixtures" / "graph" / "mini_toolkit"
BUILD_SPEC = ROOT / "tests" / "fixtures" / "graph" / "synthetic" / "builder"
_CORE_SCHEMAS = ("graph", "atoms", "collections")


def make_toolkit(dest: Path) -> Path:
    """Copy the mini toolkit to *dest*, add the real core schemas and step order, write its generated registry."""
    shutil.copytree(MINI_TOOLKIT, dest)
    for name in _CORE_SCHEMAS:
        shutil.copy(ROOT / "schema" / "core" / f"{name}.schema.json", dest / "schema" / "core")
    shutil.copy(ROOT / "tools" / "step_order.json", dest / "tools")
    shutil.copy(ROOT / "schema" / "step_order.schema.json", dest / "schema")
    clear_shared_caches()
    registry, _extraction = generate_registry(str(dest))
    write_json(dest, "tools/entry_key_registry.json", registry)
    return dest


def copy_build_spec(dest: Path) -> Path:
    """Copy the synthetic build spec folder to *dest* and return it."""
    shutil.copytree(BUILD_SPEC, dest)
    return dest


def write_json(root: Path, rel: str, document: Any) -> None:
    """Write *document* as JSON to ``root/rel``, creating folders."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
