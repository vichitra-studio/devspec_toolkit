"""What the runner hands a script: the spec folder it may change, the documents loaded from it, read-only git.

A script works on a scratch copy of the host (the runner installs the result into the spec folder only after every
script and invariant passed), so ``spec_root`` and ``host_root`` here are scratch folders, never the host's own.  A
script keeps a path it writes into a spec file relative, and does not store ``spec_root`` or ``host_root`` in a file.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from specdev_tools.graph.kinds import KindRegistry, load_kind_registry
from specdev_tools.migration.writer import DocumentSet

# The git subcommands the migration may call: all of them only read.
READ_ONLY_GIT = frozenset({"rev-parse", "status", "merge-base", "ls-files", "log", "show", "cat-file", "diff"})


class GitReadError(Exception):
    """A git call failed, or a subcommand outside ``READ_ONLY_GIT`` was asked for."""


def read_git(git_root: str, *args: str) -> str:
    """Run ``git -C <git_root> <args>`` and return its stdout; only the subcommands of ``READ_ONLY_GIT`` are allowed.

    Raises:
        GitReadError: the subcommand is not read-only, git is missing, or git exits non-zero (the message holds its stderr).
    """
    if not args or args[0] not in READ_ONLY_GIT:
        raise GitReadError(f"git {' '.join(args[:1])}: the migration makes read-only git calls only ({', '.join(sorted(READ_ONLY_GIT))})")
    try:
        done = subprocess.run(["git", "-C", git_root, *args], capture_output=True, text=True, check=False)
    except OSError as error:
        raise GitReadError(f"git cannot be run: {error}") from None
    if done.returncode != 0:
        raise GitReadError(f"git {' '.join(args)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


@dataclass
class MigrationContext:
    """One script's view of the run.

    ``documents`` is the ``DocumentSet`` of ``spec_root`` for this script: ``documents.load(rel)`` reads a spec JSON file
    once, the script edits ``.data`` in place, and the runner calls ``documents.write()`` after ``apply`` (only files
    whose data changed are written, in their own style).  A script that calls a library writer (one that writes a file
    itself) does not also hold unsaved edits to the same file in ``documents``.
    """

    spec_root: str
    host_root: str
    git_root: str
    toolkit_root: str
    dry_run: bool
    documents: DocumentSet
    from_version: str
    to_version: str
    _registry: KindRegistry | None = field(default=None, repr=False)

    def kind_registry(self) -> KindRegistry:
        """The kind registry of the toolkit (``tools/entry_key_registry.json`` under ``toolkit_root``)."""
        if self._registry is None:
            self._registry = load_kind_registry(self.toolkit_root)
        return self._registry

    def git(self, *args: str) -> str:
        """A read-only git call in the host's real work tree (the migration never changes it)."""
        return read_git(self.git_root, *args)
