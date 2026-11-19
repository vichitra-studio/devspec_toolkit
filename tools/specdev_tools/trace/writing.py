"""The write skeleton of the commands that write spec files and the trace lock.

Kept apart from ``trace/lockfile.py`` (the lock file: format, reading, atomic replace, the advisory lock) because it
builds the graph: the git merge driver reads only the lock file and must not load ``graph.build``, and
``graph.lifecycle`` imports ``trace.lockfile``.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import missing_seeds, read_seed_texts
from specdev_tools.graph.model import Graph
from specdev_tools.trace.lockfile import with_write_lock


def refuse_unreadable(graph: Graph, what: str) -> None:
    """Raise a ``FindingError`` (E520) naming the spec files that could not be read, for a write *what* that plans from *graph*.

    A file that cannot be read gives no nodes, so the links it holds are not in the graph: a rename could not rewrite
    them, a delete could not list them, and ``attest --prune`` would take their lock entries for orphans.  Nothing is
    written until the file is repaired.  ``locked_graph`` applies it to every write; a dry run calls it on the graph it
    was given.
    """
    if graph.load_errors:
        files = ", ".join(error.file for error in graph.load_errors)
        raise FindingError(make_error(
            "E520",
            f"{what} refused: {files} cannot be read, so the links it holds are not in the graph and the lock "
            "cannot be checked against them; repair the file, then run the command again",
        ))


@contextmanager
def locked_graph(spec_root: str, repo_root: str, what: str) -> Iterator[Graph]:
    """Hold the write lock of *spec_root* and yield the graph built under it (the files as they are when written).

    A write plans from the graph built after the lock is taken, so a file changed by another process between the
    caller's own read and the lock is not planned from stale text.  Raises ``LockError`` (E769) when another write
    holds the lock, and E520 (``refuse_unreadable``, *what* names the command) when a spec file cannot be read.
    """
    with with_write_lock(spec_root):
        graph = build_graph(spec_root, repo_root)
        refuse_unreadable(graph, what)
        yield graph


@contextmanager
def writing_graph(graph: Graph | None, spec_root: str, repo_root: str, what: str, *, write: bool) -> Iterator[Graph]:
    """The one write skeleton: yield the graph a write *what* plans from.

    For a write (*write* true) the graph is built under the write lock (``locked_graph``).  For a dry run it is the
    caller's *graph* (built here when ``None``), refused when a spec file cannot be read, and no lock is taken.
    """
    if write:
        with locked_graph(spec_root, repo_root, what) as built:
            yield built
        return
    known = graph if graph is not None else build_graph(spec_root, repo_root)
    refuse_unreadable(known, what)
    yield known


def seed_texts_for_write(graph: Graph, host_root: str) -> dict[str, str]:
    """The seed texts a write takes its hashes from; E520 when a seed of *graph* has no document under *host_root*.

    A seed that is not found has no text, and a lock entry written from it would hold the hash of the missing text
    (``missing:<seed>``), accepted as if it were the document.  This is the one place every command that writes hashes
    into the lock (``attest --yes``, the id writes, ``step create``) reads its seed texts, a dry run included, so a
    wrong *host_root* (a spec folder not directly under the repository root, with no ``--git-root``) is refused before
    anything is written.
    """
    texts = read_seed_texts(graph, host_root)
    absent = missing_seeds(graph, texts)
    if absent:
        names = ", ".join(f"{node.file} ({node.id})" for node in absent)
        noun = "seed document" if len(absent) == 1 else "seed documents"
        verb = "was" if len(absent) == 1 else "were"
        raise FindingError(make_error(
            "E520",
            f"{noun} {names} {verb} not found under {host_root}; if the repository root is another folder pass --git-root",
        ))
    return texts
