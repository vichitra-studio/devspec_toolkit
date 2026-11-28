"""T-schema-wellformed — every schema directly under schema/ is valid JSON with $id and $schema.

Covers W6-T3 invariant: toolkit schemas are well-formed.

The JSON-parse and $id/$schema checks run over schema/*.schema.json only:
the step schemas and the sub-schemas at the top level (e.g.
entry_key_registry.schema.json, seed_*.schema.json, step_order.schema.json).
The sub-schemas are not checked for a reference to step_base.schema.json
(they are not step-level artifacts). Core schemas (schema/core/*.schema.json)
get a JSON-parse check only. Every JSON file under schema/, at any depth
(core/, extras/, infra/ included), gets the duplicate-key check; for
schema/extras/ and schema/infra/ it is the only check here.

Step schemas (NN_*.schema.json) are the primary targets.

Toolkit root from this file: Path(__file__).parents[3]
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

def _all_top_level_schemas() -> list[Path]:
    """Return all *.schema.json files directly under schema/ (excluding core/)."""
    return sorted(_SCHEMA_DIR.glob("*.schema.json"))


def _step_schemas() -> list[Path]:
    """Return only step-level schemas matching NN[a]_*.schema.json."""
    return [p for p in _all_top_level_schemas() if _STEP_SCHEMA_RE.match(p.name)]


def _every_schema_file() -> list[Path]:
    """Every JSON file under schema/, at any depth (core/, extras/, infra/ and the rest)."""
    return sorted(_SCHEMA_DIR.rglob("*.json"))


def _duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """``object_pairs_hook`` that refuses an object that holds one key twice (``json.load`` keeps the last copy and drops the first without a word)."""
    keys = [key for key, _ in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise ValueError(f"duplicate key {repeated}")
    return dict(pairs)


@pytest.mark.parametrize("schema_path", _every_schema_file(), ids=lambda p: str(p.relative_to(_SCHEMA_DIR)))
def test_no_schema_file_holds_a_duplicate_key(schema_path: Path) -> None:
    """A repeated key in one object is read as the last copy only, so a declaration above it (an ``x-link``) is silently lost."""
    try:
        json.loads(schema_path.read_text(encoding="utf-8"), object_pairs_hook=_duplicate_keys)
    except ValueError as exc:
        pytest.fail(f"{schema_path.relative_to(_SCHEMA_DIR)}: {exc}")


# ---------------------------------------------------------------------------
# T-schema-wellformed: JSON parse + required top-level fields
# ---------------------------------------------------------------------------


class TestSchemaWellformed:
    """Every schema file directly under schema/ parses as valid JSON and has the
    required $id and $schema fields; a schema/core/ file parses as valid JSON."""

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
        """The text of a step schema file must hold ``vc:core:step-base`` (a substring search of the file, not a walk of ``allOf``)."""
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
