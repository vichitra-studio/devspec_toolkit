"""Unit tests for specdev_tools/context/reviewer.py.

Covers the three behaviour changes introduced to fix false-positive FAIL
verdicts when running ``context review`` on non-checklist step artifacts
(e.g. step 06 invariants):

  1. ac-* IDs excluded from upstream coverage denominator for non-checklist steps.
  2. scope.apis / scope.components IDs counted as valid traceability references.
  3. _check_acceptance_gap gated on _CHECKLIST_STEPS
     (steps 16, 16a, 16b, 16c — all share vc:16-impl-context schema).
"""
from __future__ import annotations

import pytest

from specdev_tools.context.reviewer import (
    _CHECKLIST_STEPS,
    _run_structural_pass,
    _check_acceptance_gap,
    review_artifact,
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
    def test_step_16_in_checklist_steps(self):
        assert "16" in _CHECKLIST_STEPS

    def test_step_06_not_in_checklist_steps(self):
        assert "06" not in _CHECKLIST_STEPS

    def test_step_07_not_in_checklist_steps(self):
        assert "07" not in _CHECKLIST_STEPS

    def test_step_13a_not_in_checklist_steps(self):
        # 13a produces a completeness-assessment, not a checklist.
        assert "13a" not in _CHECKLIST_STEPS

    def test_step_16a_in_checklist_steps(self):
        # 16a shares vc:16-impl-context schema — same checklist structure.
        assert "16a" in _CHECKLIST_STEPS

    def test_step_16b_in_checklist_steps(self):
        # 16b shares vc:16-impl-context schema — same checklist structure.
        assert "16b" in _CHECKLIST_STEPS

    def test_step_16c_in_checklist_steps(self):
        # 16c shares vc:16-impl-context schema — same checklist structure.
        assert "16c" in _CHECKLIST_STEPS


# ---------------------------------------------------------------------------
# 2. ac-* IDs excluded from coverage denominator for non-checklist steps
# ---------------------------------------------------------------------------

class TestAcIdExclusion:
    def test_ac_ids_not_in_dropped_for_step06(self):
        upstream = _upstream(
            frs=["fr-post-publish"],
            acs_per_fr={"fr-post-publish": ["ac-post-publish-1", "ac-post-publish-2"]},
        )
        artifact = _artifact(trace_fr_ids=["fr-post-publish"])
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        dropped = result.upstream_coverage["dropped"]
        assert "ac-post-publish-1" not in dropped
        assert "ac-post-publish-2" not in dropped

    def test_ac_ids_do_not_inflate_denominator_for_step06(self):
        """With 1 FR covered and 2 AC IDs excluded, dropped fraction must be 0."""
        upstream = _upstream(
            frs=["fr-post-publish"],
            acs_per_fr={"fr-post-publish": ["ac-post-publish-1", "ac-post-publish-2"]},
        )
        artifact = _artifact(trace_fr_ids=["fr-post-publish"])
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        covered = result.upstream_coverage["covered"]
        dropped = result.upstream_coverage["dropped"]
        assert "fr-post-publish" in covered
        assert dropped == []

    def test_ac_ids_remain_in_dropped_for_checklist_step(self):
        """For step 16, ac-* IDs should appear in dropped when not traced."""
        upstream = _upstream(
            frs=["fr-post-publish"],
            acs_per_fr={"fr-post-publish": ["ac-post-publish-1"]},
        )
        artifact = _artifact(trace_fr_ids=["fr-post-publish"])
        result = _run_structural_pass(artifact, "spec/16_impl_context.json", upstream, step_id="16")
        dropped = result.upstream_coverage["dropped"]
        assert "ac-post-publish-1" in dropped

    def test_non_ac_ids_always_appear_in_dropped_when_untraced(self):
        """API and component IDs not referenced in trace or scope appear in dropped."""
        upstream = _upstream(frs=["fr-post-publish"], apis=["api-post-page"])
        artifact = _artifact(trace_fr_ids=["fr-post-publish"])  # no scope.apis
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        dropped = result.upstream_coverage["dropped"]
        assert "api-post-page" in dropped


# ---------------------------------------------------------------------------
# 3. scope.apis and scope.components counted as covered
# ---------------------------------------------------------------------------

class TestScopeCoverage:
    def test_scope_apis_counted_as_covered(self):
        upstream = _upstream(frs=["fr-post-publish"], apis=["api-post-page"])
        artifact = _artifact(trace_fr_ids=["fr-post-publish"], scope_apis=["api-post-page"])
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        covered = result.upstream_coverage["covered"]
        dropped = result.upstream_coverage["dropped"]
        assert "api-post-page" in covered
        assert "api-post-page" not in dropped

    def test_scope_components_counted_as_covered(self):
        upstream = _upstream(frs=["fr-post-publish"], components=["ghost-cms"])
        artifact = _artifact(trace_fr_ids=["fr-post-publish"], scope_components=["ghost-cms"])
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        covered = result.upstream_coverage["covered"]
        assert "ghost-cms" in covered

    def test_scope_apis_and_components_both_covered(self):
        upstream = _upstream(
            frs=["fr-post-publish"],
            apis=["api-post-page", "api-admin-post-publish"],
            components=["ghost-cms", "headline-theme"],
        )
        artifact = _artifact(
            trace_fr_ids=["fr-post-publish"],
            scope_apis=["api-post-page", "api-admin-post-publish"],
            scope_components=["ghost-cms", "headline-theme"],
        )
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        covered = result.upstream_coverage["covered"]
        assert "api-post-page" in covered
        assert "api-admin-post-publish" in covered
        assert "ghost-cms" in covered
        assert "headline-theme" in covered
        assert result.upstream_coverage["dropped"] == []

    def test_scope_empty_arrays_do_not_crash(self):
        upstream = _upstream(frs=["fr-post-publish"], apis=["api-post-page"])
        artifact = _artifact(trace_fr_ids=["fr-post-publish"], scope_apis=[], scope_components=[])
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        # api still dropped since scope.apis is empty
        assert "api-post-page" in result.upstream_coverage["dropped"]

    def test_scope_apis_as_string_is_skipped_not_iterated(self):
        """If scope.apis is a plain string instead of an array, iterating it would
        produce single characters ('a', 'p', 'i', ...) as IDs — each a false
        unjustified reference.  The list guard in the scope collector must skip it."""
        upstream = _upstream(frs=["fr-post-publish"], apis=["api-post-page"])
        artifact = {
            "id": "test",
            "rules": [{
                "inv_id": "inv-test",
                "description": "test",
                "language": "cel",
                "expression": "true",
                "scope": {
                    # Malformed: string instead of array
                    "apis": "api-post-page",
                    "components": [],
                },
                "trace": [{"type": "fr", "id": "fr-post-publish"}],
            }],
        }
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        # The string should be ignored — no single-char IDs in unjustified
        unjustified = result.reverse_trace["unjustified"]
        assert all(len(uid) > 1 for uid in unjustified), (
            f"Single-character IDs found in unjustified — string was iterated as chars: {unjustified}"
        )
        # api-post-page itself should be in dropped (string wasn't parsed as ID)
        assert "api-post-page" in result.upstream_coverage["dropped"]

    def test_scope_non_string_items_ignored(self):
        """Non-string items in scope.apis/components must not crash the collector."""
        upstream = _upstream(frs=["fr-post-publish"], apis=["api-post-page"])
        artifact = {
            "id": "test",
            "rules": [{
                "inv_id": "inv-test",
                "description": "test",
                "language": "cel",
                "expression": "true",
                "scope": {
                    "apis": [None, 42, {"id": "api-post-page"}, "api-post-page"],
                    "components": [],
                },
                "trace": [{"type": "fr", "id": "fr-post-publish"}],
            }],
        }
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        # Only the plain string "api-post-page" should be collected.
        covered = result.upstream_coverage["covered"]
        assert "api-post-page" in covered

    def test_artifact_with_no_scope_field_does_not_crash(self):
        upstream = _upstream(frs=["fr-post-publish"])
        artifact = {
            "id": "test",
            "rules": [{
                "inv_id": "inv-test",
                "description": "test",
                "language": "cel",
                "expression": "true",
                "trace": [{"type": "fr", "id": "fr-post-publish"}],
            }],
        }
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        assert "fr-post-publish" in result.upstream_coverage["covered"]


# ---------------------------------------------------------------------------
# 4. _check_acceptance_gap gated on _CHECKLIST_STEPS
# ---------------------------------------------------------------------------

class TestAcceptanceGapGating:
    def _ac_upstream_with_text(self):
        """Upstream where ACs have description text (for Jaccard matching)."""
        spec_data = {
            "functional_requirements": [{
                "fr_id": "fr-post-publish",
                "statement": "Publish post",
                "acceptance_criteria": [{
                    "id": "ac-post-publish-1",
                    "description": "Given a creator, when post is published, then HTTP 200",
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

    @pytest.mark.parametrize("step_id", ["16", "16a", "16b", "16c"])
    def test_review_artifact_acceptance_gap_runs_for_all_checklist_steps(
        self, tmp_path, step_id
    ):
        """review_artifact generates acceptance_gap pairs for every step in _CHECKLIST_STEPS.
        All four (16/16a/16b/16c) share vc:16-impl-context schema and the same checklist
        structure — the gate must fire for all of them, not just step 16.
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
    def test_structural_pass_zero_dropped_when_all_upstream_ids_covered(self):
        """All FRs + APIs + components covered → dropped is empty.
        (Verdict computation is tested separately via review_artifact.)"""
        upstream = _upstream(
            frs=["fr-post-publish", "fr-post-read"],
            apis=["api-post-page"],
            components=["ghost-cms"],
        )
        artifact = _artifact(
            trace_fr_ids=["fr-post-publish", "fr-post-read"],
            scope_apis=["api-post-page"],
            scope_components=["ghost-cms"],
        )
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        assert result.upstream_coverage["dropped"] == []

    def test_verdict_fail_when_more_than_20pct_dropped(self, tmp_path):
        """Dropped fraction > 20% → FAIL verdict from review_artifact."""
        import json
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        repo_root = tmp_path / "toolkit"
        repo_root.mkdir()
        (repo_root / "tools").mkdir()
        step_order = {"downstream_consumers": {"04": ["06"]}}
        ((repo_root / "tools") / "step_order.json").write_text(json.dumps(step_order))

        # 5 FRs upstream; artifact only traces 1 → 4/5 = 80% dropped → FAIL
        upstream_spec = {
            "functional_requirements": [
                {"fr_id": f"fr-req-{i}", "statement": f"Req {i}"}
                for i in range(5)
            ]
        }
        (spec_dir / "04_fr_list.json").write_text(json.dumps(upstream_spec))

        artifact = {
            "id": "invariants-catalog",
            "rules": [{
                "inv_id": "inv-one",
                "description": "Only one fr covered",
                "language": "cel",
                "expression": "true",
                "scope": {"components": [], "apis": []},
                "trace": [{"type": "fr", "id": "fr-req-0"}],
            }],
        }
        artifact_path = str(spec_dir / "06_invariants.json")
        (spec_dir / "06_invariants.json").write_text(json.dumps(artifact))

        result = review_artifact(artifact_path, "06", str(spec_dir), str(repo_root))
        assert result.verdict == "FAIL"


# ---------------------------------------------------------------------------
# 6. Edge cases and additional coverage
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_upstream_functional_requirements(self):
        """When upstream has no FRs, all collections are empty and dropped is []."""
        upstream = [("spec/04_fr_list.json", {"functional_requirements": []})]
        artifact = _artifact()  # no rules
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        assert result.upstream_coverage["covered"] == []
        assert result.upstream_coverage["dropped"] == []

    def test_scope_and_trace_same_id_not_double_counted(self):
        """If scope.apis and a trace array both reference the same ID, the ID
        appears exactly once in covered (set semantics prevent duplication)."""
        upstream = _upstream(frs=["fr-post-publish"], apis=["api-post-page"])
        # Build artifact where trace AND scope both reference api-post-page
        artifact = {
            "id": "test",
            "rules": [{
                "inv_id": "inv-test",
                "description": "test",
                "language": "cel",
                "expression": "true",
                "scope": {"apis": ["api-post-page"], "components": []},
                "trace": [
                    {"type": "fr", "id": "fr-post-publish"},
                    {"type": "api", "id": "api-post-page"},
                ],
            }],
        }
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        covered = result.upstream_coverage["covered"]
        assert covered.count("api-post-page") == 1

    def test_scope_reference_to_nonexistent_upstream_id_flagged_as_scope_creep(self):
        """A scope.apis entry that has no matching upstream ID is flagged as
        unjustified (scope creep) because artifact_trace_ids is used for the
        reverse-trace check after scope IDs are added."""
        upstream = _upstream(frs=["fr-post-publish"])  # no apis in upstream
        artifact = _artifact(
            trace_fr_ids=["fr-post-publish"],
            scope_apis=["api-does-not-exist"],
        )
        result = _run_structural_pass(artifact, "spec/06_invariants.json", upstream, step_id="06")
        assert "api-does-not-exist" in result.reverse_trace["unjustified"]
        # scope_creep is kept in sync with unjustified
        assert "api-does-not-exist" in result.reverse_trace["scope_creep"]
