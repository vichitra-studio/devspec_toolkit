import json
import os
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.seed_lint import lint_seeds
from specdev_tools.core.errors import render_errors


class SeedPathValidationTests(unittest.TestCase):
    """Tests for seed path existence validation (D19 fix)."""

    def _create_temp_project(self, manifest_data, seed_files=None):
        """Create a temporary project structure with manifest and optional seed files."""
        tmpdir = tempfile.mkdtemp()
        project_root = tmpdir
        spec_dir = os.path.join(project_root, "spec")
        common_dir = os.path.join(spec_dir, "common")
        os.makedirs(common_dir, exist_ok=True)

        # Write manifest
        manifest_path = os.path.join(common_dir, "seed_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        # Create seed files if specified
        if seed_files:
            for rel_path in seed_files:
                full_path = os.path.join(project_root, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write("seed content")

        # Create a minimal prompts dir so prompt lint doesn't interfere
        repo_root = tmpdir
        prompts_dir = os.path.join(repo_root, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)

        return tmpdir, spec_dir, repo_root

    def test_valid_seed_path_passes(self):
        """Seed with valid, existing path passes lint."""
        manifest = {
            "$schema": "vc:seed-manifest",
            "seeds": [
                {"seed_id": "seed-overview", "path": "docs/seed/overview.md"}
            ],
            "global_seed_order": ["seed-overview"],
        }
        tmpdir, spec_dir, repo_root = self._create_temp_project(
            manifest, seed_files=["docs/seed/overview.md"]
        )
        errors = lint_seeds(repo_root, spec_dir)
        path_errors = [e for e in render_errors(errors) if "does not exist" in e]
        self.assertEqual(path_errors, [], f"Unexpected errors: {path_errors}")

    def test_missing_seed_path_fails(self):
        """Seed path that doesn't exist on disk produces an error."""
        manifest = {
            "$schema": "vc:seed-manifest",
            "seeds": [
                {"seed_id": "seed-missing", "path": "docs/seed/nonexistent.md"}
            ],
            "global_seed_order": ["seed-missing"],
        }
        tmpdir, spec_dir, repo_root = self._create_temp_project(manifest)
        errors = lint_seeds(repo_root, spec_dir)
        self.assertTrue(
            any("does not exist" in e and "seed-missing" in e for e in render_errors(errors)),
            f"Expected missing path error, got: {errors}",
        )

    def test_missing_path_field_fails(self):
        """Seed entry without a 'path' field produces an error."""
        manifest = {
            "$schema": "vc:seed-manifest",
            "seeds": [
                {"seed_id": "seed-no-path"}
            ],
            "global_seed_order": ["seed-no-path"],
        }
        tmpdir, spec_dir, repo_root = self._create_temp_project(manifest)
        errors = lint_seeds(repo_root, spec_dir)
        self.assertTrue(
            any("missing 'path' field" in e for e in render_errors(errors)),
            f"Expected missing path field error, got: {errors}",
        )

    def test_undeclared_seed_on_disk_emits_warning(self):
        """On-disk .md file not declared in manifest triggers W551 UNDECLARED_SEED."""
        manifest = {
            "$schema": "vc:seed-manifest",
            "seeds": [
                {"seed_id": "seed-overview", "path": "docs/seed/overview.md"}
            ],
            "global_seed_order": ["seed-overview"],
            "seed_directory": "docs/seed",
        }
        tmpdir, spec_dir, repo_root = self._create_temp_project(
            manifest, seed_files=["docs/seed/overview.md", "docs/seed/extra_undeclared.md"]
        )
        errors = lint_seeds(repo_root, spec_dir)
        w551_errors = [e for e in render_errors(errors) if "W551" in e or "UNDECLARED_SEED" in e]
        self.assertTrue(
            len(w551_errors) > 0,
            f"Expected W551 UNDECLARED_SEED warning for extra_undeclared.md, got: {errors}",
        )
        self.assertTrue(
            any("extra_undeclared.md" in e for e in w551_errors),
            f"W551 should mention the undeclared file, got: {w551_errors}",
        )

    def test_path_escape_fails(self):
        """Seed path that escapes project root produces an error."""
        manifest = {
            "$schema": "vc:seed-manifest",
            "seeds": [
                {"seed_id": "seed-escape", "path": "../../etc/passwd"}
            ],
            "global_seed_order": ["seed-escape"],
        }
        tmpdir, spec_dir, repo_root = self._create_temp_project(manifest)
        errors = lint_seeds(repo_root, spec_dir)
        self.assertTrue(
            any("escapes project root" in e for e in render_errors(errors)),
            f"Expected path escape error, got: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
