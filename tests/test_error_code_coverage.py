import re
import unittest
from pathlib import Path

from specdev_tools.core.errors import ERROR_CODES


class ErrorCodeCoverageTests(unittest.TestCase):
    def test_expected_codes_present(self):
        """All known error codes are present in ERROR_CODES (bidirectional)."""
        expected = {
            "E110",
            "E120",
            "E125",
            "E130",
            "E140",
            "E210",
            "E211",
            "E301",
            "E302",
            "E303",
            "E304",
            "E305",
            "E306",
            "E307",
            "E310",
            "E410",
            "E420",
            "E510",
            "E511",
            "E512",
            "E520",
            "E521",
            "E530",
            "E540",
            "E541",
            "E550",
            "E560",
            "E561",
            "E562",
            "E563",
            "W110",
            "W120",
            "W130",
            "W550",
            "W560",
            "W570",
            "W571",
            "W572",
            "W573",
            "W580",
            "W581",
            "E582",
            "W140",
            "W561",
            "W562",
            "W563",
        }
        actual = set(ERROR_CODES.keys())
        self.assertEqual(
            expected,
            actual,
            f"Mismatch between expected and actual error codes.\n"
            f"  Missing from expected: {actual - expected}\n"
            f"  Missing from ERROR_CODES: {expected - actual}",
        )

    def test_all_emitted_codes_registered(self):
        """Every error/warning code used as a string literal in source files exists in ERROR_CODES."""
        tools_dir = Path(__file__).resolve().parent.parent / "tools" / "specdev_tools"
        pattern = re.compile(r'"([EW]\d{3})"')
        found_codes = set()
        for py_file in tools_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            found_codes.update(pattern.findall(source))
        registered = set(ERROR_CODES.keys())
        unregistered = found_codes - registered
        self.assertFalse(
            unregistered,
            f"Codes used in source but not registered in ERROR_CODES: {sorted(unregistered)}",
        )


if __name__ == "__main__":
    unittest.main()
