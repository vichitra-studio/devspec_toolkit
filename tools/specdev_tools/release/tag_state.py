"""The spec as it stood at a commit, with the checkout's evidence: the one reader of "the state at a tag".

The previous release is judged on the graph, the declarations and the exclusions it had (ruling N3), so a binding added after it
is not missing evidence for it and a later ``code_tree_exclusions`` does not change the code tree its evidence was made on.  The
evidence is the checkout's: it reached the release commit through reviewed pull requests, and the code tree it names is the one
of the commit being read.

``tag_state`` archives the spec folder at the commit (``gitview.archive_ref``), builds the graph there and returns it with a
``ProofContext`` whose ``evidence_dir`` is the checkout's and whose ``spec_in_host`` is the checkout's spec folder (so the code
tree leaves that folder out, as it does for the live spec), and a ``GraphCheckContext`` that asks ``built_at_cap`` through that
proof context.  The archive lives while the ``with`` block does.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from specdev_tools.core.errors import refusal
from specdev_tools.core.host_declarations import HostDeclarations
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import archive_ref, resolve_ref, spec_path_in_repo
from specdev_tools.graph.model import Graph
from specdev_tools.lifecycle.executed import lock_if_present
from specdev_tools.proof.built_evidence import bind_proof_context, bind_proof_seams
from specdev_tools.proof.validity import ProofContext
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.verify.records import records_folder


def release_tag_pattern(declarations: HostDeclarations) -> str:
    """The host's ``release_tag_pattern``: the one reader of that declaration for the release gate and the rollback record.

    Raises:
        FindingError: E911 when the host declares none or declares something that is not a regular expression.
    """
    pattern = declarations.release_tag_pattern
    if not pattern:
        raise refusal("E911", "the host declares no release_tag_pattern; add one to spec/common/host_declarations.json (a regular expression, for example ^v[0-9]+[.][0-9]+[.][0-9]+$)")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise refusal("E911", f"the release_tag_pattern {pattern!r} is not a regular expression ({exc}); correct it in spec/common/host_declarations.json") from exc
    return pattern


def tag_matches(pattern: str, tag: str) -> bool:
    """Whether *tag* is a release tag: *pattern* is found in it (``re.search``)."""
    return re.search(pattern, tag) is not None


@dataclass(frozen=True)
class TagState:
    """The spec at ``commit``: its folder (an archive, gone when the block ends), graph, lock, proof context and graph-check context."""

    commit: str
    spec_dir: str
    graph: Graph
    lock: Lock | None
    proof: ProofContext
    checks: GraphCheckContext


@contextmanager
def tag_state(git_root: str, spec_root: str, repo_root: str, ref: str) -> Iterator[TagState]:
    """The ``TagState`` of the commit *ref* names, for the host at *git_root* whose spec folder is *spec_root*.

    Raises:
        GitViewError: E708 when *ref* does not resolve or the spec folder is absent at it (a release cut before the spec existed).
        FindingError: E760 when the lock at the commit cannot be read; E520 when the toolkit's ownership table cannot be read.
    """
    commit = resolve_ref(ref, git_root)
    relative = spec_path_in_repo(spec_root, git_root)
    bind_proof_seams()
    with archive_ref(commit, git_root, [relative]) as archive:
        spec_dir = os.path.join(archive, relative)
        graph = build_graph(spec_dir, repo_root)
        lock = lock_if_present(spec_dir)
        proof = ProofContext(git_root, spec_dir, records_folder(spec_root), commit=commit, spec_in_host=os.path.abspath(spec_root))
        checks = GraphCheckContext.from_graph(graph, lock, repo_root, git_root=git_root, spec_root=spec_dir)
        bind_proof_context(checks, proof)
        yield TagState(commit, spec_dir, graph, lock, proof, checks)
