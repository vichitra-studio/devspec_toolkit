"""Tests for seed_lint strict_mode and public project_root_from_spec_dir."""
import json
import os
from pathlib import Path

import pytest

from specdev_tools.validation.seed_lint import lint_seeds, project_root_from_spec_dir


class TestProjectRootFromSpecDir:
    def test_derives_parent(self, tmp_path):
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        result = project_root_from_spec_dir(str(spec_dir))
        assert result == str(tmp_path)

    def test_public_api(self):
        """project_root_from_spec_dir should be importable (not private)."""
        from specdev_tools.validation.seed_lint import project_root_from_spec_dir
        assert callable(project_root_from_spec_dir)


class TestStrictMode:
    @pytest.fixture
    def mismatched_layout(self, tmp_path):
        """Create a layout where spec_dir implies a different root than repo_root."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        other_root = tmp_path / "other"
        other_root.mkdir()
        spec_dir = other_root / "spec"
        spec_dir.mkdir()
        # Need a seed manifest for lint_seeds to proceed
        common = spec_dir / "common"
        common.mkdir()
        manifest = {
            "seeds": [],
            "global_seed_order": [],
            "step_requirements": {},
        }
        (common / "seed_manifest.json").write_text(json.dumps({
            "$schema": "https://specdev.local/schema/seed_manifest.schema.json",
            **manifest,
        }))
        return {"repo_root": str(repo_root), "spec_dir": str(spec_dir)}

    def test_strict_mode_true_fails_on_mismatch(self, mismatched_layout):
        errs = lint_seeds(
            mismatched_layout["repo_root"],
            mismatched_layout["spec_dir"],
            strict_mode=True,
        )
        assert any("E520" in e for e in errs)

    def test_strict_mode_false_warns_on_mismatch(self, mismatched_layout):
        errs = lint_seeds(
            mismatched_layout["repo_root"],
            mismatched_layout["spec_dir"],
            strict_mode=False,
        )
        # Should warn but not produce E520
        has_warning = any("scope warning" in e for e in errs)
        has_error = any("E520" in e for e in errs)
        assert has_warning
        assert not has_error
