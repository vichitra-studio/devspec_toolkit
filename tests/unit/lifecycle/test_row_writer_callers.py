"""Exit criterion 2 of M8: the anchor row's status and close record are written by the lifecycle commands only.

An AST walk over ``tools/specdev_tools/**/*.py``: a call, a reference or an import of ``write_row_state`` or ``append_close_migration``
outside ``lifecycle/`` is a finding.  The walk is shown to see a caller (``milestone.py`` calls the writer) and a stranger (a synthetic source).
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "specdev_tools"
WRITERS = frozenset({"write_row_state", "append_close_migration"})
LIFECYCLE = TOOLS / "lifecycle"


def _uses(source: str) -> list[str]:
    """The writers *source* imports, names or accesses as an attribute."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom | ast.Import):
            found += [alias.name.split(".")[-1] for alias in node.names if alias.name.split(".")[-1] in WRITERS]
        elif isinstance(node, ast.Name) and node.id in WRITERS:
            found.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in WRITERS:
            found.append(node.attr)
    return found


def _callers() -> dict[str, list[str]]:
    return {path.relative_to(ROOT).as_posix(): uses for path in sorted(TOOLS.rglob("*.py")) if (uses := _uses(path.read_text(encoding="utf-8")))}


def test_the_walk_sees_a_caller_and_a_stranger() -> None:
    assert "write_row_state" in _callers()["tools/specdev_tools/lifecycle/milestone.py"]
    assert _uses("from specdev_tools.lifecycle import anchor_store\nanchor_store.write_row_state(a)") == ["write_row_state"]
    assert _uses("from specdev_tools.lifecycle.anchor_store import append_close_migration as add") == ["append_close_migration"]


def test_the_row_writers_are_called_only_from_the_lifecycle_package() -> None:
    outside = {path: uses for path, uses in _callers().items() if not (ROOT / path).is_relative_to(LIFECYCLE)}
    assert outside == {}
