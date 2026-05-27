"""Tests for R9 changes to forward_replay_check.py.

R9/T22 introduced two changes:
1. Replaced E550 with E555 for SEMANTIC_COVERAGE_REGRESSION (line 93)
2. Added content staleness detection (W595) via _extract_content_tokens and
   _get_downstream_steps helpers.

These tests exercise the internal helpers directly (no git operations needed)
and verify error code assignments through the main check_forward_replay path.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from specdev_tools.core.errors import render_errors
from specdev_tools.validation.forward_replay_check import (
    _extract_content_tokens,
    _get_downstream_steps,
    check_forward_replay,
)


# ---------------------------------------------------------------------------
# 1. _extract_content_tokens
# ---------------------------------------------------------------------------

class TestExtractContentTokens(unittest.TestCase):
    """Tests for the _extract_content_tokens helper."""

    def _write_json(self, data: object) -> str:
        """Write *data* to a temp JSON file, return its path."""
        fd, path = tempfile.mkstemp(suffix=".json")
        import os
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(lambda: os.remove(path))
        return path

    def test_extracts_tokens_four_chars_or_more(self):
        """Tokens with 4+ lowercase chars should be extracted."""
        path = self._write_json({"description": "The user authentication module"})
        tokens = _extract_content_tokens(path)
        self.assertIn("user", tokens)
        self.assertIn("authentication", tokens)
        self.assertIn("module", tokens)

    def test_excludes_tokens_shorter_than_four_chars(self):
        """Tokens fewer than 4 chars should not appear."""
        path = self._write_json({"description": "an id is set"})
        tokens = _extract_content_tokens(path)
        # "an", "id", "is", "set" are all <= 3 chars
        self.assertNotIn("an", tokens)
        self.assertNotIn("id", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("set", tokens)

    def test_excludes_stopwords(self):
        """Common stopwords (4+ chars) must be filtered out."""
        path = self._write_json({
            "description": "this that with from have will been were they their"
        })
        tokens = _extract_content_tokens(path)
        stopwords = {"this", "that", "with", "from", "have", "will",
                     "been", "were", "they", "their"}
        for sw in stopwords:
            self.assertNotIn(sw, tokens, f"Stopword '{sw}' was not filtered")

    def test_excludes_json_schema_stopwords(self):
        """JSON/schema-related stopwords should be excluded."""
        path = self._write_json({"statement": "http https schema json"})
        tokens = _extract_content_tokens(path)
        for sw in ("http", "https", "schema", "json"):
            self.assertNotIn(sw, tokens)

    def test_extracts_kebab_case_tokens(self):
        """Kebab-case identifiers (4+ chars) should be extracted from free-text fields."""
        path = self._write_json({"description": "user-login-flow feature"})
        tokens = _extract_content_tokens(path)
        self.assertIn("user-login-flow", tokens)

    def test_extracts_tokens_from_nested_structures(self):
        """Tokens should be extracted from deeply nested dicts and lists."""
        path = self._write_json({
            "level1": {
                "level2": [
                    {"description": "deeply nested authentication"}
                ]
            }
        })
        tokens = _extract_content_tokens(path)
        self.assertIn("deeply", tokens)
        self.assertIn("nested", tokens)
        self.assertIn("authentication", tokens)

    def test_extracts_tokens_from_list_strings(self):
        """Free-text fields inside arrays of objects should be processed."""
        path = self._write_json({"items": [{"description": "important authentication"}]})
        tokens = _extract_content_tokens(path)
        self.assertIn("important", tokens)
        self.assertIn("authentication", tokens)

    def test_returns_empty_set_for_invalid_json(self):
        """Non-JSON files should return an empty set, not raise."""
        fd, path = tempfile.mkstemp(suffix=".json")
        import os
        with os.fdopen(fd, "w") as f:
            f.write("NOT VALID JSON {{{")
        self.addCleanup(lambda: os.remove(path))
        tokens = _extract_content_tokens(path)
        self.assertEqual(tokens, set())

    def test_returns_empty_set_for_missing_file(self):
        """Missing file should return an empty set, not raise."""
        tokens = _extract_content_tokens("/nonexistent/path/file.json")
        self.assertEqual(tokens, set())

    def test_lowercases_before_matching(self):
        """Input text is lowercased before token extraction."""
        path = self._write_json({"description": "UserAuthentication"})
        tokens = _extract_content_tokens(path)
        # "userauthentication" is the lowercased full word — the regex
        # matches [a-z][a-z0-9_-]{3,}, so the full lowercase string matches.
        self.assertIn("userauthentication", tokens)
        self.assertNotIn("UserAuthentication", tokens)

    def test_numeric_suffix_tokens_included(self):
        """Tokens with digits (e.g. 'milestone0001') should be included from free-text fields."""
        path = self._write_json({"rationale": "milestone0001 delivery"})
        tokens = _extract_content_tokens(path)
        self.assertIn("milestone0001", tokens)

    def test_underscore_tokens_included(self):
        """Tokens with underscores (e.g. 'user_name') should be included."""
        path = self._write_json({"notes": "user_name session_token"})
        tokens = _extract_content_tokens(path)
        self.assertIn("user_name", tokens)
        self.assertIn("session_token", tokens)

    def test_non_free_text_fields_not_scanned(self):
        """Fields like 'id', '$schema', 'owner' are NOT scanned for tokens."""
        path = self._write_json({
            "id": "authentication-module",
            "$schema": "https://example.com/schema",
            "owner": "engineering",
            "description": "placeholder content here",
        })
        tokens = _extract_content_tokens(path)
        self.assertNotIn("authentication-module", tokens)
        self.assertNotIn("engineering", tokens)
        self.assertIn("placeholder", tokens)
        self.assertIn("content", tokens)


# ---------------------------------------------------------------------------
# 2. _get_downstream_steps
# ---------------------------------------------------------------------------

class TestGetDownstreamSteps(unittest.TestCase):
    """Tests for the _get_downstream_steps helper."""

    def test_reads_downstream_consumers_correctly(self):
        """Should return the downstream list for a known step."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            tools_dir = Path(td) / "tools"
            tools_dir.mkdir()
            step_order = {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {
                    "00": ["01", "02"],
                    "01": ["02"],
                    "02": [],
                },
            }
            (tools_dir / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )
            result = _get_downstream_steps("00", spec_dir, repo_root=Path(td))
            self.assertEqual(result, ["01", "02"])

    def test_returns_empty_for_unknown_step(self):
        """A step not present in downstream_consumers returns []."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            tools_dir = Path(td) / "tools"
            tools_dir.mkdir()
            step_order = {
                "steps": ["00"],
                "downstream_consumers": {"00": ["01"]},
            }
            (tools_dir / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )
            result = _get_downstream_steps("99", spec_dir, repo_root=Path(td))
            self.assertEqual(result, [])

    def test_returns_empty_when_no_downstream_consumers_key(self):
        """If downstream_consumers is missing entirely, return []."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            tools_dir = Path(td) / "tools"
            tools_dir.mkdir()
            step_order = {"steps": ["00", "01"]}
            (tools_dir / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )
            result = _get_downstream_steps("00", spec_dir, repo_root=Path(td))
            self.assertEqual(result, [])

    def test_returns_empty_when_step_order_file_missing(self):
        """If step_order.json does not exist, return [] without error."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            # No tools/ directory at all
            result = _get_downstream_steps("00", spec_dir, repo_root=Path(td))
            self.assertEqual(result, [])

    def test_returns_empty_when_step_order_is_invalid_json(self):
        """If step_order.json is malformed, return [] without error."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            tools_dir = Path(td) / "tools"
            tools_dir.mkdir()
            (tools_dir / "step_order.json").write_text("NOT JSON", encoding="utf-8")
            result = _get_downstream_steps("00", spec_dir, repo_root=Path(td))
            self.assertEqual(result, [])

    def test_path_resolution_uses_spec_dir_parent(self):
        """_get_downstream_steps expects step_order.json at spec_dir/../tools/."""
        with tempfile.TemporaryDirectory() as td:
            # Non-standard nesting: project/my_specs/ with project/tools/
            project = Path(td) / "project"
            project.mkdir()
            spec_dir = project / "my_specs"
            spec_dir.mkdir()
            tools_dir = project / "tools"
            tools_dir.mkdir()
            step_order = {
                "steps": ["04"],
                "downstream_consumers": {"04": ["05", "06"]},
            }
            (tools_dir / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )
            result = _get_downstream_steps("04", spec_dir)
            self.assertEqual(result, ["05", "06"])

    def test_submodule_deployment_repo_root_differs_from_spec_parent(self):
        """In submodule deployments, repo_root (toolkit) differs from spec_dir.parent.

        Layout:
            project/toolkit/tools/step_order.json   (repo_root = project/toolkit)
            project/spec/                            (spec_dir = project/spec)

        _get_downstream_steps with repo_root should find step_order.json in the
        toolkit rather than falling back to spec_dir.parent (which is project/).
        """
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            project.mkdir()

            # Toolkit lives at project/toolkit/
            toolkit = project / "toolkit"
            toolkit.mkdir()
            toolkit_tools = toolkit / "tools"
            toolkit_tools.mkdir()
            step_order = {
                "steps": ["03", "04", "05"],
                "downstream_consumers": {
                    "03": ["04", "05"],
                    "04": ["05"],
                    "05": [],
                },
            }
            (toolkit_tools / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )

            # Spec lives at project/spec/ (NOT inside toolkit)
            spec_dir = project / "spec"
            spec_dir.mkdir()

            # Without repo_root, it would look at project/tools/ (spec_dir.parent)
            # which does not exist, and return [].
            result_without = _get_downstream_steps("03", spec_dir)
            self.assertEqual(result_without, [], "Without repo_root should fall back to spec_dir.parent and fail")

            # With repo_root pointing to toolkit, it should find step_order.json.
            result_with = _get_downstream_steps("03", spec_dir, repo_root=toolkit)
            self.assertEqual(result_with, ["04", "05"])


# ---------------------------------------------------------------------------
# 3. E555 error code for SEMANTIC_COVERAGE_REGRESSION
# ---------------------------------------------------------------------------

class TestE555SemanticCoverageRegression(unittest.TestCase):
    """Verify that ID regressions use E555, not the old E550."""

    def test_id_regression_uses_e555(self):
        """When an ID is dropped, the error code must be E555."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text(
                '{"id": "kept-id"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(
                    ["spec/00_charter.json", "spec/01_capabilities.json"],
                    None,
                ),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "dropped-id"}'
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            regression_errs = [e for e in render_errors(errs) if "SEMANTIC_COVERAGE_REGRESSION" in e]
            self.assertTrue(len(regression_errs) > 0, "Expected at least one regression error")
            for err in regression_errs:
                self.assertTrue(
                    err.startswith("E555"),
                    f"Expected E555 prefix, got: {err}",
                )
                self.assertNotIn("E550", err)

    def test_id_regression_includes_dropped_ids(self):
        """The E555 message must list the specific dropped IDs."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["04"]}), encoding="utf-8"
            )
            (root / "spec" / "04_frs.json").write_text(
                '{"id": "fr-remaining"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = json.dumps({
                        "id": "fr-remaining",
                        "extra_ref": "fr-alpha",
                        "another_ref": "fr-beta",
                    })
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            regression_errs = [e for e in render_errors(errs) if "E555" in e]
            self.assertTrue(len(regression_errs) > 0)
            combined = " ".join(regression_errs)
            self.assertIn("fr-alpha", combined)
            self.assertIn("fr-beta", combined)


# ---------------------------------------------------------------------------
# 4. E550 still used for FORWARD_REPLAY_MISSING (unchanged)
# ---------------------------------------------------------------------------

class TestE550ForwardReplayMissing(unittest.TestCase):
    """Verify that E550 is still used for forward-replay structural errors."""

    def test_missing_downstream_still_uses_e550(self):
        """E550 FORWARD_REPLAY_MISSING should still fire for structural gaps."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}), encoding="utf-8"
            )
            (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "02_system_sketch.json").write_text("{}", encoding="utf-8")

            # Changed 00 but not 01/02
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/00_charter.json"], None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")

            missing_errs = [e for e in render_errors(errs) if "FORWARD_REPLAY_MISSING" in e]
            self.assertTrue(len(missing_errs) > 0)
            for err in missing_errs:
                self.assertTrue(
                    err.startswith("E550"),
                    f"FORWARD_REPLAY_MISSING should use E550, got: {err}",
                )

    def test_diff_failure_still_uses_e550(self):
        """Git diff failures should still produce E550."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any(e.startswith("E550") for e in render_errors(errs)))

    def test_unknown_step_still_uses_e550(self):
        """Unknown steps in diff should produce E550."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/99_future.json"], None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            unknown_errs = [e for e in render_errors(errs) if "unknown_step_in_diff" in e]
            self.assertTrue(len(unknown_errs) > 0)
            for err in unknown_errs:
                self.assertTrue(err.startswith("E550"))


# ---------------------------------------------------------------------------
# 5. W595 CONTENT_STALENESS (bonus coverage for the staleness path)
# ---------------------------------------------------------------------------

class TestW595ContentStaleness(unittest.TestCase):
    """Verify that the W595 staleness detection path works end-to-end."""

    def setUp(self):
        from specdev_tools.core.config import reset_config
        reset_config()

    def tearDown(self):
        from specdev_tools.core.config import reset_config
        reset_config()

    def test_staleness_warning_format(self):
        """W595 should include upstream, downstream, and new_token_count."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()

            # Step order with downstream_consumers so staleness can find them
            step_order = {
                "steps": ["04", "05"],
                "downstream_consumers": {"04": ["05"]},
            }
            (root / "tools" / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )

            # New version of 04 has many new tokens
            new_04 = {
                "features": [
                    {"id": "fr-login", "description": "authentication endpoint handles sessions"},
                    {"id": "fr-signup", "description": "registration creates verified accounts"},
                    {"id": "fr-reset", "description": "password recovery workflow sends email notifications"},
                ]
            }
            # Old version had none of those descriptive tokens
            old_04 = {
                "features": [
                    {"id": "fr-login"},
                    {"id": "fr-signup"},
                    {"id": "fr-reset"},
                ]
            }
            (root / "spec" / "04_frs.json").write_text(
                json.dumps(new_04), encoding="utf-8"
            )
            # Downstream 05 has no overlap with the new tokens
            (root / "spec" / "05_apis.json").write_text(
                json.dumps({"endpoints": []}), encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json", "spec/05_apis.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = json.dumps(old_04)
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            staleness_errs = [e for e in render_errors(errs) if "W595" in e]
            self.assertTrue(
                len(staleness_errs) > 0,
                f"Expected W595 staleness warning, got errors: {errs}",
            )
            for err in staleness_errs:
                self.assertIn("CONTENT_STALENESS", err)
                self.assertIn("upstream=04", err)
                self.assertIn("downstream=05", err)
                self.assertIn("new_tokens=", err)
                self.assertIn("reflected=0", err)

    def test_no_staleness_when_downstream_reflects_new_tokens(self):
        """No W595 when the downstream step already contains added tokens."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()

            step_order = {
                "steps": ["04", "05"],
                "downstream_consumers": {"04": ["05"]},
            }
            (root / "tools" / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )

            new_04 = {
                "features": [{"id": "fr-login", "description": "authentication endpoint"}]
            }
            old_04 = {"features": [{"id": "fr-login"}]}
            (root / "spec" / "04_frs.json").write_text(
                json.dumps(new_04), encoding="utf-8"
            )
            # Downstream 05 already contains "authentication" and "endpoint"
            (root / "spec" / "05_apis.json").write_text(
                json.dumps({"description": "authentication endpoint integration"}),
                encoding="utf-8",
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json", "spec/05_apis.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = json.dumps(old_04)
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            staleness_errs = [e for e in render_errors(errs) if "W595" in e]
            self.assertEqual(
                staleness_errs, [],
                f"Expected no W595 when downstream reflects tokens, got: {staleness_errs}",
            )

    def test_no_staleness_when_fewer_than_three_new_tokens(self):
        """W595 requires at least 3 new tokens to fire (threshold in code)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()

            step_order = {
                "steps": ["04", "05"],
                "downstream_consumers": {"04": ["05"]},
            }
            (root / "tools" / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )

            # Only 2 new tokens (below the threshold of 3)
            new_04 = {"description": "login endpoint"}
            old_04 = {"description": "login"}
            (root / "spec" / "04_frs.json").write_text(
                json.dumps(new_04), encoding="utf-8"
            )
            (root / "spec" / "05_apis.json").write_text("{}", encoding="utf-8")

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json", "spec/05_apis.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = json.dumps(old_04)
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            staleness_errs = [e for e in render_errors(errs) if "W595" in e]
            self.assertEqual(
                staleness_errs, [],
                f"Expected no W595 when < 3 new tokens, got: {staleness_errs}",
            )


    def test_staleness_threshold_env_var_raises_bar(self):
        """SPECDEV_STALENESS_THRESHOLD=5 means 4 new tokens should NOT fire W595."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()

            step_order = {
                "steps": ["04", "05"],
                "downstream_consumers": {"04": ["05"]},
            }
            (root / "tools" / "step_order.json").write_text(
                json.dumps(step_order), encoding="utf-8"
            )

            # 4 new tokens (below SPECDEV_STALENESS_THRESHOLD=5)
            new_04 = {
                "features": [
                    {"description": "authentication endpoint handles sessions"}
                ]
            }
            old_04 = {"features": []}
            (root / "spec" / "04_frs.json").write_text(
                json.dumps(new_04), encoding="utf-8"
            )
            (root / "spec" / "05_apis.json").write_text("{}", encoding="utf-8")

            with patch.dict(os.environ, {"SPECDEV_STALENESS_THRESHOLD": "5"}):
                with patch(
                    "specdev_tools.validation.forward_replay_check._changed_files",
                    return_value=(["spec/04_frs.json", "spec/05_apis.json"], None),
                ):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value.returncode = 0
                        mock_run.return_value.stdout = json.dumps(old_04)
                        mock_run.return_value.stderr = ""
                        errs = check_forward_replay(str(root), base_ref="origin/main")

            staleness_errs = [e for e in render_errors(errs) if "W595" in e]
            self.assertEqual(
                staleness_errs, [],
                f"Expected no W595 with threshold=5 and 4 tokens, got: {staleness_errs}",
            )


if __name__ == "__main__":
    unittest.main()
