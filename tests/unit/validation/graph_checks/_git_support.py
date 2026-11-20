"""Tiny git repositories for the scaffold tests: a repository, a submodule, a clone that has not initialised its submodule."""
from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from unit.graph._synth import GIT_IDENTITY

SUBMODULE = "theme"


def git(repo: Path, *args: str) -> str:
    """Run ``git -C repo args`` with a fixed identity and local-file submodules allowed; its stdout."""
    done = subprocess.run(
        ["git", *GIT_IDENTITY, "-c", "protocol.file.allow=always", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return done.stdout


def make_repo(path: Path, files: Mapping[str, str]) -> Path:
    """A repository at *path* with one commit holding *files* (path to text)."""
    path.mkdir(parents=True)
    git(path, "init", "-q")
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "files")
    return path


def make_host_with_submodule(root: Path, host_files: Mapping[str, str], submodule_files: Mapping[str, str]) -> Path:
    """A host repository whose ``theme`` folder is a checked-out submodule holding *submodule_files*."""
    library = make_repo(root / "library", submodule_files)
    host = make_repo(root / "host", host_files)
    git(host, "submodule", "add", "-q", str(library), SUBMODULE)
    git(host, "commit", "-q", "-m", "add the submodule")
    return host


def clone_without_submodules(host: Path, destination: Path) -> Path:
    """A clone of *host* that has not run ``submodule update``: the submodule folder is empty."""
    subprocess.run(["git", "clone", "-q", str(host), str(destination)], capture_output=True, check=True)
    return destination
