"""Shared linter helper functions.

Centralises duplicate helpers found across hallucination_lint, spec_quality_lint,
and forward_replay_check, eliminating ~200 LOC of near-identical code.

Created by FIX-002 (Batch 0).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Iterator

from ..core.errors import SpecError, make_error
from ..core.loaders import iter_spec_artifacts


# ---------------------------------------------------------------------------
# Stopword sets — aligned across hallucination_lint and forward_replay_check
# ---------------------------------------------------------------------------

DERIVATION_STOPWORDS: frozenset[str] = frozenset({
    "that", "this", "with", "from", "have", "will", "been", "were", "they",
    "their", "than", "each", "which", "when", "what", "there", "about",
    "would", "make", "like", "into", "only", "also", "most", "some",
    "could", "should", "does", "must", "shall", "true", "false", "null",
    "http", "https", "schema", "json", "spec", "step",
})

CONTENT_STOPWORDS: frozenset[str] = frozenset({
    "that", "this", "with", "from", "have", "will", "been", "were", "they",
    "their", "than", "each", "which", "when", "what", "there", "about",
    "would", "make", "like", "into", "only", "also", "most", "some",
    "could", "should", "does", "must", "shall", "true", "false", "null",
    "http", "https", "schema", "json", "spec", "step",
})


# ---------------------------------------------------------------------------
# tokenize_free_text — replaces 3 copies of free-text tokenizer
# ---------------------------------------------------------------------------

def tokenize_free_text(text: str, *, stopwords: frozenset[str] | None = None) -> set[str]:
    """Extract significant tokens: 4+ char lowercase words, no stopwords.

    Parameters
    ----------
    text : str
        Raw text to tokenize.
    stopwords : frozenset[str] | None
        Custom stopword set.  Defaults to ``DERIVATION_STOPWORDS``.

    Returns
    -------
    set[str]
        Set of significant tokens.
    """
    if stopwords is None:
        stopwords = DERIVATION_STOPWORDS
    return {
        w for w in re.findall(r"[a-z][a-z0-9_-]{3,}", text.lower())
        if w not in stopwords
    }


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
# collect_ids_and_refs — replaces duplicates in hallucination_lint & spec_quality_lint
# ---------------------------------------------------------------------------

def collect_ids_and_refs(
    obj: Any,
    rel: str,
    ids: set[str],
    refs: list[tuple[str, str, str]],
    path: str = "",
) -> None:
    """Walk *obj* and populate *ids* (definitions) and *refs* (references).

    An ID is any value under a key ending in ``_id``, or ``"id"`` when NOT in
    a reference context.  A ref is ``"id"`` or ``"target_id"`` inside a
    reference context, any ``*_ref`` string, any item in ``*_refs`` lists,
    or items in ``"requires"`` lists.

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
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
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
            if k == "requires" and isinstance(v, list):
                for idx, item in enumerate(v):
                    if isinstance(item, str):
                        refs.append((rel, f"{p}[{idx}]", item))
            collect_ids_and_refs(v, rel, ids, refs, p)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            collect_ids_and_refs(item, rel, ids, refs, f"{path}[{i}]")


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
# check_no_duplicates — replaces 11 independent duplicate-ID detection patterns
# ---------------------------------------------------------------------------

def check_no_duplicates(
    items: list[dict[str, Any]],
    id_field: str,
    label: str,
    errors: list[SpecError],
    *,
    code: str = "",
) -> None:
    """Append a :class:`SpecError` for each duplicate *id_field* found in *items*.

    Parameters
    ----------
    items : list[dict]
        Array of objects to check.
    id_field : str
        Key to extract the ID value from each item.
    label : str
        Human-readable label for error messages (e.g. ``"api_id"``).
    errors : list[SpecError]
        Error accumulator.
    code : str
        Error code (e.g. ``"E310"``).  Defaults to ``"E520"`` when empty.
    """
    seen: set[str] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        value = item.get(id_field)
        if not isinstance(value, str):
            continue
        if value in seen:
            errors.append(
                make_error(
                    code.strip() or "E520",
                    f"Duplicate {label} '{value}' at index {i}",
                )
            )
        seen.add(value)


# ---------------------------------------------------------------------------
# load_canonical_stages — shared by step_07 validator and hallucination_lint
# ---------------------------------------------------------------------------

def load_canonical_stages(canon_dir: str) -> set[str] | None:
    """Load canonical stage values from canon/kinds/stage.json.

    Falls back to canon/manifest.json legacy format.  Returns None if
    neither source can be loaded (caller falls back to KNOWN_STAGES).

    Parameters
    ----------
    canon_dir : str
        Path to the canon directory (e.g. ``<toolkit_root>/canon``).
    """
    # Primary: canon/kinds/stage.json
    stage_path = os.path.join(canon_dir, "kinds", "stage.json")
    try:
        with open(stage_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("entries", [])
        if isinstance(entries, list) and entries:
            labels = {
                e["preferred_label"]
                for e in entries
                if isinstance(e, dict)
                and isinstance(e.get("preferred_label"), str)
                and e.get("status") != "retired"
            }
            if labels:
                return labels
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pass

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
