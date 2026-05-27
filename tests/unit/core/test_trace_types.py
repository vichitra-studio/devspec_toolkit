import unittest

from specdev_tools.core.trace_types import (
    normalize_trace_type,
    is_valid_trace_type,
    normalize_trace_types,
    TRACE_TYPES,
    CANONICAL_TRACE_TYPE,
    _FALLBACK_TYPES,
)


class TraceTypesTests(unittest.TestCase):
    def test_normalize_inv_alias(self):
        self.assertEqual(normalize_trace_type("inv"), "invariant")

    def test_accepts_invariant_and_component(self):
        self.assertTrue(is_valid_trace_type("invariant"))
        self.assertTrue(is_valid_trace_type("component"))

    def test_trace_types_loaded_from_canon(self):
        self.assertIsInstance(TRACE_TYPES, tuple)
        for t in TRACE_TYPES:
            self.assertIsInstance(t, str)
        expected_core = {"fr", "api", "nfr", "invariant", "fixture", "doc", "capability", "component", "threat"}
        for core in expected_core:
            self.assertIn(core, TRACE_TYPES, f"{core} should be in TRACE_TYPES")
        self.assertNotIn("inv", TRACE_TYPES)

    def test_canonical_trace_type_from_canon(self):
        self.assertIsInstance(CANONICAL_TRACE_TYPE, dict)
        self.assertEqual(CANONICAL_TRACE_TYPE.get("inv"), "invariant")

    def test_all_canon_types_are_valid(self):
        for t in TRACE_TYPES:
            self.assertTrue(is_valid_trace_type(t), f"{t} should be valid")

    def test_invalid_type_rejected(self):
        self.assertFalse(is_valid_trace_type("bogus"))

    def test_normalize_empty_and_whitespace(self):
        self.assertEqual(normalize_trace_type(""), "")
        self.assertEqual(normalize_trace_type("  "), "")

    def test_normalize_types_batch(self):
        self.assertEqual(normalize_trace_types(["inv", "fr", "api"]), ["invariant", "fr", "api"])

    def test_fallback_types_are_sorted(self):
        self.assertEqual(_FALLBACK_TYPES, tuple(sorted(_FALLBACK_TYPES)))

    def test_threat_is_valid_trace_type(self):
        self.assertTrue(is_valid_trace_type("threat"))


if __name__ == "__main__":
    unittest.main()
