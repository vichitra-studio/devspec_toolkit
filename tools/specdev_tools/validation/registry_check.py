"""registry_check.py — validate the project's entry_key_registry.json.

Three checks are performed in order:

  R001 / E620 REGISTRY_MISSING_STEP
      Every step in ``<repo_root>/tools/step_order.json`` must either be
      registered in the project registry (as a basename starting with
      ``<step>_``) or appear in ``registry["steps_without_entry_arrays"]``
      (the project's explicit opt-out dict).

  R002 / E621 REGISTRY_PHANTOM_BASENAME
      Every non-sentinel basename in the project registry must appear as a
      filename key in ``<repo_root>/tools/extraction_paths.json``.

  R003 / E622 REGISTRY_DRIFT
      For every registered ``(spec_file, array_path, id_field)`` triple,
      read ``<spec_root>/<spec_file>`` and verify:
      - The array_path resolves to a non-null array in the file.
      - The first entry of the array contains the registered ``id_field``.
      - For nested arrays, the same two checks apply.

CLI surface
-----------
``specdev registry-check --spec-root <dir> [--repo-root <dir>] [--git-root <dir>] [--json]``

Exits 0 if all checks pass, non-zero if any E-code fires.

Integration
-----------
Folded into ``spec-check`` via ``_run_checks`` in ``validation/spec_check.py``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..core.errors import SpecError

_REGISTRY_FILENAME = "entry_key_registry.json"
_SENTINEL_KEYS = frozenset({"canonical_refs_used", "canonical_proposals"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_step_order(repo_root: str) -> list[str]:
    path = os.path.join(repo_root, "tools", "step_order.json")
    if not os.path.isfile(path):
        return []
    data = _load_json(path)
    return data.get("steps", [])


def _load_extraction_basenames(repo_root: str) -> set[str]:
    """Return all spec filenames declared in extraction_paths.json (excluding _meta)."""
    path = os.path.join(repo_root, "tools", "extraction_paths.json")
    if not os.path.isfile(path):
        return set()
    data = _load_json(path)
    basenames: set[str] = set()
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            basenames.update(value.keys())
    return basenames


def _load_registry(spec_root: str) -> dict[str, Any]:
    """Return the raw registry dict (the ``registry`` sub-key), or {} if absent."""
    path = os.path.join(spec_root, _REGISTRY_FILENAME)
    if not os.path.isfile(path):
        return {}
    data = _load_json(path)
    return data.get("registry", {})


def _load_opted_out_steps(spec_root: str) -> set[str]:
    """Return step IDs explicitly opted out via ``steps_without_entry_arrays`` dict."""
    path = os.path.join(spec_root, _REGISTRY_FILENAME)
    if not os.path.isfile(path):
        return set()
    data = _load_json(path)
    swea = data.get("steps_without_entry_arrays", {})
    if isinstance(swea, dict):
        return set(swea.keys())
    return set()


def _registered_basenames_for_step(step: str, registry: dict[str, Any]) -> list[str]:
    """Return non-sentinel basenames matching ``step`` prefix (e.g. '04_')."""
    prefix = step + "_"
    return [
        k for k, v in registry.items()
        if not v.get("_special", False)
        and k not in _SENTINEL_KEYS
        and k.startswith(prefix)
    ]


# ---------------------------------------------------------------------------
# Check 1 — Coverage
# ---------------------------------------------------------------------------

def _check_coverage(
    repo_root: str,
    spec_root: str,
    registry: dict[str, Any],
) -> list[SpecError]:
    """R001: every step_order step is registered or opted out."""
    errs: list[SpecError] = []
    steps = _load_step_order(repo_root)
    opted_out = _load_opted_out_steps(spec_root)

    for step in steps:
        if step in opted_out:
            continue
        if not _registered_basenames_for_step(step, registry):
            errs.append(SpecError(
                code="E620",
                message=(
                    f"R001 MISSING_STEP_REGISTRATION: step '{step}' is not registered in "
                    f"entry_key_registry.json and is not in steps_without_entry_arrays. "
                    f"Add the spec file basename to the registry or document the opt-out reason."
                ),
            ))
    return errs


# ---------------------------------------------------------------------------
# Check 2 — Phantom basename
# ---------------------------------------------------------------------------

def _check_phantom_basenames(
    repo_root: str,
    registry: dict[str, Any],
) -> list[SpecError]:
    """R002: every registered basename must appear in extraction_paths.json."""
    errs: list[SpecError] = []
    extraction_paths_file = os.path.join(repo_root, "tools", "extraction_paths.json")
    if not os.path.isfile(extraction_paths_file):
        # extraction_paths.json missing entirely — skip rather than false-positive
        return errs
    extraction_basenames = _load_extraction_basenames(repo_root)

    for basename, entry in registry.items():
        if entry.get("_special", False):
            continue
        if basename in _SENTINEL_KEYS:
            continue
        if basename not in extraction_basenames:
            errs.append(SpecError(
                code="E621",
                message=(
                    f"R002 PHANTOM_BASENAME: '{basename}' is registered in "
                    f"entry_key_registry.json but does not appear in "
                    f"extraction_paths.json. Remove or rename the registry entry."
                ),
            ))
    return errs


# ---------------------------------------------------------------------------
# Check 3 — Drift detection
# ---------------------------------------------------------------------------

def _check_drift(
    spec_root: str,
    registry: dict[str, Any],
) -> list[SpecError]:
    """R003: registered (array_path, id_field) must match live spec files."""
    errs: list[SpecError] = []

    for basename, entry in registry.items():
        if entry.get("_special", False):
            continue
        if basename in _SENTINEL_KEYS:
            continue

        arrays = entry.get("arrays", [])
        if not arrays:
            # Registered with arrays:[] — no drift to check (e.g. 13a, 16)
            continue

        spec_file_path = os.path.join(spec_root, basename)
        if not os.path.isfile(spec_file_path):
            # File doesn't exist yet (future step) — skip drift check
            continue

        try:
            with open(spec_file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        for arr in arrays:
            array_path = arr["array_path"]  # e.g. ".functional_requirements"
            id_field = arr["id_field"]
            array_key = array_path.lstrip(".")

            # Check top-level array exists
            top_val = data.get(array_key)
            if top_val is None:
                errs.append(SpecError(
                    code="E622",
                    message=(
                        f"R003 REGISTRY_DRIFT: '{basename}': array_path '{array_path}' "
                        f"not found in file (key '{array_key}' missing)."
                    ),
                    path=basename,
                ))
                continue

            if not isinstance(top_val, list):
                errs.append(SpecError(
                    code="E622",
                    message=(
                        f"R003 REGISTRY_DRIFT: '{basename}': array_path '{array_path}' "
                        f"exists but is not an array (got {type(top_val).__name__})."
                    ),
                    path=basename,
                ))
                continue

            if top_val:
                first_entry = top_val[0]
                if isinstance(first_entry, dict) and id_field not in first_entry:
                    actual = list(first_entry.keys())[:6]
                    errs.append(SpecError(
                        code="E622",
                        message=(
                            f"R003 REGISTRY_DRIFT: '{basename}': array '{array_key}' "
                            f"registered id_field='{id_field}' but first entry has "
                            f"fields {actual!r}. Rename id_field in the registry or update the spec."
                        ),
                        path=basename,
                    ))

            # Check nested arrays
            for nested in arr.get("nested", []):
                nested_path = nested["array_path"].lstrip(".")  # e.g. ".tasks" → "tasks"
                nested_id_field = nested["id_field"]

                if not top_val:
                    continue  # empty top-level array — can't check nested
                first_parent = top_val[0]
                if not isinstance(first_parent, dict):
                    continue

                nested_val = first_parent.get(nested_path)
                if nested_val is None:
                    errs.append(SpecError(
                        code="E622",
                        message=(
                            f"R003 REGISTRY_DRIFT: '{basename}': nested array_path "
                            f"'{array_path}[].{nested_path}' not found under first "
                            f"parent entry (key '{nested_path}' missing)."
                        ),
                        path=basename,
                    ))
                    continue

                if not isinstance(nested_val, list):
                    errs.append(SpecError(
                        code="E622",
                        message=(
                            f"R003 REGISTRY_DRIFT: '{basename}': nested '{nested_path}' "
                            f"exists but is not an array (got {type(nested_val).__name__})."
                        ),
                        path=basename,
                    ))
                    continue

                if nested_val:
                    first_nested = nested_val[0]
                    if isinstance(first_nested, dict) and nested_id_field not in first_nested:
                        actual = list(first_nested.keys())[:6]
                        errs.append(SpecError(
                            code="E622",
                            message=(
                                f"R003 REGISTRY_DRIFT: '{basename}': nested array "
                                f"'{nested_path}' registered id_field='{nested_id_field}' "
                                f"but first entry has fields {actual!r}."
                            ),
                            path=basename,
                        ))

    return errs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_registry_check(
    spec_root: str,
    repo_root: str = ".",
    git_root: str | None = None,
) -> list[SpecError]:
    """Run all three registry checks and return combined errors.

    Args:
        spec_root: Path to the project's spec directory (contains entry_key_registry.json).
        repo_root: Path to the toolkit root (contains tools/step_order.json and
            tools/extraction_paths.json).
        git_root: Unused (accepted for API symmetry with other spec-check sub-checks).

    Returns:
        List of SpecError objects (E620/E621/E622).  Empty list = all checks pass.
    """
    registry_path = os.path.join(spec_root, _REGISTRY_FILENAME)
    if not os.path.isfile(registry_path):
        # No registry file — skip all checks silently (project hasn't adopted it yet)
        return []

    registry = _load_registry(spec_root)

    errs: list[SpecError] = []
    errs.extend(_check_coverage(repo_root, spec_root, registry))
    errs.extend(_check_phantom_basenames(repo_root, registry))
    errs.extend(_check_drift(spec_root, registry))
    return errs
