"""Tests for init_project.py pre-commit config generation."""
import os
import sys

import pytest

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from init_project import _build_pre_commit_config


class TestBuildPreCommitConfig:
    def test_repo_root_flag_present(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "--repo-root ./devspec_toolkit" in content

    def test_custom_toolkit_path(self):
        content = _build_pre_commit_config("custom/path")
        assert "--repo-root ./custom/path" in content

    def test_contains_validate_all_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "validate-all" in content

    def test_contains_canonical_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "canonical-lint" in content

    def test_contains_seed_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "seed-lint" in content

    def test_contains_dependency_order_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "dependency-order-lint" in content

    def test_path_substitution_applied(self):
        content = _build_pre_commit_config("my_toolkit")
        assert "./devspec_toolkit" not in content
        assert "./my_toolkit" in content
