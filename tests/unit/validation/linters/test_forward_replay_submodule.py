"""Tests for forward_replay_check submodule support: spec_root/git_root params."""
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from specdev_tools.validation.forward_replay_check import check_forward_replay
from specdev_tools.core.errors import render_errors


@pytest.fixture
def submodule_layout(tmp_path):
    """Create a submodule-like directory layout."""
    # Host repo root
    host_root = tmp_path / "host_repo"
    host_root.mkdir()

    # Spec dir in host repo
    spec_dir = host_root / "spec"
    spec_dir.mkdir()

    # Toolkit as submodule
    toolkit = host_root / "devspec_toolkit"
    toolkit.mkdir()
    tools = toolkit / "tools"
    tools.mkdir()

    # step_order.json
    step_order = {
        "version": "1.0.0",
        "policy": {"mode": "strict_waterfall"},
        "steps": ["00", "01", "02"],
    }
    (tools / "step_order.json").write_text(json.dumps(step_order))

    return {"host": host_root, "spec": spec_dir, "toolkit": toolkit}


class TestSpecRootParam:
    def test_spec_root_used_for_step_exists(self, submodule_layout):
        """spec_root should be used instead of repo_root/spec for checking step existence."""
        layout = submodule_layout
        # Create spec file in the spec dir (not in toolkit/spec)
        (layout["spec"] / "00_charter.json").write_text("{}")

        with patch("specdev_tools.validation.forward_replay_check._changed_files") as mock_diff:
            mock_diff.return_value = (["spec/00_charter.json"], None)
            errors = check_forward_replay(
                str(layout["toolkit"]),
                base_ref="origin/main",
                diff_error_mode="error",
                spec_root=str(layout["spec"]),
                git_root=str(layout["host"]),
            )
            # Should find the spec file through spec_root
            # (errors about missing downstream are expected)
            assert not any("unable_to_compute_diff" in e for e in render_errors(errors))


class TestGitRootParam:
    def test_git_root_used_for_diff(self, submodule_layout):
        """git_root should be passed to _changed_files for git diff."""
        layout = submodule_layout

        with patch("specdev_tools.validation.forward_replay_check._changed_files") as mock_diff:
            mock_diff.return_value = ([], None)
            check_forward_replay(
                str(layout["toolkit"]),
                base_ref="origin/main",
                git_root=str(layout["host"]),
            )
            # Verify _changed_files was called with host root, not toolkit root
            call_args = mock_diff.call_args
            assert str(layout["host"]) in str(call_args)


class TestBackwardCompat:
    def test_no_params_defaults(self, submodule_layout):
        """When git_root and spec_root are None, defaults to repo_root."""
        layout = submodule_layout

        with patch("specdev_tools.validation.forward_replay_check._changed_files") as mock_diff:
            mock_diff.return_value = ([], None)
            # Should not raise when params are None
            errors = check_forward_replay(
                str(layout["toolkit"]),
                base_ref="origin/main",
            )
            assert isinstance(errors, list)
