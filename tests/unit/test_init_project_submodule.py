"""Tests for init_project.py pre-commit config generation and seed bootstrap."""
import json
import os
import sys
from unittest import mock

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from init_project import _build_pre_commit_config, _render_ci_workflow, copy_seeds_from_manifest


class TestBuildPreCommitConfig:
    def test_repo_root_flag_present(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "--repo-root ./devspec_toolkit" in content

    def test_custom_toolkit_path(self):
        content = _build_pre_commit_config("custom/path")
        assert "--repo-root ./custom/path" in content

    def test_contains_spec_check_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "spec-check" in content

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
        assert "devspec_toolkit/" not in content
        assert "devspec_toolkit/tools" not in content
        assert "./my_toolkit" in content
        assert "my_toolkit/" in content

    def test_build_pre_commit_config_missing_template(self):
        with mock.patch("os.path.exists", return_value=False):
            content = _build_pre_commit_config("devspec_toolkit")
        assert "spec-check" in content
        assert "devspec_env/bin/python" in content
        assert "--repo-root ./devspec_toolkit" in content
        assert "--spec-root ./spec" in content
        assert "--git-root ." in content

    def test_contains_dag_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "dag-lint" in content

    def test_contains_extraction_intent_check_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "extraction-intent-check" in content

    def test_contains_canon_schema_alignment_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "canon-schema-alignment" in content

    def test_contains_canonical_integrity_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "canonical-integrity" in content


class TestManifestDerivedSeedBootstrap:
    """Verify that seed templates land at the paths declared in seeds[].path,
    not at a hardcoded docs/seed/ location."""

    def _make_seed_manifest(self, target_dir, seed_paths):
        """Write a minimal seed_manifest.json with the given seed path entries."""
        seeds = []
        for rel_path in seed_paths:
            stem = os.path.splitext(os.path.basename(rel_path))[0]
            seed_id = stem.replace("_", "-")
            seeds.append({"seed_id": seed_id, "path": rel_path})
        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "test-manifest",
            "version": "0.1.0",
            "seeds": seeds,
        }
        common_dir = os.path.join(target_dir, "spec", "common")
        os.makedirs(common_dir, exist_ok=True)
        manifest_path = os.path.join(common_dir, "seed_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return manifest_path

    def _make_seed_templates(self, templates_dir, filenames):
        """Create stub .md template files."""
        os.makedirs(templates_dir, exist_ok=True)
        for name in filenames:
            with open(os.path.join(templates_dir, name), "w") as f:
                f.write(f"# {name}\n")

    def test_seeds_land_at_manifest_declared_paths(self, tmp_path):
        """Files must be copied to the exact relative paths in seeds[].path."""
        declared_paths = [
            "docs/seed/seed_overview.md",
            "docs/seed/seed_tech_stack.md",
        ]
        manifest_path = self._make_seed_manifest(str(tmp_path), declared_paths)

        templates_dir = str(tmp_path / "seed_templates")
        self._make_seed_templates(templates_dir, ["seed_overview.md", "seed_tech_stack.md"])

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        # Read back the manifest and assert each declared path exists on disk
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        for entry in manifest_data["seeds"]:
            expected = tmp_path / entry["path"]
            assert expected.exists(), (
                f"Expected seed file at {entry['path']} (declared in manifest) "
                f"but it was not created."
            )

    def test_seeds_land_at_non_default_path_when_manifest_declares_it(self, tmp_path):
        """When the manifest declares a non-docs/seed path the file must land
        there — proving the logic is manifest-driven, not hardcoded."""
        declared_paths = ["content/seeds/seed_overview.md"]
        manifest_path = self._make_seed_manifest(str(tmp_path), declared_paths)

        templates_dir = str(tmp_path / "seed_templates")
        self._make_seed_templates(templates_dir, ["seed_overview.md"])

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        expected = tmp_path / "content" / "seeds" / "seed_overview.md"
        assert expected.exists(), (
            "Expected seed file at content/seeds/seed_overview.md "
            "(non-default path declared in manifest) but it was not created."
        )
        # The hardcoded default must NOT have been used
        assert not (tmp_path / "docs" / "seed" / "seed_overview.md").exists(), (
            "File was placed at the hardcoded docs/seed/ path instead of "
            "the manifest-declared path."
        )

    def test_fallback_is_deterministic_across_multiple_parent_dirs(self, tmp_path):
        """When a template .md has no manifest entry and multiple seed parent
        dirs exist, the fallback must always be the lexicographically first dir."""
        declared_paths = [
            "alpha/seeds/seed_a.md",
            "zeta/seeds/seed_z.md",
        ]
        manifest_path = self._make_seed_manifest(str(tmp_path), declared_paths)

        templates_dir = str(tmp_path / "seed_templates")
        # seed_extra.md has no manifest entry — will use the fallback dir
        self._make_seed_templates(
            templates_dir, ["seed_a.md", "seed_z.md", "seed_extra.md"]
        )

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        # Fallback should be sorted(parent_dirs)[0] → alpha/seeds (< zeta/seeds)
        expected_fallback = tmp_path / "alpha" / "seeds" / "seed_extra.md"
        assert expected_fallback.exists(), (
            "Unmatched template should fall back to the lexicographically first "
            "seed parent dir (alpha/seeds), not a non-deterministic choice."
        )


class TestCiWorkflowRender:
    def test_default_venv_name_in_ci(self):
        content = _render_ci_workflow(".", "devspec_env")
        # uv-driven setup: managed Python + venv on the default name
        assert "astral-sh/setup-uv" in content
        assert "uv venv devspec_env --python 3.13" in content
        assert "uv pip install --python devspec_env/bin/python" in content
        # the old pip/venv path must be gone
        assert "python -m venv" not in content
        assert "/bin/pip install" not in content

    def test_custom_venv_name_propagates(self):
        content = _render_ci_workflow(".", "customenv")
        assert "uv venv customenv --python 3.13" in content
        assert "uv pip install --python customenv/bin/python" in content
        assert "customenv/bin" in content
        # no leakage of the default venv name when a custom one is requested
        assert "devspec_env" not in content

    def test_toolkit_path_substitution(self):
        content = _render_ci_workflow("vendor/devspec_toolkit", "devspec_env")
        assert "vendor/devspec_toolkit/tools" in content
        # Every "devspec_toolkit/tools" occurrence must carry the vendor/ prefix —
        # i.e. the path substitution left no unsubstituted bare token behind.
        # (Discriminating: if replace-1 were dropped, bare tokens would remain and
        # the counts would diverge.)
        assert content.count("devspec_toolkit/tools") == content.count("vendor/devspec_toolkit/tools")
