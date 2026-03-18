"""Tests for specdev_tools.validation.governance — commit message checking.

Created by FIX-046 (Batch 5).
"""
from __future__ import annotations

import json
import os

import pytest

from specdev_tools.validation.governance import check_commit_message, load_governance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_governance(spec_dir, rules: dict | None = None):
    """Write a governance spec file with optional commit_message_rules."""
    data = {
        "id": "governance-rules",
        "commit_message_rules": rules or {},
    }
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, "10_governance.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# load_governance
# ---------------------------------------------------------------------------

class TestLoadGovernance:
    """Tests for load_governance."""

    def test_found_by_filename(self, tmp_path):
        _write_governance(str(tmp_path), {"pattern": ".*"})
        result = load_governance(str(tmp_path))
        assert result is not None
        assert result["id"] == "governance-rules"

    def test_not_found_returns_none(self, tmp_path):
        result = load_governance(str(tmp_path))
        assert result is None

    def test_fallback_by_id_pattern(self, tmp_path):
        """Should find governance even if file is not named 10_*."""
        data = {"id": "governance-custom", "commit_message_rules": {}}
        p = tmp_path / "custom_gov.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = load_governance(str(tmp_path))
        assert result is not None
        assert result["id"] == "governance-custom"

    def test_invalid_json_skipped(self, tmp_path):
        (tmp_path / "10_governance.json").write_text("NOT JSON", encoding="utf-8")
        result = load_governance(str(tmp_path))
        assert result is None


# ---------------------------------------------------------------------------
# check_commit_message
# ---------------------------------------------------------------------------

class TestCheckCommitMessage:
    """Tests for check_commit_message."""

    def test_valid_message(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
            "pattern": r"^(feat|fix|docs)\(.+\):.*\[.+\]$",
        })
        errors = check_commit_message(str(tmp_path), "feat(auth): add login [fr-login]")
        assert errors == []

    def test_invalid_message(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
            "pattern": r"^(feat|fix|docs)\(.+\):.*\[.+\]$",
        })
        errors = check_commit_message(str(tmp_path), "random commit message")
        assert len(errors) == 1
        assert "mismatch" in errors[0].render().lower()

    def test_custom_error_message(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
            "pattern": r"^(feat|fix)\(.+\):.*$",
            "error_message": "Use conventional commits!",
        })
        errors = check_commit_message(str(tmp_path), "bad")
        assert "Use conventional commits!" in errors[0].render()

    def test_no_require_ids_skips_check(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": False,
            "pattern": r"^(feat|fix)\(.+\):.*$",
        })
        errors = check_commit_message(str(tmp_path), "anything")
        assert errors == []

    def test_no_pattern_skips_check(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
        })
        errors = check_commit_message(str(tmp_path), "anything")
        assert errors == []

    def test_no_governance_file(self, tmp_path):
        errors = check_commit_message(str(tmp_path), "anything")
        assert errors == []

    def test_empty_message(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
            "pattern": r"^(feat|fix)\(.+\):.*$",
        })
        errors = check_commit_message(str(tmp_path), "")
        assert len(errors) == 1

    def test_none_message(self, tmp_path):
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
            "pattern": r"^(feat|fix)\(.+\):.*$",
        })
        errors = check_commit_message(str(tmp_path), None)
        assert len(errors) == 1

    def test_default_error_message_mentions_regex(self, tmp_path):
        pattern = r"^(feat|fix)\(.+\):.*$"
        _write_governance(str(tmp_path), {
            "require_spec_ids": True,
            "pattern": pattern,
        })
        errors = check_commit_message(str(tmp_path), "bad")
        assert pattern in errors[0].render()
