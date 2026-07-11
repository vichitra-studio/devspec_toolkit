"""Seed freshness checker for the DevSpec Toolkit context package.

Implements ``check_freshness(spec_dir, repo_root, git_root=None) -> dict``.

Compares SHA-256 hashes of seed documents against stored hashes in
seed_requirements.json (if it exists). If no seed_requirements.json exists,
returns {"status": "no_index"}.

Seed paths are resolved relative to the host repository root (``git_root``
when provided, otherwise the parent of ``spec_dir``).  This honours
``seed_manifest.json``'s contract that ``seeds[].path`` is relative to the
repository root, not relative to the spec directory.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from ..core.seed_routing import resolve_seed_paths


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_file(path: str) -> str:
    """Compute the SHA-256 hex digest of a file and return ``sha256:<hex>``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _current_hash(seed_file_map: dict[str, str], seed_id: str) -> str:
    """Hash the on-disk seed file for *seed_id*, or ``""`` if absent/unreadable.

    Shared by the indexed-seed comparison (section 4) and the untracked-seed
    coverage check (section 5) so both derive the live hash identically.
    """
    seed_path = seed_file_map.get(seed_id)
    if seed_path and os.path.isfile(seed_path):
        try:
            return _sha256_file(seed_path)
        except OSError:
            return ""
    return ""


def check_freshness(
    spec_dir: str,
    repo_root: str,
    git_root: str | None = None,
) -> dict[str, Any]:
    """Check whether seed documents are fresh against stored hashes.

    Parameters
    ----------
    spec_dir:
        Directory containing spec JSON files (and ``common/`` subdirectory).
    repo_root:
        Path to the devspec_toolkit repo root (accepted for API consistency;
        not used for seed-path resolution).
    git_root:
        Host repository root.  When provided, ``seeds[].path`` entries from
        the manifest are resolved relative to this directory — honouring the
        schema contract that paths are "relative to the repository root".
        When ``None``, falls back to ``os.path.dirname(spec_dir_abs)``, which
        is correct for the standard flat layout (host root contains ``spec/``
        as a direct child).

    Returns
    -------
    dict mapping seed-id -> freshness result, or ``{"status": "no_index"}``
    if no ``seed_requirements.json`` is found.
    """
    _ = repo_root  # accepted for API consistency; not used for path resolution

    spec_dir_abs = os.path.abspath(spec_dir)
    host_root = git_root if git_root else os.path.dirname(spec_dir_abs)

    # ------------------------------------------------------------------
    # 1. Locate seed_requirements.json.
    # ------------------------------------------------------------------
    candidate_paths = [
        os.path.join(spec_dir_abs, "seed_requirements.json"),
        os.path.join(spec_dir_abs, "common", "seed_requirements.json"),
    ]
    seed_req_path: str | None = None
    for candidate in candidate_paths:
        if os.path.isfile(candidate):
            seed_req_path = candidate
            break

    if seed_req_path is None:
        return {"status": "no_index"}

    # ------------------------------------------------------------------
    # 2. Load seed_requirements.json.
    # ------------------------------------------------------------------
    try:
        seed_req = _load_json(seed_req_path)
    except (OSError, json.JSONDecodeError):
        return {"status": "no_index"}

    seeds_index: dict[str, Any] = seed_req.get("seeds", {})
    if not seeds_index:
        return {"status": "no_index"}

    # ------------------------------------------------------------------
    # 3. Load seed_manifest.json and resolve seed file paths via host_root.
    #    Also collect the full set of manifest seed IDs (those declaring a
    #    path) so seeds present in the manifest but ABSENT from the index can
    #    be reported — otherwise they escape drift detection entirely.
    # ------------------------------------------------------------------
    manifest_path = os.path.join(spec_dir_abs, "common", "seed_manifest.json")
    seed_file_map: dict[str, str] = {}  # seed_id -> abs path
    manifest_seed_ids: list[str] = []
    if os.path.isfile(manifest_path):
        try:
            manifest = _load_json(manifest_path)
            for seed_entry in manifest.get("seeds", []):
                if not isinstance(seed_entry, dict):
                    continue
                sid = seed_entry.get("seed_id")
                if sid and seed_entry.get("path"):
                    manifest_seed_ids.append(sid)
            # resolve_seed_paths resolves each seeds[].path against host_root,
            # which is the authoritative base per seed_manifest.schema.json.
            # Resolve the UNION of indexed + manifest seeds so both stale
            # (indexed) and untracked (manifest-only) seeds can be hashed.
            resolve_ids = list(dict.fromkeys(list(seeds_index.keys()) + manifest_seed_ids))
            seed_file_map = resolve_seed_paths(manifest, resolve_ids, host_root)
        except (OSError, json.JSONDecodeError):
            pass

    # ------------------------------------------------------------------
    # 4. Compare hashes for each seed in the index.
    # ------------------------------------------------------------------
    results: dict[str, Any] = {}
    for seed_id, seed_info in seeds_index.items():
        if not isinstance(seed_info, dict):
            continue
        indexed_hash: str = seed_info.get("source_hash", "")
        current_hash = _current_hash(seed_file_map, seed_id)

        stale = bool(indexed_hash and current_hash and indexed_hash != current_hash)

        results[seed_id] = {
            "indexed_hash": indexed_hash,
            "current_hash": current_hash,
            "stale": stale,
            "untracked": False,
            "changed_sections": [],  # section detection not implemented yet
        }

    # ------------------------------------------------------------------
    # 5. Flag manifest seeds that are NOT in the index (coverage gap).
    #    build_seed_index hashes every manifest seed, so an index missing a
    #    manifest seed is stale-by-omission: edits to that seed trip no drift
    #    signal.  Report each as 'untracked' so callers can prompt a re-index.
    # ------------------------------------------------------------------
    for seed_id in manifest_seed_ids:
        if seed_id in results:
            continue
        results[seed_id] = {
            "indexed_hash": "",
            "current_hash": _current_hash(seed_file_map, seed_id),
            "stale": False,
            "untracked": True,
            "changed_sections": [],
        }

    return results
