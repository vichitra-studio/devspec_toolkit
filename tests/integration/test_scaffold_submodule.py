"""The scaffold row path check on a host whose theme is a git submodule (WI-M6b-08, section 7 item 3)."""
from __future__ import annotations

from pathlib import Path

from specdev_tools.validation.graph_checks.scaffold import scaffold_scan, scaffold_rows_untracked
from unit.validation.graph_checks._git_support import SUBMODULE, clone_without_submodules, make_host_with_submodule
from unit.validation.graph_checks._scaffold_support import scaffold_context

ROWS = {
    "row-host-file": ("src/page.ts", ["api-1"]),
    "row-host-untracked": ("src/draft.ts", ["api-1"]),
    "row-theme-file": (f"{SUBMODULE}/style.css", ["api-1"]),
    "row-theme-untracked": (f"{SUBMODULE}/robots.txt", ["api-1"]),
    "row-unbuilt-api": ("src/other.ts", ["api-2"]),
}


def _flagged(context, mode="close") -> list[str | None]:
    return [error.node_id for error in scaffold_rows_untracked(context, None, mode)]


def test_submodule_layout_tracked_untracked_uninitialised_and_merge_filter(tmp_path: Path) -> None:
    host = make_host_with_submodule(tmp_path, {"src/page.ts": "page"}, {"style.css": "css"})
    (host / "src" / "draft.ts").write_text("draft", encoding="utf-8")
    (host / SUBMODULE / "robots.txt").write_text("untracked in the submodule", encoding="utf-8")

    context = scaffold_context(ROWS, host, built=["api-1"])
    assert _flagged(context) == ["row-host-untracked", "row-theme-untracked", "row-unbuilt-api"]
    assert _flagged(context, "merge") == ["row-host-untracked", "row-theme-untracked"]

    clone = clone_without_submodules(host, tmp_path / "clone")
    scan = scaffold_scan(scaffold_context(ROWS, clone, built=["api-1"]), None, "close")
    assert [error.node_id for error in scan.findings] == ["row-host-untracked", "row-unbuilt-api"]
    assert len(scan.notes) == 2 and all(SUBMODULE in note for note in scan.notes)
