"""The git baseline of the step gate: which commit "new since" is measured against, and the spec tree as it was there.

``resolve_target_branch`` picks the branch to compare with (never the branch's own ``@{upstream}``);
``resolve_baseline`` turns it into the merge-base commit and a mode; ``materialise_baseline`` extracts the spec folder
and the seed documents of that commit into a temporary folder with the layout of the host repository, so the same checks
run on it as on the working tree.  A provider (``register_baseline_provider``) turns a spec folder into the error set of
the baseline; a baseline that cannot be had is ``unavailable``, which the gate treats as "every upstream error is new".
Git is run only through ``graph.gitview.run_git``.
"""
from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Literal

from specdev_tools.core.config import get_config
from specdev_tools.core.constants import DEFAULT_BRANCH_CANDIDATES
from specdev_tools.core.errors import FindingError, SpecError
from specdev_tools.graph.gitview import GitViewError, archive_ref, resolve_ref, run_git, spec_path_in_repo

BaseMode = Literal["merge-base", "head", "unavailable"]
BaselineMode = Literal["ok", "unavailable"]

_ORIGIN_HEAD_REF = "refs/remotes/origin/HEAD"
_NO_BASELINE_TEXT = "base: unavailable"
_HEAD_NOTE = "the baseline is HEAD itself, so no error counts as new; the branch is not the default branch"


@dataclass(frozen=True)
class BaseResolution:
    """Where "new" is measured from.

    ``ref`` is the target branch and ``commit`` the baseline commit id; both are ``None`` when ``mode`` is ``unavailable``.
    ``note`` is set when the baseline is HEAD on a branch that is not the target branch.
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
"""``(spec_dir, git_root) -> BaselineResult``; the registered one is read by the step gate."""

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


def _is_default_branch(branch: str | None, target: str) -> bool:
    return branch is not None and branch == target.rsplit("/", 1)[-1]


def resolve_baseline_commit(git_root: str, target: str | None) -> BaseResolution:
    """The merge-base of HEAD and *target*; HEAD itself when that is HEAD (mode ``head``); ``unavailable`` when none can be had.

    No target, an unknown ref, no common history (a shallow clone) and a folder that is not a repository all give
    ``unavailable``.  Mode ``head`` on a branch other than the target carries a note.

    Raises:
        GitViewError: E708 when git is missing or does not answer in time.
    """
    unavailable = BaseResolution(target, None, "unavailable")
    if target is None or target.startswith("-"):
        return unavailable
    process = run_git(git_root, ["merge-base", "HEAD", target])
    commit = process.stdout.decode("utf-8").strip()
    if process.returncode != 0 or not commit:
        return unavailable
    if commit != resolve_ref("HEAD", git_root):
        return BaseResolution(target, commit, "merge-base")
    note = None if _is_default_branch(_current_branch(git_root), target) else _HEAD_NOTE
    return BaseResolution(target, commit, "head", note)


def resolve_baseline(git_root: str, base_ref: str | None = None) -> BaseResolution:
    """``resolve_target_branch`` then ``resolve_baseline_commit``; ``unavailable`` when git cannot answer."""
    try:
        return resolve_baseline_commit(git_root, resolve_target_branch(git_root, base_ref))
    except GitViewError:
        return BaseResolution(base_ref, None, "unavailable")


def _merge_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _archive_present_seeds(commit: str, git_root: str, seed_paths: Sequence[str], destination: Path) -> None:
    """Archive each seed that exists at *commit* into *destination*, one by one: a seed added on the branch is left out."""
    for path in seed_paths:
        try:
            with archive_ref(commit, git_root, [path]) as archived:
                _merge_tree(Path(archived), destination)
        except GitViewError:
            continue


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


def merge_base_provider(compute_errors: BaselineChecks, seed_paths: SeedPaths) -> BaselineProvider:
    """The default provider: the errors of the checks on the spec tree at the merge-base commit.

    ``unavailable`` when the baseline cannot be resolved or materialised (no git, no merge-base, a spec folder absent
    at the commit) or when the checks cannot read the baseline tree.  ``seed_paths`` names the seed documents of the
    current tree; ``compute_errors`` runs the checks on the materialised tree.
    """

    def provider(spec_dir: Path, git_root: str) -> BaselineResult:
        resolution = resolve_baseline(git_root)
        if resolution.commit is None:
            return BaselineResult("unavailable", resolution=resolution)
        try:
            with materialise_baseline(git_root, resolution.commit, spec_dir, seed_paths(spec_dir)) as tree:
                errors = tuple(compute_errors(tree.root, tree.spec_dir))
        except (FindingError, OSError):
            return BaselineResult("unavailable", resolution=resolution)
        return BaselineResult("ok", errors, resolution)

    return provider


def _no_baseline(spec_dir: Path, git_root: str) -> BaselineResult:
    return BaselineResult("unavailable")


class _ProviderSlot:
    """The registered provider; holds ``_no_baseline`` until one is registered."""

    def __init__(self) -> None:
        self.provider: BaselineProvider = _no_baseline


_SLOT = _ProviderSlot()


def register_baseline_provider(fn: BaselineProvider) -> None:
    """Make *fn* the provider that ``active_baseline_provider`` returns (WI-M10-10 registers the migration-mode one)."""
    _SLOT.provider = fn


def active_baseline_provider() -> BaselineProvider:
    """The registered provider; one that always answers ``unavailable`` when none was registered."""
    return _SLOT.provider


__all__ = [
    "BaseMode",
    "BaseResolution",
    "BaselineChecks",
    "BaselineMode",
    "BaselineProvider",
    "BaselineResult",
    "BaselineTree",
    "SeedPaths",
    "active_baseline_provider",
    "materialise_baseline",
    "merge_base_provider",
    "register_baseline_provider",
    "resolve_baseline",
    "resolve_baseline_commit",
    "resolve_target_branch",
]
