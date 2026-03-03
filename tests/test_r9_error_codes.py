"""T02: Tests for R9 error codes and PROMOTABLE_PAIRS."""
import unittest

from specdev_tools.core.errors import ERROR_CODES, PROMOTABLE_PAIRS


class TestR9ErrorCodes(unittest.TestCase):
    """Verify all R9 error codes are registered and PROMOTABLE_PAIRS is correct."""

    # All new R9 codes (26 new + 4 previously unregistered)
    R9_NEW_CODES = {
        "E150", "E551", "E552", "E553", "E554", "E555",
        "E571", "E572", "E573", "E580", "E581", "E585",
        "E590", "E591", "E592", "E593", "E594", "E595",
        "E596", "E597", "E598", "E599",
        "W552",
        "W590", "W591", "W592", "W593", "W594", "W595",
        "W596", "W597",
    }

    def test_all_r9_codes_registered(self):
        """Every R9 code exists in ERROR_CODES."""
        for code in self.R9_NEW_CODES:
            self.assertIn(code, ERROR_CODES, f"{code} not registered in ERROR_CODES")

    def test_promotable_pairs_count(self):
        """PROMOTABLE_PAIRS has at least 18 W→E mappings."""
        self.assertGreaterEqual(len(PROMOTABLE_PAIRS), 18)

    def test_promotable_pairs_w_to_e(self):
        """Every key in PROMOTABLE_PAIRS is a W-code mapping to an E-code."""
        for w_code, e_code in PROMOTABLE_PAIRS.items():
            self.assertTrue(w_code.startswith("W"), f"{w_code} should start with W")
            self.assertTrue(e_code.startswith("E"), f"{e_code} should start with E")

    def test_promotable_pairs_codes_registered(self):
        """All codes in PROMOTABLE_PAIRS exist in ERROR_CODES."""
        for w_code, e_code in PROMOTABLE_PAIRS.items():
            self.assertIn(w_code, ERROR_CODES, f"W-code {w_code} not in ERROR_CODES")
            self.assertIn(e_code, ERROR_CODES, f"E-code {e_code} not in ERROR_CODES")

    def test_no_numeric_suffix_collision(self):
        """No two E-codes or W-codes share the same numeric suffix with different semantics."""
        e_codes = {k: v for k, v in ERROR_CODES.items() if k.startswith("E")}
        w_codes = {k: v for k, v in ERROR_CODES.items() if k.startswith("W")}

        # Check E-codes: no duplicate numeric suffixes
        e_nums = {}
        for code, semantic in e_codes.items():
            num = code[1:]
            if num in e_nums:
                self.fail(
                    f"E-code collision: {code} ({semantic}) and E{num} ({e_nums[num]}) "
                    f"share suffix {num}"
                )
            e_nums[num] = semantic

        # Check W-codes: no duplicate numeric suffixes
        w_nums = {}
        for code, semantic in w_codes.items():
            num = code[1:]
            if num in w_nums:
                self.fail(
                    f"W-code collision: {code} ({semantic}) and W{num} ({w_nums[num]}) "
                    f"share suffix {num}"
                )
            w_nums[num] = semantic

    def test_e550_no_longer_overloaded(self):
        """E550 is exclusively FORWARD_REPLAY_MISSING; E554 handles CANON_ENUM_DRIFT."""
        self.assertEqual(ERROR_CODES["E550"], "FORWARD_REPLAY_MISSING")
        self.assertEqual(ERROR_CODES["E554"], "CANON_ENUM_DRIFT")
        self.assertEqual(ERROR_CODES["E555"], "SEMANTIC_COVERAGE_REGRESSION")

    def test_non_promotable_codes_excluded(self):
        """Non-promotable W-codes are NOT in PROMOTABLE_PAIRS."""
        non_promotable = {"W110", "W120", "W130", "W140", "W552", "W570", "W596"}
        for code in non_promotable:
            self.assertNotIn(code, PROMOTABLE_PAIRS,
                             f"{code} should not be promotable")


if __name__ == "__main__":
    unittest.main()
