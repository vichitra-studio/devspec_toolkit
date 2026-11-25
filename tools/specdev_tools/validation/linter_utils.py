"""Shared linter helper functions.

Helpers shared by hallucination_lint, spec_quality_lint and the other linters.

Created by FIX-002 (Batch 0).
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Collection
from typing import Any, Iterator

from ..canonical.registry import load_tier_entries
from ..core.json_utils import resolve_effective_toolkit_root
from ..core.loaders import iter_spec_artifacts
from ..graph.build import build_graph
from ..graph.kinds import KindRegistryError
from ..graph.model import Graph


# ---------------------------------------------------------------------------
# Stopword sets shared by the linters
# ---------------------------------------------------------------------------

CONTENT_STOPWORDS: frozenset[str] = frozenset({
    "that", "this", "with", "from", "have", "will", "been", "were", "they",
    "their", "than", "each", "which", "when", "what", "there", "about",
    "would", "make", "like", "into", "only", "also", "most", "some",
    "could", "should", "does", "must", "shall", "true", "false", "null",
    "http", "https", "schema", "json", "spec", "step",
})


# ---------------------------------------------------------------------------
# iter_json — replaces duplicate _iter_json helpers
# ---------------------------------------------------------------------------

def iter_json(spec_dir: str) -> Iterator[str]:
    """Yield paths to all ``.json`` spec artifacts under *spec_dir*, recursively.

    Delegates to :func:`~specdev_tools.core.loaders.iter_spec_artifacts` so
    non-artifact subdirectories (``samples/``, ``migration_backups/``) are
    excluded consistently across all callers.
    """
    yield from iter_spec_artifacts(spec_dir)


# ---------------------------------------------------------------------------
# Definition source — the graph for files it covers, the legacy scan for the rest
# ---------------------------------------------------------------------------

def build_lint_graph(spec_dir: str, repo_root: str | None = None) -> Graph | None:
    """Build the spec graph of *spec_dir* for the linters, or ``None`` when the registry is unavailable.

    *repo_root* is the toolkit root; ``None`` selects the toolkit this package belongs to.  ``None`` is the "no graph" answer: callers then scan every file for ids, as before the graph.
    """
    try:
        return build_graph(spec_dir, repo_root or resolve_effective_toolkit_root(None))
    except KindRegistryError:
        return None


def graph_covered_files(graph: Graph | None) -> frozenset[str]:
    """Spec-relative paths (``/``-separated) of the files that contribute at least one node to *graph*."""
    return frozenset(node.file for node in graph.nodes) if graph is not None else frozenset()


def graph_known_ids(graph: Graph | None) -> set[str]:
    """Every id a reference may name: the graph's nodes (first definition of each), their aliases and the root ``id`` of each document read.

    An id a person or a file wrote is looked up as an id, then as an alias (``Graph.find``), so an alias is known too.
    An artifact's own ``id`` is no node; a 1.1.1 ``trace`` entry may still name it.
    """
    if graph is None:
        return set()
    known = set(graph.by_id)
    known.update(graph.alias_index)
    known.update(root_id for document in graph.documents.values() if isinstance(root_id := document.get("id"), str))
    return known


# ---------------------------------------------------------------------------
# collect_ids_and_refs — replaces duplicates in hallucination_lint & spec_quality_lint
# ---------------------------------------------------------------------------

def collect_ids_and_refs(
    obj: Any,
    rel: str,
    ids: set[str],
    refs: list[tuple[str, str, str]],
    path: str = "",
    skip_ids_for_files: Collection[str] = frozenset(),
) -> None:
    """Walk *obj* and populate *ids* (definitions) and *refs* (references).

    An ID is any value under a key ending in ``_id``, or ``"id"`` when NOT in
    a reference context.  A ref is ``"id"`` or ``"target_id"`` inside a
    reference context, any ``*_ref`` string, or any item in ``*_refs`` lists.
    A file the graph covers (*skip_ids_for_files*) defines its ids through the
    graph, so none of its fields is added to *ids*; its refs are still collected.

    Parameters
    ----------
    obj : Any
        JSON-decoded object to walk.
    rel : str
        Relative path label for error context.
    ids : set[str]
        Accumulator for discovered IDs.
    refs : list[tuple[str, str, str]]
        Accumulator for discovered references as ``(rel, path, ref_id)``.
    path : str
        Current JSON path (dot-separated).
    skip_ids_for_files : Collection[str]
        Spec-relative paths (``/``-separated) of the files whose ids come from
        the graph.  *rel* is compared after its separators are normalised.
    """
    covered = rel.replace(os.sep, "/") in skip_ids_for_files
    _walk_ids_and_refs(obj, rel, None if covered else ids, refs, path)


def _walk_ids_and_refs(
    obj: Any,
    rel: str,
    ids: set[str] | None,
    refs: list[tuple[str, str, str]],
    path: str,
) -> None:
    """Recursive body of :func:`collect_ids_and_refs`; ``ids=None`` collects references only."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if ids is not None:
                if k.endswith("_id") and isinstance(v, str):
                    ids.add(v)
                if k == "id" and isinstance(v, str) and not is_reference_context(path):
                    ids.add(v)
            if k in {"id", "target_id"} and isinstance(v, str) and is_reference_context(path):
                refs.append((rel, p, v))
            if k.endswith("_ref") and isinstance(v, str):
                refs.append((rel, p, v))
            if k.endswith("_refs") and isinstance(v, list):
                for idx, item in enumerate(v):
                    if isinstance(item, str):
                        refs.append((rel, f"{p}[{idx}]", item))
            _walk_ids_and_refs(v, rel, ids, refs, p)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_ids_and_refs(item, rel, ids, refs, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# is_reference_context — replaces _in_ref_context / _is_reference_context
# ---------------------------------------------------------------------------

def is_reference_context(path: str) -> bool:
    """Return True if *path* indicates a reference container (trace, targets, etc.).

    Handles both ``hallucination_lint`` style (split on ``.``, strip ``[…]``)
    and ``spec_quality_lint`` style (regex strip ``[N]``).
    """
    if not path:
        return False
    normalized = re.sub(r"\[\d+\]", "", path)
    segments = {seg for seg in normalized.split(".") if seg}
    return bool(segments & {
        "trace", "targets", "target_ids", "mitigations",
        "dependencies", "links", "requires",
    })


# ---------------------------------------------------------------------------
# load_canonical_stages — shared by step_07 validator and hallucination_lint
# ---------------------------------------------------------------------------

def extract_command_string(entry: Any) -> str:
    """Return the command string for a test_commands[] entry.

    test_commands[] items use oneOf [string, object{command, command_ref, ...}]
    per schema/16_impl_context.schema.json. Returns "" when neither shape applies.
    """
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        cmd = entry.get("command")
        if isinstance(cmd, str):
            return cmd
    return ""


def is_resolved_canonical_ref(value: Any) -> bool:
    """Return True if *value* is the structural shape of a resolved canonical ref.

    A resolved ref is a dict with a string ``id`` starting with ``cn:``. This
    check is structural only — it does NOT verify the id resolves against the
    canonical registry. Callers that need resolution must invoke
    :meth:`CanonicalRegistry.resolve_alias` separately.
    """
    if not isinstance(value, dict):
        return False
    cid = value.get("id")
    return isinstance(cid, str) and cid.startswith("cn:")


def load_canonical_stages(canon_dir: str) -> set[str] | None:
    """Load canonical stage values from the ``stage`` entries of the canon (``canon/kinds/stage.json``).

    Falls back to canon/manifest.json legacy format.  Returns None if
    neither source can be loaded (caller falls back to KNOWN_STAGES).

    Parameters
    ----------
    canon_dir : str
        Path to the canon directory (e.g. ``<toolkit_root>/canon``).
    """
    # Primary: the stage entries of the canon, read through the registry loader (manifest.json and kinds/)
    canon_root = os.path.abspath(canon_dir)
    labels = {
        e["preferred_label"]
        for e in load_tier_entries(os.path.dirname(canon_root), os.path.basename(canon_root))
        if e.get("kind") == "stage" and isinstance(e.get("preferred_label"), str) and e.get("status") != "retired"
    }
    if labels:
        return labels

    # Fallback: canon/manifest.json (legacy)
    manifest_path = os.path.join(canon_dir, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        stages = manifest.get("stages", {})
        if isinstance(stages, dict):
            values = stages.get("values", [])
            if isinstance(values, list) and values:
                return {v["id"] for v in values if isinstance(v, dict) and isinstance(v.get("id"), str)}
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pass
    return None
