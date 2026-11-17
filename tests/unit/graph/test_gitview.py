"""Tests for the seed reader of ``graph.gitview`` (WI-M5-02)."""
from __future__ import annotations

from pathlib import Path

from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph, Node


def _seed(seed_id: str, path: str) -> Node:
    return Node(seed_id, SEED_KIND, "seed", None, path, "", None, (), "active", None, (), seed_id)


def test_read_seed_texts_resolves_against_host_root_and_collapses_whitespace(tmp_path: Path) -> None:
    (tmp_path / "docs" / "seed").mkdir(parents=True)
    (tmp_path / "docs" / "seed" / "a.md").write_text("  One\ttwo\n\n\nthree  \n", encoding="utf-8")
    graph = Graph.from_nodes([_seed("seed-a", "docs/seed/a.md")])
    assert read_seed_texts(graph, str(tmp_path)) == {"seed-a": "One two three"}


def test_read_seed_texts_omits_a_missing_file(tmp_path: Path) -> None:
    (tmp_path / "present.md").write_text("here", encoding="utf-8")
    graph = Graph.from_nodes([_seed("seed-a", "present.md"), _seed("seed-b", "absent.md"), _seed("seed-c", "../outside.md")])
    assert read_seed_texts(graph, str(tmp_path)) == {"seed-a": "here"}
