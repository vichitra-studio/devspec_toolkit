"""The code tree id: what changes it, what does not, and the warning for a submodule with uncommitted content."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core.errors import make_error
from specdev_tools.graph.gitview import GitViewError, archive_ref
from specdev_tools.verify import code_tree
from specdev_tools.verify.code_tree import code_tree_for_host, submodule_warnings
from unit.graph._synth import git

from ._support import SEED_PATH, code_repo, commit_all, set_mtime_now, write


def _id(repo: Path, commit: str | None = None) -> str:
    return code_tree_for_host(str(repo), str(repo / "spec"), commit)


def test_spec_root_write_does_not_change_the_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    before = _id(repo)
    write(repo / "spec" / "x.json", '{"note": "edited"}\n')
    write(repo / "spec" / "extras" / "verification" / "evd-new.json", "{}\n")
    assert _id(repo) == before


def test_seed_path_edit_does_not_change_the_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    before = _id(repo)
    write(repo / "docs" / "seed.md", "seed, edited\n")
    assert _id(repo) == before


def test_src_edit_changes_the_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    before = _id(repo)
    write(repo / "src" / "app.py", "print('edited')\n")
    assert _id(repo) != before


def test_declared_exclusion_does_not_change_the_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path, declarations={"code_tree_exclusions": ["generated/"]})
    write(repo / "generated" / "report.txt", "one\n")
    commit_all(repo)
    before = _id(repo)
    write(repo / "generated" / "report.txt", "two\n")
    write(repo / "generated" / "more.txt", "new\n")
    assert _id(repo) == before


def test_gitignored_tracked_file_edit_changes_the_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    write(repo / ".gitignore", "built.txt\n")
    write(repo / "built.txt", "one\n")
    git(repo, "add", "-f", "built.txt", ".gitignore")
    git(repo, "commit", "-q", "-m", "track an ignored file")
    before = _id(repo)
    write(repo / "built.txt", "two\n")
    assert _id(repo) != before


def test_untracked_new_file_changes_the_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    before = _id(repo)
    write(repo / "src" / "new.py", "print('new')\n")
    assert _id(repo) != before


def test_two_clones_at_one_commit_give_one_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    first, second = tmp_path / "clone-a", tmp_path / "clone-b"
    git(tmp_path, "clone", "-q", str(repo), str(first))
    git(tmp_path, "clone", "-q", str(repo), str(second))
    assert _id(first) == _id(second) == _id(repo)


def _repo_with_submodule(tmp_path: Path) -> tuple[Path, Path]:
    library = tmp_path / "library"
    library.mkdir()
    git(library, "init", "-q", "-b", "main")
    write(library / "lib.py", "one\n")
    commit_all(library, "library")
    repo = code_repo(tmp_path)
    git(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "theme")
    git(repo, "commit", "-q", "-m", "add the submodule")
    return repo, repo / "theme"


def test_submodule_gitlink_move_changes_the_id(tmp_path: Path) -> None:
    repo, theme = _repo_with_submodule(tmp_path)
    before = _id(repo)
    write(theme / "lib.py", "two\n")
    git(theme, "add", "-A")
    git(theme, "commit", "-q", "-m", "move the pointer")
    assert _id(repo) != before


def test_dirty_submodule_warns_w350(tmp_path: Path) -> None:
    repo, theme = _repo_with_submodule(tmp_path)
    assert submodule_warnings(str(repo)) == []
    write(theme / "lib.py", "uncommitted\n")
    warnings = submodule_warnings(str(repo))
    assert [(error.code, "'theme'" in error.message) for error in warnings] == [("W350", True)]


def test_linked_worktree_gives_the_main_checkout_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    worktree = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", "-b", "other", str(worktree))
    assert (worktree / ".git").is_file()
    assert _id(worktree) == _id(repo)


def test_id_ignores_mtime_and_index_state(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    before = _id(repo)
    set_mtime_now(repo / "src" / "app.py")
    git(repo, "update-index", "--refresh")
    write(repo / "scratch.txt", "staged then removed\n")
    git(repo, "add", "scratch.txt")
    (repo / "scratch.txt").unlink()
    git(repo, "rm", "-q", "--cached", "scratch.txt")
    assert _id(repo) == before


def test_seed_directory_is_excluded_whole(tmp_path: Path) -> None:
    repo = code_repo(tmp_path, seeds=("docs/seeds",))
    write(repo / "docs" / "seeds" / "one.md", "one\n")
    write(repo / "docs" / "seeds" / "two.md", "two\n")
    commit_all(repo)
    before = _id(repo)
    write(repo / "docs" / "seeds" / "one.md", "edited\n")
    write(repo / "docs" / "seeds" / "three.md", "new\n")
    assert _id(repo) == before


def test_seed_outside_git_root_is_skipped(tmp_path: Path) -> None:
    repo = code_repo(tmp_path, seeds=("../elsewhere/seed.md", SEED_PATH))
    write(tmp_path / "elsewhere" / "seed.md", "outside\n")
    before = _id(repo)
    write(repo / "src" / "app.py", "print('edited')\n")
    assert _id(repo) != before


def test_commit_id_equals_clean_checkout_id_and_later_edit_changes_only_the_working_tree_id(tmp_path: Path) -> None:
    repo = code_repo(tmp_path)
    git(repo, "tag", "v1")
    checkout = tmp_path / "checkout"
    git(tmp_path, "clone", "-q", str(repo), str(checkout))
    git(checkout, "checkout", "-q", "v1")
    tagged = _id(repo, "v1")
    assert tagged == _id(checkout)
    write(repo / "src" / "app.py", "print('later')\n")
    assert _id(repo, "v1") == tagged
    assert _id(repo) != tagged


def test_a_repository_with_no_commit_has_an_id_that_follows_its_files(tmp_path: Path) -> None:
    repo = tmp_path / "fresh"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo / "src" / "app.py", "print('app')\n")
    first = _id(repo)
    assert first == _id(repo)
    write(repo / "src" / "app.py", "print('changed')\n")
    assert _id(repo) != first


def test_an_archived_spec_names_the_live_folder_to_leave_out_and_gives_the_live_id(tmp_path: Path) -> None:
    """A spec read from an archive of a past commit lies outside the host: without ``spec_in_host`` its folder would stay in the tree."""
    repo = code_repo(tmp_path)
    git(repo, "tag", "v1")
    live = _id(repo, "v1")
    write(repo / "src" / "app.py", "print('later')\n")
    commit_all(repo, "later")
    with archive_ref("v1", str(repo), ["spec"]) as archived:
        spec = str(Path(archived) / "spec")
        assert code_tree_for_host(str(repo), spec, "v1", spec_in_host=str(repo / "spec")) == live
        assert code_tree_for_host(str(repo), spec, "v1") != live
        assert code_tree_for_host(str(repo), str(repo / "spec"), "v1", spec_in_host=None) == live  # the default is unchanged


def test_a_commit_whose_spec_differs_from_head_gives_the_id_of_its_clean_checkout(tmp_path: Path) -> None:
    """The spec folder at the commit may differ from HEAD's and from the working tree: the id is still the commit's, and nothing real is touched."""
    repo = code_repo(tmp_path)
    write(repo / "spec" / "x.json", '{"note": "at the tag"}\n')
    commit_all(repo, "spec at the tag")
    tagged = git(repo, "rev-parse", "HEAD")
    clean = _id(repo, tagged)
    write(repo / "spec" / "x.json", '{"note": "at head"}\n')
    commit_all(repo, "spec at head")
    write(repo / "spec" / "x.json", '{"note": "in the working tree"}\n')
    files = {path: path.read_bytes() for path in repo.rglob("*") if path.is_file() and ".git" not in path.parts and path.name != "index"}
    index, status = (repo / ".git" / "index").read_bytes(), git(repo, "status", "--porcelain")
    assert _id(repo, tagged) == clean
    assert {path: path.read_bytes() for path in files} == files and (repo / ".git" / "index").read_bytes() == index
    assert git(repo, "status", "--porcelain") == status
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(repo), str(clone))
    git(clone, "checkout", "-q", tagged)
    assert _id(clone) == clean


def test_a_submodule_git_cannot_ask_counts_as_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_has_changes`` answers ``False`` when git cannot list the submodule's status: no W350 for it (pinned as built)."""
    repo, theme = _repo_with_submodule(tmp_path)
    write(theme / "lib.py", "uncommitted\n")
    assert [error.code for error in submodule_warnings(str(repo))] == ["W350"]

    def cannot_ask(folder: str) -> list[str]:
        raise GitViewError(make_error("E708", "git cannot answer"))

    monkeypatch.setattr(code_tree, "status_lines", cannot_ask)
    assert submodule_warnings(str(repo)) == []

