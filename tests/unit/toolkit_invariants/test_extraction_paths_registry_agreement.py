"""T-extraction-paths-registry-agreement — registry and extraction_paths cover the same basenames.

Covers W6-T3 invariant: the two toolkit-managed data files (registry and
extraction_paths) are structurally consistent.

Key structural difference:
  - entry_key_registry.json: ``registry`` is a flat dict keyed by basename
    (e.g. ``"04_fr_list.json": {...}``).
  - extraction_paths.json: step-keyed dict where each value is a dict of
    ``{basename: [paths]}``.

This test normalises both to a set of basenames and asserts they agree.

Exclusions:
  - ``_meta`` and other ``_``-prefixed keys in extraction_paths (tooling metadata).
  - Sentinel basenames in the registry (``canonical_refs_used``, ``canonical_proposals``).
  - Registry entries with ``_special: true``.
  - Steps in ``steps_without_entry_arrays`` and ``steps_with_deferred_registration``
    are excluded from the registry side (they are registered as opted-out/deferred,
    not in ``registry``). However, those steps must NOT appear in extraction_paths
    either (they have no entry arrays to extract).

Toolkit root from this file: Path(__file__).parents[4]
  → devspec_toolkit/tests/unit/toolkit_invariants/test_extraction_paths_registry_agreement.py
  → parents[0] = devspec_toolkit/tests/unit/toolkit_invariants/
  → parents[1] = devspec_toolkit/tests/unit/
  → parents[2] = devspec_toolkit/tests/
  → parents[3] = devspec_toolkit/
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Toolkit root resolution
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
_REGISTRY_PATH = _TOOLKIT_ROOT / "tools" / "entry_key_registry.json"
_EXTRACTION_PATHS_PATH = _TOOLKIT_ROOT / "tools" / "extraction_paths.json"

_SENTINEL_KEYS = frozenset({"canonical_refs_used", "canonical_proposals"})


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_registry_doc() -> dict:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def _load_extraction_paths() -> dict:
    return json.loads(_EXTRACTION_PATHS_PATH.read_text(encoding="utf-8"))


def _registry_basenames(doc: dict) -> set[str]:
    """Return basenames from the registry dict (excluding sentinels and _special entries)."""
    basenames: set[str] = set()
    for bn, entry in doc.get("registry", {}).items():
        if bn in _SENTINEL_KEYS:
            continue
        if entry.get("_special", False):
            continue
        basenames.add(bn)
    return basenames


def _extraction_paths_basenames(ext: dict) -> set[str]:
    """Return all basenames from the step-keyed extraction_paths.json."""
    basenames: set[str] = set()
    for step_key, value in ext.items():
        if step_key.startswith("_"):
            continue  # skip _meta and similar
        if isinstance(value, dict):
            basenames.update(value.keys())
    return basenames


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def test_registry_file_exists() -> None:
    assert _REGISTRY_PATH.is_file(), f"Not found: {_REGISTRY_PATH}"


def test_extraction_paths_file_exists() -> None:
    assert _EXTRACTION_PATHS_PATH.is_file(), f"Not found: {_EXTRACTION_PATHS_PATH}"


# ---------------------------------------------------------------------------
# T-extraction-paths-registry-agreement
# ---------------------------------------------------------------------------


class TestExtractionPathsRegistryAgreement:
    """entry_key_registry.json and extraction_paths.json cover the same basenames."""

    @pytest.fixture(scope="class")
    def registry_doc(self) -> dict:
        return _load_registry_doc()

    @pytest.fixture(scope="class")
    def extraction_paths(self) -> dict:
        return _load_extraction_paths()

    @pytest.fixture(scope="class")
    def reg_basenames(self, registry_doc: dict) -> set[str]:
        return _registry_basenames(registry_doc)

    @pytest.fixture(scope="class")
    def ext_basenames(self, extraction_paths: dict) -> set[str]:
        return _extraction_paths_basenames(extraction_paths)

    def test_registry_basenames_subset_of_extraction_paths(
        self,
        reg_basenames: set[str],
        ext_basenames: set[str],
    ) -> None:
        """Every basename in the registry must also appear in extraction_paths.

        A registry entry that has no extraction path is unreachable — the
        extractor won't know which arrays to traverse.
        """
        in_registry_not_extraction = reg_basenames - ext_basenames
        assert not in_registry_not_extraction, (
            f"Basenames registered but NOT in extraction_paths.json: "
            f"{sorted(in_registry_not_extraction)}. "
            "Re-run: specdev registry-generate --repo-root <toolkit-path>"
        )

    def test_extraction_paths_basenames_subset_of_registry(
        self,
        reg_basenames: set[str],
        ext_basenames: set[str],
    ) -> None:
        """Every basename in extraction_paths must also be in the registry.

        An extraction path with no registry entry means the extractor would
        traverse arrays without knowing the id_field or kind.
        """
        in_extraction_not_registry = ext_basenames - reg_basenames
        assert not in_extraction_not_registry, (
            f"Basenames in extraction_paths.json but NOT in registry: "
            f"{sorted(in_extraction_not_registry)}. "
            "Re-run: specdev registry-generate --repo-root <toolkit-path>"
        )

    def test_sets_are_equal(
        self,
        reg_basenames: set[str],
        ext_basenames: set[str],
    ) -> None:
        """Registry basenames and extraction_paths basenames are identical sets."""
        assert reg_basenames == ext_basenames, (
            f"Mismatch between registry and extraction_paths basenames.\n"
            f"  Only in registry:         {sorted(reg_basenames - ext_basenames)}\n"
            f"  Only in extraction_paths: {sorted(ext_basenames - reg_basenames)}\n"
            "Re-run: specdev registry-generate --repo-root <toolkit-path>"
        )

    def test_registry_entry_array_paths_match_extraction_paths(
        self,
        registry_doc: dict,
        extraction_paths: dict,
    ) -> None:
        """For each registered (basename, array_path), the array_path appears in extraction_paths.

        This validates alignment at the array level — not just at the file level.
        """
        # Build extraction lookup: {basename -> [array_path_strings]}
        ext_lookup: dict[str, list[str]] = {}
        for step_key, value in extraction_paths.items():
            if step_key.startswith("_"):
                continue
            if isinstance(value, dict):
                for bn, paths in value.items():
                    ext_lookup.setdefault(bn, []).extend(paths)

        mismatches: list[str] = []
        for bn, entry in registry_doc.get("registry", {}).items():
            if bn in _SENTINEL_KEYS or entry.get("_special", False):
                continue
            ext_paths = ext_lookup.get(bn, [])
            for arr in entry.get("arrays", []):
                arr_path = arr["array_path"]
                if arr_path not in ext_paths:
                    mismatches.append(
                        f"{bn}:{arr_path} (registered but not in extraction_paths)"
                    )

        assert not mismatches, (
            f"Registry array_paths not present in extraction_paths.json:\n"
            + "\n".join(f"  - {m}" for m in mismatches)
            + "\nRe-run: specdev registry-generate --repo-root <toolkit-path>"
        )
