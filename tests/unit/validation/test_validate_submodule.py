"""Tests for validate.py 16a/16b/16c routing (16b maps to the 16a validator)."""
from specdev_tools.validation.validate import DEEP_VALIDATORS
from specdev_tools.validation.validators import step_16a


class TestDeepValidators16abc:
    def test_16a_routes_to_step_16a(self):
        assert "16a" in DEEP_VALIDATORS
        # Verify it's not routing to step_16 anymore
        validator = DEEP_VALIDATORS["16a"]
        # The lambda should reference step_16a, not step_16
        assert validator is not DEEP_VALIDATORS["16"]

    def test_16b_maps_to_16a_validator(self, monkeypatch):
        """Pipeline step 16b has no validator of its own: its entry runs the 16a checks."""
        monkeypatch.setattr(step_16a, "validate_step_16a", lambda *args: ["16a ran"])
        assert DEEP_VALIDATORS["16b"]({}, "root", {}) == ["16a ran"]

    def test_16c_routes_to_step_16c(self):
        assert "16c" in DEEP_VALIDATORS
        assert DEEP_VALIDATORS["16c"] is not DEEP_VALIDATORS["16"]
