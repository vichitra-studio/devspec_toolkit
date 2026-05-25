"""Seed index builder for the DevSpec Toolkit.

Hashes seed documents listed in seed_manifest.json and writes
seed_requirements.json so that the freshness checker can detect
when seeds have changed since a spec was last written.

Seed paths are resolved relative to the host repository root (``git_root``
when provided, otherwise the parent of ``spec_dir``).  This honours
``seed_manifest.json``'s contract that ``seeds[].path`` is relative to the
repository root, not relative to the spec directory.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from ..core.seed_routing import resolve_seed_paths


def _sha256_file(path: str) -> str:
    """Compute the SHA-256 hex digest of a file and return ``sha256:<hex>``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def build_seed_index(
    spec_dir: str,
    repo_root: str,
    git_root: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build a seed requirements index by hashing seed documents.

    Parameters
    ----------
    spec_dir:
        Directory containing spec JSON files (e.g. ``spec/``).
    repo_root:
        Path to the devspec_toolkit repo root (for API consistency).
    git_root:
        Host repository root.  When provided, ``seeds[].path`` entries from
        the manifest are resolved relative to this directory — honouring the
        schema contract that paths are "relative to the repository root".
        When ``None``, falls back to ``os.path.dirname(spec_dir_abs)``, which
        is correct for the standard flat layout (host root contains ``spec/``
        as a direct child).

    Returns
    -------
    (index_data, warnings) where index_data is the written dict and
    warnings is a list of warning strings (empty on success).
    """
    _ = repo_root  # accepted for API consistency
    spec_dir_abs = os.path.abspath(spec_dir)
    host_root = git_root if git_root else os.path.dirname(spec_dir_abs)
    warnings: list[str] = []

    # 1. Load seed_manifest.json
    manifest_path = os.path.join(spec_dir_abs, "common", "seed_manifest.json")
    if not os.path.isfile(manifest_path):
        return {}, [f"E520 MISSING_MANIFEST {manifest_path} does not exist"]

    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"E520 MANIFEST_READ_ERROR {manifest_path}: {exc}"]

    seeds_list = manifest.get("seeds", [])
    if not seeds_list:
        return {}, [f"W595 EMPTY_MANIFEST no seeds listed in {manifest_path}"]

    # 2. Collect seed IDs that have a path declared (warn on missing paths).
    all_seed_ids: list[str] = []
    no_path_ids: set[str] = set()
    for seed_entry in seeds_list:
        if not isinstance(seed_entry, dict):
            continue
        seed_id = seed_entry.get("seed_id")
        if not seed_id:
            continue
        rel_path = seed_entry.get("path")
        if not rel_path:
            warnings.append(
                f"W595 MISSING_PATH seed '{seed_id}' has no path in manifest"
            )
            no_path_ids.add(seed_id)
            continue
        all_seed_ids.append(seed_id)

    # 3. Resolve paths via host_root (authoritative per seed_manifest schema).
    #    resolve_seed_paths joins each seeds[].path against host_root and does
    #    NOT existence-filter — we check os.path.isfile ourselves below.
    resolved_paths = resolve_seed_paths(manifest, all_seed_ids, host_root)

    # 4. Hash each seed
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seeds_index: dict[str, Any] = {}

    for seed_id in all_seed_ids:
        abs_path = resolved_paths.get(seed_id)
        if abs_path is None or not os.path.isfile(abs_path):
            warnings.append(
                f"W595 SEED_NOT_FOUND seed '{seed_id}' file not found"
            )
            continue

        seeds_index[seed_id] = {
            "source_hash": _sha256_file(abs_path),
            "indexed_at": now,
        }

    # 5. Write seed_requirements.json
    output = {
        "$schema": "vc:seed-requirements",
        "seeds": seeds_index,
    }

    output_path = os.path.join(spec_dir_abs, "common", "seed_requirements.json")
    output_dir = os.path.dirname(output_path)
    if not os.path.isdir(output_dir):
        return {}, [f"E520 MISSING_DIRECTORY {output_dir} does not exist"]

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
        fh.write("\n")

    return output, warnings
