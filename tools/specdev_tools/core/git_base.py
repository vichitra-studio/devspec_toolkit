"""The git baseline of the step gate: which commit "new since" is measured against, and the spec tree as it was there.

``resolve_target_branch`` picks the branch to compare with (never the branch's own ``@{upstream}``);
``resolve_baseline`` turns it into the merge-base commit and a mode; ``materialise_baseline`` extracts the spec folder
and the seed documents of that commit into a temporary folder with the layout of the host repository, so the same checks
run on it as on the working tree.  A provider (``merge_base_provider``, or one the caller passes to ``run_step_gate``) turns a spec folder into the error set of
the baseline; a baseline that cannot be had is ``unavailable``, which the gate treats as "every upstream error is new".
Git is run only through ``graph.gitview.run_git``.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import TracebackType
from typing import Literal

from specdev_tools.core.config import get_config
from specdev_tools.core.constants import DEFAULT_BRANCH_CANDIDATES
from specdev_tools.core.errors import SpecError
from specdev_tools.graph.gitview import (
    GitViewError,
    archive_ref,
    path_exists_at,
    resolve_ref,
    run_git,
    spec_path_in_repo,
)

BaseMode = Literal["merge-base", "head", "unavailable"]
BaselineMode = Literal["ok", "unavailable"]

_ORIGIN_HEAD_REF = "refs/remotes/origin/HEAD"
_NO_BASELINE_TEXT = "base: unavailable"
_HEAD_NOTE = "the baseline is HEAD itself: only uncommitted changes count as new"
_REASON_CHARS = 200


@dataclass(frozen=True)
class BaseResolution:
    """Where "new" is measured from.

    ``ref`` is the target branch and ``commit`` the baseline commit id; both are ``None`` when ``mode`` is ``unavailable``.
    ``note`` is one line of what the reader should know: why the baseline is ``unavailable``, or (mode ``head``) that
    the baseline is HEAD on a branch that is not the target branch.
    """

    ref: str | None
    commit: str | None
    mode: BaseMode
    note: str | None = None

    def describe(self) -> str:
        """The header line the gate prints: the ref, the commit and the mode, or ``base: unavailable``."""
        if self.commit is None:
            return _NO_BASELINE_TEXT
        return f"base: {self.ref} {self.commit[:12]} ({self.mode})"


@dataclass(frozen=True)
class BaselineResult:
    """What a provider returns: ``ok`` with the baseline's errors, or ``unavailable`` (strict: all upstream errors are new)."""

    mode: BaselineMode
    errors: tuple[SpecError, ...] = ()
    resolution: BaseResolution | None = None


BaselineProvider = Callable[[Path, str], BaselineResult]
"""``(spec_dir, git_root) -> BaselineResult``; ``run_step_gate`` takes one as its ``provider`` argument (``merge_base_provider`` by default)."""

BaselineChecks = Callable[[Path, Path], Sequence[SpecError]]
"""``(baseline_root, baseline_spec_dir) -> errors``: the checks run on a materialised baseline with ``baseline_root`` as git root and spec root."""

SeedPaths = Callable[[Path], Sequence[str]]
"""``spec_dir -> seed paths`` relative to the git root, as the current tree names them."""


class BaselineTree:
    """A materialised baseline: a temporary folder laid out like the host repository (``root``), holding the spec folder (``spec_dir``).

    Use it as a context manager; the folder is deleted on exit.
    """

    def __init__(self, directory: tempfile.TemporaryDirectory[str], spec_path: str) -> None:
        self._directory = directory
        self.root = Path(directory.name)
        self.spec_dir = self.root / spec_path

    def __enter__(self) -> BaselineTree:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self._directory.cleanup()


def _ref_exists(ref: str, git_root: str) -> bool:
    try:
        resolve_ref(ref, git_root)
    except GitViewError:
        return False
    return True


def _origin_head(git_root: str) -> str | None:
    process = run_git(git_root, ["symbolic-ref", "--short", "-q", _ORIGIN_HEAD_REF])
    target = process.stdout.decode("utf-8").strip()
    return target if process.returncode == 0 and target and _ref_exists(target, git_root) else None


def resolve_target_branch(git_root: str, base_ref: str | None = None) -> str | None:
    """The ref the baseline is taken against; never the current branch's ``@{upstream}``.

    Order: *base_ref* (the ``--base-ref`` flag), ``SPECDEV_REPLAY_BASE_REF``, the ``origin/HEAD`` symbolic ref, then the
    first existing of ``DEFAULT_BRANCH_CANDIDATES``.  A flag or environment value is returned as given (it is checked
    when the baseline commit is resolved).  ``None`` when no ref is found.

    Raises:
        GitViewError: E708 when git is missing or does not answer in time.
    """
    explicit = base_ref or get_config().replay_base_ref
    if explicit:
        return explicit
    return _origin_head(git_root) or next((c for c in DEFAULT_BRANCH_CANDIDATES if _ref_exists(c, git_root)), None)


def _current_branch(git_root: str) -> str | None:
    process = run_git(git_root, ["symbolic-ref", "--short", "-q", "HEAD"])
    return process.stdout.decode("utf-8").strip() or None if process.returncode == 0 else None


def _remotes(git_root: str) -> list[str]:
    process = run_git(git_root, ["remote"])
    return process.stdout.decode("utf-8").split() if process.returncode == 0 else []


def _is_default_branch(branch: str | None, target: str, git_root: str) -> bool:
    """Whether *branch* is the branch *target* names: the same full name, or *target* is that name behind one remote name."""
    if branch is None:
        return False
    return branch == target or any(target == f"{remote}/{branch}" for remote in _remotes(git_root))


def _unavailable(target: str | None, reason: str) -> BaseResolution:
    return BaseResolution(target, None, "unavailable", reason)


def _repository_problem(git_root: str) -> str | None:
    """Why *git_root* has no usable history (not a repository, no commit yet), or ``None``."""
    if run_git(git_root, ["rev-parse", "--git-dir"]).returncode != 0:
        return "not a git repository"
    if run_git(git_root, ["rev-parse", "--verify", "--quiet", "HEAD^{commit}"]).returncode != 0:
        return "no commit yet"
    return None


def resolve_baseline_commit(git_root: str, target: str | None) -> BaseResolution:
    """The merge-base of HEAD and *target*; HEAD itself when that is HEAD (mode ``head``); ``unavailable`` when none can be had.

    Every ``unavailable`` carries its reason in ``note``: not a git repository, no commit yet, no base ref found,
    *target* does not name a commit, or no common history with *target* (a shallow clone).  Mode ``head`` on a branch
    other than the target carries a note.

    Raises:
        GitViewError: E708 when git is missing or does not answer in time.
    """
    problem = _repository_problem(git_root)
    if problem is not None:
        return _unavailable(target, problem)
    if target is None:
        return _unavailable(None, f"no base ref found ({', '.join(DEFAULT_BRANCH_CANDIDATES)}); pass --base-ref")
    if target.startswith("-") or not _ref_exists(target, git_root):
        return _unavailable(target, f"{target} does not name a commit")
    process = run_git(git_root, ["merge-base", "HEAD", target])
    commit = process.stdout.decode("utf-8").strip()
    if process.returncode != 0 or not commit:
        return _unavailable(target, f"no common history with {target} (a shallow clone?)")
    if commit != resolve_ref("HEAD", git_root):
        return BaseResolution(target, commit, "merge-base")
    note = None if _is_default_branch(_current_branch(git_root), target, git_root) else _HEAD_NOTE
    return BaseResolution(target, commit, "head", note)


def resolve_baseline(git_root: str, base_ref: str | None = None) -> BaseResolution:
    """``resolve_target_branch`` then ``resolve_baseline_commit``; ``unavailable`` (with the reason) when git cannot answer."""
    try:
        return resolve_baseline_commit(git_root, resolve_target_branch(git_root, base_ref))
    except GitViewError as error:
        return _unavailable(base_ref, error.error.message)


def _archive_present_seeds(commit: str, git_root: str, seed_paths: Sequence[str], destination: Path) -> None:
    """Archive each seed that exists at *commit* into *destination*, one by one: a seed added on the branch is left out.

    Only a seed that git says is absent at *commit* is skipped; any other git failure propagates.
    """
    for path in seed_paths:
        if not path_exists_at(commit, git_root, path):
            continue
        with archive_ref(commit, git_root, [path]) as archived:
            shutil.copytree(archived, destination, dirs_exist_ok=True)


def materialise_baseline(git_root: str, commit: str, spec_dir: str | Path, seed_paths: Sequence[str]) -> BaselineTree:
    """The spec folder and the seed documents as they are at *commit*, in a temporary folder laid out like the host repository.

    *seed_paths* are relative to *git_root*; a seed absent at *commit* is left out.  The caller deletes the folder
    (use the result as a context manager).

    Raises:
        GitViewError: E708 when *spec_dir* is outside *git_root*, absent at *commit*, or git fails.
    """
    spec_path = spec_path_in_repo(str(spec_dir), git_root)
    try:
        directory = archive_ref(commit, git_root, [spec_path, *seed_paths])
    except GitViewError:
        directory = archive_ref(commit, git_root, [spec_path])
        _archive_present_seeds(commit, git_root, seed_paths, Path(directory.name))
    return BaselineTree(directory, spec_path)


def host_paths_in(errors: Sequence[SpecError], replacements: Sequence[tuple[str, str]]) -> tuple[SpecError, ...]:
    """*errors* with every *replacements* ``(old, new)`` applied, in the order given, to their ``message``, ``path`` and ``file``.

    A finding with no ``old`` in any of the three fields is returned as the same object.  List the longer ``old`` first
    (the spec folder before the root that holds it).  No path boundary is checked, because the baseline folder's name is unique.
    """
    out: list[SpecError] = []
    for error in errors:
        changes: dict[str, str] = {}
        for name in ("message", "path", "file"):
            text = getattr(error, name)
            if not text:
                continue
            for old, new in replacements:
                text = text.replace(old, new)
            if text != getattr(error, name):
                changes[name] = text
        out.append(replace(error, **changes) if changes else error)
    return tuple(out)


def _tree_replacements(tree: BaselineTree, spec_dir: Path, git_root: str) -> list[tuple[str, str]]:
    """What turns a path inside the baseline tree into the same path of the current tree: the spec folder as the caller names it, then the host root.

    Each ``old`` comes as given and as its real path (a temporary folder may sit behind a symbolic link), the longer first: the
    real path of ``/tmp/x`` is ``/private/tmp/x``, which contains the other.
    """
    pairs = [(tree.spec_dir, str(spec_dir)), (tree.root, git_root)]
    return [(form, new) for old, new in pairs for form in sorted({str(old), os.path.realpath(old)}, key=len, reverse=True)]


def merge_base_provider(
    compute_errors: BaselineChecks, seed_paths: SeedPaths, base_ref: str | None = None
) -> BaselineProvider:
    """The default provider: the errors of the checks on the spec tree at the merge-base commit.

    ``unavailable``, with the reason in ``resolution.note``, when the baseline cannot be resolved or materialised (no
    git, no merge-base, a spec folder absent at the commit) or when the checks fail on the baseline tree (any
    ``Exception``: a baseline that older tooling cannot read is no reason to stop the gate).  ``seed_paths`` names the seed documents of the
    current tree; ``compute_errors`` runs the checks on the materialised tree; *base_ref* (``--base-ref``) names the
    branch to compare with, as ``resolve_target_branch`` reads it.
    """

    def provider(spec_dir: Path, git_root: str) -> BaselineResult:
        resolution = resolve_baseline(git_root, base_ref)
        if resolution.commit is None:
            return BaselineResult("unavailable", resolution=resolution)
        try:
            if not path_exists_at(resolution.commit, git_root, spec_path_in_repo(str(spec_dir), git_root)):
                reason = f"the spec folder is not in the base commit {resolution.commit[:12]}: every error of an earlier step counts as new"
                return BaselineResult("unavailable", resolution=replace(resolution, note=reason))
            with materialise_baseline(git_root, resolution.commit, spec_dir, seed_paths(spec_dir)) as tree:
                errors = host_paths_in(compute_errors(tree.root, tree.spec_dir), _tree_replacements(tree, spec_dir, git_root))
        except Exception as error:  # noqa: BLE001 - the baseline tree is old data: whatever breaks on it makes it unavailable
            text = " ".join(str(error).split())
            text = text if len(text) <= _REASON_CHARS else text[:_REASON_CHARS].rstrip() + "..."
            reason = f"the checks could not run on the baseline tree: {type(error).__name__}: {text}"
            return BaselineResult("unavailable", resolution=replace(resolution, note=reason))
        return BaselineResult("ok", errors, resolution)

    return provider


__all__ = [
    "BaseMode",
    "BaseResolution",
    "BaselineChecks",
    "BaselineMode",
    "BaselineProvider",
    "BaselineResult",
    "BaselineTree",
    "SeedPaths",
    "host_paths_in",
    "materialise_baseline",
    "merge_base_provider",
    "resolve_baseline",
    "resolve_baseline_commit",
    "resolve_target_branch",
]
