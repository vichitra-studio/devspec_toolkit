"""End-to-end integration test for manifest-driven seed routing (DEVSPEC-43 §6).

Exercises the full chain across three components — seed_lint, structure.py,
reviewer.py — with a single fixture that routes a NON-DEFAULT seed to a late
step (step "09") and also exercises the bare "16" umbrella key (§G).

One fixture, three component assertions.

Placement: tests/integration/ — matches the majority pytest-convention used by
other integration tests in this directory (NOT the main()-style outlier in
test_seed_manifest.py).
"""
from __future__ import annotations

import json
import os

import pytest

from specdev_tools.validation.seed_lint import lint_seeds
from specdev_tools.core.errors import render_errors
from specdev_tools.context.structure import get_step_structure
from specdev_tools.context.reviewer import _check_seed_distillation

# Toolkit root for repo_root args.
_TOOLKIT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)


@pytest.fixture()
def late_step_seed_project(tmp_path):
    """Build a host project with:
      - seed-domain-model routed to step "09" (non-default, late step)
      - seed-impl routed to step "16" umbrella (bare key, §G)
      - a 09_impl_plan.json artifact that distills seed-domain-model terms
      - an impl_context/ms_alpha_plan.json artifact that distills seed-impl terms

    Returns a dict of paths used by the tests.
    """
    # ------------------------------------------------------------------ dirs
    spec_dir = tmp_path / "spec"
    common_dir = spec_dir / "common"
    impl_dir = spec_dir / "impl_context"
    seed_dir = tmp_path / "docs" / "seed"
    for d in [common_dir, impl_dir, seed_dir]:
        d.mkdir(parents=True)

    # ---------------------------------------------------------------- seeds
    seed_domain_model_path = seed_dir / "seed_domain_model.md"
    seed_domain_model_path.write_text(
        # Use space-separated proper nouns that the _PROPER_NOUN_PATTERN regex
        # (\b[A-Z][a-z]{2,}\b) will extract.  CamelCase words like "UserProfile"
        # don't produce \b boundaries between the two halves so they won't be
        # extracted — use simple capitalized words instead.
        # These terms also appear in the 09 artifact below.
        "Postgres Kafka Redis services for storage messaging caching",
        encoding="utf-8",
    )

    seed_impl_path = seed_dir / "seed_impl.md"
    seed_impl_path.write_text(
        "Implementation context: Kubernetes Terraform Helm deployment pipeline GitOps ArgoCD",
        encoding="utf-8",
    )

    # -------------------------------------------------------------- manifest
    seed_roadmap_path = seed_dir / "seed_roadmap.md"
    seed_roadmap_path.write_text(
        "Roadmap context: Sprint Milestone Release Iteration Backlog Epics",
        encoding="utf-8",
    )

    manifest = {
        "global_seed_order": ["seed-domain-model", "seed-impl", "seed-roadmap"],
        "seeds": [
            {"seed_id": "seed-domain-model", "path": "docs/seed/seed_domain_model.md"},
            {"seed_id": "seed-impl", "path": "docs/seed/seed_impl.md"},
            {"seed_id": "seed-roadmap", "path": "docs/seed/seed_roadmap.md"},
        ],
        "step_requirements": {
            "09": ["seed-domain-model"],    # late-step route
            "14": ["seed-roadmap"],         # second late-step route (AC §6)
            "16": ["seed-impl"],            # bare umbrella key (§G)
        },
    }
    (common_dir / "seed_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # -------------------------------------------------------------- artifacts
    # Step 09 artifact — distills domain model terms (no W140).
    # Uses the same simple proper nouns as the seed so W140 doesn't fire.
    impl_plan = {
        "id": "impl-plan",
        "description": (
            "Postgres database for storage, Kafka messaging layer, Redis caching service."
        ),
    }
    (spec_dir / "09_impl_plan.json").write_text(json.dumps(impl_plan), encoding="utf-8")

    # Step 14 artifact — distills roadmap seed terms (no W140).
    roadmap_artifact = {
        "id": "roadmap",
        "description": (
            "Sprint planning with Milestone targets. Release Iteration tracks Backlog Epics."
        ),
    }
    (spec_dir / "14_roadmap.json").write_text(json.dumps(roadmap_artifact), encoding="utf-8")

    # impl_context artifact — distills impl seed terms (no W140 for step 16)
    ms_plan = {
        "id": "ms-alpha",
        "description": (
            "Kubernetes deployment via Terraform and Helm. "
            "GitOps workflow managed by ArgoCD pipeline."
        ),
    }
    (impl_dir / "ms_alpha_plan.json").write_text(json.dumps(ms_plan), encoding="utf-8")

    return {
        "spec_dir": str(spec_dir),
        "tmp_path": str(tmp_path),
    }


# ---------------------------------------------------------------------------
# E(a): seed_lint emits no false W553 (range) for step "09" or "16"
# ---------------------------------------------------------------------------

class TestSeedLintNoFalseWarnings:
    """seed_lint emits no false W553 for late-step routes or bare "16" key."""

    def test_no_w553_for_late_step_09(self, late_step_seed_project):
        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=late_step_seed_project["spec_dir"],
            project_root=late_step_seed_project["tmp_path"],
        )
        rendered = render_errors(errors)
        w553 = [e for e in rendered if "W553" in e]
        assert w553 == [], f"No W553 expected for known step '09'. Got: {w553}"

    def test_no_w553_for_bare_16_umbrella_key(self, late_step_seed_project):
        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=late_step_seed_project["spec_dir"],
            project_root=late_step_seed_project["tmp_path"],
        )
        rendered = render_errors(errors)
        w553 = [e for e in rendered if "W553" in e]
        assert w553 == [], f"No W553 expected for bare '16' umbrella key. Got: {w553}"

    def test_no_w140_for_step_09_artifact_with_sufficient_overlap(self, late_step_seed_project):
        """Artifact distills seed-domain-model terms → W140 must not fire for that pair."""
        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=late_step_seed_project["spec_dir"],
            project_root=late_step_seed_project["tmp_path"],
        )
        rendered = render_errors(errors)
        w140 = [e for e in rendered if "W140" in e and "seed-domain-model" in e]
        assert w140 == [], (
            "No W140 expected for seed-domain-model/09_impl_plan pair "
            f"(artifact has sufficient overlap). Got: {w140}"
        )

    def test_no_w553_for_late_step_14(self, late_step_seed_project):
        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=late_step_seed_project["spec_dir"],
            project_root=late_step_seed_project["tmp_path"],
        )
        rendered = render_errors(errors)
        w553 = [e for e in rendered if "W553" in e]
        assert w553 == [], f"No W553 expected for known step '14'. Got: {w553}"

    def test_no_w140_for_step_14_artifact_with_sufficient_overlap(self, late_step_seed_project):
        """Artifact distills seed-roadmap terms → W140 must not fire for that pair."""
        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=late_step_seed_project["spec_dir"],
            project_root=late_step_seed_project["tmp_path"],
        )
        rendered = render_errors(errors)
        w140 = [e for e in rendered if "W140" in e and "seed-roadmap" in e]
        assert w140 == [], (
            "No W140 expected for seed-roadmap/14_roadmap pair "
            f"(artifact has sufficient overlap). Got: {w140}"
        )

    def test_no_w140_for_impl_context_artifact_with_bare_16_key(self, late_step_seed_project):
        """impl_context artifact distills seed-impl (16 umbrella) → no W140."""
        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=late_step_seed_project["spec_dir"],
            project_root=late_step_seed_project["tmp_path"],
        )
        rendered = render_errors(errors)
        w140 = [e for e in rendered if "W140" in e and "seed-impl" in e]
        assert w140 == [], (
            "No W140 expected for seed-impl/ms_alpha_plan pair "
            f"(artifact has sufficient overlap). Got: {w140}"
        )


# ---------------------------------------------------------------------------
# E(b): structure.py surfaces seed in seeds_required for step "09"
# ---------------------------------------------------------------------------

class TestStructureSeedsRequiredE2E:
    """get_step_structure returns manifest seeds for step 09."""

    def test_seeds_required_contains_seed_domain_model(self, late_step_seed_project):
        result = get_step_structure(
            "09",
            late_step_seed_project["spec_dir"],
            _TOOLKIT_ROOT,
        )
        seeds = result["seeds_required"]
        assert "seed-domain-model" in seeds, (
            f"seed-domain-model must appear in seeds_required for step 09. Got: {seeds}"
        )

    def test_seeds_required_does_not_contain_seed_impl(self, late_step_seed_project):
        """seed-impl is routed to step '16' only, not step '09'."""
        result = get_step_structure(
            "09",
            late_step_seed_project["spec_dir"],
            _TOOLKIT_ROOT,
        )
        seeds = result["seeds_required"]
        assert "seed-impl" not in seeds, (
            f"seed-impl is step-16-only and must not appear for step 09. Got: {seeds}"
        )

    def test_seeds_required_contains_seed_roadmap_for_step_14(self, late_step_seed_project):
        """seed-roadmap is routed to step '14'; seeds_required must include it."""
        result = get_step_structure(
            "14",
            late_step_seed_project["spec_dir"],
            _TOOLKIT_ROOT,
        )
        seeds = result["seeds_required"]
        assert "seed-roadmap" in seeds, (
            f"seed-roadmap must appear in seeds_required for step 14. Got: {seeds}"
        )

    def test_seeds_required_does_not_contain_seed_domain_model_for_step_14(
        self, late_step_seed_project
    ):
        """seed-domain-model is step-09-only; must not appear for step 14."""
        result = get_step_structure(
            "14",
            late_step_seed_project["spec_dir"],
            _TOOLKIT_ROOT,
        )
        seeds = result["seeds_required"]
        assert "seed-domain-model" not in seeds, (
            f"seed-domain-model is step-09-only and must not appear for step 14. Got: {seeds}"
        )


# ---------------------------------------------------------------------------
# E(c): reviewer.py _check_seed_distillation covers seed for step "09"
# ---------------------------------------------------------------------------

class TestReviewerDistillationE2E:
    """_check_seed_distillation covers manifest-routed seed for step 09."""

    def test_distillation_passes_when_artifact_contains_seed_terms(self, late_step_seed_project):
        """Artifact with seed-domain-model terms → no distillation pair (PASS).

        The seed uses simple capitalized proper nouns that _PROPER_NOUN_PATTERN
        (\b[A-Z][a-z]{2,}\b) extracts.  The artifact echoes all of them.
        """
        spec_dir = late_step_seed_project["spec_dir"]
        # Artifact echoes the proper nouns extracted from the seed
        artifact = {
            "id": "impl-plan",
            "description": "Postgres database for storage Kafka messaging Redis caching service",
        }
        artifact_path = os.path.join(spec_dir, "09_impl_plan.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "09", spec_dir)
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]
        assert len(distillation_pairs) == 0, (
            "Artifact with seed terms must not produce distillation pairs. "
            f"Got: {distillation_pairs}"
        )

    def test_distillation_fires_when_artifact_missing_seed_terms(self, late_step_seed_project):
        """Artifact that omits seed-domain-model terms → at least one distillation pair.

        The seed has 'Postgres', 'Kafka', 'Redis' (proper nouns that extract).
        The artifact has none of them — distillation pair must fire.
        """
        spec_dir = late_step_seed_project["spec_dir"]
        # Artifact uses only generic lowercase words — none match the seed's proper nouns
        artifact = {
            "id": "impl-plan",
            "description": "generic implementation plan without any specific terminology here",
        }
        artifact_path = os.path.join(spec_dir, "09_impl_plan.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "09", spec_dir)
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]
        assert len(distillation_pairs) >= 1, (
            "Artifact missing seed terms must produce at least one distillation pair. "
            f"Got: {distillation_pairs}"
        )


# ---------------------------------------------------------------------------
# §G: bare "16" umbrella key at seed_lint integration level
# ---------------------------------------------------------------------------

class TestBare16UmbrellaKeyE2E:
    """seed_lint union for impl_context artifacts includes bare step_requirements["16"] seeds."""

    def test_seed_impl_included_for_impl_context_artifact(self, late_step_seed_project):
        """seed-impl is routed via bare "16" key.

        The impl_context artifact distills seed-impl terms → no W140.
        This confirms seed-impl was included in the required set for step "16"
        (as opposed to not being checked at all, which would also produce no W140).

        Cross-check: alter the artifact to be empty and confirm W140 DOES fire
        for seed-impl, proving it was checked.
        """
        spec_dir = late_step_seed_project["spec_dir"]
        tmp = late_step_seed_project["tmp_path"]

        # Overwrite the impl_context artifact with empty content
        impl_artifact_path = os.path.join(spec_dir, "impl_context", "ms_alpha_plan.json")
        with open(impl_artifact_path, "w", encoding="utf-8") as f:
            json.dump({"id": "ms-alpha", "description": "nothing related here"}, f)

        errors = lint_seeds(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=spec_dir,
            project_root=tmp,
        )
        rendered = render_errors(errors)
        # With empty artifact, W140 must fire for seed-impl (proving it's checked)
        w140_impl = [e for e in rendered if "W140" in e and "seed-impl" in e]
        assert len(w140_impl) >= 1, (
            "W140 must fire for seed-impl when impl_context artifact lacks distillation "
            f"(confirms seed-impl is checked for step '16'). Got W140: {rendered}"
        )
