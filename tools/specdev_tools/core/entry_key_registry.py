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

import fnmatch
import json
import os
import re
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
ALWAYS_EXCLUDED = frozenset(["canonical_refs_used", "canonical_proposals"])
_ALWAYS_EXCLUDED = ALWAYS_EXCLUDED  # earlier name, kept for existing importers

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
                            excluded.add(array_top_key(_arr["array_path"]))
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

    registry, _ = _load(repo_root)
    key = _match_registry_key(spec_file, registry)
    if key is None:
        return None  # unknown file — caller uses fallback

    entry = registry[key]
    if entry.get("_special"):
        # sentinel (canonical_refs_used etc.) — no entry arrays
        return []

    arrays: List[RegistryEntry] = []
    for arr in entry.get("arrays", []):
        _flatten_entry(arr, arr["array_path"], arrays)
    return arrays


def is_glob_key(key: str) -> bool:
    """True when a registry file key is a glob (``impl_context/ms_*_plan.json``)."""
    return "*" in key or "?" in key or "[" in key


def match_glob_key(spec_file: str, key: str) -> bool:
    """True when *spec_file* (relative path or basename) matches the glob *key*.

    The key is relative to the spec directory, so a spec path such as
    ``spec/impl_context/ms_1_plan.json`` matches ``impl_context/ms_*_plan.json``
    by its trailing path components.
    """
    path_parts = spec_file.replace(os.sep, "/").split("/")
    key_parts = key.split("/")
    if len(path_parts) < len(key_parts):
        return False
    # Segment-wise, so a ``*`` never crosses a ``/`` (the same rule ``glob.glob`` applies).
    tail = path_parts[-len(key_parts):]
    return all(fnmatch.fnmatchcase(p, k) for p, k in zip(tail, key_parts))


def _match_registry_key(spec_file: str, registry: Dict[str, Any]) -> Optional[str]:
    """Registry key for *spec_file*: the basename, else the first matching glob key."""
    basename = os.path.basename(spec_file)
    if basename in registry:
        return basename
    for key in registry:
        if is_glob_key(key) and match_glob_key(spec_file, key):
            return key
    return None


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
        # A map-keyed node has no id field: the map key is the id (see iter_nodes).
        id_field=node.get("id_field", ""),
        kind=node["kind"],
    ))
    for nested in node.get("nested", []):
        child_path = join_nested_path(full_path, nested["array_path"])
        _flatten_entry(nested, child_path, out)


def join_nested_path(parent_full: str, relative: str) -> str:
    """Full path of a nested entry: ``<parent>[]<relative>``, or ``<parent><relative>`` under a map.

    A map-keyed parent's full path already ends in ``{}``, which plays the part of ``[]``.
    """
    rel = "." + relative.lstrip(".")
    if parent_full.endswith("{}"):
        return parent_full + rel
    return f"{parent_full}[]{rel}"


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

_SEG = r"[A-Za-z_][A-Za-z0-9_]*"
_TOKEN_RE = re.compile(rf"\.?({_SEG}(?:\.{_SEG})*)(\[\]|\{{\}})?")
_KEY_RE = re.compile(rf"^\.?({_SEG})")


def _parse_array_path(array_path: str) -> List[Tuple[List[str], str]]:
    """Split a registry ``array_path`` into ``(keys, marker)`` hops.

    Grammar: ``.name`` descends an object property (dotted names chain), ``[]`` follows an
    array-valued property, ``{}`` follows a map-valued property.  Each hop is the dotted keys
    walked from the current object plus the marker that ends it (``"[]"``, ``"{}"`` or ``""``
    for the final hop of an array path).  Raises ``ValueError`` on a malformed path.
    """
    text = array_path if array_path.startswith(".") else "." + array_path
    hops: List[Tuple[List[str], str]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None or m.start() != pos:
            raise ValueError(f"malformed array_path {array_path!r}")
        hops.append((m.group(1).split("."), m.group(2) or ""))
        pos = m.end()
    if not hops:
        raise ValueError(f"malformed array_path {array_path!r}")
    return hops


parse_array_path = _parse_array_path  # public name; the underscore name stays for existing importers


def array_top_key(array_path: str) -> str:
    """First property name of *array_path*: ``.a.b[].c`` -> ``a``, ``.env{}`` -> ``env``."""
    m = _KEY_RE.match(array_path)
    if m is None:
        raise ValueError(f"malformed array_path {array_path!r}")
    return m.group(1)


def array_leaf_key(array_path: str) -> str:
    """Last property name of *array_path*: ``.m[].tasks`` -> ``tasks``, ``.plan.items`` -> ``items``."""
    return _parse_array_path(array_path)[-1][0][-1]


def iter_nodes(data: Any, array_path: str):
    """Yield ``(item, concrete_path, key_or_None)`` for every node at *array_path*.

    *array_path* uses the registry grammar: ``.name`` descends an object property,
    ``[]`` follows an array property, ``{}`` follows a map property whose keys are the node
    ids.  A leading dot is optional.  Examples: ``.functional_requirements``,
    ``.milestones[].tasks``, ``.plan.items``, ``.environments{}``.

    ``key_or_None`` is the map key for a node under a ``{}`` leaf, else ``None``.  The concrete
    path is jq-style: ``.milestones[0].tasks[2]``, ``.environments["prod"]``.

    Non-dict containers, missing keys and wrongly typed values are skipped silently.  Only dict
    nodes are yielded (callers read an id field off them).
    """
    if not isinstance(data, dict):
        return
    hops = _parse_array_path(array_path)
    last = len(hops) - 1

    def _descend(node: Any, hop_index: int, prefix: str):
        if not isinstance(node, dict):
            return
        keys, marker = hops[hop_index]
        cur: Any = node
        for k in keys:
            if not isinstance(cur, dict):
                return
            cur = cur.get(k)
        base = prefix + "." + ".".join(keys)
        is_last = hop_index == last
        if marker == "{}":
            if not isinstance(cur, dict):
                return
            for key, item in cur.items():
                item_path = f"{base}[{json.dumps(key)}]"
                if is_last:
                    if isinstance(item, dict):
                        yield item, item_path, key
                else:
                    yield from _descend(item, hop_index + 1, item_path)
            return
        if not isinstance(cur, list):
            return
        for idx, item in enumerate(cur):
            item_path = f"{base}[{idx}]"
            if is_last:
                if isinstance(item, dict):
                    yield item, item_path, None
            else:
                yield from _descend(item, hop_index + 1, item_path)

    yield from _descend(data, 0, "")


def iter_array_path(data: Any, array_path: str):
    """Yield ``(item, jq_index_path)`` for every leaf item at *array_path*.

    Thin wrapper over :func:`iter_nodes` that drops the map key.  For the array-only paths of
    the pre-1.2.0 registry (``.milestones``, ``.milestones[].tasks``, any depth) the output is
    identical to the original single-purpose walker; paths in the wider grammar (dotted object
    paths, ``{}`` maps) are walked too.
    """
    for item, path, _key in iter_nodes(data, array_path):
        yield item, path


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
        if not v.get("_special", False) and not is_glob_key(k)
    ]


def get_step_for_file(basename: str, repo_root: str) -> Optional[str]:
    """Return the step string for a registered basename, or None.

    Args:
        basename: spec file basename (e.g. "04_fr_list.json").
        repo_root: filesystem path to the toolkit root directory.
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.
    """
    registry, _ = _load(repo_root)
    key = _match_registry_key(basename, registry)
    entry = registry.get(key) if key is not None else None
    if entry and not entry.get("_special"):
        return entry.get("step")
    return None
