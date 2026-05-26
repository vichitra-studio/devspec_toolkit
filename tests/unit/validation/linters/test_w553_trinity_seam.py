"""Trinity seam tests for seed routing — DEVSPEC-43 §6 §3.17.

Asserts at the seed_lint / helper levels that:
  (a) resolve_seeds_for_step("16b") includes seeds from step_requirements["16b"]
      PLUS the bare "16" umbrella.
  (b) seed_lint emits NO W553 for the "16b" key (it is a known step).

NOTE: The agent-contract assertions ("specdev-trinity-impl instructs ingestion of
step_requirements[16b]") are guarded-by-construction via the .md edit and have NO
pytest-level precedent in this suite.  No agent/.md grep test is added.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from specdev_tools.core.seed_routing import resolve_seeds_for_step
from specdev_tools.validation.seed_lint import lint_seeds
from specdev_tools.core.errors import render_errors

_TOOLKIT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir)
)


def _build_project_with_seeds(tmpdir, step_requirements, seeds):
    """Build minimal project structure for seed_lint tests."""
    spec_dir = os.path.join(tmpdir, "spec")
    os.makedirs(os.path.join(spec_dir, "common"), exist_ok=True)
    seed_dir = os.path.join(tmpdir, "docs", "seed")
    os.makedirs(seed_dir, exist_ok=True)

    global_seed_order = [s["seed_id"] for s in seeds]
    manifest_seeds = []
    for s in seeds:
        rel_path = f"docs/seed/{s['seed_id'].replace('-', '_')}.md"
        abs_path = os.path.join(tmpdir, rel_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(s.get("text", "seed content"))
        manifest_seeds.append({"seed_id": s["seed_id"], "path": rel_path})

    manifest = {
        "global_seed_order": global_seed_order,
        "seeds": manifest_seeds,
        "step_requirements": step_requirements,
    }
    manifest_path = os.path.join(spec_dir, "common", "seed_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    return spec_dir


class TestTrinitySeam(unittest.TestCase):
    """seed_lint/helper level assertions for step "16b" routing (§F)."""

    # ------------------------------------------------------------------
    # F(a): resolve_seeds_for_step("16b") includes own + umbrella seeds
    # ------------------------------------------------------------------

    def test_16b_includes_own_and_umbrella_seeds(self):
        """resolve_seeds_for_step("16b") returns seeds from "16b" AND bare "16" umbrella."""
        manifest = {
            "global_seed_order": ["seed-umbrella", "seed-16b-specific"],
            "step_requirements": {
                "16":  ["seed-umbrella"],       # bare key
                "16b": ["seed-16b-specific"],   # 16b-specific
            },
        }
        _, step_ids = resolve_seeds_for_step("16b", manifest)
        self.assertIn(
            "seed-16b-specific", step_ids,
            "seed-16b-specific must be in step_ids for step '16b'",
        )
        self.assertIn(
            "seed-umbrella", step_ids,
            "seed-umbrella (from bare '16' key) must be in step_ids for step '16b'",
        )

    def test_16b_excludes_seeds_from_16a_and_16c(self):
        """step "16b" must NOT receive seeds routed to "16a" or "16c"."""
        manifest = {
            "global_seed_order": ["seed-a", "seed-b", "seed-c"],
            "step_requirements": {
                "16a": ["seed-a"],
                "16b": ["seed-b"],
                "16c": ["seed-c"],
            },
        }
        _, step_ids = resolve_seeds_for_step("16b", manifest)
        self.assertIn("seed-b", step_ids, "seed-b (own) must be in step_ids for 16b")
        self.assertNotIn("seed-a", step_ids, "seed-a (16a-only) must NOT be in 16b step_ids")
        self.assertNotIn("seed-c", step_ids, "seed-c (16c-only) must NOT be in 16b step_ids")

    # ------------------------------------------------------------------
    # F(b): seed_lint emits NO W553 for "16b" key
    # ------------------------------------------------------------------

    def test_seed_lint_no_w553_for_16b_key(self):
        """step_requirements["16b"] is a known pipeline step → no W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project_with_seeds(
                tmpdir,
                step_requirements={"16b": ["seed-code-review"]},
                seeds=[{"seed_id": "seed-code-review", "text": "code review content"}],
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(
                w553, [],
                msg=f"No W553 expected for known step '16b'. Got: {w553}",
            )

    def test_seed_lint_no_w553_for_all_trinity_steps(self):
        """16, 16a, 16b, 16c all known → no W553 for any of them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project_with_seeds(
                tmpdir,
                step_requirements={
                    "16":  ["seed-base"],
                    "16a": ["seed-base"],
                    "16b": ["seed-base"],
                    "16c": ["seed-base"],
                },
                seeds=[{"seed_id": "seed-base", "text": "base seed content"}],
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(
                w553, [],
                msg=f"No W553 for any trinity step. Got: {w553}",
            )


if __name__ == "__main__":
    unittest.main()
