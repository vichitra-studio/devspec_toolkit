"""Tests for W553 SEED_STEP_UNKNOWN (repurposed from the old SEED_STEP_OUT_OF_RANGE).

DEVSPEC-43 §3.9: seed_lint now accepts any pipeline step in step_requirements
(the old "out of range" gate is gone).  W553 is repurposed to fire when a key
is NOT a known pipeline step (phantom / typo detection).

Covers:
  B1 — late steps (e.g. "09") produce no W553 (accepted range widened).
  B2 — phantom/typo keys ("9", "02b", "17") produce W553 SEED_STEP_UNKNOWN.
  B3 — known steps including "16" and "16b" produce no W553.
  B4 — bare "16" key + impl_context artifact: seed_lint union includes the seed
       (no false W140 / W553), tested at the seed_lint integration level.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from specdev_tools.validation.seed_lint import lint_seeds
from specdev_tools.core.errors import render_errors

# Absolute path to toolkit root (for repo_root / step_order.json lookup).
_TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir))


def _build_project(
    tmpdir: str,
    *,
    seeds: list[dict],            # {seed_id, relpath, text}
    global_seed_order: list[str],
    step_requirements: dict,
    spec_artifacts: dict | None = None,
) -> str:
    """Build a minimal project structure and return spec_dir."""
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
            # Support nested paths like "impl_context/ms_alpha_plan.json"
            target = os.path.join(spec_dir, filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f)

    return spec_dir


def _seed_tuple(seed_id: str, relpath: str, text: str = "seed content text") -> dict:
    return {"seed_id": seed_id, "relpath": relpath, "text": text}


class TestW553SeedStepUnknown(unittest.TestCase):
    """W553 SEED_STEP_UNKNOWN — phantom step detection."""

    # ------------------------------------------------------------------
    # B1: late steps (e.g. "09") produce NO W553
    # ------------------------------------------------------------------

    def test_late_step_09_no_w553(self):
        """step_requirements["09"] is a known pipeline step → no W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-test-philosophy", "seed_test_philosophy.md")],
                global_seed_order=["seed-test-philosophy"],
                step_requirements={"09": ["seed-test-philosophy"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(w553, [], f"No W553 expected for known step '09'. Got: {w553}")

    def test_late_step_14_no_w553(self):
        """step_requirements["14"] is a known pipeline step → no W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-domain-model", "seed_domain_model.md")],
                global_seed_order=["seed-domain-model"],
                step_requirements={"14": ["seed-domain-model"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(w553, [], f"No W553 expected for known step '14'. Got: {w553}")

    # ------------------------------------------------------------------
    # B2: phantom / typo step keys fire W553
    # ------------------------------------------------------------------

    def test_unpadded_step_9_fires_w553(self):
        """step_requirements["9"] is NOT a known step (should be "09") → W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-overview", "seed_overview.md")],
                global_seed_order=["seed-overview"],
                step_requirements={"9": ["seed-overview"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertTrue(
                any("9" in e for e in w553),
                msg=f"W553 must fire for phantom step '9'. Got: {w553}",
            )

    def test_nonexistent_step_02b_fires_w553(self):
        """step_requirements["02b"] is not a pipeline step → W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-overview", "seed_overview.md")],
                global_seed_order=["seed-overview"],
                step_requirements={"02b": ["seed-overview"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertTrue(
                any("02b" in e for e in w553),
                msg=f"W553 must fire for phantom step '02b'. Got: {w553}",
            )

    def test_step_17_beyond_pipeline_fires_w553(self):
        """step_requirements["17"] exceeds pipeline range → W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-overview", "seed_overview.md")],
                global_seed_order=["seed-overview"],
                step_requirements={"17": ["seed-overview"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertTrue(
                any("17" in e for e in w553),
                msg=f"W553 must fire for phantom step '17'. Got: {w553}",
            )

    # ------------------------------------------------------------------
    # B3: Trinity and known steps do NOT fire W553
    # ------------------------------------------------------------------

    def test_step_16_no_w553(self):
        """Bare step "16" is a known pipeline step → no W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-overview", "seed_overview.md")],
                global_seed_order=["seed-overview"],
                step_requirements={"16": ["seed-overview"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(w553, [], f"No W553 expected for known step '16'. Got: {w553}")

    def test_step_16b_no_w553(self):
        """step "16b" is a known trinity sub-phase → no W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-overview", "seed_overview.md")],
                global_seed_order=["seed-overview"],
                step_requirements={"16b": ["seed-overview"]},
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(w553, [], f"No W553 expected for known step '16b'. Got: {w553}")

    def test_all_trinity_sub_phases_no_w553(self):
        """16a, 16b, 16c are all known steps → none produce W553."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed_tuple("seed-overview", "seed_overview.md"),
                    _seed_tuple("seed-impl", "seed_impl.md"),
                ],
                global_seed_order=["seed-overview", "seed-impl"],
                step_requirements={
                    "16":  ["seed-overview"],
                    "16a": ["seed-overview"],
                    "16b": ["seed-impl"],
                    "16c": ["seed-impl"],
                },
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(w553, [], f"No W553 for any trinity sub-phase. Got: {w553}")

    # ------------------------------------------------------------------
    # B4: bare "16" key + impl_context artifact: seed included in union
    # (seed_lint integration level, complementing test_seed_routing.py helper tests)
    # ------------------------------------------------------------------

    def test_impl_context_artifact_with_bare_16_key_no_false_w140_w553(self):
        """seed-x routed via step_requirements["16"] only (no 16a/16b/16c entry).

        An impl_context artifact (path contains 'impl_context/') maps to step "16"
        via _step_from_path.  The seed-x should be required for step "16" → either:
          - seed-x distills into the artifact (no W140), or
          - the artifact has low overlap, but seed-x IS checked (W140 may fire for it).

        What must NOT happen: W553 for the bare "16" key or silence on seed-x
        (it should be in the step_required set and thus checked).

        To make this deterministic: give the artifact sufficient overlap with seed-x
        so W140 does NOT fire — proving seed-x was included in the required set and
        passed the overlap threshold (as opposed to not being checked at all).
        """
        seed_text = "authentication login endpoint validation security xyzzy"
        artifact_data = {
            "id": "ms-alpha",
            "description": "authentication login endpoint validation security xyzzy implementation",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-x", "seed_x.md", text=seed_text)],
                global_seed_order=["seed-x"],
                step_requirements={
                    "16": ["seed-x"],   # bare key only, no 16a/16b/16c
                },
                spec_artifacts={
                    "impl_context/ms_alpha_plan.json": artifact_data,
                },
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)
            # No W553 for the "16" key
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(w553, [], f"No W553 expected for bare '16' key. Got: {w553}")
            # Sufficient overlap → no W140 for seed-x (confirms seed-x was checked
            # and passed the overlap threshold, not skipped)
            w140 = [e for e in rendered if "W140" in e and "seed-x" in e]
            self.assertEqual(
                w140,
                [],
                msg=(
                    "W140 must not fire for seed-x (overlap is sufficient). "
                    "If it fires, either seed-x was incorrectly routed or the overlap "
                    f"algorithm degraded. Got: {w140}"
                ),
            )


class TestE520UnknownSeedIdLintIntegration(unittest.TestCase):
    """TEST 2: lint_seeds emits E520 when step_requirements references a
    seed_id that is NOT declared in manifest["seeds"].

    Coverage gap: test_seed_routing.py::TestResolveSeedPaths::test_omits_unknown_seed_id
    only verifies that resolve_seed_paths SILENTLY OMITS unknown IDs at the helper layer.
    It does NOT test that lint_seeds raises E520 at the integration boundary — those are
    separate paths.

    Discrimination logic:
    - manifest["seeds"] declares only "seed-known" (with a real on-disk file).
    - step_requirements["04"] references "seed-ghost", which is NOT in manifest["seeds"].
    - lint_seeds must fire E520 referencing "seed-ghost".
    - If the `if sid not in seed_id_set` guard in seed_lint.py were removed or
      bypassed, no E520 would fire and this assertion would fail.
    """

    def test_unknown_seed_id_in_step_requirements_fires_e520(self):
        """step_requirements["04"] references "seed-ghost" which is not in
        manifest["seeds"] → lint_seeds must emit E520 naming "seed-ghost".

        Using a KNOWN pipeline step (04) isolates E520 from W553; a phantom
        step would produce W553 noise that could mask the E520 signal we need.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed_tuple("seed-known", "seed_known.md",
                                   text="authentication login endpoint validation security")],
                global_seed_order=["seed-known"],
                step_requirements={
                    "04": ["seed-ghost"],   # "seed-ghost" NOT in manifest["seeds"]
                },
            )
            errors = lint_seeds(repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir)
            rendered = render_errors(errors)

            # E520 must fire and name the unknown seed_id.
            e520 = [e for e in rendered if "E520" in e and "seed-ghost" in e]
            self.assertTrue(
                len(e520) >= 1,
                msg=(
                    "E520 must fire for step_requirements['04'] referencing undeclared "
                    f"seed_id 'seed-ghost'. Got rendered errors: {rendered}"
                ),
            )

            # W553 must NOT fire — "04" is a known pipeline step.
            w553 = [e for e in rendered if "W553" in e]
            self.assertEqual(
                w553,
                [],
                msg=(
                    "W553 must not fire for known step '04'. "
                    f"Got: {w553}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
