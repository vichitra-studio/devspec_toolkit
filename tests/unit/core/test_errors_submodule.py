"""Tests for SubmoduleDetectionError and SchemaRegistryError."""
import pytest
from specdev_tools.core.errors import (
    SpecdevError,
    SubmoduleDetectionError,
    SchemaRegistryError,
)


class TestSpecdevError:
    def test_base_class(self):
        err = SpecdevError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"


class TestSubmoduleDetectionError:
    def test_inherits_specdev_error(self):
        err = SubmoduleDetectionError()
        assert isinstance(err, SpecdevError)

    def test_default_message(self):
        err = SubmoduleDetectionError()
        assert "--git-root" in str(err)
        assert "--spec-root" in str(err)

    def test_custom_message(self):
        err = SubmoduleDetectionError("custom msg")
        assert str(err) == "custom msg"


class TestSchemaRegistryError:
    def test_inherits_specdev_error(self):
        err = SchemaRegistryError("https://example.com/schema")
        assert isinstance(err, SpecdevError)

    def test_message_contains_uri(self):
        err = SchemaRegistryError("vc:foo")
        assert "vc:foo" in str(err)
        assert "schema_registry.json" in str(err)

    def test_uri_attribute(self):
        err = SchemaRegistryError("test-uri")
        assert err.uri == "test-uri"

    def test_with_detail(self):
        err = SchemaRegistryError("test-uri", detail="file not found")
        assert "file not found" in str(err)

    def test_without_detail(self):
        err = SchemaRegistryError("test-uri")
        assert "Detail" not in str(err)
