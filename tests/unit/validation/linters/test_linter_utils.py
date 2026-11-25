"""Tests for specdev_tools.validation.linter_utils — shared linter helpers.

Created by FIX-044 (Batch 5).
"""
from __future__ import annotations

import os

from specdev_tools.validation.linter_utils import (
    CONTENT_STOPWORDS,
    collect_ids_and_refs,
    extract_command_string,
    is_reference_context,
    iter_json,
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

    def test_content_is_frozenset(self):
        assert isinstance(CONTENT_STOPWORDS, frozenset)

    def test_common_stopwords_present(self):
        for word in ("that", "this", "with", "from", "true", "false"):
            assert word in CONTENT_STOPWORDS

    def test_json_schema_terms_present(self):
        for word in ("http", "https", "schema", "json"):
            assert word in CONTENT_STOPWORDS


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

    def test_skip_ids_for_files_collects_refs_but_no_ids(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        obj = {"items": [{"fr_id": "fr-a", "id": "x-1"}], "api_ref": "api-create"}
        collect_ids_and_refs(obj, "04_fr_list.json", ids, refs, skip_ids_for_files={"04_fr_list.json"})
        assert ids == set()
        assert [ref[2] for ref in refs] == ["api-create"]

    def test_skip_ids_for_files_matches_a_platform_path(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        rel = os.path.join("impl_context", "ms_x_plan.json")
        collect_ids_and_refs({"fr_id": "fr-a"}, rel, ids, refs, skip_ids_for_files={"impl_context/ms_x_plan.json"})
        assert ids == set()

    def test_skip_ids_for_other_files_keeps_ids(self):
        ids: set[str] = set()
        refs: list[tuple[str, str, str]] = []
        collect_ids_and_refs({"fr_id": "fr-a"}, "other.json", ids, refs, skip_ids_for_files={"04_fr_list.json"})
        assert ids == {"fr-a"}


def test_canonical_stages_are_read_through_the_registry_loader(tmp_path):
    """A stage entry in ``manifest.json`` counts, as it does for every other canon reader; a retired one does not."""
    import json

    from specdev_tools.validation.linter_utils import load_canonical_stages

    canon = tmp_path / "canon"
    canon.mkdir()
    entries = [
        {"id": f"cn:core:stage:{name}", "kind": "stage", "preferred_label": name, "status": status}
        for name, status in (("dev", "active"), ("qa", "active"), ("old", "retired"))
    ]
    (canon / "manifest.json").write_text(json.dumps({"registry_version": "1.0.0", "entries": entries}), encoding="utf-8")

    assert load_canonical_stages(str(canon)) == {"dev", "qa"}
