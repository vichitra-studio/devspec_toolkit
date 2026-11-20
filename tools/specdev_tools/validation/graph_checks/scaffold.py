"""The scaffold row path check (E746): the file a step-15 scaffold row names is a tracked file.

*Tracked* is read once per run with ``git ls-files -s -z --recurse-submodules`` at the host root, so the files of a
checked-out submodule count.  A submodule that is not checked out is listed as one entry of mode 160000 (a gitlink):
a row under it cannot be judged and is skipped with a note, never reported; when every row to check lies under such a
submodule the whole check skips with that reason.  Without git or outside a repository the whole check skips with the
reason.

``merge`` checks a row only when one of the APIs it ``realises`` is built (a built API needs its file); ``close`` and
``release`` check every row.  ``scaffold_scan`` is the whole outcome (findings, notes, skip reason); ``scaffold_rows_untracked`` is its findings.
"""
from __future__ import annotations

import posixpath
import sys
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.gitview import GitViewError, git_reason, run_git
from specdev_tools.graph.model import Node
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext

from .built import BuiltState, compute_built
from .codes import SCAFFOLD_PATH_NOT_TRACKED
from .context import GRAPH_NOT_BUILT, GraphCheckContext, Mode
from specdev_tools.graph.names import MERGE, REALISES, SCAFFOLD_ROW, link_targets

PATH_FIELD = "path"
GITLINK_MODE = "160000"
NO_HOST_ROOT = "no host repository root to read tracked files from"


class TrackedFilesUnavailable(Exception):
    """The tracked files of the host could not be read (no git, not a repository); the message is the reason."""


@dataclass(frozen=True)
class TrackedFiles:
    """What ``git ls-files`` says: the tracked file paths, and the paths of submodules that are not checked out."""

    files: frozenset[str]
    unchecked_submodules: frozenset[str]

    def submodule_of(self, path: str) -> str | None:
        """The unchecked submodule *path* lies under, or ``None``."""
        return next((module for module in sorted(self.unchecked_submodules) if path.startswith(module + "/")), None)


@dataclass
class ScaffoldScan:
    """The outcome of one scan: the findings, a note for each row under a submodule that is not checked out, and why the whole check was skipped (``None`` when it ran)."""

    findings: list[SpecError] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skip_reason: str | None = None


def read_tracked_files(git_root: str) -> TrackedFiles:
    """The tracked paths under *git_root* (relative to it), submodules included, in one ``git ls-files`` call.

    Raises:
        TrackedFilesUnavailable: git is missing or does not answer, or *git_root* is not in a repository.
    """
    try:
        process = run_git(git_root, ["ls-files", "-s", "-z", "--recurse-submodules"])
    except GitViewError as error:
        raise TrackedFilesUnavailable(error.error.message) from error
    if process.returncode != 0:
        raise TrackedFilesUnavailable(f"git ls-files failed: {git_reason(process)}")
    files: set[str] = set()
    unchecked: set[str] = set()
    for entry in process.stdout.decode("utf-8", errors="replace").split("\0"):
        meta, _, path = entry.partition("\t")
        if path:
            (unchecked if meta.split(" ", 1)[0] == GITLINK_MODE else files).add(path)
    return TrackedFiles(frozenset(files), frozenset(unchecked))


def _row_path(ctx: GraphCheckContext, row: Node) -> str | None:
    """The ``path`` of *row* as a normalised relative path; ``None`` when it has none (the schema owns that)."""
    value = (item_of(ctx.graph, row) or {}).get(PATH_FIELD)
    return posixpath.normpath(value) if isinstance(value, str) and value else None


def _rows_to_check(ctx: GraphCheckContext, api_ids: Collection[str] | None, mode: Mode) -> list[Node]:
    """The scaffold rows in play, those that realise one of *api_ids* when given, and in merge mode only those with a built API."""
    wanted = None if api_ids is None else {ctx.graph.canonical_id(name) for name in api_ids}
    built = compute_built(ctx) if mode == MERGE else {}
    rows = []
    for row in ctx.in_play_nodes():
        if row.kind != SCAFFOLD_ROW:
            continue
        apis = link_targets(ctx.graph, row, REALISES)
        if wanted is not None and not wanted.intersection(apis):
            continue
        if mode == MERGE and not any(built.get(api) is not None and built[api].state is BuiltState.BUILT for api in apis):
            continue
        rows.append(row)
    return rows


def scaffold_scan(ctx: GraphCheckContext, api_ids: Collection[str] | None, mode: Mode) -> ScaffoldScan:
    """The whole outcome of the scaffold check: the findings, the notes of rows under a submodule that is not checked out, and ``skip_reason`` when the check could not run.

    A gate that must know "every row is tracked" reads this: an empty ``findings`` with a ``skip_reason`` is "could not check" (no host root, no git, every row under an absent submodule), not "clean".
    """
    if ctx.git_root is None:
        return ScaffoldScan(skip_reason=NO_HOST_ROOT)
    try:
        tracked = read_tracked_files(ctx.git_root)
    except TrackedFilesUnavailable as error:
        return ScaffoldScan(skip_reason=str(error))
    scan = ScaffoldScan()
    rows = _rows_to_check(ctx, api_ids, mode)
    modules: set[str] = set()
    for row in rows:
        path = _row_path(ctx, row)
        if path is None or path in tracked.files:
            continue
        module = tracked.submodule_of(path)
        if module is not None:
            scan.notes.append(f"scaffold row {row.id} path {path} is under submodule {module}, which is not checked out: not checked")
            modules.add(module)
            continue
        scan.findings.append(ctx.finding(
            SCAFFOLD_PATH_NOT_TRACKED, row,
            f"scaffold row {row.id} names {path}, which is not a tracked file ({mode} mode); add and commit the file, or correct the row's path",
        ))
    if rows and len(scan.notes) == len(rows):
        scan.skip_reason = f"every scaffold row to check is under a submodule that is not checked out ({', '.join(sorted(modules))})"
    return scan


def scaffold_rows_untracked(ctx: GraphCheckContext, api_ids: Collection[str] | None, mode: Mode) -> list[SpecError]:
    """E746 for each scaffold row in play whose path is not a tracked file, in step then id order.

    Only rows that realise one of *api_ids* are read when it is given; in ``merge`` mode only rows with a built API.
    Empty when git cannot be read, and then also when it is clean: a gate that must tell the two apart calls ``scaffold_scan`` and reads ``skip_reason``.
    """
    return scaffold_scan(ctx, api_ids, mode).findings


def check_scaffold_paths(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E746 for every scaffold row of the spec that *mode* checks (see ``scaffold_rows_untracked``)."""
    return scaffold_rows_untracked(ctx, None, mode)


def run_scaffold_paths(ctx: CheckContext) -> dict[str, Any]:
    """The registered function: E746 findings at merge; a skip when no graph could be built or git cannot be read; some rows under a submodule that is not checked out are noted on stderr; all of them: a skip."""
    gctx = GraphCheckContext.from_registry(ctx)
    if gctx is None:
        return check_registry.skip(GRAPH_NOT_BUILT)
    scan = scaffold_scan(gctx, None, MERGE)
    if scan.skip_reason is not None:
        return check_registry.skip(scan.skip_reason)
    if not gctx.quiet:
        for note in scan.notes:
            print(f"note: {note}", file=sys.stderr)
    return check_registry.check_result(scan.findings)
