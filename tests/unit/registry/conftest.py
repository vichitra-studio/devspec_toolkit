"""Shared fixtures for the registry tests: the mini spec-graph toolkit and a JSON editor."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_MINI = _ROOT / "tests" / "fixtures" / "graph" / "mini_toolkit"
_CORE_SCHEMAS = ("graph", "atoms", "collections")

EditJson = Callable[[Path, str, Callable[[dict], None]], None]


def _edit_json(root: Path, rel: str, fn: Callable[[dict], None]) -> None:
    """Load the JSON file ``root/rel``, apply *fn* to it in place and write it back."""
    path = root / rel
    doc = json.loads(path.read_text())
    fn(doc)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def _build_mini_toolkit(dest: Path) -> Path:
    """Copy the mini toolkit to *dest* plus the real core schemas and step order it needs."""
    shutil.copytree(_MINI, dest)
    for name in _CORE_SCHEMAS:
        shutil.copy(_ROOT / "schema" / "core" / f"{name}.schema.json", dest / "schema" / "core")
    shutil.copy(_ROOT / "tools" / "step_order.json", dest / "tools")
    shutil.copy(_ROOT / "schema" / "step_order.schema.json", dest / "schema")
    return dest


@pytest.fixture
def edit_json() -> EditJson:
    """``edit_json(root, rel, fn)``: edit a JSON file of a temporary toolkit in place."""
    return _edit_json


@pytest.fixture
def mini_toolkit_at() -> Callable[[Path], Path]:
    """``mini_toolkit_at(dest)``: copy of the mini toolkit at *dest*, with the real core schemas."""
    return _build_mini_toolkit


@pytest.fixture
def mini_toolkit(tmp_path: Path) -> Path:
    """The mini fixture toolkit in a temporary directory."""
    return _build_mini_toolkit(tmp_path / "tk")
