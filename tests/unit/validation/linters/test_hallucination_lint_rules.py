"""Tests for R9 content derivation check in hallucination_lint.py.

Covers _check_content_derivation (W594 low overlap, W590 missing upstream),
_extract_free_text_tokens, _tokenize, and edge cases around threshold
configurability and steps with no upstream dependencies.
"""

import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.hallucination_lint import (
    _check_content_derivation,
    _extract_free_text_tokens,
    DERIVATION_STOPWORDS,
)
from specdev_tools.validation.linter_utils import tokenize_free_text
from specdev_tools.core.errors import render_errors

# Local alias replacing the removed backward-compat _tokenize from hallucination_lint
_tokenize = lambda text: tokenize_free_text(text, stopwords=DERIVATION_STOPWORDS)


def _write_step_order(root: Path, deps: dict[str, list[str]]) -> None:
    """Write a minimal step_order.json with given allowed_upstream_dependencies."""
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "step_order.json").write_text(
        json.dumps({
            "version": "1.0.0",
            "policy": {"mode": "strict_waterfall"},
            "steps": sorted(deps.keys()),
            "allowed_upstream_dependencies": deps,
        }),
        encoding="utf-8",
    )


def _write_spec(spec_dir: Path, filename: str, data: dict) -> None:
    """Write a JSON spec artifact into spec_dir."""
    spec_dir.mkdir(exist_ok=True)
    (spec_dir / filename).write_text(json.dumps(data), encoding="utf-8")


class TestTokenize(unittest.TestCase):
    """Tests for the _tokenize helper."""

    def test_extracts_4plus_char_words(self):
        tokens = _tokenize("The user authentication module handles login flow")
        self.assertIn("user", tokens)
        self.assertIn("authentication", tokens)
        self.assertIn("module", tokens)
        self.assertIn("handles", tokens)
        self.assertIn("login", tokens)
        self.assertIn("flow", tokens)  # 4 chars exactly

    def test_excludes_short_words(self):
        tokens = _tokenize("a is of to in the")
        self.assertEqual(tokens, set())

    def test_excludes_3char_words(self):
        tokens = _tokenize("use the api for fun")
        # "use", "the", "api", "for", "fun" are all 3 chars or less
        self.assertEqual(tokens, set())

    def test_excludes_stopwords(self):
        tokens = _tokenize("this should have been true false null schema json")
        # all of these are in _DERIVATION_STOPWORDS
        self.assertEqual(tokens, set())

    def test_case_insensitive(self):
        tokens = _tokenize("Authentication LOGIN")
        self.assertIn("authentication", tokens)
        self.assertIn("login", tokens)

    def test_hyphenated_and_underscored_tokens(self):
        tokens = _tokenize("user-login session_token")
        self.assertIn("user-login", tokens)
        self.assertIn("session_token", tokens)

    def test_mixed_alphanum(self):
        tokens = _tokenize("oauth2 error404")
        # "oauth2" starts with 'o' (alpha) and is 6 chars -> included
        self.assertIn("oauth2", tokens)
        # "error404" starts with 'e' (alpha) -> included
        self.assertIn("error404", tokens)

    def test_tokens_starting_with_digit_excluded(self):
        # regex requires [a-z] start
        tokens = _tokenize("123invalid 4ever")
        self.assertNotIn("123invalid", tokens)
        self.assertNotIn("4ever", tokens)


class TestExtractFreeTextTokens(unittest.TestCase):
    """Tests for _extract_free_text_tokens."""

    def test_extracts_from_description(self):
        data = {"description": "The authentication module verifies credentials"}
        tokens = _extract_free_text_tokens(data)
        self.assertIn("authentication", tokens)
        self.assertIn("module", tokens)
        self.assertIn("verifies", tokens)
        self.assertIn("credentials", tokens)

    def test_extracts_from_multiple_fields(self):
        data = {
            "description": "handles authentication",
            "rationale": "security compliance requirement",
            "statement": "system shall validate tokens",
        }
        tokens = _extract_free_text_tokens(data)
        self.assertIn("authentication", tokens)
        self.assertIn("security", tokens)
        self.assertIn("compliance", tokens)
        self.assertIn("requirement", tokens)
        self.assertIn("system", tokens)
        self.assertIn("validate", tokens)
        self.assertIn("tokens", tokens)

    def test_recurses_into_nested_dicts(self):
        data = {
            "capabilities": [
                {"description": "manages database connections efficiently"}
            ]
        }
        tokens = _extract_free_text_tokens(data)
        self.assertIn("manages", tokens)
        self.assertIn("database", tokens)
        self.assertIn("connections", tokens)
        self.assertIn("efficiently", tokens)

    def test_ignores_non_free_text_fields(self):
        data = {"id": "fr-login", "name": "Login Feature", "version": "production ready"}
        tokens = _extract_free_text_tokens(data)
        # "id", "name", "version" are not in _DERIVATION_FREE_TEXT_FIELDS
        self.assertEqual(tokens, set())

    def test_empty_object_yields_no_tokens(self):
        self.assertEqual(_extract_free_text_tokens({}), set())
        self.assertEqual(_extract_free_text_tokens([]), set())

    def test_handles_non_string_values(self):
        data = {"description": 42, "rationale": None, "statement": True}
        self.assertEqual(_extract_free_text_tokens(data), set())


class TestCheckContentDerivation(unittest.TestCase):
    """Tests for _check_content_derivation."""

    def test_sufficient_overlap_produces_no_w594(self):
        """Downstream with >= threshold token overlap passes cleanly."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            # Shared vocabulary: enough tokens to pass threshold=5
            shared_text = (
                "authentication module handles credential validation "
                "using secure token exchange protocol"
            )

            _write_spec(spec_dir, "00_charter.json", {
                "description": shared_text,
            })
            _write_spec(spec_dir, "01_capabilities.json", {
                "description": shared_text + " plus extra capability details",
            })

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "01_capabilities.json",
                json.loads((spec_dir / "01_capabilities.json").read_text()),
                str(spec_dir),
                str(root),
            )

            w594_errors = [e for e in render_errors(errs) if "W594" in e]
            self.assertEqual(w594_errors, [], f"Unexpected W594 errors: {w594_errors}")

    def test_low_overlap_emits_w594(self):
        """Downstream with < threshold overlap triggers W594."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            # Upstream: completely different vocabulary
            _write_spec(spec_dir, "00_charter.json", {
                "description": "elephant giraffe rhinoceros hippopotamus zebra",
            })
            # Downstream: no overlap with upstream
            downstream_data = {
                "description": "spacecraft navigation algorithm trajectory computation",
            }
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            w594_errors = [e for e in render_errors(errs) if "W594" in e]
            self.assertEqual(len(w594_errors), 1)
            self.assertIn("CONTENT_DERIVATION_LOW_OVERLAP", w594_errors[0])
            self.assertIn("overlap=0", w594_errors[0])

    def test_missing_upstream_file_emits_w590(self):
        """When upstream artifact file is absent, W590 is emitted and no crash."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            # Only step 01 exists, step 00 is missing
            downstream_data = {
                "description": "authentication module handles credential validation",
            }
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            w590_errors = [e for e in render_errors(errs) if "W590" in e]
            self.assertEqual(len(w590_errors), 1)
            self.assertIn("CROSS_STEP_UPSTREAM_MISSING", w590_errors[0])
            self.assertIn("00", w590_errors[0])

    def test_missing_upstream_with_other_upstream_present(self):
        """If one upstream is missing but another provides enough overlap, no W594."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            shared_text = (
                "authentication module handles credential validation "
                "using secure token exchange protocol"
            )

            # Step 00 exists with shared vocabulary
            _write_spec(spec_dir, "00_charter.json", {
                "description": shared_text,
            })
            # Step 01 is missing (not written)

            downstream_data = {
                "description": shared_text + " plus downstream details",
            }
            _write_spec(spec_dir, "02_sketch.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
                "02": ["00", "01"],
            })

            errs = _check_content_derivation(
                "02_sketch.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            # W590 for missing step 01
            w590_errors = [e for e in render_errors(errs) if "W590" in e]
            self.assertEqual(len(w590_errors), 1)
            self.assertIn("01", w590_errors[0])

            # No W594 because step 00 provides enough overlap
            w594_errors = [e for e in render_errors(errs) if "W594" in e]
            self.assertEqual(w594_errors, [])

    def test_threshold_is_configurable(self):
        """Custom threshold changes when W594 fires."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            # Exactly 3 shared tokens: "authentication", "module", "handles"
            _write_spec(spec_dir, "00_charter.json", {
                "description": "authentication module handles",
            })
            downstream_data = {
                "description": "authentication module handles spacecraft navigation",
            }
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            # threshold=3 -> exactly meets threshold -> no W594
            errs_pass = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
                threshold=3,
            )
            w594_pass = [e for e in render_errors(errs_pass) if "W594" in e]
            self.assertEqual(w594_pass, [])

            # threshold=4 -> overlap=3 < 4 -> W594
            errs_fail = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
                threshold=4,
            )
            w594_fail = [e for e in render_errors(errs_fail) if "W594" in e]
            self.assertEqual(len(w594_fail), 1)
            self.assertIn("overlap=3", w594_fail[0])
            self.assertIn("threshold=4", w594_fail[0])

    def test_step_00_no_upstream_no_w594(self):
        """Step 00 has no upstream dependencies, so no derivation check fires."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            charter_data = {
                "description": "spacecraft navigation algorithm trajectory computation",
            }
            _write_spec(spec_dir, "00_charter.json", charter_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "00_charter.json",
                charter_data,
                str(spec_dir),
                str(root),
            )

            self.assertEqual(errs, [])

    def test_missing_step_order_file_returns_empty(self):
        """If step_order.json is absent, no errors are produced."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            downstream_data = {"description": "some content here for testing"}
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)
            # No tools/step_order.json created

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            self.assertEqual(errs, [])

    def test_non_step_filename_returns_empty(self):
        """Files not matching NN_ pattern produce no derivation errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            _write_step_order(root, {"00": [], "01": ["00"]})
            data = {"description": "random content without upstream derivation"}

            errs = _check_content_derivation(
                "custom_file.json",
                data,
                str(spec_dir),
                str(root),
            )

            self.assertEqual(errs, [])

    def test_downstream_with_no_free_text_returns_empty(self):
        """If downstream artifact has no free-text fields, derivation is skipped."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            _write_spec(spec_dir, "00_charter.json", {
                "description": "authentication module handles credential validation",
            })
            # Downstream has no free-text fields
            downstream_data = {"id": "cap-1", "version": "1.0.0"}
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            self.assertEqual(errs, [])

    def test_all_upstreams_missing_no_w594(self):
        """If all upstream artifacts are missing, W590 for each but no W594."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            downstream_data = {
                "description": "authentication module handles credential validation securely",
            }
            _write_spec(spec_dir, "02_sketch.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
                "02": ["00", "01"],
            })

            errs = _check_content_derivation(
                "02_sketch.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            w590_errors = [e for e in render_errors(errs) if "W590" in e]
            w594_errors = [e for e in render_errors(errs) if "W594" in e]
            # Both step 00 and 01 are missing
            self.assertEqual(len(w590_errors), 2)
            # No W594 because upstream_tokens is empty -> early return
            self.assertEqual(w594_errors, [])

    def test_malformed_step_order_json_returns_empty(self):
        """If step_order.json is invalid JSON, no errors are produced."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()
            tools = root / "tools"
            tools.mkdir()
            (tools / "step_order.json").write_text("{bad json", encoding="utf-8")

            downstream_data = {"description": "some content for testing purposes here"}
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            self.assertEqual(errs, [])

    def test_step_with_suffix_letter_recognized(self):
        """Steps like 02a, 13a, 16c are correctly parsed and checked."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            _write_spec(spec_dir, "02_sketch.json", {
                "description": "system architecture design component interaction details",
            })
            downstream_data = {
                "description": "completely unrelated spacecraft propulsion engineering",
            }
            _write_spec(spec_dir, "02a_glossary.json", downstream_data)

            _write_step_order(root, {
                "02": [],
                "02a": ["02"],
            })

            errs = _check_content_derivation(
                "02a_glossary.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            w594_errors = [e for e in render_errors(errs) if "W594" in e]
            self.assertEqual(len(w594_errors), 1)
            self.assertIn("02a_glossary.json", w594_errors[0])

    def test_w594_error_message_includes_token_counts(self):
        """W594 message includes overlap count, threshold, downstream and upstream token counts."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            _write_spec(spec_dir, "00_charter.json", {
                "description": "elephant giraffe rhinoceros hippopotamus zebra antelope",
            })
            downstream_data = {
                "description": "spacecraft navigation algorithm trajectory computation orbital",
            }
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            w594_errors = [e for e in render_errors(errs) if "W594" in e]
            self.assertEqual(len(w594_errors), 1)
            msg = w594_errors[0]
            self.assertIn("overlap=", msg)
            self.assertIn("threshold=", msg)
            self.assertIn("downstream has", msg)
            self.assertIn("upstream has", msg)
            self.assertIn("tokens", msg)

    def test_upstream_with_invalid_json_skipped_gracefully(self):
        """If upstream artifact has invalid JSON, it is skipped (treated as missing)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_dir = root / "spec"
            spec_dir.mkdir()

            # Write invalid JSON for upstream
            (spec_dir / "00_charter.json").write_text("{bad json", encoding="utf-8")

            downstream_data = {
                "description": "authentication module credential validation security",
            }
            _write_spec(spec_dir, "01_capabilities.json", downstream_data)

            _write_step_order(root, {
                "00": [],
                "01": ["00"],
            })

            errs = _check_content_derivation(
                "01_capabilities.json",
                downstream_data,
                str(spec_dir),
                str(root),
            )

            # The invalid upstream is treated as missing -> W590
            w590_errors = [e for e in render_errors(errs) if "W590" in e]
            self.assertEqual(len(w590_errors), 1)
            self.assertIn("00", w590_errors[0])


if __name__ == "__main__":
    unittest.main()
