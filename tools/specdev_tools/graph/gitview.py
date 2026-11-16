"""The spec graph as it stood at a git ref.

The ref is resolved and its spec folder is archived into a temporary directory (``git archive``, a read-only git
command), then the graph is built there with the current toolkit registry.  Git is run with an argument list and a
timeout; a missing git, a folder that is not a repository, an unknown ref and a spec folder absent at the ref are all
E708.
"""
from __future__ import annotations

import io
import os
import subprocess
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from specdev_tools.core.constants import DEFAULT_BRANCH_CANDIDATES
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.generation.schema_differ import get_user_version
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import collapse_whitespace
from specdev_tools.graph.kinds import SEED_KIND
from specdev_tools.graph.model import Graph

GIT_TIMEOUT_SECONDS = 30
PREVIOUS_COMMIT = "HEAD~1"
_MAX_REASON_CHARS = 240


class GitViewError(Exception):
    """A ref could not be viewed; ``error`` is the ``SpecError`` that reports it (E708 or E709)."""

    def __init__(self, error: SpecError) -> None:
        super().__init__(error.message)
        self.error = error


@dataclass(frozen=True)
class Snapshot:
    """The spec at one point: its graph and the text of each seed file.

    ``seeds`` maps a seed id to its whitespace-collapsed file content; a seed whose file is absent has no entry.
    """

    graph: Graph
    seeds: Mapping[str, str]


def _fail(code: str, message: str) -> GitViewError:
    return GitViewError(make_error(code, message))


def _reason(process: subprocess.CompletedProcess[bytes]) -> str:
    text = " ".join(process.stderr.decode("utf-8", errors="replace").split())
    return text if len(text) <= _MAX_REASON_CHARS else text[:_MAX_REASON_CHARS].rstrip() + "..."


def _run_git(git_root: str, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    """Run ``git -C <git_root> <args>``; E708 when git is missing or does not answer in time."""
    try:
        return subprocess.run(["git", "-C", git_root, *args], capture_output=True, check=False, timeout=GIT_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise _fail("E708", "git is not installed or not on PATH") from None
    except subprocess.TimeoutExpired:
        raise _fail("E708", f"git {args[0]} did not finish within {GIT_TIMEOUT_SECONDS} seconds") from None


def resolve_ref(ref: str, git_root: str) -> str:
    """The commit id that *ref* (a tag, branch or commit id) names in the repository at *git_root*.

    Raises:
        GitViewError: E708 when git is missing, *git_root* is not a repository or *ref* names no commit.
    """
    if ref.startswith("-"):
        raise _fail("E708", f"'{ref}' is not a git ref")
    if not os.path.isdir(git_root):
        raise _fail("E708", f"the git root {git_root} is not a directory")
    process = _run_git(git_root, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    if process.returncode == 0:
        return process.stdout.decode("utf-8").strip()
    if "not a git repository" in _reason(process).lower():
        raise _fail("E708", f"{git_root} is not a git repository")
    raise _fail("E708", f"ref '{ref}' does not name a commit in {git_root}")


def default_base_ref(git_root: str) -> str:
    """The commit where HEAD left the default branch, or ``HEAD~1`` when no default branch is found.

    The default branch is the first of ``DEFAULT_BRANCH_CANDIDATES`` that shares history with HEAD.

    Raises:
        GitViewError: E708 when git is missing or does not answer in time.
    """
    for candidate in DEFAULT_BRANCH_CANDIDATES:
        process = _run_git(git_root, ["merge-base", "HEAD", candidate])
        if process.returncode == 0:
            return process.stdout.decode("utf-8").strip()
    return PREVIOUS_COMMIT


def spec_path_in_repo(spec_root: str, git_root: str) -> str:
    """The path of *spec_root* relative to *git_root*, ``/``-separated.

    Raises:
        GitViewError: E708 when *spec_root* is not inside *git_root*.
    """
    relative = os.path.relpath(os.path.realpath(spec_root), os.path.realpath(git_root))
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        raise _fail("E708", f"the spec folder {spec_root} is not inside the git root {git_root}, so it cannot be found in the repository")
    return Path(relative).as_posix()


def archive_ref(ref: str, git_root: str, paths: Sequence[str]) -> tempfile.TemporaryDirectory[str]:
    """Extract *paths* (relative to *git_root*) as they are at *ref* into a new temporary directory.

    The caller owns the directory: use it as a context manager or call ``cleanup()``.

    Raises:
        GitViewError: E708 when the ref does not resolve, a path is absent at the ref, or git fails.
    """
    commit = resolve_ref(ref, git_root)
    process = _run_git(git_root, ["archive", "--format=tar", commit, "--", *paths])
    if process.returncode != 0:
        raise _fail("E708", f"{', '.join(paths)} cannot be read at ref '{ref}': {_reason(process)}")
    directory = tempfile.TemporaryDirectory(prefix="specdev-gitview-")
    try:
        with tarfile.open(fileobj=io.BytesIO(process.stdout)) as archive:
            archive.extractall(directory.name, filter="data")
    except (tarfile.TarError, OSError) as exc:
        directory.cleanup()
        raise _fail("E708", f"the archive of {', '.join(paths)} at ref '{ref}' cannot be unpacked: {exc}") from exc
    return directory


def _seed_texts(spec_dir: str, graph: Graph) -> dict[str, str]:
    """Whitespace-collapsed content of each seed file found inside *spec_dir*; other seeds have no entry."""
    root = os.path.realpath(spec_dir)
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


def _predates_message(ref: str, spec_dir: str) -> str:
    stamp = get_user_version(Path(spec_dir))
    seen = f"its spec is stamped toolkit {stamp}" if stamp else "its spec carries no toolkit stamp"
    return f"the tree at ref '{ref}' has no graph nodes (it predates the 1.2.0 node model; {seen})"


def load_snapshot_at(ref: str, git_root: str, spec_path: str, repo_root: str) -> Snapshot:
    """The ``Snapshot`` of the spec folder *spec_path* (relative to *git_root*) at *ref*, built with the toolkit at *repo_root*.

    Raises:
        GitViewError: E708 when the ref or the spec folder at the ref cannot be read; E709 when the tree at the ref has
            no graph node (seeds do not count).
        KindRegistryError: the registry of the toolkit is missing or unreadable (E520).
    """
    with archive_ref(ref, git_root, [spec_path]) as archived:
        spec_dir = os.path.join(archived, spec_path)
        graph = build_graph(spec_dir, repo_root)
        if all(node.kind == SEED_KIND for node in graph.nodes):
            raise _fail("E709", _predates_message(ref, spec_dir))
        return Snapshot(graph, _seed_texts(spec_dir, graph))


def load_graph_at(ref: str, git_root: str, spec_path: str, repo_root: str) -> Graph:
    """The graph of the spec folder *spec_path* (relative to *git_root*) at *ref*; raises as ``load_snapshot_at`` does."""
    return load_snapshot_at(ref, git_root, spec_path, repo_root).graph
