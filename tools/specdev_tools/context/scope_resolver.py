"""Scope resolver for the DevSpec Toolkit context package.

``resolve_scope(entry_id, spec_dir, repo_root)`` is a thin alias over ``specdev trace`` (kept for one release): the
scope of an entry is its lineage (``trace --up``) and its impact (``trace --down``) in the spec graph.
"""
from __future__ import annotations

import os
import sys
from typing import Any

from ..graph.kinds import SEED_STEP, KindRegistryError
from ..graph.model import Node
from ..graph.trace import group_by_kind, trace_node


DEPRECATION_NOTE = "specdev context scope is deprecated and will be removed: use `specdev trace <id>`"


def _source_file(spec_dir_abs: str, node: Node) -> str:
    """The file of *node* as ``<spec folder name>/<path in the spec folder>``; a seed keeps its manifest path."""
    if node.step == SEED_STEP:
        return node.file
    return f"{os.path.basename(spec_dir_abs)}/{node.file}"


def resolve_scope(entry_id: str | None, spec_dir: str, repo_root: str) -> dict[str, Any]:
    """The scope of *entry_id*: its lineage and impact in the spec graph, with no siblings.

    Prints a one-line deprecation note on stderr.  ``entry_id=None`` gives an empty result with ``scope="all"``.

    Returns a dict with ``entry``, ``resolved_ids`` (kind to sorted ids, the entry included), ``source_files`` (id to
    ``{file, path}``) and, when the entry is not a node of the graph or the kind registry cannot be read,
    ``scope_warning``.  Never writes a file.
    """
    print(DEPRECATION_NOTE, file=sys.stderr)
    if not entry_id:
        return {"entry": None, "resolved_ids": {}, "source_files": {}, "scope": "all"}

    from ..graph.build import build_graph  # graph.build imports context._utils: a module-level import is a cycle

    spec_dir_abs = os.path.abspath(spec_dir)
    result: dict[str, Any] = {"entry": entry_id, "resolved_ids": {}, "source_files": {}}
    try:
        graph = build_graph(spec_dir_abs, os.path.abspath(repo_root))
    except KindRegistryError as exc:
        result["scope_warning"] = f"the spec graph could not be built ({exc}): scope is empty"
        return result
    if entry_id not in graph.by_id:
        result["scope_warning"] = f"entry_id '{entry_id}' not found in any spec file — scope may be incomplete"
        return result

    reached = trace_node(graph, entry_id).reached
    result["resolved_ids"] = {kind: sorted(node.id for node in nodes) for kind, nodes in group_by_kind(reached).items()}
    result["source_files"] = {
        node.id: {"file": _source_file(spec_dir_abs, node), "path": node.jq_path} for node in reached
    }
    return result
