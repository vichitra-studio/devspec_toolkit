"""T02: Tests for R9 error codes and PROMOTABLE_PAIRS."""
import unittest

from specdev_tools.core.errors import ERROR_CODES, PROMOTABLE_PAIRS

# Numeric suffixes where E{N} and W{N} intentionally carry DIFFERENT semantic
# names.  These are legitimate divergences documented in errors.py (non-
# promotable pairs, independent concepts that happen to share a number, or
# graduated severity with distinct names).  Any numeric suffix that appears in
# both an E-code and a W-code but whose names are NOT equal must be listed
# here; any NEW unexplained divergence will cause
# test_no_numeric_suffix_collision to fail.
CROSS_PREFIX_SEMANTIC_ALLOWLIST = {
    "110",  # E=UNKNOWN_CANONICAL_ID          / W=DEPRECATED_CANONICAL_USED
    "120",  # E=CANONICAL_KIND_MISMATCH       / W=ALIAS_DEPRECATED
    "130",  # E=CANONICAL_VERSION_MISMATCH    / W=CANONICAL_REF_VERSION_OMITTED
    "140",  # E=AMBIGUOUS_ALIAS               / W=SEED_CONTENT_OVERLAP_LOW
    "550",  # E=FORWARD_REPLAY_MISSING        / W=SEMANTIC_COVERAGE_SKIP
    "551",  # E=SCHEMA_ENUM_EXTRA             / W=UNDECLARED_SEED
    "552",  # E=MISSING_PAIRED_SCHEMA         / W=POTENTIAL_UNREGISTERED_PAIRING
    "553",  # E=MISSING_ENUM_PATH             / W=SEED_STEP_UNKNOWN
    "554",  # E=CANON_ENUM_DRIFT              / W=HARDCODED_SEED_REFERENCE
    "585",  # E=DAG_CIRCULAR_DEPENDENCY       / W=ANCHOR_DRIFT_SKIP
    "590",  # E=CROSS_STEP_ID_NOT_FOUND       / W=CROSS_STEP_UPSTREAM_MISSING
    "592",  # E=COVERAGE_THRESHOLD_BREACH     / W=COVERAGE_THRESHOLD_WARN
    "596",  # E=DAG_DEAD_END_PRODUCER         / W=UNDECLARED_UPSTREAM_REF
    "597",  # E=EXTRACTION_INTENT_UPSTREAM_GAP/ W=EXTRACTION_INTENT_VAGUE
    "598",  # E=EXTRACTION_INTENT_INVALID_REF / W=ID_STABILITY_REMOVAL
    "599",  # E=DAG_CONSUMER_INCONSISTENCY    / W=EVIDENCE_TOO_SHORT
    "606",  # E=GLOSSARY_PROPOSAL_DRIFT       / W=GLOSSARY_CANON_ORPHAN
    "607",  # E=GLOSSARY_CANON_DRIFT          / W=ANCHOR_CONTEXT_PATH_MISSING
    "608",  # E=TOOLKIT_VERSION_MISMATCH      / W=ANCHOR_LEGACY_SCHEMA
}


class TestR9ErrorCodes(unittest.TestCase):
    """Verify all R9 error codes are registered and PROMOTABLE_PAIRS is correct."""

    # All new R9 codes (26 new + 4 previously unregistered) + DEVSPEC-89 additions
    R9_NEW_CODES = {
        "E150", "E551", "E552", "E553", "E554", "E555",
        "E571", "E572", "E573", "E580", "E581", "E585",
        "E590", "E591", "E592", "E593", "E594", "E595",
        "E596", "E597", "E598", "E599",
        "E615",
        "W552",
        "W590", "W591", "W592", "W593", "W594", "W595",
        "W596", "W597",
        "W615",
    }

    def test_all_r9_codes_registered(self):
        """Every R9 code exists in ERROR_CODES."""
        for code in self.R9_NEW_CODES:
            self.assertIn(code, ERROR_CODES, f"{code} not registered in ERROR_CODES")

    def test_promotable_pairs_count(self):
        """PROMOTABLE_PAIRS has exactly 27 W→E mappings."""
        self.assertEqual(len(PROMOTABLE_PAIRS), 27)

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
        """Cross-prefix semantic divergence is confined to the known allowlist.

        For every numeric suffix N that appears in BOTH an E-code and a W-code,
        E{N} and W{N} must either share the same semantic name (intentional
        promotable pair) or be listed in CROSS_PREFIX_SEMANTIC_ALLOWLIST
        (intentional divergence documented at module level).

        Any NEW unexplained divergence — e.g. a developer adds E700 and W700
        with different names without updating the allowlist — will fail here.
        """
        e_nums = {k[1:]: v for k, v in ERROR_CODES.items() if k.startswith("E")}
        w_nums = {k[1:]: v for k, v in ERROR_CODES.items() if k.startswith("W")}

        shared = set(e_nums) & set(w_nums)
        unexpected_divergences = []
        for num in sorted(shared):
            e_name = e_nums[num]
            w_name = w_nums[num]
            if e_name != w_name and num not in CROSS_PREFIX_SEMANTIC_ALLOWLIST:
                unexpected_divergences.append(
                    f"  suffix {num}: E{num}={e_name}, W{num}={w_name} "
                    f"(add to CROSS_PREFIX_SEMANTIC_ALLOWLIST if intentional)"
                )

        if unexpected_divergences:
            self.fail(
                "Unexpected cross-prefix semantic divergences found:\n"
                + "\n".join(unexpected_divergences)
            )

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
