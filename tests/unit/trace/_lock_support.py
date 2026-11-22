"""Helpers that build a trace lock from a graph, for tests; ``python -m`` runs ``regenerate_example_lock``."""
from __future__ import annotations

import shlex
import shutil
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.model import Graph
from specdev_tools.trace import gaps
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import containers_of
from specdev_tools.trace.lockfile import Lock, LockEntry, write_lock
from specdev_tools.trace.suspects import lock_links

ROOT = Path(__file__).parents[3]
EXAMPLE_HOST = ROOT / "tests" / "fixtures" / "graph_example"


@pytest.fixture
def gap_providers(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """``register_gap_provider`` for one test, starting with NO provider registered; the registered providers (module state) are restored when it ends.

    The one fixture of the tests that register a coverage-gap provider, or that need the worked example without the role
    gaps it reports under the real graph checks: ``cli.main`` installs the role gap provider each time it builds its
    parser, so the fixture also turns ``install_gap_provider`` into a no-op for the test.  Import it into the test module.
    """
    from specdev_tools.validation import graph_checks  # local: trace does not import validation

    saved = list(gaps._providers)
    gaps._providers.clear()
    monkeypatch.setattr(graph_checks, "install_gap_provider", lambda: None)
    yield gaps.register_gap_provider
    gaps._providers[:] = saved


def lock_for(graph: Graph, host_root: Path | str, *, only_holders: Iterable[str] | None = None) -> Lock:
    """The lock that accepts every link of *graph* as it is now: one entry per lock link, with the current hashes.

    With *only_holders*, only the links held by those node ids.  Seed text is read under *host_root*.
    """
    hashes = compute_all(graph, read_seed_texts(graph, str(host_root)))
    wanted = None if only_holders is None else set(only_holders)
    return Lock(tuple(
        LockEntry(item.holder.id, item.link.field, item.link.target, *hashes[item.target.id], target_containers=containers_of(graph, item.target))
        for item in lock_links(graph)
        if wanted is None or item.holder.id in wanted
    ))


def git_copy_of_example(destination: Path) -> Path:
    """Copy the worked example to *destination* (a new folder), make it a git repository with one commit, and return it.

    The folder holds ``spec`` and ``docs`` as in a host repository; commands run on it take ``--spec-root ./spec``
    and ``--git-root .`` from inside it (see ``run_on_example``).
    """
    from unit.graph._synth import git  # local: _synth imports the CLI, which this module need not load

    shutil.copytree(EXAMPLE_HOST, destination)
    git(destination, "init", "-q", "-b", "main")
    git(destination, "add", "-A")
    git(destination, "commit", "-q", "-m", "worked example")
    return destination


def run_on_example(host: Path, *argv: str) -> tuple[int, str]:
    """Run ``specdev <argv>`` on the copy *host* with the three root flags of a submodule deployment: ``(exit code, output)``."""
    from unit.graph._synth import run_cli  # local, as above

    return run_cli(*argv, "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))


def regenerate_example_lock() -> None:
    """Rewrite ``tests/fixtures/graph_example/spec/extras/trace.lock.json`` from the worked example as it is now."""
    spec_dir = EXAMPLE_HOST / "spec"
    write_lock(str(spec_dir), lock_for(build_graph(str(spec_dir), str(ROOT)), EXAMPLE_HOST))


if __name__ == "__main__":
    regenerate_example_lock()
    sys.stdout.write("wrote tests/fixtures/graph_example/spec/extras/trace.lock.json\n")


DRIVER_COMMAND = f"{shlex.quote(sys.executable)} -m specdev_tools.cli lock merge"
"""The command a host's git configuration runs to merge the trace lock."""
