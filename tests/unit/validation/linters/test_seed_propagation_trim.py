"""Tests for seed propagation trim: manifest and helper validation."""

from __future__ import annotations

import unittest

from specdev_tools.validation.seed_lint import (
    _collect_required_seeds,
)


class TestSeedPropagationTrim(unittest.TestCase):
    """Verify seed manifest and helper validation."""

    def test_collect_required_seeds_empty_for_unlisted_step(self):
        """_collect_required_seeds returns empty list for steps not in step_requirements."""
        manifest = {
            "global_seed_order": ["seed-overview", "seed-tech-stack"],
            "step_requirements": {"00": ["seed-overview"]},
        }
        result = _collect_required_seeds(manifest, "07")
        self.assertEqual(result, [], f"Step 07 should have no required seeds. Got: {result}")

    def test_collect_required_seeds_returns_only_declared_seeds(self):
        """_collect_required_seeds returns only seeds declared in step_requirements, not all global seeds."""
        manifest = {
            "global_seed_order": ["seed-overview", "seed-tech-stack"],
            "step_requirements": {"00": ["seed-overview"]},
        }
        result = _collect_required_seeds(manifest, "00")
        self.assertIn("seed-overview", result)
        # seed-tech-stack is in global_seed_order but NOT in step_requirements["00"] — must be excluded
        self.assertNotIn("seed-tech-stack", result)

    def test_step_16_no_sub_steps_in_requirements(self):
        """Step 16 with no 16/16a/16b/16c in step_requirements should require no seeds."""
        manifest = {
            "global_seed_order": ["seed-overview", "seed-tech-stack"],
            "step_requirements": {"00": ["seed-overview"]},
        }
        result = _collect_required_seeds(manifest, "16")
        self.assertEqual(result, [], f"Step 16 should have no required seeds. Got: {result}")


if __name__ == "__main__":
    unittest.main()
