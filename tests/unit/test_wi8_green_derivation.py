"""
Regression lock for WI-8 (C3): anchored ci_status green derivation.

The SKILL.md --phase review post-convergence step derives ci_status:"green" from
actions[].evidence.content using ANCHORED signals, not a bare substring match.
This test encodes the exact pattern documented in SKILL.md Step C2 and asserts:
  - decoy evidence that MUST NOT yield green (AC7 guard)
  - genuine anchored pass signals that MUST yield green

Any change to the anchored-match rule in SKILL.md must be reflected here;
failing this test means the documented pattern no longer matches the implementation.

This is a regression-lock on the documented pattern (the LLM reads SKILL.md prose).
The helper below encodes that prose as executable logic so the contract is checkable.
"""

import re

# ---------------------------------------------------------------------------
# Anchored green-derivation logic (mirrors SKILL.md Step C2)
# ---------------------------------------------------------------------------

# Failure signals — any present in evidence_content ⇒ not green
_FAILURE_SIGNALS = re.compile(
    r"\b(FAIL(?:ED)?|ERROR)\b",
    re.IGNORECASE,
)

# Anchored success signals — bare "PASS" substring is NOT sufficient (AC7)
#   1. Test-runner context + PASS/PASSED as a word boundary
#   2. Explicit "N passed" counter (N ≥ 1; "0 passed" is not a success)
#   3. Explicit "exit 0" token
_ANCHORED_SUCCESS = re.compile(
    r"(?:"
    r"(?:^|\n)(?:pytest|tests?|ci|suite)\b[^\n]*\bPASS(?:ED)?\b"
    r"|"
    r"\b[1-9]\d*\s+pass(?:ed)?\b"
    r"|"
    r"\bexit\s+0\b"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def _derive_ci_green(evidence_content: str) -> bool:
    """
    Return True only when evidence_content carries an anchored CI success signal
    AND no failure signal is present.

    Mirrors SKILL.md --phase review Step C2 anchored-match rule (WI-8/C3).
    """
    if _FAILURE_SIGNALS.search(evidence_content):
        return False
    return bool(_ANCHORED_SUCCESS.search(evidence_content))


# ---------------------------------------------------------------------------
# AC7: decoy evidence that must NOT yield green
# ---------------------------------------------------------------------------


class TestDecoyEvidence:
    """Decoys that look like passing output but must not yield ci_status:"green"."""

    def test_bypassed_is_not_green(self):
        # "BYPASSED" contains no anchored success signal — no test runner prefix,
        # no "N passed", no "exit 0". Substring "PASS" embedded in the word is
        # NOT a word boundary match and does not satisfy the anchored rule.
        assert _derive_ci_green("BYPASSED") is False

    def test_passed_zero_of_three_suites_is_not_green(self):
        # "PASSED 0 of 3 suites" — 0 tests actually passed. The word PASSED
        # appears but without a test-runner keyword prefix. "0 of 3 suites" does
        # not match "\b\d+\s+pass(ed)?\b" (no "passed" follows the digit).
        assert _derive_ci_green("PASSED 0 of 3 suites") is False

    def test_compile_pass_tests_fail_is_not_green(self):
        # Failure signal (FAIL) is present — overrides the PASS substring.
        assert _derive_ci_green("compile PASS / tests FAIL") is False

    def test_bare_pass_substring_in_middle_is_not_green(self):
        # "BUILD PASS" without a test-runner keyword at line start.
        assert _derive_ci_green("Build step: BUILD PASS") is False

    def test_passed_with_failures_elsewhere_is_not_green(self):
        # Mixed output: a passing line AND a failing line — failure wins.
        content = "pytest tests/unit/ PASSED\ncollected 0 items / ERROR in conftest.py"
        assert _derive_ci_green(content) is False


# ---------------------------------------------------------------------------
# AC7: genuine anchored pass signals that MUST yield green
# ---------------------------------------------------------------------------


class TestAnchoredSuccessSignals:
    """Genuine CI pass signals that satisfy the anchored rule."""

    def test_pytest_pass_line_is_green(self):
        # Exact pattern from ms_auth_plan.json fixture evidence (type="fr" primary branch).
        # Line starts with "pytest", contains PASS as a word.
        content = "pytest tests/test_auth.py::test_login_issues_jwt PASS — 1 test for fr-user-login"
        assert _derive_ci_green(content) is True

    def test_pytest_passed_line_is_green(self):
        # "PASSED" variant (word boundary after D).
        content = "pytest tests/test_session.py PASSED — 2 tests for fr-session-create"
        assert _derive_ci_green(content) is True

    def test_n_passed_counter_is_green(self):
        # Explicit "N passed" counter — no test runner prefix needed.
        assert _derive_ci_green("3 passed, 0 warnings") is True

    def test_exit_0_token_is_green(self):
        # Explicit exit code token.
        assert _derive_ci_green("CI pipeline completed — exit 0") is True

    def test_ci_keyword_prefix_is_green(self):
        # "ci" as a prefix keyword.
        assert _derive_ci_green("ci: all checks PASSED") is True

    def test_tests_keyword_prefix_is_green(self):
        # "tests" plural prefix.
        assert _derive_ci_green("tests: PASSED (fr-user-login verification complete)") is True


# ---------------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------------


class TestBoundaryCases:
    def test_empty_evidence_is_not_green(self):
        assert _derive_ci_green("") is False

    def test_whitespace_evidence_is_not_green(self):
        assert _derive_ci_green("   ") is False

    def test_bypassed_with_pass_embedded_is_not_green(self):
        # Explicitly confirm word-boundary behaviour: BYPASSED embeds PASS but
        # the P in PASS is NOT at a word boundary within BYPASSED.
        assert _derive_ci_green("All gates BYPASSED") is False

    def test_n_passed_zero_does_not_match(self):
        # "0 passed" means 0 tests actually ran and passed — morally equivalent to
        # the "PASSED 0 of 3 suites" decoy (AC7). The counter pattern requires N ≥ 1
        # (pattern: \b[1-9]\d*\s+pass(ed)?\b).
        assert _derive_ci_green("0 passed") is False

    def test_multiline_pass_and_no_fail_is_green(self):
        # Multi-line evidence where passing line appears after setup lines.
        content = "setting up fixtures...\npytest tests/test_auth.py PASS\ncleaning up"
        assert _derive_ci_green(content) is True
