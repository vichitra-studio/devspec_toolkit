"""The code tree id: a git tree id of the host's code, with the spec folder, the seed documents and the declared exclusions left out.

The id says which code a run or an attestation is about.  It is the tree git would write for the working tree (edits,
deletions and untracked files that are not ignored included) minus the files the declared exclusions name; it is built in a
temporary index, so the repository's own index and refs are never touched and a commit is not needed.  With ``commit`` the
id is that commit's tree minus the same paths, which equals the id of a clean checkout of the commit.

``code_tree_for_host`` is the entry point every other module uses: it reads the host declarations and the seed manifest and
takes no owner argument.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.host_declarations import HostDeclarations, HostDeclarationsError, load_host_declarations
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.seed_routing import resolve_seed_paths
from specdev_tools.graph.gitview import GitViewError, git_reason, relative_inside, resolve_ref, run_git

SEED_MANIFEST_FILE = "common/seed_manifest.json"
"""The seed manifest, relative to the spec folder."""

_INDEX_NAME = "index"


def same_code_tree(first: str, second: str) -> bool:
    """Whether two code tree ids name the same tree."""
    return first == second


def _git_failure(args: Sequence[str], process: subprocess.CompletedProcess[bytes]) -> GitViewError:
    return GitViewError(make_error("E708", f"git {args[0]} failed while the code tree was computed: {git_reason(process)}"))


def _git_in_index(git_root: str, index: str, args: Sequence[str]) -> str:
    """The stdout of ``git -C <git_root> <args>`` run on the index file *index* (``run_git`` with ``GIT_INDEX_FILE`` set); E708 when git fails."""
    process = run_git(git_root, args, env={**os.environ, "GIT_INDEX_FILE": index})
    if process.returncode != 0:
        raise _git_failure(args, process)
    return process.stdout.decode("utf-8", errors="replace")


def _has_head(git_root: str) -> bool:
    return run_git(git_root, ["rev-parse", "--verify", "--quiet", "HEAD^{commit}"]).returncode == 0


def _start_of_index(git_root: str, commit: str | None) -> str | None:
    """The commit the temporary index starts from: *commit*, else HEAD; ``None`` for a repository with no commit."""
    if commit is not None:
        return resolve_ref(commit, git_root)
    return "HEAD" if _has_head(git_root) else None


def code_tree_id(git_root: str, spec_root: str, seed_paths: Sequence[str], exclusions: Sequence[str], commit: str | None = None) -> str:
    """The code tree id of the repository at *git_root*.

    The tree is HEAD's, with the working tree on top (``git add -A``); with *commit* it is that commit's, with nothing on top.
    The spec folder *spec_root* (when it lies inside *git_root*), every path of *seed_paths* (relative to *git_root*) and
    every pathspec of *exclusions* are taken out of it.  Nothing in the repository changes except that git stores the tree.

    Raises:
        GitViewError: E708 when git is missing or fails, *git_root* is not a repository or *commit* names no commit.
    """
    root = os.path.abspath(git_root)
    start = _start_of_index(root, commit)
    spec_path = relative_inside(root, spec_root)
    removals = [*([spec_path] if spec_path is not None else []), *seed_paths, *exclusions]
    with tempfile.TemporaryDirectory(prefix="specdev-code-tree-") as folder:
        index = os.path.join(folder, _INDEX_NAME)
        if start is not None:
            _git_in_index(root, index, ["read-tree", start])
        if commit is None:
            _git_in_index(root, index, ["add", "-A"])
        if removals:
            _git_in_index(root, index, ["rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", *removals])
        return _git_in_index(root, index, ["write-tree"]).strip()


def seed_pathspecs(git_root: str, spec_root: str) -> list[str]:
    """The paths of the seed documents of the manifest under *spec_root*, relative to *git_root*; a seed outside *git_root* is left out.

    A host with no manifest has none.
    """
    manifest = read_json_object(os.path.join(spec_root, SEED_MANIFEST_FILE))
    if manifest is None:
        return []
    seed_ids = [entry["seed_id"] for entry in manifest.get("seeds") or [] if isinstance(entry, dict) and "seed_id" in entry]
    resolved = resolve_seed_paths(manifest, seed_ids, git_root).values()
    relative = (relative_inside(git_root, path) for path in resolved)
    return [path for path in relative if path is not None]


def declarations_of(spec_root: str) -> HostDeclarations:
    """The host declarations of *spec_root*.

    Raises:
        FindingError: E520 when the declarations file cannot be read or breaks its schema.
    """
    try:
        return load_host_declarations(spec_root)
    except HostDeclarationsError as exc:
        raise FindingError(make_error("E520", f"the host declarations {exc.path} cannot be read: {exc.reason}; correct the file")) from exc


def code_tree_for_host(git_root: str, spec_root: str, commit: str | None = None, *, spec_in_host: str | None = None) -> str:
    """The code tree id of the host: ``code_tree_id`` with the seed documents of the manifest and the declared ``code_tree_exclusions`` left out.

    The manifest and the declarations are read from *spec_root*.  The spec folder taken out of the tree is *spec_in_host* when
    given, else *spec_root*: a spec read from an archive of a past commit (outside the host) leaves the same files out as the
    live spec folder it was archived from.

    Raises:
        GitViewError: E708, as ``code_tree_id``.
        FindingError: E520 when the host declarations file cannot be read.
    """
    declarations = declarations_of(spec_root)
    return code_tree_id(git_root, spec_in_host or spec_root, seed_pathspecs(git_root, spec_root), declarations.code_tree_exclusions, commit)


def dirty_submodules(git_root: str) -> list[str]:
    """The paths (relative to *git_root*) of the initialised submodules that hold uncommitted content, sorted.

    The code tree holds a submodule as the commit it has checked out, so its uncommitted content is not in the id.
    """
    process = run_git(git_root, ["submodule", "status"])
    if process.returncode != 0:
        return []
    lines = process.stdout.decode("utf-8", errors="replace").splitlines()
    paths = [line[1:].split(" ", 1)[1].rsplit(" (", 1)[0] for line in lines if line and line[0] != "-"]
    return sorted(path for path in paths if run_git(os.path.join(git_root, path), ["status", "--porcelain"]).stdout.strip())


def submodule_warnings(git_root: str) -> list[SpecError]:
    """One W350 for each submodule of *git_root* with uncommitted content."""
    return [
        make_error("W350", f"submodule '{path}' has uncommitted content that the code tree does not see; commit it in the submodule and update the pointer here")
        for path in dirty_submodules(git_root)
    ]
