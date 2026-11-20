"""M6c WI-07: the M3 legacy shim is gone, and so is the ``shim`` column of the schema-change rows.

The exit-criterion test of the item, not a repo-wide scanner: the module cannot be imported, its test file is gone,
no ``.py`` under ``tools/`` or ``tests/`` imports it, and no row of ``tools/schema_changes.json`` carries a ``shim`` key.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The name the WI-01 checklist gave the shim; asserted first so that a renamed shim cannot pass vacuously.
SHIM_NAME = "_legacy_shim"
SHIM_MODULE = f"specdev_tools.validation.{SHIM_NAME}"
SHIM_TEST = ROOT / "tests" / "unit" / "validation" / "test_legacy_shim.py"


def test_shim_module_is_gone_under_the_checklist_name() -> None:
    assert SHIM_MODULE == "specdev_tools.validation._legacy_shim"
    assert importlib.util.find_spec(SHIM_MODULE) is None
    assert not (ROOT / "tools" / "specdev_tools" / "validation" / f"{SHIM_NAME}.py").exists()


def test_shim_test_file_is_gone() -> None:
    assert not SHIM_TEST.exists()


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def test_nothing_imports_the_shim() -> None:
    importers = [
        path.relative_to(ROOT).as_posix()
        for folder in ("tools", "tests")
        for path in (ROOT / folder).rglob("*.py")
        if any(name.split(".")[-1] == SHIM_NAME for name in _imported_names(path))
    ]
    assert importers == []


def test_no_schema_change_row_has_a_shim_key() -> None:
    rows = json.loads((ROOT / "tools" / "schema_changes.json").read_text(encoding="utf-8"))["rows"]
    assert rows
    assert [row["id"] for row in rows if "shim" in row] == []
