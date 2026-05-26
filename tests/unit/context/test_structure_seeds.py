"""Tests for context/structure.py seeds_required for late pipeline steps.

DEVSPEC-43 §3.9 / §6: get_step_structure / _seeds_required must return
manifest-declared seeds for ANY pipeline step (00–16c), not just early ones.

Existing tests in test_context_cli.py only check that the seeds_required key
EXISTS (and is empty because the spec_corpus fixture has no seed_manifest.json).
These tests verify the CONTENT of seeds_required for late steps by supplying a
real seed_manifest.json in a temporary spec_dir.
"""
from __future__ import annotations

import json
import os

from specdev_tools.context.structure import _seeds_required, get_step_structure

# Toolkit repo root (for repo_root argument to get_step_structure).
_TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))


def _build_spec_dir_with_manifest(
    tmpdir: str,
    *,
    global_seed_order: list[str],
    step_requirements: dict,
) -> str:
    """Create spec/common/seed_manifest.json and return spec_dir."""
    spec_dir = os.path.join(tmpdir, "spec")
    os.makedirs(os.path.join(spec_dir, "common"), exist_ok=True)

    manifest = {
        "global_seed_order": global_seed_order,
        "seeds": [
            {"seed_id": sid, "path": f"docs/seed/{sid.replace('-', '_')}.md"}
            for sid in global_seed_order
        ],
        "step_requirements": step_requirements,
    }
    manifest_path = os.path.join(spec_dir, "common", "seed_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    return spec_dir


# ---------------------------------------------------------------------------
# C: _seeds_required — late step
# ---------------------------------------------------------------------------

class TestSeedsRequiredLateStep:
    """_seeds_required returns manifest-declared seeds for late steps."""

    def test_step_09_returns_manifest_seed(self, tmp_path):
        """_seeds_required("09") returns a seed routed to step 09."""
        spec_dir = _build_spec_dir_with_manifest(
            str(tmp_path),
            global_seed_order=["seed-test-philosophy"],
            step_requirements={"09": ["seed-test-philosophy"]},
        )
        result = _seeds_required("09", spec_dir)
        assert "seed-test-philosophy" in result, (
            f"Expected 'seed-test-philosophy' in seeds_required for step 09. Got: {result}"
        )

    def test_step_09_respects_global_seed_order(self, tmp_path):
        """_seeds_required("09") returns seeds in global_seed_order order."""
        spec_dir = _build_spec_dir_with_manifest(
            str(tmp_path),
            global_seed_order=["seed-a", "seed-b", "seed-c"],
            step_requirements={"09": ["seed-c", "seed-a"]},
        )
        result = _seeds_required("09", spec_dir)
        # global_seed_order is [a, b, c]; step requires a and c → ordered [a, c]
        assert result.index("seed-a") < result.index("seed-c"), (
            f"global_seed_order must be respected. Got: {result}"
        )
        # seed-b is in global but NOT required for step 09 → must be absent
        assert "seed-b" not in result, (
            f"seed-b is not required for step 09 and must not appear. Got: {result}"
        )

    def test_step_14_returns_manifest_seed(self, tmp_path):
        """_seeds_required("14") returns a seed routed to step 14."""
        spec_dir = _build_spec_dir_with_manifest(
            str(tmp_path),
            global_seed_order=["seed-domain-model"],
            step_requirements={"14": ["seed-domain-model"]},
        )
        result = _seeds_required("14", spec_dir)
        assert "seed-domain-model" in result, (
            f"Expected 'seed-domain-model' in seeds_required for step 14. Got: {result}"
        )

    def test_step_not_in_requirements_returns_empty(self, tmp_path):
        """_seeds_required for a step with no entry returns []."""
        spec_dir = _build_spec_dir_with_manifest(
            str(tmp_path),
            global_seed_order=["seed-a"],
            step_requirements={"00": ["seed-a"]},
        )
        result = _seeds_required("09", spec_dir)
        assert result == [], f"Step 09 not in requirements → must return []. Got: {result}"

    def test_no_manifest_returns_empty(self, tmp_path):
        """When no seed_manifest.json exists, _seeds_required returns []."""
        spec_dir = str(tmp_path / "spec")
        os.makedirs(spec_dir, exist_ok=True)
        result = _seeds_required("09", spec_dir)
        assert result == [], f"Missing manifest → must return []. Got: {result}"


# ---------------------------------------------------------------------------
# C: get_step_structure → seeds_required key — late step
# ---------------------------------------------------------------------------

class TestGetStepStructureSeedsRequired:
    """get_step_structure returns correct seeds_required for late steps."""

    def test_step_09_seeds_required_via_get_step_structure(self, tmp_path):
        """get_step_structure for step 09 returns the manifest-declared seeds."""
        spec_dir = _build_spec_dir_with_manifest(
            str(tmp_path),
            global_seed_order=["seed-test-philosophy", "seed-domain-model"],
            step_requirements={"09": ["seed-test-philosophy"]},
        )
        result = get_step_structure("09", spec_dir, _TOOLKIT_ROOT)
        seeds = result["seeds_required"]
        assert "seed-test-philosophy" in seeds, (
            f"seed-test-philosophy must be in seeds_required for step 09 via get_step_structure. "
            f"Got: {seeds}"
        )
        # seed-domain-model is global-only for step 09 → must be absent
        assert "seed-domain-model" not in seeds, (
            f"seed-domain-model is global-only for step 09 and must not appear. Got: {seeds}"
        )

    def test_seeds_required_key_present_in_output(self, tmp_path):
        """get_step_structure always includes seeds_required key."""
        # Use a spec_dir with no seed_manifest.json — key must still exist, just empty
        spec_dir = str(tmp_path / "spec")
        os.makedirs(spec_dir, exist_ok=True)
        result = get_step_structure("09", spec_dir, _TOOLKIT_ROOT)
        assert "seeds_required" in result, "seeds_required key must always be present"
        assert result["seeds_required"] == [], (
            f"Without manifest, seeds_required must be []. Got: {result['seeds_required']}"
        )
