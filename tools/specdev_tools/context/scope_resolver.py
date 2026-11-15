"""Scope resolver for the DevSpec Toolkit context package.

Implements ``resolve_scope(entry_id, spec_dir, repo_root) -> dict``.

Given an entity ID (e.g. a milestone, FR, capability), traverses the
trace graph to discover all reachable IDs and their source locations.

Phase A of the context package implementation.
"""
from __future__ import annotations

import collections
import json
import os
from typing import Any

from ..core.constants import resolve_extras_path


# ---------------------------------------------------------------------------
# ID prefix -> bucket name mapping for grouped output.
# ---------------------------------------------------------------------------
_PREFIX_TO_BUCKET: dict[str, str] = {
    "milestone": "milestones",
    "task": "tasks",
    "fr": "frs",
    "api": "apis",
    "fix": "fixtures",
    "fixture": "fixtures",
    "nfr": "nfrs",
    "threat": "threats",
    "cap": "capabilities",
    "inv": "invariants",
}

# Ordered bucket names (determines output key order)
_BUCKETS: list[str] = [
    "milestones",
    "tasks",
    "frs",
    "apis",
    "fixtures",
    "nfrs",
    "threats",
    "capabilities",
    "invariants",
]


def _id_to_bucket(entity_id: str) -> str:
    """Classify an entity ID into a bucket name by prefix heuristics."""
    for prefix, bucket in _PREFIX_TO_BUCKET.items():
        if entity_id.startswith(prefix + "-") or entity_id == prefix:
            return bucket
    return "other"


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _iter_spec_files(spec_dir: str):
    """Yield (abs_path, data) for every JSON file directly in *spec_dir* (non-recursive)."""
    spec_dir_abs = os.path.abspath(spec_dir)
    if not os.path.isdir(spec_dir_abs):
        return
    for fname in sorted(os.listdir(spec_dir_abs)):
        if not fname.endswith(".json"):
            continue
        full_path = os.path.join(spec_dir_abs, fname)
        if not os.path.isfile(full_path):
            continue
        try:
            data = _load_json(full_path)
        except (OSError, json.JSONDecodeError):
            continue
        yield full_path, data


# ---------------------------------------------------------------------------
# Trace graph construction
# ---------------------------------------------------------------------------

def _collect_entity_ids_and_traces(
    data: dict,
    file_path: str,
    # outputs written in-place
    id_to_file: dict[str, dict[str, str]],
    adjacency: dict[str, set[str]],
) -> None:
    """Walk a spec data dict, registering entity IDs and trace edges.

    For each object that has a ``*_id`` field (e.g. ``fr_id``, ``api_id``),
    the ID is registered with its file path and array index.

    For each ``trace`` array entry ``{type, id}`` and ``targets`` array entry,
    a directed edge is added in *adjacency* (bidirectional: both directions
    are added so BFS reaches everything).
    """

    def _scan(obj: Any, parent_array_key: str | None, array_index: int | None) -> None:
        if isinstance(obj, dict):
            # Collect entity definitions (*_id fields)
            entity_id: str | None = None
            for k, v in obj.items():
                if k.endswith("_id") and isinstance(v, str) and v:
                    entity_id = v
                    break  # one primary ID per object

            if entity_id:
                if entity_id not in id_to_file:
                    # Build a jq-like path descriptor
                    if parent_array_key is not None and array_index is not None:
                        jq_path = f".{parent_array_key}[{array_index}]"
                    else:
                        jq_path = "."
                    id_to_file[entity_id] = {
                        "file": file_path,
                        "path": jq_path,
                    }

                # Collect trace edges from this entity
                for trace_entry in obj.get("trace", []):
                    if isinstance(trace_entry, dict):
                        linked = trace_entry.get("id")
                        if isinstance(linked, str) and linked:
                            adjacency[entity_id].add(linked)
                            adjacency[linked].add(entity_id)

                # Collect targets edges (fixtures -> apis, threats -> apis)
                for target_entry in obj.get("targets", []):
                    if isinstance(target_entry, dict):
                        linked = target_entry.get("id")
                        if isinstance(linked, str) and linked:
                            adjacency[entity_id].add(linked)
                            adjacency[linked].add(entity_id)

                # Collect fr_refs (roadmap milestones/tasks -> FRs)
                for fr_ref in obj.get("fr_refs", []):
                    if isinstance(fr_ref, str) and fr_ref:
                        adjacency[entity_id].add(fr_ref)
                        adjacency[fr_ref].add(entity_id)

                # Collect source_milestones (roadmap tasks)
                for ms_ref in obj.get("source_milestones", []):
                    if isinstance(ms_ref, str) and ms_ref:
                        adjacency[entity_id].add(ms_ref)
                        adjacency[ms_ref].add(entity_id)

            # Recurse into values
            for k, v in obj.items():
                if isinstance(v, list):
                    for i, item in enumerate(v):
                        _scan(item, parent_array_key=k, array_index=i)
                elif isinstance(v, dict):
                    _scan(v, parent_array_key=None, array_index=None)

    _scan(data, parent_array_key=None, array_index=None)


def _build_trace_graph(spec_dir: str) -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    """Walk all spec files to build a complete trace graph.

    Returns:
        id_to_file: entity_id -> {"file": abs_path, "path": jq_path}
        adjacency: entity_id -> set of connected entity IDs (bidirectional)
    """
    id_to_file: dict[str, dict[str, str]] = {}
    adjacency: dict[str, set[str]] = collections.defaultdict(set)

    for file_path, data in _iter_spec_files(spec_dir):
        _collect_entity_ids_and_traces(data, file_path, id_to_file, adjacency)

    return id_to_file, adjacency


def _bfs_reachable(entry_id: str, adjacency: dict[str, set[str]]) -> set[str]:
    """BFS from *entry_id* over *adjacency*; returns all reachable IDs."""
    visited: set[str] = set()
    queue = collections.deque([entry_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for neighbour in adjacency.get(current, set()):
            if neighbour not in visited:
                queue.append(neighbour)
    return visited


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_scope(entry_id: str | None, spec_dir: str, repo_root: str) -> dict[str, Any]:
    """Resolve all spec entities reachable from *entry_id* via the trace graph.

    Parameters
    ----------
    entry_id:
        The ID to start traversal from (e.g. ``"milestone-02"``,
        ``"fr-payment-create"``).  Pass ``None`` to get an empty result
        with ``scope="all"`` as a signal for callers to include everything.
    spec_dir:
        Directory containing spec JSON files.
    repo_root:
        Path to the devspec_toolkit repo root.  Used to regenerate
        ``trace_matrix.json`` at the start of every context command
        (locked decision 4a).

    Returns
    -------
    dict with keys:
        entry, resolved_ids, source_files, [scope], [scope_warning]
    """
    if not entry_id:
        return {
            "entry": None,
            "resolved_ids": {},
            "source_files": {},
            "scope": "all",
        }

    spec_dir_abs = os.path.abspath(spec_dir)

    # Locked decision 4a: regenerate trace_matrix.json at start of every context command.
    repo_root_abs = os.path.abspath(repo_root)
    try:
        from ..validation.matrix import build_trace_matrix
        matrix_result = build_trace_matrix(repo_root_abs, spec_dir_abs)
        matrix_out = resolve_extras_path(spec_dir_abs, "trace_matrix.json")
        os.makedirs(os.path.dirname(matrix_out), exist_ok=True)
        with open(matrix_out, "w", encoding="utf-8") as _fh:
            json.dump(matrix_result, _fh, indent=2)
    except Exception:
        pass  # best-effort; in-memory graph continues regardless

    # ------------------------------------------------------------------
    # 1. Build trace graph from spec files.
    # ------------------------------------------------------------------
    id_to_file, adjacency = _build_trace_graph(spec_dir_abs)

    # ------------------------------------------------------------------
    # 2. BFS from entry_id.
    # ------------------------------------------------------------------
    reachable = _bfs_reachable(entry_id, adjacency)

    scope_warning: str | None = None
    if entry_id not in id_to_file:
        scope_warning = f"entry_id '{entry_id}' not found in any spec file — scope may be incomplete"

    # ------------------------------------------------------------------
    # 3. Group reachable IDs into buckets.
    # ------------------------------------------------------------------
    buckets: dict[str, list[str]] = {b: [] for b in _BUCKETS}
    other: list[str] = []

    for eid in sorted(reachable):
        bucket = _id_to_bucket(eid)
        if bucket in buckets:
            buckets[bucket].append(eid)
        else:
            other.append(eid)

    # Remove empty buckets from output (cleaner for consumers)
    resolved_ids: dict[str, list[str]] = {k: v for k, v in buckets.items() if v}
    if other:
        resolved_ids["other"] = sorted(other)

    # ------------------------------------------------------------------
    # 4. Build source_files mapping for known IDs.
    # ------------------------------------------------------------------
    source_files: dict[str, dict[str, str]] = {}
    for eid in reachable:
        if eid in id_to_file:
            entry_info = id_to_file[eid].copy()
            # Make the file path relative to spec_dir for portability
            abs_file = entry_info["file"]
            try:
                rel_file = os.path.relpath(abs_file, os.path.dirname(spec_dir_abs))
            except ValueError:
                rel_file = abs_file
            entry_info["file"] = rel_file
            source_files[eid] = entry_info

    result: dict[str, Any] = {
        "entry": entry_id,
        "resolved_ids": resolved_ids,
        "source_files": source_files,
    }
    if scope_warning:
        result["scope_warning"] = scope_warning
    return result
