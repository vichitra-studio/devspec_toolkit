"""The git merge driver of the trace lock, and the function that installs it in a clone.

Two branches that attest different links change different lines of ``trace.lock.json``, but neighbouring lines make
git's text merge conflict.  The driver merges the three versions entry by entry, keyed by (source, field, target), so
those merges need no hand work.  When both sides changed the same entry the older chain stamp wins (DOC L526): the
lock stores no time, so "older" is read from the history: the stamp the base entry has predates both branches, and
when there is no base entry (both added the link) the smaller stamp is taken, which does not depend on which side is
merged into which.  A stored stamp that is not the current one makes the link suspect, so a choice between two stamps
can make a suspect, never hide one.

Every version must be a valid lock (one entry per key, hashes, version): ``parse_lock`` refuses the others, and the
driver then leaves git's conflict in place.  Git config is per clone and not committed, so ``install_driver`` has to
run once in each clone; without it git falls back to a text merge and the loader reports E760 with the repair line.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

from specdev_tools.core.constants import TRACE_LOCK_FILENAME
from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.graph.gitview import GitViewError, git_reason, run_git
from specdev_tools.trace.lockfile import Lock, LockEntry, parse_lock, replace_file_atomically, serialise_lock

DRIVER_NAME = "specdev-trace-lock"
DRIVER_DESCRIPTION = "specdev trace lock merge"
DRIVER_ARGUMENTS = "%O %A %B %P"
ATTRIBUTES_GIT_PATH = "info/attributes"


class LockMergeError(FindingError):
    """The merge or the installation cannot go on; ``error`` is the finding (E520, or E760 from a malformed version)."""


@dataclass(frozen=True)
class DriverInstall:
    """What ``install_driver`` set: the attributes file it wrote, the line in it and the driver command in git config."""

    attributes_file: str
    attribute_line: str
    driver_config: str


def _entry_rank(entry: LockEntry) -> tuple[str, str, bool]:
    return (entry.chain_stamp, entry.content_hash, entry.baseline)


def merge_entry(base: LockEntry | None, ours: LockEntry | None, theirs: LockEntry | None) -> LockEntry | None:
    """The merged entry of one key from its three versions (``None`` = absent); ``None`` means the entry is gone.

    A change on one side only is taken; one side deleting and the other changing keeps the changed entry; two
    different changes keep the base entry, or the entry with the smaller (chain stamp, content hash, baseline) when the
    base has none.
    """
    if ours == theirs or theirs == base:
        return ours
    if ours == base:
        return theirs
    if ours is None or theirs is None:
        return theirs if ours is None else ours
    return base if base is not None else min(ours, theirs, key=_entry_rank)


def merge_locks(base: Lock, ours: Lock, theirs: Lock) -> Lock:
    """The lock that merges *ours* and *theirs* on top of *base*, entry by entry (see ``merge_entry``)."""
    keys = {entry.key for lock in (base, ours, theirs) for entry in lock.entries}
    merged = (merge_entry(base.get(*key), ours.get(*key), theirs.get(*key)) for key in sorted(keys))
    return Lock(tuple(entry for entry in merged if entry is not None))


def _read_version(path: str, role: str, pathname: str, *, empty_is_empty_lock: bool = False) -> Lock:
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise LockMergeError(make_error("E520", f"cannot read the {role} version {path} of {pathname}: {error}")) from None
    if empty_is_empty_lock and not text.strip():
        return Lock()
    return parse_lock(text, path)


def merge_files(base_path: str, ours_path: str, theirs_path: str, pathname: str) -> None:
    """Merge the lock versions at *base_path*, *ours_path* and *theirs_path*; the result replaces *ours_path*.

    *pathname* is the repository path of the lock, used in findings.  An empty base file is an empty lock (git passes
    one when both branches added the file).

    Raises:
        LockMergeError: E520 when a version cannot be read or the result cannot be written.
        LockError: E760 when a version is not a valid lock, so the conflict stays for the person to resolve.
    """
    base = _read_version(base_path, "base", pathname, empty_is_empty_lock=True)
    ours = _read_version(ours_path, "ours", pathname)
    theirs = _read_version(theirs_path, "theirs", pathname)
    try:
        replace_file_atomically(ours_path, serialise_lock(merge_locks(base, ours, theirs)))
    except OSError as error:
        raise LockMergeError(make_error("E520", f"cannot write the merged lock to {ours_path}: {error}")) from None


def _git(git_root: str, args: Sequence[str]) -> str:
    """Stdout of ``git -C <git_root> <args>``, stripped; E520 when git is missing, slow or fails."""
    try:
        process = run_git(git_root, args)
    except GitViewError as error:
        raise LockMergeError(make_error("E520", error.error.message)) from None
    if process.returncode != 0:
        raise LockMergeError(make_error("E520", f"git {' '.join(args)} failed in {git_root}: {git_reason(process)}"))
    return process.stdout.decode("utf-8", errors="replace").strip()


def git_top_level(folder: str) -> str:
    """The top folder of the working tree that holds *folder* (``git rev-parse --show-toplevel``); E520 outside a repository."""
    return _git(folder, ["rev-parse", "--show-toplevel"])


def attribute_line(spec_rel_path: str) -> str:
    """The attributes line that routes the lock of the spec folder *spec_rel_path* (relative to the git root) to the driver."""
    parts = [] if spec_rel_path in ("", ".") else [spec_rel_path.strip("/")]
    return f"{'/'.join([*parts, 'extras', TRACE_LOCK_FILENAME])} merge={DRIVER_NAME}"


def _add_line_once(path: str, line: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        text = ""
    if line in text.splitlines():
        return
    separator = "" if not text or text.endswith("\n") else "\n"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{separator}{line}\n")


def install_driver(git_root: str, spec_rel_path: str, driver_command: str) -> DriverInstall:
    """Install the lock merge driver in the clone at *git_root*; safe to call again, it changes nothing the second time.

    Adds the line ``<spec_rel_path>/extras/trace.lock.json merge=specdev-trace-lock`` to the file git names for
    ``info/attributes`` (not versioned, so no committed ``.gitattributes`` changes the host's code tree) and sets
    ``merge.specdev-trace-lock.driver`` to ``"<driver_command> %O %A %B %P"`` and ``.name`` in the clone's git config.
    *driver_command* is run by a shell: quote what needs it, for example ``<venv>/bin/specdev lock merge``.

    Raises:
        LockMergeError: E520 when git is missing or fails, or the attributes file cannot be written.
    """
    attributes_file = os.path.join(git_root, _git(git_root, ["rev-parse", "--git-path", ATTRIBUTES_GIT_PATH]))
    line = attribute_line(spec_rel_path)
    driver_config = f"{driver_command} {DRIVER_ARGUMENTS}"
    try:
        _add_line_once(attributes_file, line)
    except OSError as error:
        raise LockMergeError(make_error("E520", f"cannot write {attributes_file}: {error}")) from None
    _git(git_root, ["config", f"merge.{DRIVER_NAME}.driver", driver_config])
    _git(git_root, ["config", f"merge.{DRIVER_NAME}.name", DRIVER_DESCRIPTION])
    return DriverInstall(attributes_file, line, driver_config)
