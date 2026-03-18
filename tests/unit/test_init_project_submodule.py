"""Tests for init_project.py submodule detection and generated hook content."""
import os
import sys
import pytest

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from init_project import _build_pre_commit_template


class TestBuildPreCommitTemplate:
    def test_submodule_includes_spec_root(self):
        content = _build_pre_commit_template("devspec_toolkit", is_submodule=True)
        assert "--spec-root" in content

    def test_submodule_includes_git_root(self):
        content = _build_pre_commit_template("devspec_toolkit", is_submodule=True)
        assert "--git-root" in content

    def test_non_submodule_no_spec_root(self):
        content = _build_pre_commit_template("devspec_toolkit", is_submodule=False)
        assert "--spec-root" not in content

    def test_non_submodule_no_git_root(self):
        content = _build_pre_commit_template("devspec_toolkit", is_submodule=False)
        assert "--git-root" not in content

    def test_repo_root_flag_present(self):
        content = _build_pre_commit_template("devspec_toolkit", is_submodule=True)
        assert "--repo-root ./devspec_toolkit" in content

    def test_custom_toolkit_path(self):
        content = _build_pre_commit_template("custom/path", is_submodule=True)
        assert "--repo-root ./custom/path" in content
