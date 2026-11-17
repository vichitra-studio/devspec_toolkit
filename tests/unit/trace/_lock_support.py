"""Helpers that build a trace lock from a graph, for tests; ``python -m`` runs ``regenerate_example_lock``."""
from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.model import Graph
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.lockfile import Lock, LockEntry, write_lock
from specdev_tools.trace.suspects import lock_links

ROOT = Path(__file__).parents[3]
EXAMPLE_HOST = ROOT / "tests" / "fixtures" / "graph_example"


def lock_for(graph: Graph, host_root: Path | str, *, only_holders: Iterable[str] | None = None) -> Lock:
    """The lock that accepts every link of *graph* as it is now: one entry per lock link, with the current hashes.

    With *only_holders*, only the links held by those node ids.  Seed text is read under *host_root*.
    """
    hashes = compute_all(graph, read_seed_texts(graph, str(host_root)))
    wanted = None if only_holders is None else set(only_holders)
    return Lock(tuple(
        LockEntry(item.holder.id, item.link.field, item.link.target, *hashes[item.target.id])
        for item in lock_links(graph)
        if wanted is None or item.holder.id in wanted
    ))


def regenerate_example_lock() -> None:
    """Rewrite ``tests/fixtures/graph_example/spec/extras/trace.lock.json`` from the worked example as it is now."""
    spec_dir = EXAMPLE_HOST / "spec"
    write_lock(str(spec_dir), lock_for(build_graph(str(spec_dir), str(ROOT)), EXAMPLE_HOST))


if __name__ == "__main__":
    regenerate_example_lock()
    sys.stdout.write("wrote tests/fixtures/graph_example/spec/extras/trace.lock.json\n")
