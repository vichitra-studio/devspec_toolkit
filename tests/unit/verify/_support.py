"""Builders of the git repositories the verify tests run on: a small code repository, and the worked example as a host."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from unit.graph._synth import ROOT, git
from unit.trace._lock_support import git_copy_of_example

SEED_PATH = "docs/seed.md"


def write(path: Path, text: str) -> Path:
    """Write *text* to *path*, creating folders; returns *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path: Path, document: Any) -> Path:
    """Write *document* as JSON to *path*; returns *path*."""
    return write(path, json.dumps(document, indent=2) + "\n")


def commit_all(repo: Path, message: str = "change") -> None:
    """Stage everything in *repo* and commit it."""
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def code_repo(tmp_path: Path, name: str = "host", *, seeds: tuple[str, ...] = (SEED_PATH,), declarations: dict[str, Any] | None = None) -> Path:
    """A git repository with code under ``src/``, a spec folder with a seed manifest (and declarations), and one commit."""
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo / "src" / "app.py", "print('app')\n")
    write(repo / "docs" / "seed.md", "seed\n")
    manifest = {"seeds": [{"seed_id": f"seed-{index}", "path": path} for index, path in enumerate(seeds)]}
    write_json(repo / "spec" / "common" / "seed_manifest.json", manifest)
    write_json(repo / "spec" / "x.json", {"note": "spec"})
    if declarations is not None:
        write_json(repo / "spec" / "common" / "host_declarations.json", declarations)
    commit_all(repo, "initial")
    return repo


def example_host(tmp_path: Path, name: str = "host") -> Path:
    """The worked example as a git host (one commit); it holds a spec folder and seed documents and no code."""
    return git_copy_of_example(tmp_path / name)


def edit_doc(host: Path, rel: str, edit: Any) -> None:
    """Apply *edit* (a function of the parsed document, edited in place) to the spec file ``spec/<rel>`` of *host*."""
    path = host / "spec" / rel
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    write_json(path, document)


def graph_of(host: Path) -> Graph:
    """The graph of the spec folder of *host*, built with the real toolkit."""
    return build_graph(str(host / "spec"), str(ROOT))


def set_mtime_now(path: Path) -> None:
    """Make the modification time of *path* now plus one hour."""
    stamp = path.stat().st_mtime + 3600
    os.utime(path, (stamp, stamp))
