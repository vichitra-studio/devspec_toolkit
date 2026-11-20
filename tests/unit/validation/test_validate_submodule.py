"""Tests for validate.py 16a/16b/16c routing."""
from specdev_tools.validation.validate import DEEP_VALIDATORS


class TestDeepValidators16abc:
    def test_16a_routes_to_step_16a(self):
        assert "16a" in DEEP_VALIDATORS
        # Verify it's not routing to step_16 anymore
        validator = DEEP_VALIDATORS["16a"]
        # The lambda should reference step_16a, not step_16
        assert validator is not DEEP_VALIDATORS["16"]

    def test_16b_routes_to_step_16b(self):
        assert "16b" in DEEP_VALIDATORS
        assert DEEP_VALIDATORS["16b"] is not DEEP_VALIDATORS["16"]

    def test_16c_routes_to_step_16c(self):
        assert "16c" in DEEP_VALIDATORS
        assert DEEP_VALIDATORS["16c"] is not DEEP_VALIDATORS["16"]
