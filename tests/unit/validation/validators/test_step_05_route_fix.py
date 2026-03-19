import unittest

from specdev_tools.validation.validators.step_05 import validate_step_05


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


class Step05RouteValidationTests(unittest.TestCase):
    """Tests for Step 05 duplicate method/path detection (D18 fix)."""

    def test_duplicate_path_is_detected(self):
        """Two APIs with same method + path must produce an error."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "path": "/api/users"},
                {"api_id": "api-2", "method": "GET", "path": "/api/users"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate API method/route" in e for e in _render(errors)),
            f"Expected duplicate path error, got: {_render(errors)}",
        )

    def test_different_paths_are_accepted(self):
        """Two APIs with same method but different paths are fine."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "path": "/api/users"},
                {"api_id": "api-2", "method": "GET", "path": "/api/posts"},
            ]
        }
        errors = validate_step_05(instance, ".")
        path_errors = [e for e in _render(errors) if "Duplicate API method/route" in e]
        self.assertEqual(path_errors, [])

    def test_same_path_different_methods_are_accepted(self):
        """Same path with different HTTP methods is fine (REST pattern)."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "path": "/api/users"},
                {"api_id": "api-2", "method": "POST", "path": "/api/users"},
            ]
        }
        errors = validate_step_05(instance, ".")
        path_errors = [e for e in _render(errors) if "Duplicate API method/route" in e]
        self.assertEqual(path_errors, [])

    def test_backward_compat_route_field(self):
        """Legacy 'route' field is still detected for backward compatibility."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "route": "/api/users"},
                {"api_id": "api-2", "method": "GET", "route": "/api/users"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate API method/route" in e for e in _render(errors)),
            f"Expected duplicate path error via 'route' fallback, got: {_render(errors)}",
        )

    def test_path_preferred_over_route(self):
        """When both 'path' and 'route' exist, 'path' takes precedence."""
        instance = {
            "apis": [
                {"api_id": "api-1", "method": "GET", "path": "/v2/users", "route": "/v1/users"},
                {"api_id": "api-2", "method": "GET", "path": "/v2/users", "route": "/v1/posts"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate API method/route 'GET /v2/users'" in e for e in _render(errors)),
            f"Expected duplicate on path, not route, got: {_render(errors)}",
        )

    def test_duplicate_api_id_still_detected(self):
        """Existing duplicate api_id check still works."""
        instance = {
            "apis": [
                {"api_id": "api-same", "method": "GET", "path": "/api/a"},
                {"api_id": "api-same", "method": "POST", "path": "/api/b"},
            ]
        }
        errors = validate_step_05(instance, ".")
        self.assertTrue(
            any("Duplicate api_id" in e for e in _render(errors)),
            f"Expected duplicate api_id error, got: {_render(errors)}",
        )


if __name__ == "__main__":
    unittest.main()
