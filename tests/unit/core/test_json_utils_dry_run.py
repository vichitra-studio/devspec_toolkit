"""Tests for json_utils dry-run and validate_against_schema_field (ticket #15 scope)."""
from __future__ import annotations

import json
import pathlib

from specdev_tools.core.json_utils import (
    json_delete,
    json_insert,
    json_patch,
    validate_against_schema_field,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec_file(tmp_path: pathlib.Path, content: dict | None = None) -> pathlib.Path:
    f = tmp_path / "04_fr_list.json"
    f.write_text(json.dumps(content or {"owner": "api", "items": [1, 2]}), encoding="utf-8")
    return f


def _make_schema(tmp_path: pathlib.Path, step: str = "04") -> pathlib.Path:
    """Create a minimal schema/<step>_*.schema.json with a known field."""
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir(exist_ok=True)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "allOf": [
            {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "enum": ["api", "ui", "product"]},
                    "items": {"type": "array", "items": {"type": "integer"}},
                },
            }
        ],
    }
    schema_file = schema_dir / f"{step}_fr_list.schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    return tmp_path  # return repo_root


# ---------------------------------------------------------------------------
# dry_run tests
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_patch_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)
        original = f.read_text(encoding="utf-8")

        result = json_patch(str(f), ".owner", '"product"', dry_run=True)

        assert f.read_text(encoding="utf-8") == original, "File must not be modified in dry-run"
        assert "[dry-run]" in result
        assert "product" in result

    def test_patch_dry_run_false_writes(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)

        result = json_patch(str(f), ".owner", '"product"', dry_run=False)

        content = json.loads(f.read_text(encoding="utf-8"))
        assert content["owner"] == "product"
        assert "[dry-run]" not in result

    def test_insert_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)
        original = f.read_text(encoding="utf-8")

        result = json_insert(str(f), ".items", "99", dry_run=True)

        assert f.read_text(encoding="utf-8") == original
        assert "[dry-run]" in result
        assert "99" in result

    def test_delete_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)
        original = f.read_text(encoding="utf-8")

        result = json_delete(str(f), ".items[0]", dry_run=True)

        assert f.read_text(encoding="utf-8") == original
        assert "[dry-run]" in result


# ---------------------------------------------------------------------------
# validate_against_schema_field tests
# ---------------------------------------------------------------------------


class TestValidateAgainstSchemaField:
    def test_valid_value_returns_empty(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('"api"', "04.owner", repo_root)

        assert errors == []

    def test_invalid_value_returns_errors(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('"not_a_valid_owner"', "04.owner", repo_root)

        assert len(errors) > 0
        assert any("not_a_valid_owner" in e or "api" in e or "valid" in e.lower() for e in errors)

    def test_bad_format_returns_error(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('"api"', "no-dot-here", repo_root)

        assert len(errors) == 1
        assert "expected '<step>.<field>'" in errors[0]

    def test_unknown_step_returns_error(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('"api"', "99.owner", repo_root)

        assert len(errors) == 1
        assert "not found" in errors[0].lower() or "99" in errors[0]

    def test_unknown_field_returns_error(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('"api"', "04.nonexistent_field", repo_root)

        assert len(errors) == 1
        assert "nonexistent_field" in errors[0]

    def test_invalid_json_value_returns_error(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field("not json {}", "04.owner", repo_root)

        assert len(errors) == 1
        assert "not valid JSON" in errors[0]

    def test_valid_array_field(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field("[1, 2, 3]", "04.items", repo_root)

        assert errors == []

    def test_invalid_array_items_type(self, tmp_path: pathlib.Path) -> None:
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('["string", "not_int"]', "04.items", repo_root)

        assert len(errors) > 0

    def test_three_part_format_returns_not_implemented(self, tmp_path: pathlib.Path) -> None:
        """Three-part <step>.<schema_suffix>.<field> returns 'not yet implemented' error."""
        repo_root = str(_make_schema(tmp_path))

        errors = validate_against_schema_field('"any"', "16.anchor.steps", repo_root)

        assert len(errors) == 1
        assert "not yet implemented" in errors[0]
