import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.validators.step_05 import validate_step_05


class Step05RouteValidationTests(unittest.TestCase):
    """Tests for Step 05 duplicate method/route detection (D18 fix)."""

    def test_duplicate_route_is_detected(self):
        """Two APIs with same method + route must produce an error."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "route": "/api/users"},
                {"api_id": "api-2", "method": "GET", "route": "/api/users"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate API method/route" in e for e in errors),
            f"Expected duplicate route error, got: {errors}",
        )

    def test_different_routes_are_accepted(self):
        """Two APIs with same method but different routes are fine."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "route": "/api/users"},
                {"api_id": "api-2", "method": "GET", "route": "/api/posts"},
            ]
        }
        errors = validate_step_05(instance, ".")
        route_errors = [e for e in errors if "Duplicate API method/route" in e]
        self.assertEqual(route_errors, [])

    def test_same_route_different_methods_are_accepted(self):
        """Same route with different HTTP methods is fine (REST pattern)."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "route": "/api/users"},
                {"api_id": "api-2", "method": "POST", "route": "/api/users"},
            ]
        }
        errors = validate_step_05(instance, ".")
        route_errors = [e for e in errors if "Duplicate API method/route" in e]
        self.assertEqual(route_errors, [])

    def test_backward_compat_path_field(self):
        """Legacy 'path' field is still detected for backward compatibility."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "path": "/api/users"},
                {"api_id": "api-2", "method": "GET", "path": "/api/users"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate API method/route" in e for e in errors),
            f"Expected duplicate route error via 'path' fallback, got: {errors}",
        )

    def test_route_preferred_over_path(self):
        """When both 'route' and 'path' exist, 'route' takes precedence."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "route": "/v2/users", "path": "/v1/users"},
                {"api_id": "api-2", "method": "GET", "route": "/v2/users", "path": "/v1/posts"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate API method/route 'GET /v2/users'" in e for e in errors),
            f"Expected duplicate on route, not path, got: {errors}",
        )

    def test_duplicate_api_id_still_detected(self):
        """Existing duplicate api_id check still works."""
        instance = {
            "apis": [
                {"api_id": "api-same", "method": "GET", "route": "/api/a"},
                {"api_id": "api-same", "method": "POST", "route": "/api/b"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate api_id" in e for e in errors),
            f"Expected duplicate api_id error, got: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
