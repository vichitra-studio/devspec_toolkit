"""registry_check.py — validate the toolkit's entry_key_registry.json.

Two checks (R002/R003) are performed plus one novelty-detection warning (R004).
R001 was moved to the toolkit's own unit test suite (T-step-registry-coverage)
because the registry generator (W3) guarantees coverage as an internal contract.

  R002 / E621 REGISTRY_PHANTOM_BASENAME
      Every non-sentinel basename in the toolkit registry must appear as a
      filename key in ``<repo_root>/tools/extraction_paths.json``.

  R003 / E622 REGISTRY_DRIFT
      For every registered ``(spec_file, array_path, id_field)`` triple,
      read ``<spec_root>/<spec_file>`` and verify:
      - The array_path resolves to a non-null array in the file.
      - The first entry of the array contains the registered ``id_field``.
      - Nested arrays are checked only when present: a present-but-wrong-shape
        nested array (wrong id_field or not an array) still fires E622, but a
        missing nested array is not drift (nested arrays may be optional per
        schema; a missing *required* nested array is caught by schema
        validation in ``spec-check`` instead).

  R004 / W614 UNREGISTERED_ARRAY
      For every ``.json`` file in ``<spec_root>/``, scan top-level arrays
      whose first item contains a field matching ``^[a-z][a-z0-9_]*_id$``
      or bare ``id``.  If that ``(basename, array_path)`` pair is absent from
      the toolkit registry, emit a W614 warning prompting the toolkit to be
      updated.  TraceRef arrays (``.trace``) and sentinel arrays
      (``canonical_refs_used``, ``canonical_proposals``) are excluded.
      Severity is WARNING — the generator may not yet cover the new array.

Registry is loaded from ``<repo_root>/tools/entry_key_registry.json`` (toolkit-side).
Spec files for R003/R004 are read from ``<spec_root>/`` (host-repo spec dir).

CLI surface
-----------
``specdev registry-check --spec-root <dir> [--repo-root <dir>] [--git-root <dir>] [--json]``

Exits 0 if all checks pass, non-zero if any E-code fires.
W614 warnings do not cause a non-zero exit unless promoted via
``SPECDEV_WARNINGS_AS_ERRORS=1`` or ``SPECDEV_PROMOTE_CODES=W614``.

Integration
-----------
Folded into ``spec-check`` via ``_run_checks`` in ``validation/spec_check.py``.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ..core.errors import SpecError

_REGISTRY_FILENAME = "entry_key_registry.json"
_SENTINEL_KEYS = frozenset({"canonical_refs_used", "canonical_proposals"})

# R004: pattern that identifies an entry-id field (e.g. fr_id, capability_id, bare id).
_ID_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*_id$")

# R004: traceRef array keys excluded from novelty scanning (cross-step foreign-key refs,
# intentionally absent from the registry per generator Rule B).
_TRACEREF_ARRAY_KEYS = frozenset({"trace"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


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


def _load_registry(repo_root: str) -> dict[str, Any]:
    """Return the raw registry dict (the ``registry`` sub-key), or {} if absent.

    Reads from ``<repo_root>/tools/entry_key_registry.json`` (toolkit-side).
    """
    path = os.path.join(repo_root, "tools", _REGISTRY_FILENAME)
    if not os.path.isfile(path):
        return {}
    data = _load_json(path)
    return data.get("registry", {})


def _load_registry_doc(repo_root: str) -> dict[str, Any]:
    """Return the full registry document (all top-level keys), or {} if absent.

    Used by R004 to access ``_sentinels`` alongside ``registry``.
    """
    path = os.path.join(repo_root, "tools", _REGISTRY_FILENAME)
    if not os.path.isfile(path):
        return {}
    return _load_json(path)


# ---------------------------------------------------------------------------
# NOTE: R001 (REGISTRY_MISSING_STEP / E620) has been moved to the toolkit
# unit test suite as T-step-registry-coverage.  The registry generator (W3)
# enforces step coverage as an internal contract, making a host-runtime check
# redundant and noisy.  The E620 error code is retained for historical
# reference and backward compatibility with any external tools that parse it.
# ---------------------------------------------------------------------------

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
            _check_array_entry(arr, data, basename, "", errs, is_root=True)

    return errs


def _check_array_entry(
    entry: dict,
    container,
    basename: str,
    display_prefix: str,
    errs: list,
    *,
    is_root: bool,
) -> None:
    """Recursively validate one registry array entry against spec *container*.

    ``container`` is the object holding this entry's array — the root document
    at the top level, or the first item of the parent array one level down.
    Validation descends through ``entry["nested"]`` to arbitrary depth (e.g.
    step 14's ``milestones[].tasks[].acceptance_criteria``), checking against
    the *first* element at each level (a representative-sample drift check, as
    the original single-level implementation did).

    ``display_prefix`` accumulates the human-readable path used in messages,
    e.g. ``.milestones[]`` when validating a nested entry under milestones.
    ``is_root`` distinguishes the top-level "not found in file" wording from
    the nested "not found under first parent entry" wording, preserving the
    original R003 message text for existing (one-level) cases.
    """
    array_key = entry["array_path"].lstrip(".")
    id_field = entry["id_field"]
    full_display = f"{display_prefix}{entry['array_path']}"

    val = container.get(array_key) if isinstance(container, dict) else None

    if val is None:
        # Top-level registered arrays are the file's primary entries — an absent
        # one is genuine drift.  Nested arrays, however, may be OPTIONAL per
        # schema (e.g. a roadmap task's ``acceptance_criteria``); their required
        # presence is owned by schema validation and the registry-generate
        # byte-exact gate, so a missing nested key is NOT drift here — only a
        # present-but-wrong-shape nested array is (checked below).  Flagging
        # missing optional nested arrays would false-positive on schema-valid
        # host specs (DEVSPEC-125).
        #
        # DECISION (DEVSPEC-125): this deliberately narrows standalone
        # ``registry-check`` — a missing *required* nested array is no longer
        # flagged here.  registry_check cannot read the schema's ``required``, so
        # it cannot tell required from optional; the canonical ``spec-check`` gate
        # runs schema validation alongside this check and catches a missing
        # required array (e.g. milestone.tasks) with its own E-code, so the
        # signal is preserved end-to-end without the false-positive.
        if is_root:
            errs.append(SpecError(
                code="E622",
                message=(
                    f"R003 REGISTRY_DRIFT: '{basename}': array_path '{full_display}' "
                    f"not found in file (key '{array_key}' missing)."
                ),
                path=basename,
            ))
        return

    if not isinstance(val, list):
        errs.append(SpecError(
            code="E622",
            message=(
                f"R003 REGISTRY_DRIFT: '{basename}': array_path '{full_display}' "
                f"exists but is not an array (got {type(val).__name__})."
            ),
            path=basename,
        ))
        return

    if not val:
        return  # empty array — can't sample the first element or descend

    first_entry = val[0]
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

    # Recurse into deeper nested arrays using the first element as the container.
    if not isinstance(first_entry, dict):
        return
    for nested in entry.get("nested", []):
        _check_array_entry(
            nested, first_entry, basename, f"{full_display}[]", errs, is_root=False
        )


# ---------------------------------------------------------------------------
# Check 4 — Unregistered arrays (host-side novelty detection)
# ---------------------------------------------------------------------------

def _check_unregistered_arrays(
    spec_root: str,
    repo_root: str,
    registry: dict[str, Any],
) -> list[SpecError]:
    """R004 / W614: scan host spec files for id-bearing arrays absent from the registry.

    For each ``.json`` file in *spec_root*, walks top-level arrays whose first
    item contains a field matching ``^[a-z][a-z0-9_]*_id$`` or bare ``id``.
    If the ``(basename, array_path)`` pair is not declared in the toolkit
    registry, emits W614 UNREGISTERED_ARRAY (warning severity).

    Scope note (DEVSPEC-125): this novelty scan is intentionally TOP-LEVEL only
    and must stay that way.  R004 inspects spec DATA, not schema, so it cannot
    recurse correctly: a nested traceRef array (e.g. milestones[].deliverables,
    items {type, id, note}) is data-indistinguishable from a real nested entry
    like dependencyItem ({type, id}) — the only discriminator is the items'
    ``$ref`` URI, which lives in the schema.  A recursive R004 would therefore
    false-positive W614 on every nested traceRef array; suppressing that would
    require resolving $refs, i.e. re-implementing the generator.  Deep-nested
    entry coverage is instead owned by the schema-driven generator, its
    byte-exact golden gate, and the explicit 3-deep unit tests — no host-side
    signal is lost by keeping this scan top-level.

    Exclusions:
    - Sentinel arrays listed in ``registry["_sentinels"]`` (e.g.
      ``canonical_refs_used``, ``canonical_proposals``).
    - TraceRef arrays (``.trace``) — cross-step foreign-key refs intentionally
      absent from the registry per generator Rule B.
    - Arrays whose first item has no id-like field (e.g. pure config arrays).
    - Files that are not registered AND not in ``steps_without_entry_arrays``
      (those are future/unknown steps — skip entirely rather than flood output).
    """
    errs: list[SpecError] = []

    # Build the full doc once to get _sentinels
    registry_doc = _load_registry_doc(repo_root)
    dynamic_sentinels = frozenset(registry_doc.get("_sentinels", []))
    excluded_keys = _SENTINEL_KEYS | dynamic_sentinels | _TRACEREF_ARRAY_KEYS

    # Build set of (basename, array_path) pairs already declared in registry
    registered_pairs: set[tuple[str, str]] = set()
    for bn, entry in registry.items():
        if entry.get("_special", False) or bn in _SENTINEL_KEYS:
            continue
        for arr in entry.get("arrays", []):
            registered_pairs.add((bn, arr["array_path"]))

    if not os.path.isdir(spec_root):
        return errs

    for fname in sorted(os.listdir(spec_root)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(spec_root, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(data, dict):
            continue

        for key, val in data.items():
            if key in excluded_keys:
                continue
            if not isinstance(val, list) or not val:
                continue
            first = val[0]
            if not isinstance(first, dict):
                continue

            # Detect id-bearing items
            id_fields = [
                k for k in first
                if _ID_FIELD_RE.match(k) or k == "id"
            ]
            if not id_fields:
                continue

            array_path = f".{key}"
            if (fname, array_path) not in registered_pairs:
                # Infer kind from the id field
                id_field = id_fields[0]
                if id_field == "id":
                    inferred_kind = key.rstrip("s")  # naive singularise
                else:
                    inferred_kind = id_field[:-3]  # strip trailing _id

                errs.append(SpecError(
                    code="W614",
                    message=(
                        f"R004 UNREGISTERED_ARRAY {fname}:{array_path} "
                        f"(kind={inferred_kind}). "
                        f"Update toolkit schema and re-run specdev registry-generate."
                    ),
                    path=fname,
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
    """Run registry checks R002, R003, and R004; return combined errors/warnings.

    R001 (REGISTRY_MISSING_STEP / E620) was moved to the toolkit's own unit
    test suite (T-step-registry-coverage) after W3 — the registry generator
    now enforces step coverage as an internal contract.

    Args:
        spec_root: Path to the project's spec directory (used for R003 drift
            check and R004 novelty scan — reading live spec files).
        repo_root: Path to the toolkit root (contains tools/entry_key_registry.json,
            tools/step_order.json, and tools/extraction_paths.json).
        git_root: Unused (accepted for API symmetry with other spec-check sub-checks).

    Returns:
        List of SpecError objects (E621/E622/W614).  Empty list = all checks pass.
        W614 warnings do not cause non-zero exit unless promoted via env vars.
    """
    del git_root  # accepted for API symmetry; not used by registry checks
    # Registry now lives toolkit-side at <repo_root>/tools/entry_key_registry.json
    registry_path = os.path.join(repo_root, "tools", _REGISTRY_FILENAME)
    if not os.path.isfile(registry_path):
        # No registry file — skip all checks silently (toolkit hasn't generated it yet)
        return []

    registry = _load_registry(repo_root)

    errs: list[SpecError] = []
    errs.extend(_check_phantom_basenames(repo_root, registry))
    errs.extend(_check_drift(spec_root, registry))
    errs.extend(_check_unregistered_arrays(spec_root, repo_root, registry))
    return errs
