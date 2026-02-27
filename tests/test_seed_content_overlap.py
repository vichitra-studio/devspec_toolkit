from __future__ import annotations

import json
import os
import tempfile
import unittest

from specdev_tools.validation.seed_lint import lint_seeds


def _make_project(tmpdir, spec_data=None, seed_text="", seed_id="seed-overview"):
    """Create a minimal project structure for seed lint testing."""
    spec_dir = os.path.join(tmpdir, "spec")
    os.makedirs(os.path.join(spec_dir, "common"), exist_ok=True)
    seed_dir = os.path.join(tmpdir, "docs", "seed")
    os.makedirs(seed_dir, exist_ok=True)

    seed_path = os.path.join(seed_dir, f"{seed_id.replace('-', '_')}.md")
    with open(seed_path, "w", encoding="utf-8") as f:
        f.write(seed_text)

    manifest = {
        "seed_directory": "docs/seed",
        "seeds": [
            {"seed_id": seed_id, "path": os.path.relpath(seed_path, tmpdir)}
        ],
        "global_seed_order": [seed_id],
        "nested_order": [],
        "step_requirements": {},
        "docs_policy": {"doc_paths": ["README.md"]},
    }
    with open(os.path.join(spec_dir, "common", "seed_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    if spec_data is not None:
        with open(os.path.join(spec_dir, "00_charter.json"), "w", encoding="utf-8") as f:
            json.dump(spec_data, f)

    return spec_dir


class TestSeedContentOverlap(unittest.TestCase):
    def test_seed_overlap_below_threshold_emits_W140(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_data = {
                "seed_refs": [{"seed_id": "seed-overview"}],
                "goals": [{"goal_id": "goal-alpha"}],
            }
            seed_text = "completely unrelated document about weather patterns"
            spec_dir = _make_project(tmpdir, spec_data=spec_data, seed_text=seed_text)
            # Use tmpdir as both repo_root and project_root
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            w140 = [e for e in errors if "W140" in e]
            self.assertTrue(len(w140) > 0, f"Expected W140 warning. Got: {errors}")

    def test_seed_overlap_sufficient_no_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_data = {
                "seed_refs": [{"seed_id": "seed-overview"}],
                "description": "authentication login endpoint validation security",
            }
            seed_text = "This document covers authentication login endpoint validation security testing"
            spec_dir = _make_project(tmpdir, spec_data=spec_data, seed_text=seed_text)
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            w140 = [e for e in errors if "W140" in e]
            self.assertEqual(w140, [], f"Did not expect W140. Got: {w140}")

    def test_seed_overlap_no_seed_refs_skips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_data = {"goals": [{"goal_id": "goal-alpha"}]}
            seed_text = "some seed content"
            spec_dir = _make_project(tmpdir, spec_data=spec_data, seed_text=seed_text)
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            w140 = [e for e in errors if "W140" in e]
            self.assertEqual(w140, [], f"Did not expect W140 for no seed_refs. Got: {w140}")


if __name__ == "__main__":
    unittest.main()
