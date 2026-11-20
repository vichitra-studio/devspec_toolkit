"""The spec graph as it stood at a git ref.

The ref is resolved and its spec folder is archived into a temporary directory (``git archive``, a read-only git
command), then the graph is built there with the current toolkit registry.  The seed files the manifest names are
archived from the repository root, and ``read_seed_texts`` reads them under the archive root.  Git is run with an argument list and a
timeout; a missing git, a folder that is not a repository, an unknown ref and a spec folder absent at the ref are all
E708.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from specdev_tools.core.constants import DEFAULT_BRANCH_CANDIDATES
from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.generation.schema_differ import get_user_version
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph, Node, collapse_whitespace

GIT_TIMEOUT_SECONDS = 30
PREVIOUS_COMMIT = "HEAD~1"
_TREE_ENTRY = "040000 tree "
_MAX_REASON_CHARS = 240


class GitViewError(FindingError):
    """A ref could not be viewed; ``error`` is the ``SpecError`` that reports it (E708 or E709)."""


@dataclass(frozen=True)
class Snapshot:
    """The spec at one point: its graph and the text of each seed file.

    ``seeds`` maps a seed id to its whitespace-collapsed file content; a seed whose file is absent has no entry.
    """

    graph: Graph
    seeds: Mapping[str, str]


def _fail(code: str, message: str) -> GitViewError:
    return GitViewError(make_error(code, message))


def git_reason(process: subprocess.CompletedProcess[bytes]) -> str:
    text = " ".join(process.stderr.decode("utf-8", errors="replace").split())
    return text if len(text) <= _MAX_REASON_CHARS else text[:_MAX_REASON_CHARS].rstrip() + "..."


def run_git(git_root: str, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    """Run ``git -C <git_root> <args>`` (bytes out); E708 when git is missing or does not answer in time.

    The one place that starts git for the toolkit: ``trace.merge_driver`` uses it too and re-wraps the error."""
    try:
        return subprocess.run(["git", "-C", git_root, *args], capture_output=True, check=False, timeout=GIT_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise _fail("E708", "git is not installed or not on PATH") from None
    except subprocess.TimeoutExpired:
        raise _fail("E708", f"git {args[0]} did not finish within {GIT_TIMEOUT_SECONDS} seconds") from None


def require_git_root_folder(git_root: str) -> None:
    """E708 when *git_root* is not a folder."""
    if not os.path.isdir(git_root):
        raise _fail("E708", f"the git root {git_root} is not a directory")


def resolve_ref(ref: str, git_root: str) -> str:
    """The commit id that *ref* (a tag, branch or commit id) names in the repository at *git_root*.

    Raises:
        GitViewError: E708 when git is missing, *git_root* is not a repository or *ref* names no commit.
    """
    if ref.startswith("-"):
        raise _fail("E708", f"'{ref}' is not a git ref")
    require_git_root_folder(git_root)
    process = run_git(git_root, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    if process.returncode == 0:
        return process.stdout.decode("utf-8").strip()
    if "not a git repository" in git_reason(process).lower():
        raise _fail("E708", f"{git_root} is not a git repository")
    raise _fail("E708", f"ref '{ref}' does not name a commit in {git_root}")


def default_base_ref(git_root: str) -> str:
    """The commit where HEAD left the default branch, or ``HEAD~1`` when no default branch is found.

    The default branch is the first of ``DEFAULT_BRANCH_CANDIDATES`` that shares history with HEAD.

    Raises:
        GitViewError: E708 when git is missing or does not answer in time.
    """
    for candidate in DEFAULT_BRANCH_CANDIDATES:
        process = run_git(git_root, ["merge-base", "HEAD", candidate])
        if process.returncode == 0:
            return process.stdout.decode("utf-8").strip()
    return PREVIOUS_COMMIT


def host_root_of(spec_root: str, git_root: str | None = None) -> str:
    """The host repository root: *git_root* when given, else the folder that holds the spec folder (as ``spec-check`` derives it).

    Seed documents are read from here and git history is read here, so every command that takes ``--git-root``
    resolves an absent flag through this function, never to the current folder.
    """
    return os.path.abspath(git_root) if git_root else os.path.dirname(os.path.abspath(spec_root))


def relative_inside(root: str, path: str) -> str | None:
    """*path* relative to *root* (both resolved through symlinks), ``/``-separated; ``None`` when it lies outside *root*."""
    relative = os.path.relpath(os.path.realpath(path), os.path.realpath(root))
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return Path(relative).as_posix()


def spec_path_in_repo(spec_root: str, git_root: str) -> str:
    """The path of *spec_root* relative to *git_root*, ``/``-separated.

    Raises:
        GitViewError: E708 when *spec_root* is not inside *git_root*.
    """
    relative = relative_inside(git_root, spec_root)
    if relative is None:
        raise _fail("E708", f"the spec folder {spec_root} is not inside the git root {git_root}, so it cannot be found in the repository")
    return relative


def git_top_level(folder: str) -> str | None:
    """The top folder of the git working tree that holds *folder* (``git rev-parse --show-toplevel``); ``None`` outside a repository.

    The one home of this lookup: ``touched_steps``, ``validate._detect_git_root`` and the lock merge driver (through its own wrapper) call it.

    Raises:
        GitViewError: E708 when git is missing or does not answer in time.
    """
    process = run_git(folder, ["rev-parse", "--show-toplevel"])
    top = process.stdout.decode("utf-8", errors="replace").strip()
    return top if process.returncode == 0 and top else None


def _tree_entry(ref: str, git_root: str, path: str, *, from_top: bool = False) -> str:
    """The ``git ls-tree`` line of *path* at *ref* (``<mode> <type> <object>\t<path>``), empty when the path is absent.

    *path* is relative to *git_root*, or to the repository top with *from_top*.
    """
    commit = resolve_ref(ref, git_root)
    process = run_git(git_root, ["ls-tree", *(["--full-tree"] if from_top else []), commit, "--", path])
    if process.returncode != 0:
        raise _fail("E708", f"{path} cannot be looked up at ref '{ref}': {git_reason(process)}")
    return process.stdout.decode("utf-8", errors="replace").strip()


def path_exists_at(ref: str, git_root: str, path: str) -> bool:
    """Whether *path* (relative to *git_root*) exists at *ref*, as a file or a folder; ``False`` only when git answers that it does not.

    Raises:
        GitViewError: E708 when the ref does not resolve or git fails.
    """
    return bool(_tree_entry(ref, git_root, path))


def _prefix_in_repository(git_root: str) -> str:
    """The path of *git_root* inside its repository, ``/``-separated without the trailing slash; empty at the repository top.

    Raises:
        GitViewError: E708 when git fails.
    """
    process = run_git(git_root, ["rev-parse", "--show-prefix"])
    if process.returncode != 0:
        raise _fail("E708", f"{git_root} is not inside a git repository: {git_reason(process)}")
    return process.stdout.decode("utf-8", errors="replace").strip().rstrip("/")


def folder_exists_at(ref: str, git_root: str, path: str) -> bool:
    """Whether *path* (relative to *git_root*) is a folder at *ref*; a file, a link or nothing there is ``False``.

    Raises:
        GitViewError: E708 when the ref does not resolve or git fails.
    """
    path = os.path.normpath(path)
    if path == ".":
        # ls-tree of "." lists the content of the folder, not one tree line: ask about the folder itself, as git sees it
        prefix = _prefix_in_repository(git_root)
        if not prefix:
            resolve_ref(ref, git_root)  # the top of a repository is a folder at every commit
            return True
        return _tree_entry(ref, git_root, prefix, from_top=True).startswith(_TREE_ENTRY)
    return _tree_entry(ref, git_root, path).startswith(_TREE_ENTRY)


def archive_ref(ref: str, git_root: str, paths: Sequence[str]) -> tempfile.TemporaryDirectory[str]:
    """Extract *paths* (relative to *git_root*) as they are at *ref* into a new temporary directory.

    The caller owns the directory: use it as a context manager or call ``cleanup()``.

    Raises:
        GitViewError: E708 when the ref does not resolve, a path is absent at the ref, or git fails.
    """
    commit = resolve_ref(ref, git_root)
    process = run_git(git_root, ["archive", "--format=tar", commit, "--", *paths])
    if process.returncode != 0:
        raise _fail("E708", f"{', '.join(paths)} cannot be read at ref '{ref}': {git_reason(process)}")
    directory = tempfile.TemporaryDirectory(prefix="specdev-gitview-")
    try:
        with tarfile.open(fileobj=io.BytesIO(process.stdout)) as archive:
            archive.extractall(directory.name, filter="data")
    except (tarfile.TarError, OSError) as exc:
        directory.cleanup()
        raise _fail("E708", f"the archive of {', '.join(paths)} at ref '{ref}' cannot be unpacked: {exc}") from exc
    return directory


def _git_stdout(git_root: str, args: Sequence[str]) -> str:
    """The stdout of ``git -C <git_root> <args>``; E708 when git is missing, too slow or fails."""
    process = run_git(git_root, args)
    if process.returncode != 0:
        raise _fail("E708", f"git {args[0]} failed in {git_root}: {git_reason(process)}")
    return process.stdout.decode("utf-8", errors="replace")


def commits_touching(git_root: str, path: str, max_count: int) -> list[str]:
    """Up to *max_count* ids of the commits that touched *path* (relative to *git_root*), newest first.

    Raises:
        GitViewError: E708 when git is missing, too slow, or *git_root* is not a repository.
    """
    return _git_stdout(git_root, ["log", "--format=%H", f"--max-count={max_count}", "--", path]).split()


def is_shallow_repository(git_root: str) -> bool:
    """Whether the repository at *git_root* is a shallow clone.

    Raises:
        GitViewError: E708 when git is missing, too slow, or *git_root* is not a repository.
    """
    return _git_stdout(git_root, ["rev-parse", "--is-shallow-repository"]).strip() == "true"


def read_seed_texts(graph: Graph, host_root: str) -> dict[str, str]:
    """Whitespace-collapsed content of the file of each seed of *graph*, found under the directory *host_root*.

    A seed's path (``Node.file``) is read relative to *host_root*: the host root of the working tree, or the root of an
    archive extraction.  A seed whose file is missing, unreadable or outside *host_root* has no entry.
    """
    root = os.path.realpath(host_root)
    texts: dict[str, str] = {}
    for node in (n for n in graph.nodes if n.kind == SEED_KIND):
        path = os.path.realpath(os.path.join(root, node.file))
        if os.path.commonpath([root, path]) != root:
            continue
        try:
            texts[node.id] = collapse_whitespace(Path(path).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return texts


def missing_seeds(graph: Graph, texts: Mapping[str, str]) -> tuple[Node, ...]:
    """The seed nodes of *graph* that have no entry in *texts* (what ``read_seed_texts`` returned): their document was not found."""
    return tuple(node for node in graph.nodes if node.kind == SEED_KIND and node.id not in texts)


def read_seed_texts_noting(graph: Graph, host_root: str) -> dict[str, str]:
    """``read_seed_texts`` for a command that reads: it also says once on stderr which seed documents were not found.

    A seed that was not found makes its links suspect, which is what a wrong host root looks like; the line names the
    folder searched and ``--git-root``, so the cause is seen at the first read.
    """
    texts = read_seed_texts(graph, host_root)
    absent = missing_seeds(graph, texts)
    if absent:
        names = ", ".join(f"{node.file} ({node.id})" for node in absent)
        print(
            f"note: seed documents not found under {host_root}: {names}; their links count as suspect; "
            "if the repository root is another folder pass --git-root",
            file=sys.stderr,
        )
    return texts


def read_seed_texts_at(ref: str, git_root: str, graph: Graph) -> dict[str, str]:
    """Whitespace-collapsed seed texts as they are at *ref*: the seed files of *graph* archived from the repository root.

    A seed path is relative to the repository root (``schema/seed_manifest.schema.json``), so the files are archived
    from *git_root* and read under the archive root.  A seed file absent at *ref* has no entry.

    Raises:
        GitViewError: E708 when *ref* does not resolve or git fails.
    """
    paths = sorted({node.file for node in graph.nodes if node.kind == SEED_KIND})
    commit = resolve_ref(ref, git_root)
    try:
        return _read_archived_seeds(commit, git_root, graph, paths)
    except GitViewError:
        texts: dict[str, str] = {}
        for path in paths:
            try:
                texts.update(_read_archived_seeds(commit, git_root, graph, [path]))
            except GitViewError:
                continue
        return texts


def _read_archived_seeds(commit: str, git_root: str, graph: Graph, paths: Sequence[str]) -> dict[str, str]:
    """Archive *paths* at *commit* and read the seeds of *graph* under the archive root; ``{}`` for no paths."""
    if not paths:
        return {}
    with archive_ref(commit, git_root, paths) as root:
        return read_seed_texts(graph, root)


def _predates_message(ref: str, spec_dir: str) -> str:
    stamp = get_user_version(Path(spec_dir))
    seen = f"its spec is stamped toolkit {stamp}" if stamp else "its spec carries no toolkit stamp"
    return f"the tree at ref '{ref}' has no graph nodes (it may predate the 1.2.0 node model; {seen})"


def load_snapshot_at(ref: str, git_root: str, spec_path: str, repo_root: str) -> Snapshot:
    """The ``Snapshot`` of the spec folder *spec_path* (relative to *git_root*) at *ref*, built with the toolkit at *repo_root*.

    Raises:
        GitViewError: E708 when the ref or the spec folder at the ref cannot be read; E709 when the tree at the ref has
            no graph node (seeds do not count); a tree from before 1.2.0 that has ids the registry reads is compared as
            it is.
        KindRegistryError: the registry of the toolkit is missing or unreadable (E520).
    """
    from specdev_tools.graph.build import build_graph  # not at the top: the git merge driver imports this module and builds no graph

    with archive_ref(ref, git_root, [spec_path]) as archived:
        spec_dir = os.path.join(archived, spec_path)
        graph = build_graph(spec_dir, repo_root)
        if all(node.kind == SEED_KIND for node in graph.nodes):
            raise _fail("E709", _predates_message(ref, spec_dir))
        return Snapshot(graph, read_seed_texts_at(ref, git_root, graph))


def load_graph_at(ref: str, git_root: str, spec_path: str, repo_root: str) -> Graph:
    """The graph of the spec folder *spec_path* (relative to *git_root*) at *ref*; raises as ``load_snapshot_at`` does."""
    return load_snapshot_at(ref, git_root, spec_path, repo_root).graph
