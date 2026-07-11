"""entry_key_registry.py — deterministic entry-key registry for spec files.

Maps each spec file's top-level entry arrays to the canonical id field and
kind string for that array.  Used by json_utils to replace the interim
``_ID_CANDIDATE_FIELDS`` / ``_KIND_LOOKUP`` broad scan with a deterministic
per-file lookup.

Registry data location (toolkit-side)
--------------------------------------
The registry JSON file lives in the **toolkit** root under ``tools/``, NOT
in the host project's spec directory.  The canonical path is::

    <repo_root>/tools/entry_key_registry.json

where ``repo_root`` is the toolkit directory (typically ``./devspec_toolkit``
in submodule deployments).  The registry is generated from toolkit schemas
via ``specdev registry-generate --repo-root <toolkit>``.

All public API functions require a ``repo_root: str`` parameter (the filesystem
path to the toolkit root).  Calls without ``repo_root`` raise
``FileNotFoundError`` immediately rather than silently falling back to an empty
registry — missing ``repo_root`` indicates misconfiguration and must be loud.

Public API (what json_utils consumes)
--------------------------------------
list_entries(spec_file, repo_root)
    Return the registered (array_path, id_field, kind) tuples for a file,
    including nested array entries with their full dot-notation path.
    Returns an empty list if the file has no entry arrays in the registry
    (e.g. 13a, 16).  Returns None for **unknown** files (callers fall back
    to legacy broad scan).

find_entry(spec_file, id_value, repo_root)
    Not used by the current json_utils hot path (which iterates all entries
    via list_entries + index-builds), but exposed for the bundle assembler
    Not used by the current hot path but exposed for callers that need direct entry lookup.

is_corpus_excluded(array_key, repo_root)
    True for array keys that must never contribute to nearest-id corpus
    (e.g. ``canonical_refs_used``, ``canonical_proposals``).

Design constraints
------------------
- Pure functions, no I/O at import time — data loaded lazily on first call.
- Registry data lives toolkit-side at ``<repo_root>/tools/entry_key_registry.json``.
  Generated from schemas; projects must not hand-edit it.
- ``repo_root`` is a required parameter on all public API calls.  No env-var
  fallback, no implicit state.  Misconfiguration is loud (FileNotFoundError).
- Cache is keyed by ``os.path.realpath(repo_root)`` so that relative paths,
  symlinks, and absolute paths to the same directory collapse to one entry.
- No global feature list, no plugins, no extension points.
- Fallback to ``None`` (not empty list) for unknown filenames so callers can
  distinguish "known file with no arrays" from "unknown file".
- Steps registered with ``arrays: []`` (e.g. 13a, 16) return an empty list
  rather than None — callers skip the legacy broad scan for those files.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, FrozenSet, List, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class RegistryEntry(NamedTuple):
    """One registered (array, id_field, kind) triple for a spec file."""
    array_path: str   # jq path string, e.g. ".functional_requirements"
    id_field: str     # entry id field name, e.g. "fr_id"
    kind: str         # singular kind label, e.g. "functional_requirement"


# ---------------------------------------------------------------------------
# Data loading (lazy, per-spec_root cache, thread-safe)
# ---------------------------------------------------------------------------

# Cache is keyed by realpath(repo_root) → (registry_dict, excluded_keys_frozenset)
_REGISTRY_CACHE: Dict[str, Tuple[Dict[str, Any], FrozenSet[str]]] = {}
_LOAD_LOCK = threading.Lock()

# Always-excluded array keys — sentinel entries that signal corpus exclusion
# regardless of which spec file contains them.  Additional per-array
# exclusions are declared via ``corpus_excluded: true`` in the registry JSON
# and precomputed into the excluded-keys set at load time.
_ALWAYS_EXCLUDED = frozenset(["canonical_refs_used", "canonical_proposals"])

_REGISTRY_FILENAME = "entry_key_registry.json"


def _load(repo_root: str) -> Tuple[Dict[str, Any], FrozenSet[str]]:
    """Load registry JSON from ``<repo_root>/tools/entry_key_registry.json``, caching by realpath.

    Thread-safe via double-checked locking.  Returns ``(registry_dict,
    excluded_keys_frozenset)``.

    Args:
        repo_root: filesystem path to the toolkit root directory.  The registry
            is resolved at ``<repo_root>/tools/entry_key_registry.json``.
            Must be non-empty and non-None — omitting it is a misconfiguration.

    Raises:
        FileNotFoundError: if ``<repo_root>/tools/entry_key_registry.json`` does not exist,
            or if ``repo_root`` is None/empty.
            This is always a misconfiguration — do not catch silently.
    """
    if not repo_root:
        raise FileNotFoundError(
            "repo_root is required; toolkit registry at <repo_root>/tools/entry_key_registry.json"
        )
    cache_key = os.path.realpath(repo_root)
    if cache_key not in _REGISTRY_CACHE:
        with _LOAD_LOCK:
            if cache_key not in _REGISTRY_CACHE:
                path = os.path.join(repo_root, "tools", _REGISTRY_FILENAME)
                if not os.path.isfile(path):
                    raise FileNotFoundError(
                        f"Entry-key registry not found at {path!r}. "
                        f"Run 'specdev registry-generate --repo-root <toolkit>' to regenerate it "
                        f"(repo_root={repo_root!r})."
                    )
                with open(path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                registry = raw.get("registry", {})
                # Precompute the excluded keys set from per-array declarations.
                excluded: set = set(_ALWAYS_EXCLUDED)
                for _entry in registry.values():
                    if _entry.get("_special"):
                        continue
                    for _arr in _entry.get("arrays", []):
                        if _arr.get("corpus_excluded", False):
                            excluded.add(_arr["array_path"].lstrip("."))
                _REGISTRY_CACHE[cache_key] = (registry, frozenset(excluded))
    return _REGISTRY_CACHE[cache_key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_entries(spec_file: str, repo_root: str) -> Optional[List[RegistryEntry]]:
    """Return registered entry arrays for *spec_file* (basename-matched).

    Includes nested array entries with their full dot-notation path
    (e.g. ``.milestones[].tasks`` for tasks nested inside milestones).
    The list is flat — callers receive a single sequence of
    ``(array_path, id_field, kind)`` triples.

    Returns:
        - ``list`` (possibly empty) if the file is **known** to the registry.
          Empty list means the step's file has no entry arrays (e.g. 13a, 16).
        - ``None`` if the file is **unknown** — caller should fall back to the
          legacy broad ``_ID_CANDIDATE_FIELDS`` scan.

    Args:
        spec_file: basename or relative path of the spec file.
            ``"spec/04_fr_list.json"`` and ``"04_fr_list.json"`` both work.
        repo_root: filesystem path to the toolkit root directory.
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.

    Raises:
        FileNotFoundError: if entry_key_registry.json does not exist under
            ``<repo_root>/tools/``.
    """
    if not spec_file:
        return None  # None/empty → unknown file

    basename = os.path.basename(spec_file)
    registry, _ = _load(repo_root)

    if basename not in registry:
        return None  # unknown file — caller uses fallback

    entry = registry[basename]
    if entry.get("_special"):
        # sentinel (canonical_refs_used etc.) — no entry arrays
        return []

    arrays: List[RegistryEntry] = []
    for arr in entry.get("arrays", []):
        _flatten_entry(arr, arr["array_path"], arrays)
    return arrays


def _flatten_entry(
    node: Dict[str, Any],
    full_path: str,
    out: List[RegistryEntry],
) -> None:
    """Append *node* (and its ``nested`` descendants, recursively) to *out*.

    ``full_path`` is the resolved jq-style path to *node*'s array, with ``[]``
    separating each array level, e.g. ``.milestones`` at the top level and
    ``.milestones[].tasks[].acceptance_criteria`` three levels deep.  Each
    nested entry's own ``array_path`` is relative to a parent item, so the
    convention is ``<full_path>[].<child.array_path>``.  Recursion handles
    arbitrary depth (schema ``arrayEntry.nested`` is defined recursively).
    """
    out.append(RegistryEntry(
        array_path=full_path,
        id_field=node["id_field"],
        kind=node["kind"],
    ))
    for nested in node.get("nested", []):
        child_path = f"{full_path}[].{nested['array_path'].lstrip('.')}"
        _flatten_entry(nested, child_path, out)


def find_entry(
    spec_file: str,
    id_value: str,
    repo_root: str,
) -> Optional[Tuple[str, str, str]]:
    """Find registry entry for *id_value* in *spec_file*.

    Returns:
        ``(array_path, id_field, kind)`` if a matching array is registered,
        else ``None``.

    Note: This does NOT scan the actual file — it returns the registered
    tuple for the array that *should* contain entries of this id.  The caller
    must still index the file's data to locate the specific entry.

    Limitation: when multiple arrays in the same file all use bare ``id`` as
    their id field (e.g. ``edge_cases`` and ``trace`` in 11_redteam.json),
    there is no prefix heuristic to disambiguate them.  In that case this
    function returns ``None``.  Callers that need to locate a bare-id entry
    should iterate all arrays via ``list_entries`` and scan each one.

    Args:
        spec_file: basename or relative path.
        id_value: the id string to look up (e.g. "fr-newsletter-subscribe").
            Used only for suffix-based heuristics; the registry matches by
            array registration, not by scanning actual id values.
        repo_root: filesystem path to the toolkit root directory.
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.

    Raises:
        FileNotFoundError: if entry_key_registry.json does not exist under
            ``<repo_root>/tools/``.
    """
    entries = list_entries(spec_file, repo_root)
    if not entries:
        return None

    # Match by id field suffix convention: e.g. "fr-*" → fr_id field.
    # This is a best-effort hint for story-04 bundle use; json_utils does its
    # own per-entry scan via list_entries + index build.
    if len(entries) == 1:
        e = entries[0]
        return (e.array_path, e.id_field, e.kind)

    # Multiple arrays: pick by id prefix matching id_field stem.
    # e.g. "fr-*" → id starts with "fr-" → fr_id array
    # Arrays with id_field="id" yield stem="" — skip them; startswith("") is
    # always True and would silently match any id value.
    for e in entries:
        stem = e.id_field.replace("_id", "").replace("_", "-")
        if not stem:
            continue  # bare "id" field → no reliable prefix heuristic
        if id_value.startswith(stem + "-") or id_value.startswith(stem):
            return (e.array_path, e.id_field, e.kind)

    # Fall through: return None — callers that need disambiguation for bare-id
    # arrays must scan all arrays via list_entries (json_utils does this).
    return None


def is_corpus_excluded(array_key: str, repo_root: str) -> bool:
    """Return True if *array_key* must not contribute to nearest-id corpus.

    Always-excluded keys are hard-coded in ``_ALWAYS_EXCLUDED`` (e.g.
    ``canonical_refs_used``, ``canonical_proposals``); additional per-array
    exclusions can be declared via ``corpus_excluded: true`` in the registry
    JSON.  The excluded set is precomputed at first load so this function
    is O(1) on the hot path.

    Args:
        array_key: the raw top-level key of the array (e.g. "canonical_refs_used").
        repo_root: filesystem path to the toolkit root directory.
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.

    Raises:
        FileNotFoundError: if entry_key_registry.json does not exist under
            ``<repo_root>/tools/``.
    """
    _, excluded_keys = _load(repo_root)
    return array_key in excluded_keys


# ---------------------------------------------------------------------------
# array_path walking (shared by json_utils, matrix, and any consumer that
# resolves a registry array_path against actual spec data)
# ---------------------------------------------------------------------------

def iter_array_path(data: Any, array_path: str):
    """Yield ``(item, jq_index_path)`` for every leaf item at *array_path*.

    *array_path* is a registry-style jq path where ``[].`` separates each array
    level, e.g. ``.milestones``, ``.milestones[].tasks``, or
    ``.milestones[].tasks[].acceptance_criteria``.  A leading dot is optional.
    The walker descends through **all** array segments (arbitrary depth),
    iterating every element at each level, and yields each leaf-array item
    together with its concrete index path
    (e.g. ``.milestones[0].tasks[2].acceptance_criteria[1]``).

    Non-dict containers, missing keys, and non-list values are skipped silently
    — the same lenient contract the previous single-level implementations used.
    Only dict leaf items are yielded (callers read an id field off them).

    This replaces three separate ``partition("[].")`` reimplementations that
    each split on only the first array level and therefore silently dropped
    entries nested two-or-more levels deep.
    """
    if not isinstance(data, dict):
        return
    segments = array_path.lstrip(".").split("[].")

    def _descend(node: Any, seg_index: int, prefix: str):
        key = segments[seg_index]
        is_last = seg_index == len(segments) - 1
        if not isinstance(node, dict):
            return
        val = node.get(key)
        if not isinstance(val, list):
            return
        for idx, item in enumerate(val):
            item_path = f"{prefix}.{key}[{idx}]"
            if is_last:
                if isinstance(item, dict):
                    yield item, item_path
            elif isinstance(item, dict):
                yield from _descend(item, seg_index + 1, item_path)

    yield from _descend(data, 0, "")


def all_registered_basenames(repo_root: str) -> List[str]:
    """Return all non-sentinel basenames registered in the registry.

    Utility used by coverage tests to verify step_order.json coverage.

    Args:
        repo_root: filesystem path to the toolkit root directory.
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.
    """
    registry, _ = _load(repo_root)
    return [
        k for k, v in registry.items()
        if not v.get("_special", False)
    ]


def get_step_for_file(basename: str, repo_root: str) -> Optional[str]:
    """Return the step string for a registered basename, or None.

    Args:
        basename: spec file basename (e.g. "04_fr_list.json").
        repo_root: filesystem path to the toolkit root directory.
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.
    """
    registry, _ = _load(repo_root)
    entry = registry.get(basename)
    if entry and not entry.get("_special"):
        return entry.get("step")
    return None
