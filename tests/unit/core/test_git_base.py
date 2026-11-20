"""Tests for the git baseline of the step gate (WI-M6a-02)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core import git_base
from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import (
    host_paths_in,
    materialise_baseline,
    merge_base_provider,
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


def test_head_on_another_branch_says_only_uncommitted_changes_count(repo: Path) -> None:
    head = _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    resolution = resolve_baseline(str(repo))
    assert (resolution.commit, resolution.mode) == (head, "head")
    assert resolution.note == "the baseline is HEAD itself: only uncommitted changes count as new"


def test_head_on_a_slashed_default_branch_adds_no_note(repo: Path, tmp_path: Path) -> None:
    """``release/1.0`` against ``origin/release/1.0``: the full branch name is compared, not the last path part."""
    _base_files(repo)
    git(repo, "checkout", "-q", "-b", "release/1.0")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "release/1.0:release/1.0")
    git(repo, "fetch", "-q", "origin")

    assert resolve_baseline(str(repo), "origin/release/1.0").note is None
    assert resolve_baseline(str(repo), "release/1.0").note is None


def test_a_target_that_only_ends_like_the_branch_still_gets_the_note(repo: Path) -> None:
    """Branch ``main`` against the local branch ``feature/main``: ``feature`` is no remote, so the names differ."""
    _base_files(repo)
    git(repo, "branch", "feature/main")
    assert resolve_baseline(str(repo), "feature/main").note == "the baseline is HEAD itself: only uncommitted changes count as new"


def test_every_unavailable_baseline_carries_its_reason(repo: Path, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert resolve_baseline(str(plain)).note == "not a git repository"
    assert resolve_baseline(str(repo)).note == "no commit yet"
    _base_files(repo)
    assert resolve_baseline(str(repo), "nope").note == "nope does not name a commit"
    assert resolve_baseline(str(repo), "--evil").note == "--evil does not name a commit"
    git(repo, "branch", "-q", "-m", "odd")
    assert resolve_baseline(str(repo)).note == "no base ref found (origin/main, origin/master, main, master); pass --base-ref"


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


def test_unrelated_history_says_no_common_history(repo: Path) -> None:
    _base_files(repo)
    git(repo, "checkout", "-q", "--orphan", "other")
    _commit(repo, "unrelated", z="1")
    resolution = resolve_baseline(str(repo), "main")
    assert (resolution.mode, resolution.note) == ("unavailable", "no common history with main (a shallow clone?)")


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


def test_a_git_failure_other_than_an_absent_seed_propagates(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commit = _base_files(repo)

    def failing(*_args: object) -> bool:
        raise GitViewError(SpecError(code="E708", message="git broke"))

    monkeypatch.setattr(git_base, "path_exists_at", failing)
    with pytest.raises(GitViewError, match="git broke"):
        materialise_baseline(str(repo), commit, repo / SPEC, ["docs/seeds/absent.md"])


def test_spec_folder_absent_at_base_gives_unavailable(repo: Path) -> None:
    _commit(repo, "no spec yet", readme="x")
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "spec arrives", spec__01_x__json="{}")
    seen: list[Path] = []
    provider = merge_base_provider(lambda root, _spec: seen.append(root) or [], lambda _: [])

    result = provider(repo / SPEC, str(repo))

    assert result.mode == "unavailable"
    assert seen == []
    assert result.resolution is not None and result.resolution.commit is not None
    assert result.resolution.note == (
        f"the spec folder is not in the base commit {result.resolution.commit[:12]}: every error of an earlier step counts as new"
    )
    with pytest.raises(GitViewError):
        materialise_baseline(str(repo), git(repo, "rev-parse", "HEAD~1"), repo / SPEC, [])


@pytest.mark.parametrize("failure", [ValueError("boom"), AttributeError("'list' object has no attribute 'get'"), KeyError("x")])
def test_checks_that_raise_on_the_baseline_tree_make_it_unavailable_with_the_reason(repo: Path, failure: Exception) -> None:
    _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "edit", **{SEED.replace("/", "__"): "charter v2"})
    seen: list[Path] = []

    def checks(root: Path, _spec: Path) -> list[SpecError]:
        seen.append(root)
        raise failure

    result = merge_base_provider(checks, lambda _: [SEED])(repo / SPEC, str(repo))

    assert result.mode == "unavailable" and result.errors == ()
    assert result.resolution is not None and result.resolution.note is not None
    assert result.resolution.note.startswith(f"the checks could not run on the baseline tree: {type(failure).__name__}: ")
    assert not seen[0].exists()


def test_a_long_failure_text_is_cut_in_the_reason(repo: Path) -> None:
    _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "edit", a="1")

    def checks(_root: Path, _spec: Path) -> list[SpecError]:
        raise ValueError("x " * 500)

    result = merge_base_provider(checks, lambda _: [])(repo / SPEC, str(repo))
    assert result.resolution is not None and result.resolution.note is not None
    assert len(result.resolution.note) < 300 and result.resolution.note.endswith("...")


def test_a_keyboard_interrupt_is_not_swallowed(repo: Path) -> None:
    _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "edit", a="1")

    def checks(_root: Path, _spec: Path) -> list[SpecError]:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        merge_base_provider(checks, lambda _: [])(repo / SPEC, str(repo))


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


def test_provider_measures_against_the_branch_it_was_given(repo: Path) -> None:
    base = _base_files(repo)
    git(repo, "branch", "trunk")
    _commit(repo, "second", **{SEED.replace("/", "__"): "charter v2"})

    result = merge_base_provider(lambda *_: [], lambda _: [SEED], "trunk")(repo / SPEC, str(repo))

    assert result.resolution is not None
    assert (result.resolution.ref, result.resolution.commit, result.resolution.mode) == ("trunk", base, "merge-base")


def test_a_branch_named_like_the_end_of_the_target_still_gets_the_note(repo: Path, tmp_path: Path) -> None:
    """Branch ``1.0`` against ``origin/release/1.0`` is not the default branch: only a whole name behind one remote name is."""
    _base_files(repo)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main:release/1.0")
    git(repo, "fetch", "-q", "origin")
    git(repo, "checkout", "-q", "-b", "1.0")

    assert resolve_baseline(str(repo), "origin/release/1.0").note == "the baseline is HEAD itself: only uncommitted changes count as new"


def test_a_slashed_branch_against_the_plain_name_gets_the_note(repo: Path) -> None:
    """Branch ``feature/main`` against ``main``: the names differ, whatever they end in."""
    _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature/main")
    assert resolve_baseline(str(repo), "main").note == "the baseline is HEAD itself: only uncommitted changes count as new"


def test_host_paths_in_replaces_the_root_in_message_path_and_file_and_keeps_the_rest_as_it_is() -> None:
    root = "/tmp/baseline-x"
    touched = SpecError("E520", f"{root}/spec/04.json:a/1/b: bad", path=f"{root}/spec/04.json", file=f"{root}/spec/04.json", owner="step:04")
    untouched = SpecError("E700", "no node", owner="step:04", node_id="fr-a")

    out = host_paths_in([touched, untouched], [(root, "/host")])

    assert out[0] == SpecError("E520", "/host/spec/04.json:a/1/b: bad", path="/host/spec/04.json", file="/host/spec/04.json", owner="step:04")
    assert out[1] is untouched


def test_host_paths_in_applies_the_first_pair_first() -> None:
    error = SpecError("E520", "/tmp/b/spec/04.json: bad")
    assert host_paths_in([error], [("/tmp/b/spec", "spec"), ("/tmp/b", "/host")])[0].message == "spec/04.json: bad"


def test_the_baseline_errors_come_back_with_the_names_of_the_current_tree(repo: Path) -> None:
    """The checks run in a temporary folder: a finding of it names the spec folder and the root as the current tree does."""
    _base_files(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "edit", a="1")

    def checks(root: Path, spec: Path) -> list[SpecError]:
        real = Path(spec).resolve()
        return [
            SpecError("E520", f"{spec}/01_x.json:a/0: bad"),
            SpecError("E520", f"{real}/01_x.json:a/1: bad", file=str(real / "01_x.json")),
            SpecError("E761", f"seed {root}/{SEED} not found", path=f"{root}/{SEED}"),
        ]

    result = merge_base_provider(checks, lambda _: [SEED])(repo / SPEC, str(repo))

    assert [e.message for e in result.errors] == [
        f"{repo / SPEC}/01_x.json:a/0: bad", f"{repo / SPEC}/01_x.json:a/1: bad", f"seed {repo}/{SEED} not found",
    ]
    assert result.errors[1].file == f"{repo / SPEC}/01_x.json" and result.errors[2].path == f"{repo}/{SEED}"


def test_a_spec_folder_named_through_a_symlink_keeps_its_own_name_in_the_baseline_paths(repo: Path, tmp_path: Path) -> None:
    """The spec folder as the caller names it is replaced first: the host root inside it must not turn it into the real path."""
    commit = _base_files(repo)
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)
    with materialise_baseline(str(repo), commit, link / SPEC, []) as tree:
        pairs = git_base._tree_replacements(tree, link / SPEC, str(repo))
        assert pairs[0][1] == str(link / SPEC) and pairs[-1][1] == str(repo)
        error = SpecError(code="E520", message=f"bad {tree.spec_dir}/01_x.json", path=f"{tree.spec_dir}/01_x.json")
        (found,) = host_paths_in([error], pairs)
    assert found.path == f"{link / SPEC}/01_x.json" and found.message == f"bad {link / SPEC}/01_x.json"
