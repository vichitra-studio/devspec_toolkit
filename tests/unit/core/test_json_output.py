"""Tests for specdev_tools.core.json_output.format_errors_json."""
from __future__ import annotations

import json

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.core.json_output import format_errors_json


class TestFormatErrorsJson:
    """Unit tests for the shared JSON output formatter."""

    def test_empty_errors_returns_pass(self) -> None:
        result = json.loads(format_errors_json([]))
        assert result["status"] == "PASS"
        assert result["error_count"] == 0
        assert result["warning_count"] == 0
        assert result["errors"] == []

    def test_only_warnings_returns_warn(self) -> None:
        errors = [
            SpecError(code="W571", message="vague quantifier found"),
            SpecError(code="W593", message="vague language in free text"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["status"] == "WARN"
        assert result["error_count"] == 0
        assert result["warning_count"] == 2
        assert len(result["errors"]) == 2
        assert all(e["severity"] == "warning" for e in result["errors"])

    def test_only_errors_returns_fail(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["status"] == "FAIL"
        assert result["error_count"] == 1
        assert result["warning_count"] == 0

    def test_mixed_errors_and_warnings_returns_fail(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found"),
            SpecError(code="W571", message="vague quantifier"),
            SpecError(code="E520", message="unresolved input"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["status"] == "FAIL"
        assert result["error_count"] == 2
        assert result["warning_count"] == 1
        assert len(result["errors"]) == 3

    def test_context_dict_merging(self) -> None:
        result = json.loads(
            format_errors_json([], context={"command": "validate-all", "spec_dir": "/tmp/spec"})
        )
        assert result["command"] == "validate-all"
        assert result["spec_dir"] == "/tmp/spec"
        assert result["status"] == "PASS"

    def test_context_does_not_overwrite_core_fields(self) -> None:
        # context keys with same names as core fields will overwrite — this is
        # by design so callers can inject additional metadata, but core fields
        # should be set before context is merged.
        result = json.loads(
            format_errors_json(
                [SpecError(code="E510", message="placeholder")],
                context={"command": "test"},
            )
        )
        assert result["command"] == "test"
        # status should still reflect errors (set before context merge)
        assert result["status"] == "FAIL"

    def test_error_with_path_field(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found", path="spec/04_frs.json"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["errors"][0]["path"] == "spec/04_frs.json"
        assert result["errors"][0]["code"] == "E510"
        assert result["errors"][0]["message"] == "placeholder found"
        assert result["errors"][0]["severity"] == "error"

    def test_error_without_path_omits_path_key(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found"),
        ]
        result = json.loads(format_errors_json(errors))
        assert "path" not in result["errors"][0]

    def test_output_is_valid_json(self) -> None:
        errors = [
            SpecError(code="E510", message='has "quotes" and \\ backslashes'),
        ]
        raw = format_errors_json(errors)
        parsed = json.loads(raw)
        assert parsed["errors"][0]["message"] == 'has "quotes" and \\ backslashes'

    def test_severity_classification(self) -> None:
        errors = [
            SpecError(code="E510", message="err"),
            SpecError(code="W571", message="warn"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["errors"][0]["severity"] == "error"
        assert result["errors"][1]["severity"] == "warning"
