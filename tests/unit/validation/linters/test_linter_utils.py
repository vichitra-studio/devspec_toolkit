"""Tests for specdev_tools.validation.linter_utils — shared linter helpers.

Created by FIX-044 (Batch 5).
"""
from __future__ import annotations

from specdev_tools.validation.linter_utils import (
    CONTENT_STOPWORDS,
    DERIVATION_STOPWORDS,
    collect_ids_and_refs,
    extract_command_string,
    is_reference_context,
    iter_json,
    tokenize_free_text,
)


class TestExtractCommandString:
    """Tests for extract_command_string."""

    def test_string_input(self):
        assert extract_command_string("pytest -q") == "pytest -q"

    def test_dict_with_string_command(self):
        assert extract_command_string({"command": "jq -e '.'"}) == "jq -e '.'"

    def test_dict_with_non_string_command(self):
        assert extract_command_string({"command": 42}) == ""

    def test_dict_without_command(self):
        assert extract_command_string({"command_ref": {"id": "cn:project:command:jq"}}) == ""

    def test_dict_with_command_and_command_ref(self):
        # Object-form may carry both fields; helper returns the literal command string
        # and lets ref-resolution stay the consumer's concern (linter / integrity check).
        entry = {"command": "jq -e '.'", "command_ref": {"id": "cn:project:command:jq"}}
        assert extract_command_string(entry) == "jq -e '.'"

    def test_empty_string_input(self):
        # Returned verbatim; callers .strip() before equality match in step_16
        assert extract_command_string("") == ""

    def test_whitespace_only_command_returned_verbatim(self):
        assert extract_command_string("   ") == "   "
        assert extract_command_string({"command": "   "}) == "   "

    def test_non_string_non_dict_input(self):
        assert extract_command_string(None) == ""
        assert extract_command_string(123) == ""
        assert extract_command_string(["pytest"]) == ""


# ---------------------------------------------------------------------------
# Stopword constants
# ---------------------------------------------------------------------------

class TestStopwords:
    """Verify stopword sets contain expected members and are frozensets."""

    def test_derivation_is_frozenset(self):
        assert isinstance(DERIVATION_STOPWORDS, frozenset)

    def test_content_is_frozenset(self):
        assert isinstance(CONTENT_STOPWORDS, frozenset)

    def test_common_stopwords_present(self):
        for word in ("that", "this", "with", "from", "true", "false"):
            assert word in DERIVATION_STOPWORDS
            assert word in CONTENT_STOPWORDS

    def test_json_schema_terms_present(self):
        for word in ("http", "https", "schema", "json"):
            assert word in DERIVATION_STOPWORDS


# ---------------------------------------------------------------------------
# tokenize_free_text
# ---------------------------------------------------------------------------

class TestTokenizeFreeText:
    """Tests for tokenize_free_text."""

    def test_extracts_long_words(self):
        result = tokenize_free_text("The authentication module handles user login")
        assert "authentication" in result
        assert "module" in result
        assert "handles" in result
        assert "login" in result

    def test_filters_short_words(self):
        result = tokenize_free_text("The cat sat on a mat")
        # All words are <= 3 chars or stopwords
        assert result == set()

    def test_removes_stopwords(self):
        result = tokenize_free_text("this schema will have been were")
        assert result == set()

    def test_custom_stopwords(self):
        custom = frozenset({"login"})
        result = tokenize_free_text("user login page", stopwords=custom)
        assert "login" not in result
        assert "user" in result
        assert "page" in result

    def test_empty_string(self):
        assert tokenize_free_text("") == set()

    def test_lowercases(self):
        result = tokenize_free_text("Authentication Module")
        assert "authentication" in result
        assert "module" in result

    def test_ignores_numbers_only(self):
        result = tokenize_free_text("12345 67890")
        # Pattern requires starting with [a-z]
        assert result == set()


# ---------------------------------------------------------------------------
# iter_json
# ---------------------------------------------------------------------------

class TestIterJson:
    """Tests for iter_json."""

    def test_finds_json_files(self, tmp_path):
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("not json")
        results = list(iter_json(str(tmp_path)))
        assert len(results) == 2
        assert all(r.endswith(".json") for r in results)

    def test_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.json").write_text("{}")
        (sub / "b.json").write_text("{}")
        results = list(iter_json(str(tmp_path)))
        assert len(results) == 2

    def test_empty_dir(self, tmp_path):
        assert list(iter_json(str(tmp_path))) == []


# ---------------------------------------------------------------------------
# is_reference_context
# ---------------------------------------------------------------------------

class TestIsReferenceContext:
    """Tests for is_reference_context."""

    def test_trace_context(self):
        assert is_reference_context("trace.items[0]") is True

    def test_targets_context(self):
        assert is_reference_context("targets[0]") is True

    def test_target_ids_context(self):
        assert is_reference_context("target_ids[0]") is True

    def test_mitigations_context(self):
        assert is_reference_context("mitigations[0]") is True

    def test_dependencies_context(self):
        assert is_reference_context("dependencies[0]") is True

    def test_requires_context(self):
        assert is_reference_context("requires[0]") is True

    def test_not_reference_context(self):
        assert is_reference_context("requirements[0]") is False

    def test_empty_path(self):
        assert is_reference_context("") is False

    def test_nested_with_indexes(self):
        assert is_reference_context("foo[0].trace[1].bar") is True


# ---------------------------------------------------------------------------
# collect_ids_and_refs
# ---------------------------------------------------------------------------

class TestCollectIdsAndRefs:
    """Tests for collect_ids_and_refs."""

    def test_collects_id_field(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        collect_ids_and_refs({"id": "fr-login"}, "test.json", ids, refs)
        assert "fr-login" in ids

    def test_collects_suffixed_id(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        collect_ids_and_refs({"fr_id": "fr-login"}, "test.json", ids, refs)
        assert "fr-login" in ids

    def test_collects_ref_field(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        collect_ids_and_refs({"api_ref": "api-create"}, "test.json", ids, refs)
        assert len(refs) == 1
        assert refs[0][2] == "api-create"

    def test_collects_refs_list(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        collect_ids_and_refs({"nfr_refs": ["nfr-a", "nfr-b"]}, "test.json", ids, refs)
        assert len(refs) == 2

    def test_requires_list_is_not_a_reference_source(self):
        """No schema declares ``requires`` any more, so a ``requires`` list names no reference."""
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        collect_ids_and_refs({"requires": ["fr-a", "fr-b"]}, "test.json", ids, refs)
        assert refs == []

    def test_id_in_reference_context_is_ref(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        obj = {"trace": [{"id": "fr-login", "type": "implements"}]}
        collect_ids_and_refs(obj, "test.json", ids, refs)
        assert "fr-login" in [r[2] for r in refs]

    def test_nested_objects(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        obj = {"items": [{"fr_id": "fr-a"}, {"fr_id": "fr-b"}]}
        collect_ids_and_refs(obj, "test.json", ids, refs)
        assert ids == {"fr-a", "fr-b"}
