"""Tests for the seed reader of ``graph.gitview`` (WI-M5-02)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.graph.gitview import GitViewError, commits_touching, is_shallow_repository, read_seed_texts, read_seed_texts_at
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph, Node

from ._synth import git


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


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    return tmp_path


def _commit_file(repo: Path, rel: str, text: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"{rel} {text}")
    return git(repo, "rev-parse", "HEAD")


def test_commits_touching_lists_only_commits_of_the_path_newest_first_and_capped(repo: Path) -> None:
    first = _commit_file(repo, "a.md", "one")
    _commit_file(repo, "b.md", "other")
    second = _commit_file(repo, "a.md", "two")
    assert commits_touching(str(repo), "a.md", 10) == [second, first]
    assert commits_touching(str(repo), "a.md", 1) == [second]


def test_commits_touching_outside_a_repository_is_e708(tmp_path: Path) -> None:
    with pytest.raises(GitViewError) as raised:
        commits_touching(str(tmp_path), "a.md", 5)
    assert raised.value.error.code == "E708"


def test_is_shallow_repository_is_false_for_a_normal_repository(repo: Path) -> None:
    _commit_file(repo, "a.md", "one")
    assert is_shallow_repository(str(repo)) is False


def test_read_seed_texts_at_reads_each_ref_from_the_repository_root(repo: Path) -> None:
    old = _commit_file(repo, "docs/seed/a.md", "old  text")
    _commit_file(repo, "docs/seed/a.md", "new text")
    graph = Graph.from_nodes([_seed("seed-a", "docs/seed/a.md")])
    assert read_seed_texts_at(old, str(repo), graph) == {"seed-a": "old text"}
    assert read_seed_texts_at("HEAD", str(repo), graph) == {"seed-a": "new text"}


def test_read_seed_texts_at_keeps_the_seeds_present_when_another_is_absent(repo: Path) -> None:
    _commit_file(repo, "present.md", "here")
    graph = Graph.from_nodes([_seed("seed-a", "present.md"), _seed("seed-b", "absent.md")])
    assert read_seed_texts_at("HEAD", str(repo), graph) == {"seed-a": "here"}


def test_read_seed_texts_at_unknown_ref_is_e708(repo: Path) -> None:
    _commit_file(repo, "present.md", "here")
    graph = Graph.from_nodes([_seed("seed-a", "present.md")])
    with pytest.raises(GitViewError) as raised:
        read_seed_texts_at("no-such-ref", str(repo), graph)
    assert raised.value.error.code == "E708"
