import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.trace_types import normalize_trace_type, is_valid_trace_type


class TraceTypesTests(unittest.TestCase):
    def test_normalize_inv_alias(self):
        self.assertEqual(normalize_trace_type("inv"), "invariant")

    def test_accepts_invariant_and_component(self):
        self.assertTrue(is_valid_trace_type("invariant"))
        self.assertTrue(is_valid_trace_type("component"))


if __name__ == "__main__":
    unittest.main()
