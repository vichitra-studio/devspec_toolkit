"""What the runner hands a script: the spec folder it may change, the documents loaded from it, read-only git.

A script works on a scratch copy of the host (the runner installs the result into the spec folder only after every
script and invariant passed), so ``spec_root`` and ``host_root`` here are scratch folders, never the host's own.  A
script keeps a path it writes into a spec file relative, and does not store ``spec_root`` or ``host_root`` in a file.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.constants import STATUS_IN_PROGRESS  # noqa: F401  (the stamp's status; also imported from here by the runner, the triage and update)
from specdev_tools.core.step_paths import PLAN_DIR_NAME

from specdev_tools.graph.kinds import KindRegistry, load_kind_registry
from specdev_tools.migration.writer import DocumentSet

CAPTURE_FILE = os.path.join("extras", "migration", "capture.json")
"""The capture file, relative to the spec folder, in the platform's own separators."""
CAPTURE_REL = CAPTURE_FILE.replace(os.sep, "/")
"""The same path with ``/``, the form a spec file's ``rel`` and a worklist item use."""

# The git subcommands the migration may call: all of them only read.
READ_ONLY_GIT = frozenset({"rev-parse", "status", "merge-base", "ls-files", "log", "show", "cat-file", "diff"})


class GitReadError(Exception):
    """A git call failed, or a subcommand outside ``READ_ONLY_GIT`` was asked for."""


def read_git(git_root: str, *args: str) -> str:
    """Run ``git -C <git_root> <args>`` and return its stdout; only the subcommands of ``READ_ONLY_GIT`` are allowed.

    This is not ``gitview.git_stdout`` because the whitelist is the point: it is what the no-git-writes test pins.

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


@dataclass(frozen=True)
class Snapshot:
    """The spec folder at one moment: a digest of every file, the parsed JSON files, the plan hashes.

    ``documents`` holds the parsed content of each ``*.json`` file that parses; treat it as read-only.
    """

    root: str
    files: Mapping[str, str]
    documents: Mapping[str, Any]
    plan_hashes: Mapping[str, str]


def file_key(rel: str) -> str:
    """The key a script's ``touches`` names for the file *rel*: its step id, its first folder, or ``specdev_version``."""
    head, _, tail = rel.partition("/")
    if not tail:
        stem = head.split("_", 1)[0]
        return stem if stem and stem[0].isdigit() else head
    return "16" if head == PLAN_DIR_NAME else head


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
