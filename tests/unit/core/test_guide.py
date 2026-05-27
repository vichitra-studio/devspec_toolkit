"""Tests for the `specdev guide` subcommand and the guide loader module."""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from specdev_tools.core.guide import format_guide_text, load_guides, lookup_guide


# ---------------------------------------------------------------------------
# Guide loader unit tests
# ---------------------------------------------------------------------------

class TestLoadGuides:
    """Tests for load_guides()."""

    def test_loads_all_bundled_yaml_files(self) -> None:
        guides = load_guides()
        assert len(guides) >= 5, "Expected E110, E110-UNKNOWN_CANONICAL_ID, E530, E530-INVENTED_ENUM_OR_ID, E530-LINKED_TEST_FILE_NOT_FOUND"

    def test_e110_key_present(self) -> None:
        guides = load_guides()
        assert "E110" in guides

    def test_e530_invented_key_present(self) -> None:
        guides = load_guides()
        assert "E530-INVENTED_ENUM_OR_ID" in guides

    def test_e530_linked_key_present(self) -> None:
        guides = load_guides()
        assert "E530-LINKED_TEST_FILE_NOT_FOUND" in guides

    def test_e530_base_key_present(self) -> None:
        guides = load_guides()
        assert "E530" in guides

    def test_missing_directory_returns_empty(self, tmp_path) -> None:
        guides = load_guides(guides_dir=tmp_path / "nonexistent")
        assert guides == {}

    def test_invalid_yaml_file_is_skipped(self, tmp_path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(": invalid: yaml: {{{{", encoding="utf-8")
        # Should not raise; bad file is silently skipped
        guides = load_guides(guides_dir=tmp_path)
        assert "bad" not in guides

    def test_yaml_without_code_key_is_skipped(self, tmp_path) -> None:
        no_code = tmp_path / "nocode.yaml"
        no_code.write_text("title: No code key\nresolution: nothing\n", encoding="utf-8")
        guides = load_guides(guides_dir=tmp_path)
        assert guides == {}


class TestLookupGuide:
    """Tests for lookup_guide()."""

    def test_bare_code_e110_found(self) -> None:
        entry = lookup_guide("E110")
        assert entry is not None
        assert entry["code"] == "E110"

    def test_bare_code_e530_found(self) -> None:
        entry = lookup_guide("E530")
        assert entry is not None
        assert entry["code"] == "E530"
        assert entry.get("subcode") is None  # base catch-all entry, not a subcoded one

    def test_subcoded_e530_invented_found(self) -> None:
        entry = lookup_guide("E530-INVENTED_ENUM_OR_ID")
        assert entry is not None
        assert entry.get("subcode") == "INVENTED_ENUM_OR_ID"

    def test_subcoded_e530_linked_found(self) -> None:
        entry = lookup_guide("E530-LINKED_TEST_FILE_NOT_FOUND")
        assert entry is not None
        assert entry.get("subcode") == "LINKED_TEST_FILE_NOT_FOUND"

    def test_unknown_code_returns_none(self) -> None:
        entry = lookup_guide("EXXXUNKNOWN")
        assert entry is None

    def test_unknown_subcoded_falls_back_to_base(self) -> None:
        # E530-NONEXISTENT_SUBCODE: no exact match → falls back to bare "E530".
        # E530.yaml (base catch-all) ships with the package, so entry is non-None.
        entry = lookup_guide("E530-NONEXISTENT_SUBCODE")
        assert entry is not None
        assert entry["code"] == "E530"
        assert entry.get("subcode") is None  # base entry has no subcode field

    def test_lookup_uses_provided_guides_dict(self, tmp_path) -> None:
        guide_file = tmp_path / "E999.yaml"
        guide_file.write_text(
            "code: E999\ntitle: Test guide\ntrigger: test\nresolution: fix it\n",
            encoding="utf-8",
        )
        guides = load_guides(guides_dir=tmp_path)
        entry = lookup_guide("E999", guides)
        assert entry is not None
        assert entry["title"] == "Test guide"


class TestFormatGuideText:
    """Tests for format_guide_text()."""

    def test_returns_non_empty_string(self) -> None:
        entry = lookup_guide("E110")
        assert entry is not None
        text = format_guide_text(entry)
        assert isinstance(text, str)
        assert len(text.strip()) > 0

    def test_contains_code_in_header(self) -> None:
        entry = lookup_guide("E110")
        assert entry is not None
        text = format_guide_text(entry)
        assert "E110" in text

    def test_code_arg_used_as_header(self) -> None:
        # When code_arg is provided, the header must match the caller's invocation.
        entry = lookup_guide("E110")
        assert entry is not None
        text_bare = format_guide_text(entry, code_arg="E110")
        assert text_bare.startswith("=== E110:")
        # Subcoded form should also use the caller's string verbatim.
        entry_sub = lookup_guide("E110-UNKNOWN_CANONICAL_ID")
        assert entry_sub is not None
        text_sub = format_guide_text(entry_sub, code_arg="E110-UNKNOWN_CANONICAL_ID")
        assert text_sub.startswith("=== E110-UNKNOWN_CANONICAL_ID:")

    def test_contains_trigger_section(self) -> None:
        entry = lookup_guide("E110")
        assert entry is not None
        text = format_guide_text(entry)
        assert "Trigger:" in text

    def test_contains_resolution_section(self) -> None:
        entry = lookup_guide("E110")
        assert entry is not None
        text = format_guide_text(entry)
        assert "Resolution:" in text

    def test_e530_invented_text_non_empty(self) -> None:
        entry = lookup_guide("E530-INVENTED_ENUM_OR_ID")
        assert entry is not None
        text = format_guide_text(entry)
        assert len(text.strip()) > 0

    def test_e530_linked_text_non_empty(self) -> None:
        entry = lookup_guide("E530-LINKED_TEST_FILE_NOT_FOUND")
        assert entry is not None
        text = format_guide_text(entry)
        assert len(text.strip()) > 0


# ---------------------------------------------------------------------------
# CLI dispatch tests (via sys.argv patching)
# ---------------------------------------------------------------------------

def _run_cli(*argv: str) -> tuple[int, str, str]:
    """Invoke cli.main() with the given args; return (exit_code, stdout, stderr)."""
    from specdev_tools import cli

    captured_out = StringIO()
    captured_err = StringIO()
    exit_code = 0
    with patch("sys.argv", ["specdev"] + list(argv)):
        with patch("sys.stdout", captured_out):
            with patch("sys.stderr", captured_err):
                try:
                    cli.main()
                except SystemExit as exc:
                    exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, captured_out.getvalue(), captured_err.getvalue()


class TestGuideCLI:
    """CLI dispatch tests for `specdev guide`."""

    def test_e110_human_output_non_empty(self) -> None:
        code, out, _ = _run_cli("guide", "E110")
        assert code == 0
        assert len(out.strip()) > 0

    def test_e530_invented_human_output_non_empty(self) -> None:
        code, out, _ = _run_cli("guide", "E530-INVENTED_ENUM_OR_ID")
        assert code == 0
        assert len(out.strip()) > 0

    def test_e530_linked_human_output_non_empty(self) -> None:
        code, out, _ = _run_cli("guide", "E530-LINKED_TEST_FILE_NOT_FOUND")
        assert code == 0
        assert len(out.strip()) > 0

    def test_unknown_code_exits_nonzero(self) -> None:
        code, _, _ = _run_cli("guide", "EXXXUNKNOWN")
        assert code != 0

    def test_unknown_code_signals_no_remediation_guide(self) -> None:
        _, out, err = _run_cli("guide", "EXXXUNKNOWN")
        combined = out + err
        assert "no remediation guide" in combined

    def test_json_flag_returns_valid_json(self) -> None:
        code, out, _ = _run_cli("guide", "E110", "--json")
        assert code == 0
        data = json.loads(out)
        assert "code" in data
        assert data["code"] == "E110"
        assert "guide" in data

    def test_json_flag_guide_key_is_dict(self) -> None:
        _, out, _ = _run_cli("guide", "E530-INVENTED_ENUM_OR_ID", "--json")
        data = json.loads(out)
        assert isinstance(data["guide"], dict)

    def test_json_flag_unknown_code_has_error_key(self) -> None:
        code, out, _ = _run_cli("guide", "EXXXUNKNOWN", "--json")
        assert code != 0
        data = json.loads(out)
        assert data["code"] == "EXXXUNKNOWN"
        assert data.get("error") == "no remediation guide"

    def test_e530_base_code_human_output_non_empty(self) -> None:
        code, out, _ = _run_cli("guide", "E530")
        assert code == 0
        assert len(out.strip()) > 0

    def test_e530_base_code_header_matches_input(self) -> None:
        _, out, _ = _run_cli("guide", "E530")
        assert out.startswith("=== E530:")

    def test_e110_header_matches_input(self) -> None:
        # CLI must use the caller's code string in the header, not the subcode form.
        _, out, _ = _run_cli("guide", "E110")
        assert out.startswith("=== E110:")
        assert not out.startswith("=== E110-UNKNOWN_CANONICAL_ID:")

    def test_repo_root_flag_accepted(self) -> None:
        # --repo-root should be accepted without error even though it's not
        # used for guide resolution
        code, out, _ = _run_cli("guide", "E110", "--repo-root", ".")
        assert code == 0
        assert len(out.strip()) > 0
