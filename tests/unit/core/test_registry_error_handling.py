"""Tests for SchemaRegistry error handling enhancements."""
import json
import os
import pytest
import tempfile
from specdev_tools.core.registry import SchemaRegistry


@pytest.fixture
def registry_dir(tmp_path):
    """Create a minimal registry setup."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()

    # Write a valid schema
    schema_file = schema_dir / "test.schema.json"
    schema_file.write_text(json.dumps({"type": "object"}))

    # Write registry mapping
    registry = {
        "vc:test": "schema/test.schema.json",
    }
    (tools_dir / "schema_registry.json").write_text(json.dumps(registry))

    return tmp_path


class TestUriExists:
    def test_existing_uri(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        assert reg.uri_exists("vc:test") is True

    def test_missing_uri(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        assert reg.uri_exists("vc:nonexistent") is False


class TestLoadWithFallback:
    def test_existing_uri_returns_schema(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        result = reg.load_with_fallback("vc:test")
        assert result == {"type": "object"}

    def test_missing_uri_returns_default(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        default = {"type": "string"}
        result = reg.load_with_fallback("vc:missing", default=default)
        assert result == default

    def test_missing_uri_no_default_raises(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        with pytest.raises(FileNotFoundError):
            reg.load_with_fallback("vc:missing")


class TestEnhancedErrorMessages:
    def test_load_missing_suggests_registry(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        with pytest.raises(FileNotFoundError, match="schema_registry.json"):
            reg.load("vc:missing")

    def test_load_missing_suggests_repo_root(self, registry_dir):
        reg = SchemaRegistry(str(registry_dir))
        with pytest.raises(FileNotFoundError, match="--repo-root"):
            reg.load("vc:missing")
