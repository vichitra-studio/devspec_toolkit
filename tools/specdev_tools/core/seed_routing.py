"""Shared seed-routing helpers for the DevSpec pipeline.

Provides two pure functions that centralise the logic for resolving which seed
IDs are required by a pipeline step and for mapping those IDs to absolute file
paths.  The functions are intentionally stateless and do not touch the
filesystem beyond ``os.path.join`` — all I/O and error-reporting is left to
callers.

Created for DEVSPEC-43 (generalise seed routing).
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_TRINITY_SUB_KEYS: Tuple[str, ...] = ("16a", "16b", "16c")


def resolve_seeds_for_step(
    step_id: str,
    manifest: Dict,
) -> Tuple[List[str], List[str]]:
    """Resolve seed IDs required by *step_id* from a parsed seed manifest.

    Parameters
    ----------
    step_id:
        Pipeline step identifier, e.g. ``"09"``, ``"16"``, ``"16b"``.
    manifest:
        Parsed ``seed_manifest.json`` dict.  Expected keys:

        * ``global_seed_order`` — list of seed_id strings defining load order.
        * ``seeds`` — list of ``{seed_id, path, ...}`` objects.
        * ``step_requirements`` — dict mapping step id → list of seed_ids.

        Any of these may be absent; the function handles that gracefully.

    Returns
    -------
    (global_seed_ids, step_seed_ids):
        *global_seed_ids* is ``manifest["global_seed_order"]`` verbatim (or
        ``[]`` if absent).  *step_seed_ids* is the ordered, de-duplicated list
        of seed IDs required by *step_id*, computed according to the
        three-branch routing logic below.

    Routing branches
    ----------------
    ``step_id == "16"``
        Raw set = union of ``step_requirements["16"] ∪ ["16a"] ∪ ["16b"] ∪
        ["16c"]``.  All four keys are consulted (including the bare ``"16"``
        key, unlike the legacy ``seed_lint._collect_required_seeds`` which
        skipped it).

    ``step_id ∈ {"16a", "16b", "16c"}``
        Raw set = ``step_requirements[step_id] ∪ step_requirements["16"]``.
        The bare ``"16"`` key acts as an umbrella that merges into every
        trinity sub-phase.

    Any other step_id
        Raw set = ``step_requirements[step_id]`` only.  The umbrella semantics
        are **16-family-only** and are NOT generalised to steps like ``"02a"``
        or ``"13a"``.

    Ordering of *step_seed_ids*
        Seeds in ``global_seed_order`` appear first (in global order).  Any
        step-required seed absent from ``global_seed_order`` is appended
        afterward in the order it was encountered while building the union.
        De-duplication: a seed appearing across multiple sub-keys counts once.
    """
    global_order: List[str] = list(manifest.get("global_seed_order") or [])
    step_requirements: Dict[str, List[str]] = manifest.get("step_requirements") or {}

    # ------------------------------------------------------------------
    # 1. Compute raw seed-id set (ordered by encounter for remainder step)
    # ------------------------------------------------------------------
    raw_ids: List[str] = _collect_raw_ids(step_id, step_requirements)

    # ------------------------------------------------------------------
    # 2. Order: global_seed_order first, then remainder in encounter order
    # ------------------------------------------------------------------
    step_seed_ids = _apply_ordering(raw_ids, global_order)

    return global_order, step_seed_ids


def resolve_seed_paths(
    manifest: Dict,
    seed_ids: List[str],
    host_root: str,
) -> Dict[str, str]:
    """Resolve a list of seed IDs to absolute paths under *host_root*.

    Parameters
    ----------
    manifest:
        Parsed ``seed_manifest.json`` dict.
    seed_ids:
        List of seed_id strings to resolve (order preserved in result).
    host_root:
        Absolute path to the host repository root (the ``--git-root`` value).
        Each ``seeds[].path`` entry is joined to this root via
        ``os.path.join(host_root, entry_path)``; if *entry_path* is already
        absolute ``os.path.join`` returns it unchanged.

    Returns
    -------
    dict mapping seed_id → absolute path string.
        A *seed_id* present in *seed_ids* but absent from
        ``manifest["seeds"]`` is **silently omitted** from the result — the
        E520 "unknown seed_id" error is reported elsewhere by seed_lint.
        Paths are returned WITHOUT existence-filtering; callers are responsible
        for checking whether files exist on disk.
    """
    # Build seed_id → path lookup from manifest
    seed_lookup: Dict[str, str] = {}
    for entry in manifest.get("seeds") or []:
        if isinstance(entry, dict):
            sid = entry.get("seed_id")
            path = entry.get("path")
            if sid and path:
                seed_lookup[sid] = path

    result: Dict[str, str] = {}
    for seed_id in seed_ids:
        if seed_id not in seed_lookup:
            continue  # silently omit unknown seed IDs
        entry_path = seed_lookup[seed_id]
        abs_path = os.path.join(host_root, entry_path)
        result[seed_id] = abs_path

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_raw_ids(
    step_id: str,
    step_requirements: Dict[str, List[str]],
) -> List[str]:
    """Return a de-duplicated list of seed IDs in encounter order.

    The list preserves the order in which IDs were first seen across the
    keys consulted for *step_id*.
    """
    seen: set[str] = set()
    result: List[str] = []

    def _add(ids: List[str]) -> None:
        for sid in (ids or []):
            if sid not in seen:
                seen.add(sid)
                result.append(sid)

    if step_id == "16":
        # Aggregate: bare "16" key PLUS all three trinity sub-keys.
        _add(step_requirements.get("16", []))
        for sub in _TRINITY_SUB_KEYS:
            _add(step_requirements.get(sub, []))
    elif step_id in _TRINITY_SUB_KEYS:
        # Sub-phase: own requirements PLUS the umbrella bare "16" key.
        _add(step_requirements.get(step_id, []))
        _add(step_requirements.get("16", []))
    else:
        # Plain step: own requirements only, no umbrella.
        _add(step_requirements.get(step_id, []))

    return result


def _apply_ordering(raw_ids: List[str], global_order: List[str]) -> List[str]:
    """Order *raw_ids* by *global_order* position; append the rest.

    Replicates the ordering logic in ``seed_lint._collect_required_seeds``
    (lines 63-65)::

        ordered = [s for s in global_order if s in required]
        remaining = [s for s in required if s not in set(global_order)]

    The difference here is that *raw_ids* is already a de-duplicated list in
    encounter order, so "remaining" preserves encounter order rather than set
    iteration order (which is non-deterministic in the original).
    """
    required_set = set(raw_ids)
    global_set = set(global_order)

    ordered = [s for s in global_order if s in required_set]
    remaining = [s for s in raw_ids if s not in global_set]

    return ordered + remaining
