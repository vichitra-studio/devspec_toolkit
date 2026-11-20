"""Unit tests for specdev_tools/context/reviewer.py.

Covers the checklist-step set, the gating of ``_check_acceptance_gap`` on it
(steps 16a, 16b, 16c share vc:16-impl-context), the verdict rule, and that the
structural pass reports nothing (the 1.1.1 ``trace`` arrays it counted are gone).
"""
from __future__ import annotations

import pytest

from specdev_tools.context.reviewer import (
    _CHECKLIST_STEPS,
    _check_acceptance_gap,
    _compute_verdict,
    review_artifact,
    StructuralReview,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upstream(frs=None, apis=None, components=None, acs_per_fr=None):
    """Build a minimal upstream spec tuple list.

    frs        -- list of fr_id strings, e.g. ["fr-post-publish"]
    apis       -- list of api_id strings, e.g. ["api-post-page"]
    components -- list of component_id strings, e.g. ["ghost-cms"]
    acs_per_fr -- dict {fr_id: [ac_id, ...]} to add acceptance_criteria
    """
    frs = frs or []
    apis = apis or []
    components = components or []
    acs_per_fr = acs_per_fr or {}

    fr_list = []
    for fr_id in frs:
        entry = {"fr_id": fr_id, "statement": f"FR: {fr_id}"}
        if fr_id in acs_per_fr:
            # Use criterion_id — the actual field name in step 04 spec ACs,
            # which ends in _id and is therefore collected by _collect_id_values.
            entry["acceptance_criteria"] = [
                {"criterion_id": ac_id, "text": f"AC text for {ac_id}"}
                for ac_id in acs_per_fr[fr_id]
            ]
        fr_list.append(entry)

    api_list = [{"api_id": api_id} for api_id in apis]
    comp_list = [{"component_id": cid} for cid in components]

    spec_data = {
        "functional_requirements": fr_list,
        "apis": api_list,
        "components": comp_list,
    }
    return [("spec/04_fr_list.json", spec_data)]


def _artifact(trace_fr_ids=None, scope_apis=None, scope_components=None,
              rules=None):
    """Build a minimal invariant-style artifact (step 06)."""
    trace_fr_ids = trace_fr_ids or []
    scope_apis = scope_apis or []
    scope_components = scope_components or []
    rules = rules or []

    if not rules and trace_fr_ids:
        rules = [
            {
                "inv_id": f"inv-{fr_id}",
                "description": f"Invariant for {fr_id}",
                "language": "cel",
                "expression": "true",
                "scope": {
                    "components": scope_components,
                    "apis": scope_apis,
                },
                "trace": [{"type": "fr", "id": fr_id}],
            }
            for fr_id in trace_fr_ids
        ]
    return {"id": "invariants-catalog", "rules": rules}


# ---------------------------------------------------------------------------
# 1. _CHECKLIST_STEPS constant
# ---------------------------------------------------------------------------

class TestChecklistSteps:
    def test_step_16_not_in_checklist_steps(self):
        # Step 16 is the Trinity Anchor (vc:16-anchor) — scope/ownership/drift,
        # no checklist. The anchor split removed step 16 from this set.
        assert "16" not in _CHECKLIST_STEPS

    def test_step_06_not_in_checklist_steps(self):
        assert "06" not in _CHECKLIST_STEPS

    def test_step_07_not_in_checklist_steps(self):
        assert "07" not in _CHECKLIST_STEPS

    def test_step_16a_in_checklist_steps(self):
        # 16a uses vc:16-impl-context and authors the checklist.
        assert "16a" in _CHECKLIST_STEPS

    def test_step_16b_in_checklist_steps(self):
        # 16b uses vc:16-impl-context and populates execution evidence.
        assert "16b" in _CHECKLIST_STEPS

    def test_step_16c_in_checklist_steps(self):
        # 16c uses vc:16-impl-context and records the review verdict.
        assert "16c" in _CHECKLIST_STEPS


# ---------------------------------------------------------------------------
# 4. _check_acceptance_gap gated on _CHECKLIST_STEPS
# ---------------------------------------------------------------------------

class TestAcceptanceGapGating:
    def _ac_upstream_with_text(self):
        """Upstream where ACs have description text (for Jaccard matching).
        Uses canonical step-04 field names: criterion_id + text."""
        spec_data = {
            "functional_requirements": [{
                "fr_id": "fr-post-publish",
                "statement": "Publish post",
                "acceptance_criteria": [{
                    "criterion_id": "ac-post-publish-1",
                    "text": "Given a creator, when post is published, then HTTP 200",
                }],
            }]
        }
        return [("spec/04_fr_list.json", spec_data)]

    def test_check_acceptance_gap_function_has_no_step_id_gate(self):
        """_check_acceptance_gap has no step_id parameter — it always runs when called.
        Gating is the caller's responsibility (review_artifact checks _CHECKLIST_STEPS).
        Calling it directly on a step-06-style artifact produces pairs because the
        function itself cannot know the step context."""
        upstream = self._ac_upstream_with_text()
        artifact = _artifact(trace_fr_ids=["fr-post-publish"])
        pairs = _check_acceptance_gap(artifact, "spec/06_invariants.json", upstream)
        # The invariant artifact has no checklist items with matching descriptions,
        # so at least one acceptance_gap pair should be generated when called raw.
        assert len(pairs) >= 1, (
            "Expected _check_acceptance_gap to produce pairs when called directly "
            "(gating only exists in review_artifact, not in the function itself)"
        )

    def test_review_artifact_no_acceptance_gap_pairs_for_step06(self, tmp_path):
        """review_artifact must not include acceptance_gap pairs for step 06."""
        import json
        # Write a minimal upstream spec and artifact to tmp_path.
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        repo_root = tmp_path / "toolkit"
        repo_root.mkdir()
        tools_dir = repo_root / "tools"
        tools_dir.mkdir()

        # step_order: 04 is upstream of 06
        step_order = {
            "downstream_consumers": {
                "04": ["06"],
                "05": ["06"],
            }
        }
        (tools_dir / "step_order.json").write_text(json.dumps(step_order))

        upstream_spec = {
            "functional_requirements": [{
                "fr_id": "fr-post-publish",
                "statement": "Publish a post",
                "acceptance_criteria": [{
                    "criterion_id": "ac-post-publish-1",
                    "text": "Given creator, when publish triggered, then HTTP 200",
                }],
            }]
        }
        (spec_dir / "04_fr_list.json").write_text(json.dumps(upstream_spec))

        artifact = {
            "id": "invariants-catalog",
            "rules": [{
                "inv_id": "inv-post-accessible",
                "description": "Published post returns HTTP 200 at canonical URL",
                "language": "cel",
                "expression": "post.status == 'published' ? response.status == 200 : true",
                "scope": {"components": [], "apis": []},
                "trace": [{"type": "fr", "id": "fr-post-publish"}],
            }],
        }
        artifact_path = str(spec_dir / "06_invariants.json")
        (spec_dir / "06_invariants.json").write_text(json.dumps(artifact))

        result = review_artifact(
            artifact_path,
            step_id="06",
            spec_dir=str(spec_dir),
            repo_root=str(repo_root),
        )
        acceptance_gaps = [p for p in result.semantic_pairs if p.check_type == "acceptance_gap"]
        assert acceptance_gaps == [], (
            f"Expected no acceptance_gap pairs for step 06, got: {acceptance_gaps}"
        )
        # All other semantic checks also produce no pairs for this data:
        # faithfulness skips (FR statement too short), quantifier_weakening finds
        # no upstream metrics, seed_distillation skips (step 06 has no seeds in manifest),
        # scope_completeness returns [] when schema registry is absent.
        assert result.verdict == "PASS"

    @pytest.mark.parametrize("step_id", ["16a", "16b", "16c"])
    def test_review_artifact_acceptance_gap_runs_for_all_checklist_steps(
        self, tmp_path, step_id
    ):
        """review_artifact generates acceptance_gap pairs for every step in _CHECKLIST_STEPS.
        16a/16b/16c share vc:16-impl-context and author the checklist — the gate must
        fire for all three. Step 16 is the anchor and has no checklist; it is not in
        the set, tested separately in TestChecklistSteps.
        Uses canonical step-04 field names (criterion_id, text) to match real data shape.
        """
        import json
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        repo_root = tmp_path / "toolkit"
        repo_root.mkdir()
        (repo_root / "tools").mkdir()

        step_order = {"downstream_consumers": {"04": [step_id]}}
        ((repo_root / "tools") / "step_order.json").write_text(json.dumps(step_order))

        upstream_spec = {
            "functional_requirements": [{
                "fr_id": "fr-post-publish",
                "statement": "Publish a post",
                "acceptance_criteria": [{
                    # Use canonical step-04 field names: criterion_id + text
                    "criterion_id": "ac-post-publish-1",
                    "text": (
                        "Given authenticated creator xyzzy, when publish triggered, "
                        "then GET /xyzzy-post/ returns HTTP 200 to unauthenticated visitor"
                    ),
                }],
            }]
        }
        (spec_dir / "04_fr_list.json").write_text(json.dumps(upstream_spec))

        # Checklist item whose description deliberately does NOT match the AC text
        # (Jaccard < 0.25) so an acceptance_gap pair is generated.
        artifact = {
            "id": "impl-context",
            "plan": {
                "spec_alignment": {
                    "checklist": [{
                        "id": "DEPLOY_CONFIG",
                        "description": "Deploy configuration is applied correctly",
                        "type": "behavior",
                        "layer": "config",
                        "checklist_status": "pending",
                    }]
                }
            }
        }
        artifact_path = str(spec_dir / "impl_context.json")
        (spec_dir / "impl_context.json").write_text(json.dumps(artifact))

        result = review_artifact(
            artifact_path,
            step_id=step_id,
            spec_dir=str(spec_dir),
            repo_root=str(repo_root),
        )
        acceptance_gaps = [p for p in result.semantic_pairs if p.check_type == "acceptance_gap"]
        assert len(acceptance_gaps) >= 1, (
            f"Expected at least one acceptance_gap pair for step {step_id} with unmatched AC"
        )


# ---------------------------------------------------------------------------
# 5. Verdict logic
# ---------------------------------------------------------------------------

class TestVerdict:
    # --- Direct _compute_verdict unit tests ---

    def test_compute_verdict_pass_when_nothing_dropped_no_pairs(self):
        sr = StructuralReview(
            upstream_coverage={"covered": ["fr-a"], "dropped": []},
            reverse_trace={"unjustified": [], "scope_creep": []},
        )
        assert _compute_verdict(sr, []) == "PASS"

    def test_compute_verdict_needs_semantic_review_when_pairs_present(self):
        sr = StructuralReview(
            upstream_coverage={"covered": ["fr-a"], "dropped": []},
            reverse_trace={"unjustified": [], "scope_creep": []},
        )
        assert _compute_verdict(sr, ["pair"]) == "NEEDS_SEMANTIC_REVIEW"

    def test_compute_verdict_exactly_20pct_dropped_is_pass(self):
        """Threshold is > 0.20 (strict), so exactly 1/5 = 20% must be PASS, not FAIL."""
        sr = StructuralReview(
            upstream_coverage={"covered": ["a", "b", "c", "d"], "dropped": ["e"]},
            reverse_trace={"unjustified": [], "scope_creep": []},
        )
        assert _compute_verdict(sr, []) == "PASS"

    def test_compute_verdict_fail_when_dropped_fraction_exceeds_20pct(self):
        """2/5 = 40% dropped → FAIL."""
        sr = StructuralReview(
            upstream_coverage={"covered": ["a", "b", "c"], "dropped": ["d", "e"]},
            reverse_trace={"unjustified": [], "scope_creep": []},
        )
        assert _compute_verdict(sr, []) == "FAIL"

    def test_compute_verdict_fail_beats_needs_semantic_review(self):
        """FAIL takes priority over NEEDS_SEMANTIC_REVIEW.
        When dropped > 20% AND semantic pairs are present, verdict must be FAIL,
        not NEEDS_SEMANTIC_REVIEW — structural failure is checked first."""
        sr = StructuralReview(
            upstream_coverage={"covered": ["a", "b", "c"], "dropped": ["d", "e"]},
            reverse_trace={"unjustified": [], "scope_creep": []},
        )
        assert _compute_verdict(sr, ["pair"]) == "FAIL"

    def test_compute_verdict_empty_upstream_is_pass(self):
        """Zero total upstream IDs → fraction check skipped → PASS."""
        sr = StructuralReview(
            upstream_coverage={"covered": [], "dropped": []},
            reverse_trace={"unjustified": [], "scope_creep": []},
        )
        assert _compute_verdict(sr, []) == "PASS"


# ---------------------------------------------------------------------------
# 6. The structural pass reports nothing
# ---------------------------------------------------------------------------

class TestStructuralPassReportsNothing:
    def test_artifact_with_1_1_1_trace_arrays_is_not_counted(self, tmp_path):
        """No ``trace`` array exists in a 1.2.0 artifact, so the pass counts nothing: a 1.1.1-shaped artifact
        that traces one of five upstream FRs gives an empty structural review and a PASS, not a FAIL."""
        import json
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        repo_root = tmp_path / "toolkit"
        (repo_root / "tools").mkdir(parents=True)
        (repo_root / "tools" / "step_order.json").write_text(json.dumps({"downstream_consumers": {"04": ["06"]}}))
        upstream_spec = {"functional_requirements": [{"fr_id": f"fr-req-{i}", "statement": f"Req {i}"} for i in range(5)]}
        (spec_dir / "04_fr_list.json").write_text(json.dumps(upstream_spec))
        artifact = _artifact(trace_fr_ids=["fr-req-0"])
        (spec_dir / "06_invariants.json").write_text(json.dumps(artifact))

        result = review_artifact(str(spec_dir / "06_invariants.json"), "06", str(spec_dir), str(repo_root))
        assert result.structural.upstream_coverage == {"covered": [], "dropped": []}
        assert result.structural.reverse_trace == {"unjustified": [], "scope_creep": []}
        assert result.verdict != "FAIL"
