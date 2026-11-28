"""Support for the proposer tests (WI-M10-09): a copy of the invented gold set, a tree loaded from it, an edit of one of its files."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.proposers import MigratedTree, load_tree
from specdev_tools.migration.writer import DocumentSet

from ._support import REAL_ROOT

GOLD = REAL_ROOT / "tests" / "fixtures" / "migration" / "refines_gold"


def copy_gold(tmp_path: Path) -> Path:
    """A copy of ``refines_gold`` under *tmp_path* (the host folder; its spec folder is ``<host>/spec``)."""
    host = tmp_path / "gold"
    shutil.copytree(GOLD, host)
    (host / "README.md").unlink()
    return host


def tree_of(host: Path) -> MigratedTree:
    """The tree a proposer reads for the spec folder of *host*, against the live toolkit."""
    spec = str(host / "spec")
    ctx = MigrationContext(spec, str(host), str(host), str(REAL_ROOT), False, DocumentSet(spec), "1.1.1", "1.1.1")
    return load_tree(ctx)


def edit(host: Path, rel: str, change: Callable[[Any], None]) -> None:
    """Rewrite the JSON file ``spec/<rel>`` of *host* after *change* edited its parsed content in place."""
    path = host / "spec" / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def labels(host: Path) -> dict[str, dict[str, Any]]:
    """The gold labels: task criterion id to ``{half, refines, shape}``."""
    return json.loads((host / "gold.json").read_text(encoding="utf-8"))["criteria"]


def task_criterion(data: Any, criterion_id: str) -> dict[str, Any]:
    """The task criterion *criterion_id* of a parsed ``14_roadmap.json``."""
    return next(c for m in data["milestones"] for t in m["tasks"] for c in t["acceptance_criteria"] if c["criterion_id"] == criterion_id)
