"""Tests for specdev_tools.core.loaders — shared upstream ID loaders.

Created by FIX-043 (Batch 5).
"""
from __future__ import annotations

import json

import pytest

from specdev_tools.core.loaders import (
    KEBAB_ID_RE,
    check_cross_step_refs,
    kebab_id_re,
    load_json_artifact,
    load_sibling_artifact,
    load_upstream_ids,
)


# ---------------------------------------------------------------------------
# KEBAB_ID_RE constant
# ---------------------------------------------------------------------------

class TestKebabIdRe:
    """Tests for the KEBAB_ID_RE compiled regex pattern."""

    def test_simple_kebab(self):
        assert KEBAB_ID_RE.match("hello-world")

    def test_single_word(self):
        assert KEBAB_ID_RE.match("hello")

    def test_numeric_prefix(self):
        assert KEBAB_ID_RE.match("123-abc")

    def test_multi_segment(self):
        assert KEBAB_ID_RE.match("fr-user-login-page")

    def test_rejects_uppercase(self):
        assert not KEBAB_ID_RE.match("Hello-World")

    def test_rejects_underscore(self):
        assert not KEBAB_ID_RE.match("hello_world")

    def test_rejects_trailing_dash(self):
        assert not KEBAB_ID_RE.match("hello-")

    def test_rejects_leading_dash(self):
        assert not KEBAB_ID_RE.match("-hello")

    def test_rejects_empty(self):
        assert not KEBAB_ID_RE.match("")

    def test_rejects_double_dash(self):
        assert not KEBAB_ID_RE.match("hello--world")


# ---------------------------------------------------------------------------
# kebab_id_re() factory
# ---------------------------------------------------------------------------

class TestKebabIdReFactory:
    """Tests for the kebab_id_re(prefix) factory function."""

    def test_prefix_match(self):
        pat = kebab_id_re("fr")
        assert pat.match("fr-login")
        assert pat.match("fr-user-auth")

    def test_prefix_no_match_wrong_prefix(self):
        pat = kebab_id_re("fr")
        assert not pat.match("api-login")

    def test_prefix_no_match_bare_prefix(self):
        pat = kebab_id_re("fr")
        assert not pat.match("fr")

    def test_special_chars_escaped(self):
        pat = kebab_id_re("fr.x")
        # Dot should be escaped — should not match "frXx-foo"
        assert not pat.match("frXx-foo")
        assert pat.match("fr.x-foo")


# ---------------------------------------------------------------------------
# load_upstream_ids
# ---------------------------------------------------------------------------

class TestLoadUpstreamIds:
    """Tests for load_upstream_ids."""

    def test_valid_ids(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-login"}, {"fr_id": "fr-logout"}]}),
            encoding="utf-8",
        )
        result = load_upstream_ids(tmp_path, "04", "requirements", "fr_id")
        assert result == {"fr-login", "fr-logout"}

    def test_missing_file_returns_none(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        result = load_upstream_ids(tmp_path, "99", "items", "id")
        assert result is None

    def test_missing_spec_dir_returns_none(self, tmp_path):
        result = load_upstream_ids(tmp_path, "04", "requirements", "fr_id")
        assert result is None

    def test_empty_array_returns_empty_set(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text(
            json.dumps({"requirements": []}),
            encoding="utf-8",
        )
        result = load_upstream_ids(tmp_path, "04", "requirements", "fr_id")
        assert result == set()

    def test_fallback_keys(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text(
            json.dumps({"alt_reqs": [{"fr_id": "fr-alt"}]}),
            encoding="utf-8",
        )
        result = load_upstream_ids(
            tmp_path, "04", "requirements", "fr_id",
            fallback_keys=("alt_reqs",),
        )
        assert result == {"fr-alt"}

    def test_fallback_keys_not_needed(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-main"}], "alt_reqs": [{"fr_id": "fr-alt"}]}),
            encoding="utf-8",
        )
        result = load_upstream_ids(
            tmp_path, "04", "requirements", "fr_id",
            fallback_keys=("alt_reqs",),
        )
        assert result == {"fr-main"}

    def test_malformed_json_raises(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text("NOT JSON", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_upstream_ids(tmp_path, "04", "requirements", "fr_id")

    def test_non_dict_items_ignored(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-a"}, "not-a-dict", 42]}),
            encoding="utf-8",
        )
        result = load_upstream_ids(tmp_path, "04", "requirements", "fr_id")
        assert result == {"fr-a"}

    def test_multiple_files_takes_first(self, tmp_path):
        """Only the first matching file is read (os.listdir order may vary)."""
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_a.json").write_text(
            json.dumps({"items": [{"id": "a"}]}),
            encoding="utf-8",
        )
        (spec / "04_b.json").write_text(
            json.dumps({"items": [{"id": "b"}]}),
            encoding="utf-8",
        )
        result = load_upstream_ids(tmp_path, "04", "items", "id")
        assert result is not None
        # Should have found one of the files
        assert len(result) == 1

    def test_spec_root_fallback_used_when_toolkit_spec_missing(self, tmp_path):
        """spec_root is consulted when toolkit spec/ has no matching file."""
        toolkit = tmp_path / "toolkit"
        (toolkit / "spec").mkdir(parents=True)
        # toolkit spec/ exists but has no step-04 file

        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-host"}]}),
            encoding="utf-8",
        )

        result = load_upstream_ids(
            toolkit, "04", "requirements", "fr_id",
            spec_root=str(host_spec),
        )
        assert result == {"fr-host"}

    def test_spec_root_takes_precedence_over_toolkit_spec(self, tmp_path):
        """spec_root is searched first when provided and distinct from toolkit
        spec/. This prevents the toolkit's own fixture specs from shadowing the
        host repo's artifacts in submodule deployments (see loaders.load_upstream_ids
        docstring)."""
        toolkit = tmp_path / "toolkit"
        (toolkit / "spec").mkdir(parents=True)
        (toolkit / "spec" / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-toolkit"}]}),
            encoding="utf-8",
        )

        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-host"}]}),
            encoding="utf-8",
        )

        result = load_upstream_ids(
            toolkit, "04", "requirements", "fr_id",
            spec_root=str(host_spec),
        )
        assert result == {"fr-host"}

    def test_spec_root_none_skips_fallback(self, tmp_path):
        """When spec_root is None, the fallback path is not consulted."""
        toolkit = tmp_path / "toolkit"
        (toolkit / "spec").mkdir(parents=True)
        # No step-04 file in toolkit spec, and no spec_root provided

        result = load_upstream_ids(
            toolkit, "04", "requirements", "fr_id",
            spec_root=None,
        )
        assert result is None

    def test_spec_root_missing_dir_returns_none(self, tmp_path):
        """spec_root pointing at a non-existent directory falls through to None."""
        toolkit = tmp_path / "toolkit"
        (toolkit / "spec").mkdir(parents=True)

        result = load_upstream_ids(
            toolkit, "04", "requirements", "fr_id",
            spec_root=str(tmp_path / "nonexistent" / "spec"),
        )
        assert result is None


# ---------------------------------------------------------------------------
# load_sibling_artifact
# ---------------------------------------------------------------------------

class TestLoadSiblingArtifact:
    """Tests for load_sibling_artifact."""

    def test_sibling_found(self, tmp_path):
        (tmp_path / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-x"}]}),
            encoding="utf-8",
        )
        artifact = tmp_path / "08_fixtures.json"
        artifact.write_text("{}", encoding="utf-8")
        result = load_sibling_artifact(str(artifact), "04", "requirements", "fr_id")
        assert result == {"fr-x"}

    def test_sibling_not_found_empty_set(self, tmp_path):
        artifact = tmp_path / "08_fixtures.json"
        artifact.write_text("{}", encoding="utf-8")
        result = load_sibling_artifact(str(artifact), "99", "items", "id")
        assert result == set()

    def test_fallback_root(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_frs.json").write_text(
            json.dumps({"requirements": [{"fr_id": "fr-fb"}]}),
            encoding="utf-8",
        )
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        artifact = other_dir / "08_fixtures.json"
        artifact.write_text("{}", encoding="utf-8")
        result = load_sibling_artifact(
            str(artifact), "04", "requirements", "fr_id",
            fallback_root=str(tmp_path),
        )
        assert result == {"fr-fb"}

    def test_invalid_json_returns_empty(self, tmp_path):
        (tmp_path / "04_frs.json").write_text("NOT JSON", encoding="utf-8")
        artifact = tmp_path / "08_fixtures.json"
        artifact.write_text("{}", encoding="utf-8")
        result = load_sibling_artifact(str(artifact), "04", "requirements", "fr_id")
        assert result == set()


# ---------------------------------------------------------------------------
# check_cross_step_refs
# ---------------------------------------------------------------------------

class TestCheckCrossStepRefs:
    """Tests for check_cross_step_refs."""

    def test_valid_refs_no_errors(self):
        errors: list[str] = []
        upstream: dict[str, tuple[set[str] | None, str, str]] = {
            "fr-": ({"fr-login", "fr-logout"}, "04_frs.json", "FR"),
        }
        check_cross_step_refs(["fr-login"], upstream, errors)
        assert errors == []

    def test_invalid_ref_appends_e590(self):
        errors: list[str] = []
        upstream: dict[str, tuple[set[str] | None, str, str]] = {
            "fr-": ({"fr-login"}, "04_frs.json", "FR"),
        }
        check_cross_step_refs(["fr-nonexistent"], upstream, errors)
        assert len(errors) == 1
        assert "E590" in errors[0]
        assert "fr-nonexistent" in errors[0]

    def test_missing_upstream_appends_w590(self):
        errors: list[str] = []
        upstream: dict[str, tuple[set[str] | None, str, str]] = {
            "fr-": (None, "04_frs.json", "FR"),
        }
        check_cross_step_refs(["fr-login"], upstream, errors)
        assert len(errors) == 1
        assert "W590" in errors[0]

    def test_code_prefix_included(self):
        errors: list[str] = []
        upstream: dict[str, tuple[set[str] | None, str, str]] = {
            "fr-": ({"fr-login"}, "04_frs.json", "FR"),
        }
        check_cross_step_refs(["fr-missing"], upstream, errors, code_prefix="fixture 'fix-login' ")
        assert "fixture 'fix-login'" in errors[0]

    def test_empty_targets_no_errors(self):
        errors: list[str] = []
        upstream: dict[str, tuple[set[str] | None, str, str]] = {
            "fr-": ({"fr-login"}, "04_frs.json", "FR"),
        }
        check_cross_step_refs([], upstream, errors)
        assert errors == []

    def test_empty_target_id_skipped(self):
        errors: list[str] = []
        upstream: dict[str, tuple[set[str] | None, str, str]] = {
            "fr-": ({"fr-login"}, "04_frs.json", "FR"),
        }
        check_cross_step_refs(["", "fr-login"], upstream, errors)
        assert errors == []


# ---------------------------------------------------------------------------
# load_json_artifact
# ---------------------------------------------------------------------------

class TestLoadJsonArtifact:
    """Tests for load_json_artifact."""

    def test_valid_json(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = load_json_artifact(p)
        assert result == {"key": "value"}

    def test_missing_file_returns_empty_dict(self, tmp_path):
        result = load_json_artifact(tmp_path / "nonexistent.json")
        assert result == {}

    def test_non_dict_returns_empty_dict(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        result = load_json_artifact(p)
        assert result == {}

    def test_malformed_json_raises(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text("NOT JSON", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_json_artifact(p)
