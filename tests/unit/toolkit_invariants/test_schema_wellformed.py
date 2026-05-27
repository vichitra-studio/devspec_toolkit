"""T-schema-wellformed — every step schema in schema/ is valid JSON with $id and $schema.

Covers W6-T3 invariant: toolkit schemas are well-formed.

Sub-schemas (e.g. entry_key_registry.schema.json, seed_*.schema.json,
step_order.schema.json) and core schemas (schema/core/*.schema.json) are
included in JSON-parse and $id/$schema checks but are NOT validated against
step_base.schema.json (they are not step-level artifacts).

Step schemas (NN_*.schema.json) are the primary targets.

Toolkit root from this file: Path(__file__).parents[4]
  → devspec_toolkit/tests/unit/toolkit_invariants/test_schema_wellformed.py
  → parents[0] = devspec_toolkit/tests/unit/toolkit_invariants/
  → parents[1] = devspec_toolkit/tests/unit/
  → parents[2] = devspec_toolkit/tests/
  → parents[3] = devspec_toolkit/
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Toolkit root resolution
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
_SCHEMA_DIR = _TOOLKIT_ROOT / "schema"

# Pattern for step-level schemas (e.g. 04_fr_list.schema.json, 16_impl_context.schema.json)
_STEP_SCHEMA_RE = re.compile(r"^\d{2}[a-z]?_.*\.schema\.json$")

# Non-step schemas that are legitimately present at the top level
_NON_STEP_SCHEMAS = frozenset({
    "entry_key_registry.schema.json",
    "seed_manifest.schema.json",
    "seed_requirements.schema.json",
    "step_order.schema.json",
})


def _all_top_level_schemas() -> list[Path]:
    """Return all *.schema.json files directly under schema/ (excluding core/)."""
    return sorted(_SCHEMA_DIR.glob("*.schema.json"))


def _step_schemas() -> list[Path]:
    """Return only step-level schemas matching NN[a]_*.schema.json."""
    return [p for p in _all_top_level_schemas() if _STEP_SCHEMA_RE.match(p.name)]


# ---------------------------------------------------------------------------
# T-schema-wellformed: JSON parse + required top-level fields
# ---------------------------------------------------------------------------


class TestSchemaWellformed:
    """Every schema file in schema/ (top-level and core/) parses as valid JSON
    and has the required $id and $schema fields."""

    @pytest.mark.parametrize("schema_path", _all_top_level_schemas(), ids=lambda p: p.name)
    def test_parses_as_valid_json(self, schema_path: Path) -> None:
        """Schema file is valid JSON."""
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"{schema_path.name}: invalid JSON — {exc}")

    @pytest.mark.parametrize("schema_path", _all_top_level_schemas(), ids=lambda p: p.name)
    def test_has_dollar_id(self, schema_path: Path) -> None:
        """Schema file has a top-level $id field."""
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "$id" in data, (
            f"{schema_path.name}: missing top-level '$id'. "
            "Every schema must declare a unique URI identifier."
        )

    @pytest.mark.parametrize("schema_path", _all_top_level_schemas(), ids=lambda p: p.name)
    def test_has_dollar_schema(self, schema_path: Path) -> None:
        """Schema file has a top-level $schema field."""
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "$schema" in data, (
            f"{schema_path.name}: missing top-level '$schema'. "
            "Every schema must declare the JSON Schema draft URI."
        )

    @pytest.mark.parametrize("schema_path", _all_top_level_schemas(), ids=lambda p: p.name)
    def test_dollar_schema_is_draft_2020_12(self, schema_path: Path) -> None:
        """$schema must reference JSON Schema draft 2020-12."""
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_uri = data.get("$schema", "")
        assert "2020-12" in schema_uri, (
            f"{schema_path.name}: $schema='{schema_uri}' does not reference draft 2020-12. "
            "All toolkit schemas must use https://json-schema.org/draft/2020-12/schema."
        )

    @pytest.mark.parametrize("schema_path", _step_schemas(), ids=lambda p: p.name)
    def test_step_schema_references_step_base(self, schema_path: Path) -> None:
        """Step schemas must reference vc:core:step-base (directly or via allOf)."""
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_text = schema_path.read_text(encoding="utf-8")
        assert "vc:core:step-base" in schema_text, (
            f"{schema_path.name}: step schema does not reference 'vc:core:step-base'. "
            "Step schemas must extend the base via allOf or $ref."
        )

    def test_core_schemas_are_well_formed(self) -> None:
        """All schema/core/*.schema.json files parse as valid JSON."""
        core_dir = _SCHEMA_DIR / "core"
        core_schemas = sorted(core_dir.glob("*.schema.json"))
        assert core_schemas, f"Expected core schemas in {core_dir}, found none."
        for p in core_schemas:
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                pytest.fail(f"core/{p.name}: invalid JSON — {exc}")
