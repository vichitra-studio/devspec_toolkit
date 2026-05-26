"""Tests for W140 SEED_CONTENT_OVERLAP_LOW — step-only blind-spot.

DEVSPEC-43 §6 acceptance criterion: consumers use step_seed_ids ONLY (not
global ∪ step).  Every existing W140 fixture places the seed in BOTH
global_seed_order AND step_requirements[step], so a silent widening (using
the union) would be undetectable.

This module adds the missing fixture: a seed present in global_seed_order but
ABSENT from step_requirements[<step under test>].  A correct implementation
must NOT fire W140 for that pair.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from specdev_tools.validation.seed_lint import lint_seeds
from specdev_tools.core.errors import render_errors

# Absolute path to toolkit root (for step_order.json and schema_registry.json lookup).
_TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir))


def _build_project(
    tmpdir: str,
    *,
    seeds: list[dict],                  # list of {seed_id, relpath, text}
    global_seed_order: list[str],
    step_requirements: dict,
    spec_artifacts: dict | None = None, # filename -> JSON-serialisable data
) -> str:
    """Build a minimal project tree and return the spec_dir path."""
    spec_dir = os.path.join(tmpdir, "spec")
    os.makedirs(os.path.join(spec_dir, "common"), exist_ok=True)
    seed_dir = os.path.join(tmpdir, "docs", "seed")
    os.makedirs(seed_dir, exist_ok=True)

    manifest_seeds = []
    for s in seeds:
        abs_path = os.path.join(seed_dir, s["relpath"])
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(s["text"])
        manifest_seeds.append({
            "seed_id": s["seed_id"],
            "path": os.path.relpath(abs_path, tmpdir),
        })

    manifest = {
        "seed_directory": "docs/seed",
        "seeds": manifest_seeds,
        "global_seed_order": global_seed_order,
        "step_requirements": step_requirements,
    }
    manifest_path = os.path.join(spec_dir, "common", "seed_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    if spec_artifacts:
        for filename, data in spec_artifacts.items():
            with open(os.path.join(spec_dir, filename), "w", encoding="utf-8") as f:
                json.dump(data, f)

    return spec_dir


class TestW140StepSeedOnly(unittest.TestCase):
    """Pin that W140 uses step_seed_ids exclusively, not global_seed_order ∪ step_seed_ids."""

    def test_global_only_seed_absent_from_step_does_not_fire_w140(self):
        """seed-extra is in global_seed_order but NOT in step_requirements["00"].

        The 00_charter.json artifact does NOT distill seed-extra.
        A correct implementation must NOT emit W140 for seed-extra / 00_charter pair
        because seed-extra is not step-required for step 00.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    {
                        "seed_id": "seed-required",
                        "relpath": "seed_required.md",
                        "text": "authentication login endpoint validation security",
                    },
                    {
                        "seed_id": "seed-extra",
                        "relpath": "seed_extra.md",
                        # Deliberately unrelated — nothing from this text appears in the artifact.
                        # If the union were used, W140 would fire for seed-extra.
                        "text": "weather patterns precipitation forecast entirely unrelated content",
                    },
                ],
                global_seed_order=["seed-required", "seed-extra"],
                step_requirements={
                    # step 00 requires ONLY seed-required, not seed-extra
                    "00": ["seed-required"],
                },
                spec_artifacts={
                    "00_charter.json": {
                        "description": "authentication login endpoint validation security",
                    },
                },
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w140 = [e for e in rendered if "W140" in e]

            # seed-extra is global-only for step 00 → must NOT produce W140
            w140_extra = [e for e in w140 if "seed-extra" in e]
            self.assertEqual(
                w140_extra,
                [],
                msg=(
                    "W140 must NOT fire for seed-extra (global-only, not step-required for 00). "
                    f"Got: {w140_extra}"
                ),
            )

    def test_step_required_seed_with_low_overlap_still_fires_w140(self):
        """Sanity-check: seed-required IS in step_requirements["00"] and the artifact
        does NOT distill it → W140 must fire (as control, proving the above absence
        is meaningful, not just a vacuous pass because lint_seeds skipped all seeds).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    {
                        "seed_id": "seed-required",
                        "relpath": "seed_required.md",
                        "text": "completely unrelated document about weather patterns",
                    },
                    {
                        "seed_id": "seed-extra",
                        "relpath": "seed_extra.md",
                        "text": "another unrelated document",
                    },
                ],
                global_seed_order=["seed-required", "seed-extra"],
                step_requirements={
                    "00": ["seed-required"],  # required → W140 must fire when low overlap
                },
                spec_artifacts={
                    "00_charter.json": {
                        "goals": [{"goal_id": "goal-alpha"}],
                    },
                },
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w140 = [e for e in rendered if "W140" in e]
            self.assertTrue(
                any("seed-required" in e for e in w140),
                msg=(
                    "Control: W140 must fire for seed-required (step-required, low overlap). "
                    f"Got W140 lines: {w140}"
                ),
            )
            # seed-extra is still global-only → must NOT fire even in this scenario
            w140_extra = [e for e in w140 if "seed-extra" in e]
            self.assertEqual(
                w140_extra,
                [],
                msg=f"seed-extra (global-only) must not produce W140 even in control test. Got: {w140_extra}",
            )

    def test_two_step_requirements_seed_used_only_for_its_step(self):
        """seed-09 routes to step 09, seed-00 routes to step 00.

        The 09 artifact does not distill seed-00 (which is in global_seed_order
        but only required for step 00).  W140 must NOT fire for seed-00/09
        pair.  W140 for seed-09/09 may fire (low overlap control).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    {
                        "seed_id": "seed-00",
                        "relpath": "seed_00.md",
                        "text": "charter governance owner domain product strategy",
                    },
                    {
                        "seed_id": "seed-09",
                        "relpath": "seed_09.md",
                        "text": "implementation plan completely unrelated to artifact text",
                    },
                ],
                global_seed_order=["seed-00", "seed-09"],
                step_requirements={
                    "00": ["seed-00"],
                    "09": ["seed-09"],
                },
                spec_artifacts={
                    # Artifact for step 09 has zero overlap with seed-09 (triggers W140 for it)
                    # but also zero overlap with seed-00 — which must NOT trigger W140.
                    "09_impl_plan.json": {
                        "milestones": [{"milestone_id": "ms-alpha"}],
                    },
                },
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w140 = [e for e in rendered if "W140" in e]

            # seed-00 is NOT required for step 09 → no W140
            w140_seed00 = [e for e in w140 if "seed-00" in e]
            self.assertEqual(
                w140_seed00,
                [],
                msg=(
                    "W140 must not fire for seed-00 against step-09 artifact "
                    f"(seed-00 is not step-required for 09). Got: {w140_seed00}"
                ),
            )


class TestEmptyStepRequirementsNoFallback(unittest.TestCase):
    """TEST 3: explicit step_requirements[NN] = [] must suppress all seed-grounding
    checks for that step — no fallback to global_seed_order.

    Coverage gap: existing tests only confirm that a seed in global_seed_order but
    absent from step_requirements[step] is not flagged.  None of them check the
    short-circuit path triggered by `if not required_seeds: continue` in
    _check_seed_content_overlap, i.e. when the step key IS present but maps to [].

    Discrimination logic:
    - global_seed_order has "seed-global" with genuinely unrelated text
      ("weather forecast precipitation tornado") — low-overlap if evaluated.
    - step_requirements["09"] = [] (explicit empty list) for the spec artifact
      "09_impl_plan.json" whose content contains none of the global seed text.
    - A correct implementation (empty-step skip fires) → no W140 for step 09.
    - A broken implementation that falls back to global_seed_order → would check
      "seed-global" against the artifact → low overlap → emits W140 → test FAILS.

    The global seeds are declared in manifest["seeds"] (on disk) to avoid E520
    noise from the global_seed_order unknown-seed check.
    """

    def test_explicit_empty_step_requirements_suppresses_seed_check(self):
        """step_requirements["09"] = [] with a real spec artifact present must
        produce NO W140, confirming the empty-step short-circuit fires and no
        fallback to global_seed_order occurs.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    {
                        "seed_id": "seed-global",
                        "relpath": "seed_global.md",
                        # Genuinely unrelated text; if fallback occurred it would trigger W140.
                        "text": "weather forecast precipitation tornado isobar barometric pressure",
                    },
                ],
                global_seed_order=["seed-global"],
                step_requirements={
                    # Explicit empty list for step 09 — the key IS present, value is [].
                    "09": [],
                },
                spec_artifacts={
                    "09_impl_plan.json": {
                        "id": "impl-plan",
                        "milestones": [{"milestone_id": "ms-alpha", "title": "Phase one"}],
                    },
                },
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)

            # No W140 must fire for step 09.  A broken fallback to global_seed_order
            # would emit W140 for "seed-global" against "09_impl_plan.json" (low overlap).
            w140 = [e for e in rendered if "W140" in e]
            self.assertEqual(
                w140,
                [],
                msg=(
                    "W140 must not fire for step 09 when step_requirements['09'] = []. "
                    "An empty requirement list must short-circuit all seed-grounding "
                    "checks — there must be NO fallback to global_seed_order. "
                    f"Got W140 lines: {w140} (full errors: {rendered})"
                ),
            )

            # No seed-path E520 must fire: seed-global IS declared in manifest["seeds"]
            # and its on-disk file exists.  (Schema-validation E520s from the test manifest
            # lacking $schema are unrelated and filtered out here.)
            e520_seed = [e for e in rendered if "E520" in e and "seed-global" in e]
            self.assertEqual(
                e520_seed,
                [],
                msg=(
                    "No seed-path E520 expected — seed-global is declared and exists on disk. "
                    f"Got: {e520_seed}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
