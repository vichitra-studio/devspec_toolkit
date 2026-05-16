"""T-matrix-registry-agreement — build_trace_matrix() findings agree with registry declarations.

Covers W6-T3 invariant: the matrix does not discover entity kinds that the
registry doesn't know about.

Two assertions are made:

  1. Registry-kinds subset check (no matrix-discovered entities are unknown).
     We derive "matrix-discovered kinds" by running list_entries() over the
     host spec corpus (the same path build_trace_matrix() uses) and collecting
     the `kind` values the registry resolved.  Since the registry is what
     drives entity discovery inside build_trace_matrix() (W4 refactor), any
     entity that would appear in the matrix must come from a registry-declared
     kind — this assertion validates that invariant.

  2. Reverse: every registry-declared kind that should appear in the host spec
     does appear (no missing kinds modulo genuinely empty arrays).
     We check: for each kind in the registry, at least one spec file has a
     non-empty array for that kind.  Steps that are opted-out or deferred are
     excluded from the reverse check.

The host spec directory is resolved relative to the toolkit root as
``TOOLKIT_ROOT/../spec``.  If it doesn't exist (e.g. running the toolkit as a
standalone clone), all tests are skipped.

Toolkit root from this file: Path(__file__).parents[2]
  → devspec_toolkit/tests/integration/test_matrix_registry_agreement.py
  → parents[0] = devspec_toolkit/tests/integration/
  → parents[1] = devspec_toolkit/tests/
  → parents[2] = devspec_toolkit/
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from specdev_tools.core.entry_key_registry import list_entries
from specdev_tools.validation.matrix import build_trace_matrix

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
HOST_ROOT = TOOLKIT_ROOT.parent
HOST_SPEC_DIR = HOST_ROOT / "spec"
REGISTRY_PATH = TOOLKIT_ROOT / "tools" / "entry_key_registry.json"

_HOST_SPEC_AVAILABLE = HOST_SPEC_DIR.is_dir()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_registry_doc() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _all_registered_kinds(registry_doc: dict) -> set[str]:
    """Return all kind values declared in the registry (top-level and nested)."""
    kinds: set[str] = set()
    for _bn, entry in registry_doc.get("registry", {}).items():
        if entry.get("_special", False):
            continue
        for arr in entry.get("arrays", []):
            if arr.get("kind"):
                kinds.add(arr["kind"])
            for nested in arr.get("nested", []):
                if nested.get("kind"):
                    kinds.add(nested["kind"])
    return kinds


def _kinds_discovered_via_list_entries(spec_dir: str, toolkit_root: str) -> set[str]:
    """Run list_entries over all spec files and collect all resolved kind values.

    This replicates the registry-driven entity discovery path inside
    build_trace_matrix() (W4 refactor) without running the full matrix build.
    """
    kinds: set[str] = set()
    for fname in os.listdir(spec_dir):
        if not fname.endswith(".json"):
            continue
        entries = list_entries(fname, toolkit_root)
        if entries is None or not entries:
            continue
        for entry in entries:
            kinds.add(entry.kind)
    return kinds


def _kinds_with_data_in_spec(registry_doc: dict, spec_dir: str) -> set[str]:
    """Return kinds for which at least one spec file has a non-empty array."""
    kinds_with_data: set[str] = set()
    for bn, entry in registry_doc.get("registry", {}).items():
        if entry.get("_special", False):
            continue
        spec_path = os.path.join(spec_dir, bn)
        if not os.path.isfile(spec_path):
            continue
        try:
            data = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for arr_entry in entry.get("arrays", []):
            array_key = arr_entry["array_path"].lstrip(".")
            val = data.get(array_key)
            if val and isinstance(val, list):
                if arr_entry.get("kind"):
                    kinds_with_data.add(arr_entry["kind"])
            for nested in arr_entry.get("nested", []):
                if nested.get("kind"):
                    # Check if any parent item has the nested array
                    if val and isinstance(val, list) and val[0]:
                        nested_key = nested["array_path"].lstrip(".")
                        nested_val = val[0].get(nested_key) if isinstance(val[0], dict) else None
                        if nested_val and isinstance(nested_val, list):
                            kinds_with_data.add(nested["kind"])
    return kinds_with_data


# ---------------------------------------------------------------------------
# T-matrix-registry-agreement
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _HOST_SPEC_AVAILABLE,
    reason=(
        "Host spec directory not found at expected submodule path "
        f"({HOST_SPEC_DIR}). Run from the host repo context."
    ),
)
class TestMatrixRegistryAgreement:
    """build_trace_matrix() entity kinds agree with toolkit registry declarations."""

    def test_discovered_kinds_are_subset_of_registry_kinds(self) -> None:
        """All kinds discovered via list_entries over the host spec are registered kinds.

        This verifies that the registry-driven entity discovery path in
        build_trace_matrix() never introduces entity kinds that the registry
        doesn't know about — a core invariant of the W4 refactor.
        """
        registry_doc = _load_registry_doc()
        declared_kinds = _all_registered_kinds(registry_doc)

        discovered = _kinds_discovered_via_list_entries(
            str(HOST_SPEC_DIR), str(TOOLKIT_ROOT)
        )

        unknown = discovered - declared_kinds
        assert not unknown, (
            f"list_entries() resolved kinds that are not declared in the registry: "
            f"{sorted(unknown)}. "
            "The registry may be out of sync with the schemas. "
            "Re-run: specdev registry-generate --repo-root <toolkit-path>"
        )

    def test_registry_declared_kinds_appear_in_spec(self) -> None:
        """Every registry-declared kind has at least one non-empty array in the host spec.

        Kinds that are declared but genuinely absent from the host spec are
        documented in the KNOWN_EMPTY_KINDS allowlist below. All others must
        appear in at least one spec file.

        If this test fails because the host spec doesn't cover a registered kind,
        add the kind to KNOWN_EMPTY_KINDS with a rationale comment.
        """
        # Kinds that are registered in the toolkit schema but the host project
        # genuinely does not use (e.g. project-specific omissions).
        KNOWN_EMPTY_KINDS: set[str] = set()
        # extension: the extension manifest exists but may have no extensions yet.
        # Allow this kind to be empty without failing.
        KNOWN_EMPTY_KINDS.add("extension")

        registry_doc = _load_registry_doc()
        declared_kinds = _all_registered_kinds(registry_doc)
        expected_kinds = declared_kinds - KNOWN_EMPTY_KINDS

        kinds_with_data = _kinds_with_data_in_spec(registry_doc, str(HOST_SPEC_DIR))

        missing = expected_kinds - kinds_with_data
        assert not missing, (
            f"Registry-declared kinds have no data in the host spec: {sorted(missing)}. "
            "Either the host spec is incomplete for these kinds, or the kind should "
            "be added to KNOWN_EMPTY_KINDS with a rationale comment."
        )

    def test_matrix_produces_nonempty_rows(self) -> None:
        """build_trace_matrix() produces at least one matrix row from the host spec."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(HOST_SPEC_DIR))
        matrix = result.get("matrix", [])
        assert matrix, (
            "build_trace_matrix() produced an empty matrix. "
            "The host spec may be missing FR entries, or the registry is out of sync."
        )

    def test_matrix_row_kinds_come_from_registry(self) -> None:
        """Matrix rows reference only link-kinds the registry declares (fr, api, fixture, nfr, threat).

        The matrix hardcodes these 5 link kinds in its output rows. Verify
        the registry declares each of them.
        """
        registry_doc = _load_registry_doc()
        declared_kinds = _all_registered_kinds(registry_doc)
        # These are the kinds the matrix currently links (defined in matrix.py)
        matrix_link_kinds = {"fr", "api", "fixture", "nfr", "threat"}
        unknown_link_kinds = matrix_link_kinds - declared_kinds
        assert not unknown_link_kinds, (
            f"Matrix uses link kinds not declared in the registry: {sorted(unknown_link_kinds)}. "
            "Update the registry or the matrix link-kind list."
        )
