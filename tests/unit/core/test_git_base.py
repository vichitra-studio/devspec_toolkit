"""Tests for the git baseline of the step gate (WI-M6a-02)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core import git_base
from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import (
    BaselineResult,
    active_baseline_provider,
    materialise_baseline,
    merge_base_provider,
    register_baseline_provider,
    resolve_baseline,
    resolve_target_branch,
)
from specdev_tools.graph.gitview import GitViewError

from ..graph._synth import git

SEED = "docs/seeds/charter.md"
SPEC = "spec"
LOCK = "spec/extras/trace.lock.json"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str, **files: str) -> str:
    for rel, text in files.items():
        _write(repo, rel.replace("__", "/"), text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "host"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    return root


@pytest.fixture(autouse=True)
def _restore_provider():
    saved = active_baseline_provider()
    yield
    register_baseline_provider(saved)


def _base_files(repo: Path, spec: str = SPEC) -> str:
    return _commit(
        repo,
        "base",
        **{
            SEED.replace("/", "__"): "charter v1",
            f"{spec}/01_x.json".replace("/", "__"): "{}",
            f"{spec}/extras/trace.lock.json".replace("/", "__"): "lock v1",
            f"{spec}/common/canon/project.json".replace("/", "__"): "canon v1",
        },
    )


def test_target_is_merge_base_with_default_branch_not_upstream(repo: Path, tmp_path: Path) -> None:
    base = _base_files(repo)
    _commit(repo, "main moves on", main_only="x")
    git(repo, "checkout", "-q", "-b", "feature", base)
    feature_first = _commit(repo, "feature one", f1="1")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "feature:feature")
    git(repo, "branch", "-q", "--set-upstream-to=origin/feature", "feature")
    git(repo, "fetch", "-q", "origin")
    _commit(repo, "feature two", f2="2")

    resolution = resolve_baseline(str(repo))

    assert resolution.ref == "main"
    assert resolution.commit == base
    assert resolution.commit != feature_first
    assert resolution.mode == "merge-base"
    assert resolution.describe() == f"base: main {base[:12]} (merge-base)"


def test_origin_head_wins_over_the_candidate_list(repo: Path, tmp_path: Path) -> None:
    _base_files(repo)
    git(repo, "branch", "-q", "trunk")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "trunk:trunk")
    git(repo, "fetch", "-q", "origin")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")

    assert resolve_target_branch(str(repo)) == "origin/trunk"


def test_flag_wins_over_environment_and_environment_over_discovery(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base_files(repo)
    monkeypatch.setenv("SPECDEV_REPLAY_BASE_REF", "from-env")
    assert resolve_target_branch(str(repo), "from-flag") == "from-flag"
    assert resolve_target_branch(str(repo)) == "from-env"


def test_no_default_branch_gives_unavailable(repo: Path) -> None:
    _commit(repo, "only", a="1")
    git(repo, "branch", "-q", "-m", "odd")
    resolution = resolve_baseline(str(repo))
    assert (resolution.commit, resolution.mode) == (None, "unavailable")
    assert resolution.describe() == "base: unavailable"


def test_head_on_default_branch_gives_mode_head(repo: Path) -> None:
    head = _base_files(repo)
    resolution = resolve_baseline(str(repo))
    assert (resolution.commit, resolution.mode, resolution.note) == (head, "head", None)


def test_head_on_another_branch_adds_a_note(repo: Path) -> None:
    head = _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    resolution = resolve_baseline(str(repo))
    assert (resolution.commit, resolution.mode) == (head, "head")
    assert resolution.note


def test_no_git_repository_gives_unavailable(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    (plain / SPEC).mkdir(parents=True)
    provider = merge_base_provider(lambda *_: [], lambda _: [])

    result = provider(plain / SPEC, str(plain))

    assert result.mode == "unavailable"
    assert result.errors == ()
    assert result.resolution is not None and result.resolution.describe() == "base: unavailable"


def test_shallow_clone_without_merge_base_gives_unavailable(repo: Path, tmp_path: Path) -> None:
    _base_files(repo)
    _commit(repo, "second", a="1")
    _commit(repo, "third", b="1")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "--depth", "1", repo.as_uri(), str(clone))
    git(clone, "checkout", "-q", "-b", "feature")
    git(clone, "branch", "-q", "-D", "main")
    git(clone, "update-ref", "-d", "refs/remotes/origin/main")
    assert resolve_baseline(str(clone)).mode == "unavailable"


def _tree_files(root: Path) -> dict[str, str]:
    files = {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}
    return {rel: p.read_text(encoding="utf-8") for rel, p in files.items() if not rel.startswith(".git/")}


@pytest.mark.parametrize("spec", ["spec", "sub/spec"], ids=["flat", "nested"])
def test_baseline_tree_reproduces_git_root_layout(repo: Path, spec: str) -> None:
    commit = _base_files(repo, spec)
    expected = _tree_files(repo)

    with materialise_baseline(str(repo), commit, repo / spec, [SEED]) as tree:
        assert _tree_files(tree.root) == expected
        assert tree.spec_dir == tree.root / spec


@pytest.mark.parametrize("spec", ["spec", "sub/spec"], ids=["flat", "nested"])
def test_baseline_tree_contains_seed_and_lock_as_of_the_commit(repo: Path, spec: str) -> None:
    commit = _base_files(repo, spec)
    _commit(repo, "edits", **{SEED.replace("/", "__"): "charter v2", f"{spec}/extras/trace.lock.json".replace("/", "__"): "lock v2"})

    with materialise_baseline(str(repo), commit, repo / spec, [SEED]) as tree:
        assert (tree.root / SEED).read_text(encoding="utf-8") == "charter v1"
        assert (tree.spec_dir / "extras" / "trace.lock.json").read_text(encoding="utf-8") == "lock v1"


def test_baseline_tree_through_a_symlinked_spec_folder(repo: Path, tmp_path: Path) -> None:
    commit = _base_files(repo, "sub/spec")
    link = tmp_path / "link"
    link.symlink_to(repo / "sub" / "spec")

    with materialise_baseline(str(repo), commit, link, [SEED]) as tree:
        assert (tree.root / "sub/spec/01_x.json").is_file()


def test_baseline_tree_with_git_root_below_the_repository_top(repo: Path) -> None:
    _base_files(repo, "sub/spec")
    host = repo / "sub"
    _write(repo, "sub/seed.md", "seed")
    commit = _commit(repo, "seed below")

    with materialise_baseline(str(host), commit, host / "spec", ["seed.md"]) as tree:
        assert (tree.root / "seed.md").read_text(encoding="utf-8") == "seed"
        assert (tree.root / "spec/01_x.json").is_file()


def test_seed_added_on_the_branch_is_left_out_of_the_baseline(repo: Path) -> None:
    commit = _base_files(repo)
    _commit(repo, "new seed", **{"docs__seeds__added.md": "later"})

    with materialise_baseline(str(repo), commit, repo / SPEC, [SEED, "docs/seeds/added.md"]) as tree:
        assert (tree.root / SEED).is_file()
        assert not (tree.root / "docs/seeds/added.md").exists()


def test_spec_folder_absent_at_base_gives_unavailable(repo: Path) -> None:
    _commit(repo, "no spec yet", readme="x")
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "spec arrives", spec__01_x__json="{}")
    seen: list[Path] = []
    provider = merge_base_provider(lambda root, _spec: seen.append(root) or [], lambda _: [])

    result = provider(repo / SPEC, str(repo))

    assert result.mode == "unavailable"
    assert seen == []
    with pytest.raises(GitViewError):
        materialise_baseline(str(repo), git(repo, "rev-parse", "HEAD~1"), repo / SPEC, [])


def test_provider_runs_the_checks_on_the_baseline_tree_and_deletes_it(repo: Path) -> None:
    base = _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "edit", **{SEED.replace("/", "__"): "charter v2"})
    seen: list[tuple[Path, str]] = []
    error = SpecError(code="E999", message="m")

    def checks(root: Path, spec_dir: Path) -> list[SpecError]:
        seen.append((root, (root / SEED).read_text(encoding="utf-8")))
        assert spec_dir == root / SPEC
        return [error]

    result = merge_base_provider(checks, lambda _: [SEED])(repo / SPEC, str(repo))

    assert result.mode == "ok"
    assert result.errors == (error,)
    assert result.resolution is not None and result.resolution.commit == base
    assert seen[0][1] == "charter v1"
    assert not seen[0][0].exists()


def test_registered_provider_replaces_the_default(tmp_path: Path) -> None:
    assert active_baseline_provider()(tmp_path, str(tmp_path)).mode == "unavailable"
    stub = BaselineResult("ok", (SpecError(code="E1", message="m"),))
    register_baseline_provider(lambda _spec, _root: stub)

    assert git_base.active_baseline_provider()(tmp_path, str(tmp_path)) is stub
