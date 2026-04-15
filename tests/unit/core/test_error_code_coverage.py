import re
import unittest
from pathlib import Path

from specdev_tools.core.errors import ERROR_CODES


class ErrorCodeCoverageTests(unittest.TestCase):
    def test_expected_codes_present(self):
        """All known error codes are present in ERROR_CODES (bidirectional)."""
        expected = {
            # Canonical integrity (1xx)
            "E110", "E120", "E125", "E130", "E140", "E141", "E142", "E150",
            "W110", "W120", "W130", "W140", "W150",
            # Cross-artifact drift (2xx)
            "E210", "E211",
            # Proof / review closure (3xx)
            "E301", "E302", "E303", "E304", "E305", "E306", "E307",
            "E308", "E309",
            "E310", "E311", "E320",
            # Canonical registry (4xx)
            "E410", "E420", "W421", "E422",
            # Spec content quality (5xx)
            "E510", "E512", "E520", "E521", "E530", "E540", "E541",
            "E550", "E551", "E552", "E553", "E554", "E555",
            "E560", "E561", "E562", "E563",
            "E564", "E565", "E566", "E567", "E568", "E569",
            "E571", "E572", "E573",
            "E575", "E576",
            "E580", "E581", "E582", "E585",
            "W550", "W551", "W552", "W553", "W560", "W561", "W562", "W563",
            "W564", "W565", "W566", "W567", "W568", "W569",
            "W570", "W571", "W572", "W573", "W574",
            "W575", "W576",
            "W580", "W581", "W582", "W583", "W584", "W585", "W586", "W587",
            # R9: Cross-step validation (59x)
            "E590", "E591", "E592", "E593", "E594", "E595",
            "E596", "E597", "E598", "E599",
            "W590", "W591", "W592", "W593", "W594", "W595",
            "W596", "W597", "W598", "W599", "W600",
            "W601", "W602", "W603",
            "E604", "W604",
            "W605",
            # Glossary parity (6xx)
            "E606", "E607", "W606",
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
