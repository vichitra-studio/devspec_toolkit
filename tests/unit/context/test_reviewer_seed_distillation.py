"""Tests for reviewer.py seed-distillation check for late pipeline steps.

DEVSPEC-43 §3.9 / §6: _check_seed_distillation must route via the shared
seed_routing helper for ANY step (00–16c).  Existing reviewer tests only
confirm that step 06 SKIPS distillation (no seeds in manifest for step 06).

These tests verify that a LATE step (e.g. "09" or "14") with manifest-declared
seeds TRIGGERS the distillation check, producing a ReviewPair when key seed
terms are absent from the artifact.

DEVSPEC-43 Cycle-2 fix: _check_seed_distillation must accept git_root and
resolve seed paths against the host repo root, not os.path.dirname(spec_dir).
The nested-layout test (TestGitRootNestedLayout) discriminates this fix.
"""
from __future__ import annotations

import json
import os

from specdev_tools.context.reviewer import _check_seed_distillation


def _make_manifest_on_disk(tmp_path, *, global_seed_order, step_requirements, seeds_content):
    """Create spec/common/seed_manifest.json and seed files; return spec_dir str."""
    spec_dir = tmp_path / "spec"
    common_dir = spec_dir / "common"
    common_dir.mkdir(parents=True)

    seed_dir = tmp_path / "docs" / "seed"
    seed_dir.mkdir(parents=True)

    manifest_seeds = []
    for seed_id, text in seeds_content.items():
        rel_path = f"docs/seed/{seed_id.replace('-', '_')}.md"
        abs_path = tmp_path / rel_path
        abs_path.write_text(text, encoding="utf-8")
        manifest_seeds.append({"seed_id": seed_id, "path": rel_path})

    manifest = {
        "global_seed_order": global_seed_order,
        "seeds": manifest_seeds,
        "step_requirements": step_requirements,
    }
    (common_dir / "seed_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return str(spec_dir)


# ---------------------------------------------------------------------------
# D: _check_seed_distillation for late steps
# ---------------------------------------------------------------------------

class TestSeedDistillationLateStep:
    """_check_seed_distillation fires for late steps with manifest-routed seeds."""

    def test_step_09_fires_when_key_terms_missing(self, tmp_path):
        """A late-step (09) artifact missing distinctive seed terms → ReviewPair generated.

        Seed contains 'PostgreSQL', 'Kafka', 'Redis' (capitalised, non-common).
        Artifact is empty of those terms.  At least one distillation pair must be produced.
        """
        spec_dir = _make_manifest_on_disk(
            tmp_path,
            global_seed_order=["seed-tech-stack"],
            step_requirements={"09": ["seed-tech-stack"]},
            seeds_content={
                "seed-tech-stack": (
                    "Technology stack: PostgreSQL database, Kafka message broker, "
                    "Redis cache layer. All services deployed on Kubernetes."
                ),
            },
        )
        # Artifact mentions nothing about PostgreSQL/Kafka/Redis
        artifact = {
            "id": "impl-plan",
            "milestones": [{"milestone_id": "ms-alpha", "description": "Phase one work"}],
        }
        artifact_path = os.path.join(spec_dir, "09_impl_plan.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "09", spec_dir)
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]
        assert len(distillation_pairs) >= 1, (
            "Expected at least one seed_distillation pair for step 09 artifact "
            f"missing seed key terms. Got: {distillation_pairs}"
        )

    def test_step_09_no_pair_when_terms_present(self, tmp_path):
        """If the artifact contains all of the seed's key acronym/proper-noun terms,
        no distillation pair fires.

        The distillation check extracts capitalized acronyms (ALL_CAPS) and
        proper nouns (Title-case >=3 chars) minus _COMMON_WORDS.  We use only
        ALL_CAPS acronyms here (PostgreSQL, Kafka, Redis are Title-case but
        'PostgreSQL' begins uppercase — use fully-uppercase versions to avoid
        ambiguity with single leading-cap words like 'Technology' that the
        proper-noun regex also picks up).

        Strategy: write a seed with ONLY acronyms that the artifact also contains,
        so all extracted key terms are present → zero pairs.
        """
        spec_dir = _make_manifest_on_disk(
            tmp_path,
            global_seed_order=["seed-tech-stack"],
            step_requirements={"09": ["seed-tech-stack"]},
            seeds_content={
                # Use ALL-CAPS acronyms only — no leading-cap words like "Technology",
                # "Database", "Cache" etc. that would be extracted by _PROPER_NOUN_PATTERN
                # but might not appear in the artifact.
                "seed-tech-stack": "POSTGRESQL KAFKA REDIS services deployed",
            },
        )
        # Artifact echoes every capitalized acronym from the seed
        artifact = {
            "id": "impl-plan",
            "description": "POSTGRESQL KAFKA REDIS based implementation",
            "milestones": [],
        }
        artifact_path = os.path.join(spec_dir, "09_impl_plan.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "09", spec_dir)
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]
        assert len(distillation_pairs) == 0, (
            "Expected no seed_distillation pairs when artifact contains all seed acronym terms. "
            f"Got: {distillation_pairs}"
        )

    def test_step_14_fires_when_key_terms_missing(self, tmp_path):
        """Step 14 also routes seeds correctly — same behaviour as step 09."""
        spec_dir = _make_manifest_on_disk(
            tmp_path,
            global_seed_order=["seed-domain-model"],
            step_requirements={"14": ["seed-domain-model"]},
            seeds_content={
                "seed-domain-model": (
                    "Domain model entities: UserProfile, ContentItem, PublishEvent, "
                    "SubscriptionTier. GraphQL API gateway pattern."
                ),
            },
        )
        # Artifact is unrelated
        artifact = {
            "id": "roadmap",
            "phases": [{"phase_id": "ph-one", "description": "Initial phase"}],
        }
        artifact_path = os.path.join(spec_dir, "14_roadmap.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "14", spec_dir)
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]
        assert len(distillation_pairs) >= 1, (
            "Expected seed_distillation pair for step 14 artifact missing domain model terms. "
            f"Got: {distillation_pairs}"
        )

    def test_step_not_in_requirements_skips_check(self, tmp_path):
        """If the manifest has no seeds for the step, distillation check returns []."""
        spec_dir = _make_manifest_on_disk(
            tmp_path,
            global_seed_order=["seed-overview"],
            step_requirements={"00": ["seed-overview"]},  # step 09 NOT listed
            seeds_content={
                "seed-overview": "PostgreSQL Kafka Redis all important terms here",
            },
        )
        artifact = {"id": "impl-plan", "milestones": []}
        artifact_path = os.path.join(spec_dir, "09_impl_plan.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "09", spec_dir)
        assert pairs == [], (
            "Distillation must return [] when step 09 has no manifest seeds. "
            f"Got: {pairs}"
        )

    def test_step_09_does_not_pick_up_step_00_seeds(self, tmp_path):
        """Global seed routed to step 00 must NOT affect step 09 distillation.

        seed-global is in global_seed_order but only required for step 00.
        seed-09-only is required for step 09.
        The distillation check for step 09 must use ONLY seed-09-only
        (step_seed_ids, not the union), so seed-global terms are irrelevant
        and must not trigger any pair for the step-09 artifact.
        """
        spec_dir = _make_manifest_on_disk(
            tmp_path,
            global_seed_order=["seed-global", "seed-09-only"],
            step_requirements={
                "00": ["seed-global"],
                "09": ["seed-09-only"],
            },
            seeds_content={
                # seed-global has distinctive terms NOT in the artifact
                "seed-global": "Charter GovernanceBoard ExecutiveSponsor StrategicObjective",
                # seed-09-only is referenced in the artifact → no distillation pair
                "seed-09-only": "PostgreSQL Kafka Redis implementation details",
            },
        )
        # Artifact echoes seed-09-only terms but NOT seed-global terms
        artifact = {
            "id": "impl-plan",
            "description": "PostgreSQL Kafka Redis based implementation",
        }
        artifact_path = os.path.join(spec_dir, "09_impl_plan.json")
        pairs = _check_seed_distillation(artifact, artifact_path, "09", spec_dir)
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]

        # seed-global terms are not checked for step 09 → no pair for them
        global_seed_pairs = [
            p for p in distillation_pairs
            if "seed_global" in p.source.id or "GovernanceBoard" in p.concern
        ]
        assert global_seed_pairs == [], (
            "Distillation must not fire for seed-global terms against step-09 artifact "
            f"(seed-global not step-required for 09). Got: {global_seed_pairs}"
        )
        # seed-09-only terms ARE in artifact → no pair for it either (pass condition)
        assert len(distillation_pairs) == 0, (
            "No distillation pairs expected: step-09-required seed terms are present "
            f"in artifact. Got: {distillation_pairs}"
        )


# ---------------------------------------------------------------------------
# DEVSPEC-43 Cycle-2: git_root authority fix — nested layout discriminator
# ---------------------------------------------------------------------------

class TestGitRootNestedLayout:
    """_check_seed_distillation resolves seed paths via git_root, not dirname(spec_dir).

    Layout under tmp_path:
        tmp/                         ← git_root (host repo root)
          docs/seed/tech_stack.md    ← seed file, path relative to git_root
          src/
            project/
              spec/                  ← spec_dir
                common/
                  seed_manifest.json
                09_impl_plan.json

    dirname(spec_dir) = tmp/src/project  (NOT tmp)
    git_root          = tmp

    The seed manifest records path "docs/seed/tech_stack.md" relative to git_root.

    OLD behavior (dirname only): resolves to tmp/src/project/docs/seed/tech_stack.md
      → file not found → OSError → seed skipped → ZERO pairs (false negative).
    NEW behavior (git_root param): resolves to tmp/docs/seed/tech_stack.md
      → file found → key terms extracted → distillation pair produced (correct).

    The "well-grounded" variant (artifact contains all seed terms) confirms that
    with git_root the check PASSES (no pair) when terms are present.
    """

    def _build_nested_layout(self, tmp_path, *, artifact_text: str, seed_text: str) -> tuple[str, dict, str]:
        """Create the nested layout; return (spec_dir, artifact_dict, artifact_path)."""
        git_root = tmp_path  # host repo root

        # Seed file at git_root-relative path
        seed_rel = "docs/seed/tech_stack.md"
        seed_abs = git_root / seed_rel
        seed_abs.parent.mkdir(parents=True)
        seed_abs.write_text(seed_text, encoding="utf-8")

        # Nested spec dir
        spec_dir = git_root / "src" / "project" / "spec"
        common_dir = spec_dir / "common"
        common_dir.mkdir(parents=True)

        manifest = {
            "global_seed_order": ["seed-tech-stack"],
            "seeds": [{"seed_id": "seed-tech-stack", "path": seed_rel}],
            "step_requirements": {"09": ["seed-tech-stack"]},
        }
        (common_dir / "seed_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        artifact = {"id": "impl-plan", "description": artifact_text}
        artifact_path = str(spec_dir / "09_impl_plan.json")
        return str(spec_dir), artifact, artifact_path

    def test_git_root_resolves_seed_nested_layout_fires(self, tmp_path):
        """With git_root provided, seed is found and a distillation pair fires for missing terms.

        OLD code (dirname only) would silently skip the seed (file not found at
        tmp/src/project/docs/seed/tech_stack.md) → zero pairs (false negative).
        NEW code (git_root param) resolves to tmp/docs/seed/tech_stack.md → pair fires.
        """
        seed_text = "Technology stack uses POSTGRESQL KAFKA REDIS services"
        artifact_text = "Generic implementation plan with no domain-specific content"

        spec_dir, artifact, artifact_path = self._build_nested_layout(
            tmp_path, artifact_text=artifact_text, seed_text=seed_text
        )
        git_root = str(tmp_path)

        pairs = _check_seed_distillation(
            artifact, artifact_path, "09", spec_dir, git_root=git_root
        )
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]

        assert len(distillation_pairs) >= 1, (
            "Expected at least one seed_distillation pair when git_root resolves the seed "
            "in a nested layout and artifact is missing seed terms. "
            f"Got: {distillation_pairs}. "
            "This would pass with the OLD dirname-only code (seed silently skipped), "
            "confirming the test discriminates the fix."
        )

    def test_git_root_resolves_seed_nested_layout_no_pair_when_terms_present(self, tmp_path):
        """With git_root provided and artifact containing all seed acronyms, no pair fires.

        Confirms that git_root resolution is working (seed found) and the check
        correctly produces no pairs when the artifact contains the seed terms.
        """
        seed_text = "POSTGRESQL KAFKA REDIS services"
        artifact_text = "POSTGRESQL KAFKA REDIS based implementation"

        spec_dir, artifact, artifact_path = self._build_nested_layout(
            tmp_path, artifact_text=artifact_text, seed_text=seed_text
        )
        git_root = str(tmp_path)

        pairs = _check_seed_distillation(
            artifact, artifact_path, "09", spec_dir, git_root=git_root
        )
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]

        assert len(distillation_pairs) == 0, (
            "Expected zero distillation pairs when artifact contains all seed terms "
            f"(git_root resolves seed correctly). Got: {distillation_pairs}"
        )

    def test_no_git_root_nested_layout_misses_seed(self, tmp_path):
        """Without git_root, the old dirname heuristic misses the seed in a nested layout.

        This test documents and verifies the PRE-FIX behavior: when git_root is
        omitted, dirname(spec_dir) = tmp/src/project, which does NOT contain the
        seed file (it lives at tmp/docs/seed/...).  The seed is silently skipped
        (OSError caught) and zero pairs are produced — a false negative that the fix
        addresses by threading git_root.
        """
        seed_text = "Technology stack uses POSTGRESQL KAFKA REDIS services"
        artifact_text = "Generic implementation plan with no domain-specific content"

        spec_dir, artifact, artifact_path = self._build_nested_layout(
            tmp_path, artifact_text=artifact_text, seed_text=seed_text
        )

        # Call WITHOUT git_root — uses dirname(spec_dir_abs) = tmp/src/project
        pairs = _check_seed_distillation(
            artifact, artifact_path, "09", spec_dir
            # git_root intentionally omitted
        )
        distillation_pairs = [p for p in pairs if p.check_type == "seed_distillation"]

        # The seed at tmp/src/project/docs/seed/tech_stack.md does not exist →
        # OSError → seed skipped → zero pairs (this is the false-negative the fix corrects).
        assert len(distillation_pairs) == 0, (
            "Baseline: WITHOUT git_root, dirname heuristic points to the wrong root "
            "so the seed is not found and no pairs fire. "
            f"Got: {distillation_pairs}"
        )
