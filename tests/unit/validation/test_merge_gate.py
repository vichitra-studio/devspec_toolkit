"""The merge gate (``validation/merge_gate.py``): its base, the milestones a branch closes, and how ``spec-check --merge`` lists its checks."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.lifecycle.anchor_store import AnchorState
from specdev_tools.validation.check_registry import CHECK_REGISTRY, CheckContext
from specdev_tools.validation.merge_gate import (
    MERGE_BINDINGS,
    MERGE_OPEN_ITEMS,
    MERGE_PINS,
    MergeBase,
    closed_by_branch,
    resolve_merge_base,
    run_merge_checks,
)
from specdev_tools.validation import merge_gate
from specdev_tools.validation.spec_check import run_checks, run_spec_check_json

from ..graph._synth import ROOT, git
from ..trace._lock_support import git_copy_of_example

NULL_SHA = "0" * 40
UNKNOWN_SHA = "1" * 40
MERGE_CHECK_NAMES = [MERGE_OPEN_ITEMS, MERGE_PINS, MERGE_BINDINGS]


def commit(repo: Path, name: str) -> str:
    """Commit a new file *name*; the commit id."""
    (repo / name).write_text(name, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """A repository with the commits A, B (``main``), C and D (HEAD, on ``feat``); no remote; the base-ref variable unset."""
    monkeypatch.delenv("SPECDEV_REPLAY_BASE_REF", raising=False)
    reset_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    shas = {"repo": str(repo), "A": commit(repo, "a"), "B": commit(repo, "b")}
    git(repo, "checkout", "-q", "-b", "feat")
    shas["C"], shas["D"] = commit(repo, "c"), commit(repo, "d")
    yield shas
    reset_config()


def state(status: str, close: dict[str, object] | None = None) -> AnchorState:
    return AnchorState(status, None, close)


def example_context(tmp_path: Path) -> CheckContext:
    host = git_copy_of_example(tmp_path / "host")
    return CheckContext(
        repo_root=str(ROOT), spec_dir=str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"),
        quiet=True,
    )


def test_merge_mode_off_runs_no_merge_checks(tmp_path: Path) -> None:
    ctx = example_context(tmp_path)
    checks = run_checks(ctx.repo_root, ctx.spec_dir, ctx.git_root, ctx.spec_root, quiet=True)
    assert list(checks) == [spec.name for spec in CHECK_REGISTRY]
    assert not set(MERGE_CHECK_NAMES) & set(checks)


def test_merge_mode_lists_merge_checks_in_summary(tmp_path: Path) -> None:
    ctx = example_context(tmp_path)
    checks = run_checks(ctx.repo_root, ctx.spec_dir, ctx.git_root, ctx.spec_root, quiet=True, merge=True)
    assert list(checks)[-3:] == MERGE_CHECK_NAMES
    assert list(checks)[:-3] == [spec.name for spec in CHECK_REGISTRY]
    _, context = run_spec_check_json(ctx.repo_root, ctx.spec_dir, ctx.git_root, ctx.spec_root, merge=True)
    assert list(context["checks"])[-3:] == MERGE_CHECK_NAMES


def test_the_example_passes_every_merge_check_and_closes_no_milestone(tmp_path: Path) -> None:
    checks = run_merge_checks(example_context(tmp_path), None)
    assert [(name, result["status"]) for name, result in checks.items()] == [
        (MERGE_OPEN_ITEMS, "PASS"), (MERGE_PINS, "PASS"), (MERGE_BINDINGS, "SKIP"),
    ]


def test_base_ref_precedence_flag_env_default(history: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    repo = history["repo"]
    assert resolve_merge_base(None, repo) == MergeBase("main", history["B"])
    monkeypatch.setenv("SPECDEV_REPLAY_BASE_REF", "HEAD~1")
    reset_config()
    assert resolve_merge_base(None, repo) == MergeBase("HEAD~1", history["C"])
    assert resolve_merge_base("HEAD~3", repo) == MergeBase("HEAD~3", history["A"])


def test_base_ref_unresolved_is_E900(tmp_path: Path, history: dict[str, str]) -> None:
    with pytest.raises(FindingError) as unknown:
        resolve_merge_base("origin/nothing", history["repo"])
    assert unknown.value.error.code == "E900" and "origin/nothing" in unknown.value.error.message
    with pytest.raises(FindingError) as not_a_repository:
        resolve_merge_base(None, str(tmp_path))
    assert not_a_repository.value.error.code == "E900"


def test_no_default_branch_and_no_flag_is_E900(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPECDEV_REPLAY_BASE_REF", raising=False)
    reset_config()
    repo = tmp_path / "trunk"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "trunk")
    commit(repo, "a")
    with pytest.raises(FindingError) as caught:
        resolve_merge_base(None, str(repo))
    assert caught.value.error.code == "E900" and "pass --base-ref" in caught.value.error.message


@pytest.mark.parametrize("flag", [NULL_SHA, UNKNOWN_SHA], ids=["null-sha", "unknown-sha"])
def test_a_commit_id_this_clone_lacks_is_the_first_parent(history: dict[str, str], flag: str) -> None:
    base = resolve_merge_base(flag, history["repo"])
    assert base.commit == history["C"] and base.ref == "HEAD^1"
    assert base.note is not None and flag in base.note


def test_a_root_commit_has_no_base(tmp_path: Path) -> None:
    repo = tmp_path / "root"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "a")
    base = resolve_merge_base(NULL_SHA, str(repo))
    assert base.commit is None and base.ref is None and "nothing existed at the base" in (base.note or "")


def test_a_commit_id_this_clone_has_is_used_as_given(history: dict[str, str]) -> None:
    assert resolve_merge_base(history["A"], history["repo"]).commit == history["A"]


def test_closed_by_branch_is_done_now_and_not_done_at_the_base() -> None:
    head = {
        "ms-new": state("done"), "ms-closed-before": state("done"), "ms-open": state("in_progress"),
        "ms-was-open": state("done"), "ms-legacy": state("done", {"signed_off_by": "legacy-migration"}),
    }
    base = {"ms-closed-before": state("done"), "ms-open": state("in_progress"), "ms-was-open": state("in_progress")}
    assert closed_by_branch(head, base) == ["ms-new", "ms-was-open"]


def test_closed_by_branch_with_nothing_at_the_base_is_every_done_milestone() -> None:
    assert closed_by_branch({"ms-a": state("done"), "ms-b": state("pending")}, {}) == ["ms-a"]


def test_a_finding_error_of_a_check_is_that_checks_one_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(_spec_root: str) -> None:
        raise FindingError(make_error("E520", "cannot read the declarations"))

    monkeypatch.setattr(merge_gate, "declarations_of", unreadable)
    checks = run_merge_checks(example_context(tmp_path), None)
    assert [error.code for error in checks[MERGE_PINS]["errors"]] == ["E520"]
    assert checks[MERGE_OPEN_ITEMS]["status"] == "PASS"


def test_a_binding_failure_is_E901_and_owned_by_the_merge_check(tmp_path: Path) -> None:
    error = merge_gate._failed_binding("ver-x", "ms-y", 3, False)
    assert isinstance(error, SpecError) and error.code == "E901" and error.node_id == "ver-x"
    assert "exit code 3" in error.message and "did not match" in error.message
    ctx = example_context(tmp_path)
    stamped = merge_gate.with_default_owner({"status": "FAIL", "errors": [error]}, "merge-check", ctx.owner_context)
    assert [e.owner for e in stamped["errors"]] == ["merge-check"]
