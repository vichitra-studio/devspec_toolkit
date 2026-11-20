"""Tests for the seed reader of ``graph.gitview`` (WI-M5-02)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.graph.gitview import (
    GitViewError,
    commits_touching,
    git_top_level,
    is_shallow_repository,
    folder_exists_at,
    path_exists_at,
    read_seed_texts,
    read_seed_texts_at,
    relative_inside,
    spec_path_in_repo,
)
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


def test_git_top_level_of_a_nested_folder_is_the_repository_top(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert git_top_level(str(nested)) == str(tmp_path.resolve())


def test_git_top_level_is_none_outside_a_repository_and_for_a_missing_folder(tmp_path: Path) -> None:
    assert git_top_level(str(tmp_path)) is None
    assert git_top_level(str(tmp_path / "missing")) is None


def test_relative_inside_answers_the_path_below_the_root_or_none(tmp_path: Path) -> None:
    (tmp_path / "root" / "sub").mkdir(parents=True)
    root = str(tmp_path / "root")
    assert relative_inside(root, str(tmp_path / "root" / "sub")) == "sub"
    assert relative_inside(root, root) == "."
    assert relative_inside(root, str(tmp_path / "other")) is None
    assert relative_inside(root, str(tmp_path / "root" / ".." / "root-sibling")) is None


def test_relative_inside_follows_symlinks(tmp_path: Path) -> None:
    (tmp_path / "root" / "real").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "root" / "real")
    assert relative_inside(str(tmp_path / "root"), str(tmp_path / "link")) == "real"


def test_relative_inside_follows_a_symlinked_root(tmp_path: Path) -> None:
    (tmp_path / "real" / "spec").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    assert relative_inside(str(tmp_path / "link"), str(tmp_path / "real" / "spec")) == "spec"
    assert relative_inside(str(tmp_path / "real"), str(tmp_path / "link" / "spec")) == "spec"


def test_spec_path_in_repo_raises_where_relative_inside_is_none(tmp_path: Path) -> None:
    (tmp_path / "host").mkdir()
    with pytest.raises(GitViewError, match="not inside the git root"):
        spec_path_in_repo(str(tmp_path / "elsewhere"), str(tmp_path / "host"))


def test_path_exists_at_is_false_only_when_git_says_the_path_is_absent(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "a")
    assert path_exists_at("HEAD", str(tmp_path), "docs/a.md") is True
    assert path_exists_at("HEAD", str(tmp_path), "docs/b.md") is False
    with pytest.raises(GitViewError):
        path_exists_at("no-such-ref", str(tmp_path), "docs/a.md")


def test_folder_exists_at_is_true_for_a_folder_only(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "spec").write_text("a file", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "a")
    assert folder_exists_at("HEAD", str(tmp_path), "docs") is True
    assert folder_exists_at("HEAD", str(tmp_path), "docs/a.md") is False
    assert folder_exists_at("HEAD", str(tmp_path), "spec") is False
    assert folder_exists_at("HEAD", str(tmp_path), "nope") is False
    assert path_exists_at("HEAD", str(tmp_path), "spec") is True


@pytest.mark.parametrize(("path", "expected"), [
    (".", True), ("./", True), ("", True), ("docs/..", True),
    ("docs", True), ("docs/", True), ("./docs", True),
    ("docs/a.md", False), ("spec", False), ("nope", False),
])
def test_folder_exists_at_answers_the_root_of_a_commit_and_normalises_the_path(tmp_path: Path, path: str, expected: bool) -> None:
    """``git ls-tree <commit> -- .`` lists the root's content, not a tree line: the root is a folder by definition."""
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "spec").write_text("a file", encoding="utf-8")
    (tmp_path / "0.txt").write_text("sorts first: ls-tree of the root lists this line, not a tree", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "a")
    assert folder_exists_at("HEAD", str(tmp_path), path) is expected


def test_folder_exists_at_the_root_still_raises_for_a_ref_that_does_not_resolve(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    with pytest.raises(GitViewError):
        folder_exists_at("no-such-ref", str(tmp_path), ".")


def test_folder_exists_at_dot_asks_about_the_git_root_folder_when_it_is_a_subfolder_of_the_repository(tmp_path: Path) -> None:
    """``.`` is the repository top only when *git_root* is the top: a subfolder is a folder at a commit only if the commit holds it."""
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "README.md").write_text("r", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "readme")
    (tmp_path / "host").mkdir()
    (tmp_path / "host" / "a.md").write_text("a", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "host")
    assert folder_exists_at("HEAD", str(tmp_path / "host"), ".") is True
    assert folder_exists_at("HEAD~1", str(tmp_path / "host"), ".") is False
    assert folder_exists_at("HEAD~1", str(tmp_path), ".") is True
