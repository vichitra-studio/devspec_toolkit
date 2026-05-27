"""T-registry-generation — generated registry validates against its own schema.

Covers W6-T3 invariant: the registry generator produces schema-valid output.

NOTE: tests/unit/registry/test_generate.py::TestSchemaValidation already runs
generate_registry() and validates against entry_key_registry.schema.json using
jsonschema. This file does NOT duplicate that check. Instead, it focuses on the
invariant as a named toolkit-invariant (distinct concern from the generator's
unit test) and tests additional structural constraints that test_generate.py
does not cover:
  - The generated registry doc has all required top-level fields.
  - Both outputs (registry doc + extraction_paths) are non-empty dicts.
  - The schema file itself is present and valid JSON.

For the full schema-validation assertion, see:
  tests/unit/registry/test_generate.py::TestSchemaValidation::test_registry_doc_validates_against_schema

Toolkit root from this file: Path(__file__).parents[4]
  → devspec_toolkit/tests/unit/toolkit_invariants/test_registry_generation.py
  → parents[0] = devspec_toolkit/tests/unit/toolkit_invariants/
  → parents[1] = devspec_toolkit/tests/unit/
  → parents[2] = devspec_toolkit/tests/
  → parents[3] = devspec_toolkit/
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.registry.generate import generate_registry

# ---------------------------------------------------------------------------
# Toolkit root resolution
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
_SCHEMA_PATH = _TOOLKIT_ROOT / "schema" / "entry_key_registry.schema.json"
_REGISTRY_PATH = _TOOLKIT_ROOT / "tools" / "entry_key_registry.json"

_REQUIRED_TOP_LEVEL_KEYS = frozenset({
    "_format_version",
    "_note",
    "registry",
    "_sentinels",
    "steps_without_entry_arrays",
    "steps_with_deferred_registration",
})


def _run_generator():
    """Run generate_registry() against toolkit's own schemas (in-process)."""
    return generate_registry(str(_TOOLKIT_ROOT))


# ---------------------------------------------------------------------------
# T-registry-generation
# ---------------------------------------------------------------------------


class TestRegistryGeneration:
    """Registry generator produces structurally valid output."""

    def test_schema_file_exists(self) -> None:
        """entry_key_registry.schema.json must exist."""
        assert _SCHEMA_PATH.is_file(), (
            f"Schema not found: {_SCHEMA_PATH}. "
            "The toolkit schema directory may be corrupted."
        )

    def test_schema_file_is_valid_json(self) -> None:
        """entry_key_registry.schema.json must parse as valid JSON."""
        try:
            json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"entry_key_registry.schema.json: invalid JSON — {exc}")

    def test_generator_produces_registry_doc(self) -> None:
        """generate_registry() returns a non-empty dict as first element."""
        reg_doc, _ = _run_generator()
        assert isinstance(reg_doc, dict), "Registry doc is not a dict."
        assert reg_doc, "Registry doc is empty."

    def test_generator_produces_extraction_paths(self) -> None:
        """generate_registry() returns a non-empty dict as second element."""
        _, ext = _run_generator()
        assert isinstance(ext, dict), "Extraction paths is not a dict."
        assert ext, "Extraction paths doc is empty."

    def test_registry_doc_has_required_top_level_keys(self) -> None:
        """Registry doc contains all required top-level fields per schema."""
        reg_doc, _ = _run_generator()
        missing = _REQUIRED_TOP_LEVEL_KEYS - set(reg_doc.keys())
        assert not missing, (
            f"Registry doc is missing required top-level keys: {sorted(missing)}. "
            "The generator may not be writing all schema-required fields."
        )

    def test_registry_doc_validates_against_schema(self) -> None:
        """Registry doc validates against entry_key_registry.schema.json using jsonschema.

        NOTE: This is the same assertion as test_generate.py::TestSchemaValidation.
        It is included here so the toolkit_invariants suite is self-contained.
        """
        import jsonschema  # noqa: PLC0415

        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        reg_doc, _ = _run_generator()
        try:
            jsonschema.validate(instance=reg_doc, schema=schema)
        except jsonschema.ValidationError as exc:
            pytest.fail(
                f"Generated registry doc failed schema validation:\n{exc.message}"
            )

    def test_extraction_paths_has_no_meta_only(self) -> None:
        """Extraction paths must contain non-_meta step keys."""
        _, ext = _run_generator()
        step_keys = [k for k in ext if not k.startswith("_")]
        assert step_keys, (
            "Extraction paths doc contains only _meta keys — no step entries. "
            "The generator may have produced an empty result."
        )
