"""Step structure introspection for the DevSpec Toolkit context package.

Implements ``get_step_structure(step_id, spec_dir, repo_root) -> dict``.

Phase A of the context package implementation.  canon_kinds_needed is
populated via canon_extractor.extract_canon() (Phase A3/A4).
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..core.registry import SchemaRegistry
from .canon_extractor import extract_canon
from ._utils import (
    load_json as _u_load_json,
    load_step_order as _u_load_step_order,
    find_spec_file as _u_find_spec_file,
    find_step_schema_uri as _u_find_step_schema_uri,
    merge_allof as _u_merge_allof,
    compute_required_inputs as _u_compute_required_inputs,
    get_boilerplate_keys as _u_get_boilerplate_keys,
)

# Upper-bound set of steps that MAY have seed requirements. The actual
# requirements are read from seed_manifest.json step_requirements, which
# currently only covers 00, 01, 02, 02a. Steps 03 and 04 are included
# here as a forward-compatibility guard (in case the manifest is extended).
# Steps 05+ never have seed requirements and are skipped entirely.
_POSSIBLE_SEED_STEPS: frozenset[str] = frozenset(["00", "01", "02", "02a", "03", "04"])


def _load_json(path: str) -> dict:
    return _u_load_json(path)


def _load_step_order(repo_root: str) -> dict:
    """Load tools/step_order.json from *repo_root*."""
    return _u_load_step_order(repo_root)


def _compute_required_inputs(step_id: str, downstream_consumers: dict[str, list[str]]) -> list[str]:
    """Return list of upstream step IDs that *step_id* requires as input.

    Inverts downstream_consumers: step_id requires step S if step_id
    appears in downstream_consumers[S].
    """
    return _u_compute_required_inputs(step_id, downstream_consumers)


def _find_spec_file(step_id: str, spec_dir: str) -> str | None:
    """Find the spec JSON file for *step_id* inside *spec_dir*.

    Convention: files are named ``{step_id}_{name}.json``.
    Step IDs with letters (e.g. "02a", "13a", "16b") map to files like
    ``02a_delivery_baseline.json``.  We match any file whose stem starts
    with ``{step_id}_``.
    """
    return _u_find_spec_file(step_id, spec_dir)


def _spec_top_level_keys(data: dict) -> list[str]:
    """Return the top-level keys of a spec JSON document (excluding boilerplate fields)."""
    skip = _u_get_boilerplate_keys()
    return [k for k in data.keys() if k not in skip]


def _array_counts(data: dict) -> dict[str, int]:
    """Return a mapping of key -> len for every top-level array in *data*
    (excluding boilerplate fields)."""
    skip = _u_get_boilerplate_keys()
    return {k: len(v) for k, v in data.items() if isinstance(v, list) and k not in skip}


def _find_step_schema_uri(step_id: str, registry: SchemaRegistry) -> str | None:
    """Search schema_registry for a URI that matches *step_id*.

    URIs follow patterns like ``vc:04-fr-list``, ``vc:02a-delivery-baseline``.
    We search for URIs that start with ``vc:`` and contain the step_id (with
    underscores normalised to dashes).
    """
    return _u_find_step_schema_uri(step_id, registry)


def _output_schema_keys(step_id: str, registry: SchemaRegistry) -> list[str]:
    """Discover step-specific output schema keys by walking allOf[1].properties.

    The step schema has structure:
      allOf[0]: $ref to step-base
      allOf[1]: step-specific object with properties
    """
    uri = _find_step_schema_uri(step_id, registry)
    if not uri:
        return []
    try:
        schema = registry.load(uri)
    except FileNotFoundError:
        return []

    merged = _u_merge_allof(schema, registry)
    props = merged.get("properties", {})

    return [k for k in props.keys() if k not in _u_get_boilerplate_keys(registry)]


def _seeds_required(step_id: str, spec_dir: str) -> list[str]:
    """Return seed IDs required by *step_id* from seed_manifest.json.

    Only meaningful for steps 00-04; returns empty list for all others.
    """
    if step_id not in _POSSIBLE_SEED_STEPS:
        return []

    spec_dir_abs = os.path.abspath(spec_dir)
    manifest_path = os.path.join(spec_dir_abs, "common", "seed_manifest.json")
    if not os.path.exists(manifest_path):
        return []

    try:
        manifest = _load_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return []

    step_requirements: dict[str, list[str]] = manifest.get("step_requirements", {})
    return list(step_requirements.get(step_id, []))


def get_step_structure(step_id: str, spec_dir: str, repo_root: str) -> dict[str, Any]:
    """Return structural metadata for a pipeline step.

    Parameters
    ----------
    step_id:
        Pipeline step identifier, e.g. ``"04"``, ``"02a"``, ``"16c"``.
    spec_dir:
        Path to the directory containing spec JSON files (e.g. ``spec/``).
    repo_root:
        Path to the devspec_toolkit repo root (used to resolve
        ``tools/step_order.json`` and ``tools/schema_registry.json``).

    Returns
    -------
    dict with keys:
        step, required_inputs, canon_kinds_needed, seeds_required,
        output_schema_keys
    """
    repo_root_abs = os.path.abspath(repo_root)
    spec_dir_abs = os.path.abspath(spec_dir)

    # ------------------------------------------------------------------
    # 1. Load step_order.json and build the required_inputs list.
    # ------------------------------------------------------------------
    try:
        step_order = _load_step_order(repo_root_abs)
    except (OSError, json.JSONDecodeError):
        step_order = {}

    downstream_consumers: dict[str, list[str]] = step_order.get("downstream_consumers", {})
    upstream_step_ids = _compute_required_inputs(step_id, downstream_consumers)

    # ------------------------------------------------------------------
    # 2. For each upstream step, locate its spec file and extract metadata.
    # ------------------------------------------------------------------
    required_inputs: list[dict[str, Any]] = []
    for src_step in upstream_step_ids:
        spec_path = _find_spec_file(src_step, spec_dir_abs)
        entry: dict[str, Any] = {
            # "step" is an extension of the spec output contract — included
            # for consumer convenience (Phase B /specdev-step skill).
            "step": src_step,
            "file": None,
            "keys": [],
            "array_counts": {},
        }
        if spec_path and os.path.isfile(spec_path):
            try:
                data = _load_json(spec_path)
                entry["file"] = os.path.basename(spec_path)
                entry["keys"] = _spec_top_level_keys(data)
                entry["array_counts"] = _array_counts(data)
            except (OSError, json.JSONDecodeError):
                entry["file"] = os.path.basename(spec_path)
        else:
            # File doesn't exist yet — record the expected filename pattern
            entry["file"] = None

        required_inputs.append(entry)

    # ------------------------------------------------------------------
    # 3. Load the schema registry and discover output_schema_keys.
    # ------------------------------------------------------------------
    try:
        registry = SchemaRegistry(repo_root_abs)
        output_keys = _output_schema_keys(step_id, registry)
    except Exception:
        output_keys = []

    # ------------------------------------------------------------------
    # 4. Seeds required (early steps only).
    # ------------------------------------------------------------------
    seeds = _seeds_required(step_id, spec_dir_abs)

    # ------------------------------------------------------------------
    # 5. canon_kinds_needed — populated via canon_extractor.
    # ------------------------------------------------------------------
    try:
        canon_result = extract_canon(step_id, repo_root_abs)
        canon_kinds_needed = list(canon_result.get("canon_kinds", {}).keys())
    except Exception:
        canon_kinds_needed = []

    return {
        "step": step_id,
        "required_inputs": required_inputs,
        "canon_kinds_needed": canon_kinds_needed,
        "seeds_required": seeds,
        "output_schema_keys": output_keys,
    }
