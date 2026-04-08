"""Shared upstream ID loaders and JSON artifact utilities.

Centralises the repeated _load_fr_ids / _load_api_ids / _load_*_ids patterns
found across step validators, eliminating ~6 × 20 LOC of near-identical code.

Created by FIX-001 (Batch 0).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Kebab-case ID regex — replaces 8+ copies across validators
# ---------------------------------------------------------------------------

KEBAB_ID_RE: re.Pattern[str] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def kebab_id_re(prefix: str) -> re.Pattern[str]:
    """Return a compiled regex for ``<prefix>-<kebab-tail>``."""
    return re.compile(rf"^{re.escape(prefix)}-[a-z0-9]+(?:-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# load_upstream_ids — generic "scan spec/ for NN_*.json, extract IDs"
# ---------------------------------------------------------------------------

def load_upstream_ids(
    toolkit_root: str | Path,
    step_prefix: str,
    array_key: str,
    id_field: str,
    *,
    fallback_keys: tuple[str, ...] = (),
    spec_root: str | Path | None = None,
) -> Optional[set[str]]:
    """Load IDs from an upstream step artifact.

    Scans ``<toolkit_root>/spec/`` for files matching ``<step_prefix>_*.json``,
    loads the first match, and extracts *id_field* from each dict in
    *array_key*.  If *fallback_keys* is supplied, those array keys are also
    checked when *array_key* yields nothing.

    For submodule deployments where the host repo's spec lives outside
    ``toolkit_root``, pass *spec_root* (typically ``<git_root>/spec``) as a
    search path.  When *spec_root* is provided AND differs from
    ``<toolkit_root>/spec``, *spec_root* is searched first so the host repo's
    artifacts are not shadowed by the toolkit's own fixture specs.  When
    *spec_root* is absent or identical to ``<toolkit_root>/spec``, the toolkit's
    own ``spec/`` directory is the sole search path.

    Returns
    -------
    None
        If no upstream file is found (callers emit W590).
    set[str]
        Possibly-empty set of IDs when the file exists.

    Raises
    ------
    json.JSONDecodeError
        If the file exists but contains malformed JSON (propagated).
    """
    toolkit_spec = os.path.join(str(toolkit_root), "spec")

    # When spec_root is provided and is a different directory from the toolkit's
    # own spec dir, prefer spec_root so host-repo artifacts are not shadowed by
    # the toolkit's internal fixture specs.
    if spec_root and os.path.realpath(str(spec_root)) != os.path.realpath(toolkit_spec):
        result = _scan_spec_dir(
            str(spec_root), step_prefix, array_key, id_field, fallback_keys
        )
        if result is not None:
            return result
        # Fall back to toolkit spec only when spec_root yields nothing
        result = _scan_spec_dir(toolkit_spec, step_prefix, array_key, id_field, fallback_keys)
        if result is not None:
            return result
        return None

    # Original behaviour: toolkit spec only (spec_root absent or same directory)
    result = _scan_spec_dir(toolkit_spec, step_prefix, array_key, id_field, fallback_keys)
    if result is not None:
        return result

    return None


def _scan_spec_dir(
    spec_dir: str,
    step_prefix: str,
    array_key: str,
    id_field: str,
    fallback_keys: tuple[str, ...],
) -> Optional[set[str]]:
    """Scan a single spec directory for a step artifact and extract IDs.

    Returns ``None`` in three situations: the directory does not exist, no
    file matching ``<step_prefix>_*.json`` is found, or a matching file
    exists but cannot be opened (``OSError`` — e.g. permission denied).  In
    the last case ``None`` is returned intentionally rather than propagating
    the OS error; the caller (``load_upstream_ids``) treats ``None`` as
    "not found here" and may consult a *spec_root* fallback path.

    When a matching file is found and successfully parsed, returns a
    ``set[str]`` of extracted IDs — possibly empty if the array exists but
    contains no entries.  An **empty set is not ``None``**: it signals "file
    present, no IDs" and prevents ``load_upstream_ids`` from consulting the
    *spec_root* fallback.  This is intentional — it preserves the precedence
    of an explicit toolkit-side artifact over a host-repo fallback.

    ``json.JSONDecodeError`` is *not* caught and propagates to the caller.
    """
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith(f"{step_prefix}_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except OSError:
                return None

            ids = _extract_ids(data, array_key, id_field)
            if not ids and fallback_keys:
                for fk in fallback_keys:
                    ids = _extract_ids(data, fk, id_field)
                    if ids:
                        break
            return ids

    return None


def _extract_ids(data: Any, array_key: str, id_field: str) -> set[str]:
    """Extract *id_field* values from *data[array_key]*."""
    items = data.get(array_key, []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return set()
    return {
        str(item.get(id_field))
        for item in items
        if isinstance(item, dict) and item.get(id_field)
    }


# ---------------------------------------------------------------------------
# load_sibling_artifact — step_14-style "look next to artifact, fallback to spec/"
# ---------------------------------------------------------------------------

def load_sibling_artifact(
    artifact_path: str | Path,
    sibling_prefix: str,
    array_key: str,
    id_field: str,
    *,
    fallback_root: str | Path | None = None,
) -> set[str] | None:
    """Load IDs from a sibling artifact (same directory as *artifact_path*).

    If the sibling is not found beside *artifact_path* and *fallback_root* is
    given, checks ``<fallback_root>/spec/<sibling_prefix>_*.json`` as well.

    Returns
    -------
    None
        No candidate file was found in either the sibling directory or the
        ``fallback_root`` spec dir.  Callers should treat this as "upstream
        absent, skip cross-ref check".
    set[str]
        A (possibly empty) set of extracted IDs.  An **empty set is not
        None**: it signals "upstream present but contained no IDs", and
        callers should still run cross-ref validation (so stray references
        get flagged) while skipping coverage checks over an empty set.
        Malformed JSON or read errors also yield an empty set — the file
        was found but could not be mined, which is distinct from absent.
    """
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        for fn in _match_prefix(artifact_dir, sibling_prefix):
            candidates.append(artifact_dir / fn)
    if fallback_root:
        spec_dir = Path(fallback_root).resolve() / "spec"
        for fn in _match_prefix(spec_dir, sibling_prefix):
            candidates.append(spec_dir / fn)

    found_any = False
    for path in candidates:
        if not path.exists():
            continue
        found_any = True
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set()
        return _extract_ids(data, array_key, id_field)

    return set() if found_any else None


def _match_prefix(directory: Path, prefix: str) -> list[str]:
    """Return filenames in *directory* matching ``<prefix>_*.json``."""
    if not directory.is_dir():
        return []
    return [
        fn for fn in os.listdir(directory)
        if fn.startswith(f"{prefix}_") and fn.endswith(".json")
    ]


# ---------------------------------------------------------------------------
# check_cross_step_refs — upstream_map + W590/E590 pattern
# ---------------------------------------------------------------------------

def check_cross_step_refs(
    targets: list[str],
    upstream_map: dict[str, tuple[Optional[set[str]], str, str]],
    errors: list[str],
    code_prefix: str = "",
) -> None:
    """Validate *targets* against an *upstream_map* and append errors in-place.

    Parameters
    ----------
    targets : list[str]
        IDs to validate (e.g. fixture target IDs).
    upstream_map : dict
        ``{prefix: (id_set_or_None, filename, type_label)}``
    errors : list[str]
        Error accumulator — W590/E590 messages are appended here.
    code_prefix : str
        Optional context label prepended to error messages (e.g.
        ``"fixture 'fix-login'"``).
    """
    # Emit W590 once per missing upstream file
    warned_missing: set[str] = set()
    for prefix, (id_set, filename, type_label) in upstream_map.items():
        if id_set is None and filename not in warned_missing:
            errors.append(
                f"W590 CROSS_STEP_UPSTREAM_MISSING {filename} not found; "
                f"skipping {type_label} reference validation"
            )
            warned_missing.add(filename)

    # Validate each target against the upstream ID set
    for target_id in targets:
        if not target_id:
            continue
        for prefix, (id_set, filename, _) in upstream_map.items():
            if target_id.startswith(prefix):
                if id_set is not None and target_id not in id_set:
                    msg = (
                        f"E590 CROSS_STEP_ID_NOT_FOUND "
                        f"{code_prefix}target '{target_id}' not found "
                        f"in {filename}"
                    )
                    errors.append(msg.strip())
                break


# ---------------------------------------------------------------------------
# load_json_artifact — shared JSON loading with error handling
# ---------------------------------------------------------------------------

def load_json_artifact(path: str | Path) -> dict[str, Any]:
    """Load a JSON file and return its contents as a dict.

    Returns an empty dict if the file does not exist or is not a dict.
    Raises ``json.JSONDecodeError`` on malformed JSON.  Propagates
    ``PermissionError`` and other OS-level exceptions.
    """
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return data
