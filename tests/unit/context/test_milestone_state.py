"""Unit tests for tools/specdev_tools/context/milestone_state.py.

Covers:
- Per-group state derivation: pending, code_converged, blocked, verified, deferred
- Derived phase position transitions: pending, impl_in_progress, impl_complete,
  review_pending, review_complete, operator_pending, closed
- Mandatory keystone: implementation.status=="verified" => group state "verified"
  => (all non-deferred verified) => milestone "closed"
- well_formed: severity-present + description-present true/false cases
- Filesystem robustness: non-dict findings file skipped

All filesystem probes use pytest ``tmp_path`` fixtures with synthetic
``.specdev/findings/`` directories — no host filesystem access.
"""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.context.milestone_state import (
    compute_milestone_state,
    derive_group_state,
    derive_phase_position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_findings(findings_dir: Path, filename: str, findings: list) -> Path:
    """Write a synthetic findings file and return its path."""
    path = findings_dir / filename
    data = {
        "round": 1,
        "scope": "test-scope",
        "generated_at": 1700000000,
        "findings": findings,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_group(
    group_id: str,
    impl_status: str = "in_progress",
    checklist_status: str = "active",
    fixture_ref: str | None = None,
) -> dict:
    """Build a minimal checklist group dict."""
    g: dict = {
        "id": group_id,
        "checklist_status": checklist_status,
        "implementation": {"status": impl_status},
    }
    if fixture_ref is not None:
        g["fixture_ref"] = fixture_ref
    return g


def _make_plan(checklist: list[dict], ambs: list[dict] | None = None) -> dict:
    """Build a minimal plan dict."""
    return {
        "id": "ms-test-plan",
        "plan": {"spec_alignment": {"checklist": checklist}},
        "execution": {"emergent_ambiguities": ambs or []},
    }


# ---------------------------------------------------------------------------
# Per-group state: pending
# ---------------------------------------------------------------------------

class TestGroupStatePending:
    def test_no_findings_dir(self, tmp_path: Path) -> None:
        """Group with no findings file → pending."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        group = _make_group("GRP_A")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "pending"
        assert result["implementation_converged_at"] is None
        assert result["reviewer_rounds"] == 0
        assert result["findings_resolved_path"] is None
        assert result["blocking_amb_ids"] == []

    def test_only_reviewer_files_not_empty(self, tmp_path: Path) -> None:
        """Reviewer files exist with findings → still pending (no convergence)."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_B_1_r1.json", [{"kind": "bug"}])
        group = _make_group("GRP_B")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "pending"
        assert result["reviewer_rounds"] == 1

    def test_round_output_with_findings(self, tmp_path: Path) -> None:
        """Round output file has non-empty findings → pending."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_C_1.json", [{"kind": "bug"}])
        group = _make_group("GRP_C")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "pending"


# ---------------------------------------------------------------------------
# Per-group state: code_converged
# ---------------------------------------------------------------------------

class TestGroupStateCodeConverged:
    def test_empty_round_output(self, tmp_path: Path) -> None:
        """Empty round-output file → code_converged."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_D_1.json", [])
        group = _make_group("GRP_D")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "code_converged"
        assert result["implementation_converged_at"] is not None
        assert result["findings_resolved_path"] is not None
        assert result["findings_resolved_path"].endswith("findings_GRP_D_1.json")

    def test_empty_reviewer_file(self, tmp_path: Path) -> None:
        """Empty per-reviewer file also signals convergence → code_converged."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_E_2_r1.json", [])
        group = _make_group("GRP_E")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "code_converged"
        assert result["reviewer_rounds"] == 1

    def test_rr_variant_reviewer_file(self, tmp_path: Path) -> None:
        """Double-r reviewer suffix ``_rr1`` is counted as a reviewer file."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_F_1_rr1.json", [])
        group = _make_group("GRP_F")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["reviewer_rounds"] == 1
        assert result["state"] == "code_converged"


# ---------------------------------------------------------------------------
# Per-group state: blocked
# ---------------------------------------------------------------------------

class TestGroupStateBlocked:
    def test_blocked_amb_referencing_group(self, tmp_path: Path) -> None:
        """Converged group with a blocked+unresolved amb that refs group_id → blocked."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_G_1.json", [])
        group = _make_group("GRP_G")
        ambs = [
            {
                "id": "amb-test-001",
                "status": "blocked",
                "severity": "high",
                "description": "Something in GRP_G is unresolved",
                "impact": ["GRP_G"],
                "resolved": False,
            }
        ]
        result = derive_group_state(group, str(findings_dir), ambs)
        assert result["state"] == "blocked"
        assert "amb-test-001" in result["blocking_amb_ids"]
        health = result["blocking_amb_health"]
        assert len(health) == 1
        assert health[0]["well_formed"] is True

    def test_resolved_amb_does_not_block(self, tmp_path: Path) -> None:
        """A resolved blocked amb does not trigger blocked state."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_H_1.json", [])
        group = _make_group("GRP_H")
        ambs = [
            {
                "id": "amb-resolved",
                "status": "blocked",
                "severity": "medium",
                "description": "GRP_H issue resolved",
                "impact": ["GRP_H"],
                "resolved": True,
            }
        ]
        result = derive_group_state(group, str(findings_dir), ambs)
        assert result["state"] == "code_converged"
        assert result["blocking_amb_ids"] == []

    def test_missing_resolved_field_treated_as_unresolved(self, tmp_path: Path) -> None:
        """Amb without 'resolved' key defaults to unresolved → can trigger blocked."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_I_1.json", [])
        group = _make_group("GRP_I")
        ambs = [
            {
                "id": "amb-no-resolved",
                "status": "blocked",
                "severity": "low",
                "description": "GRP_I ambiguity without resolved field",
                "impact": ["GRP_I"],
                # no "resolved" key
            }
        ]
        result = derive_group_state(group, str(findings_dir), ambs)
        assert result["state"] == "blocked"

    def test_amb_not_referencing_group_is_ignored(self, tmp_path: Path) -> None:
        """Blocked amb that doesn't reference this group_id → no effect."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_GRP_J_1.json", [])
        group = _make_group("GRP_J")
        ambs = [
            {
                "id": "amb-other",
                "status": "blocked",
                "severity": "high",
                "description": "An issue in SOME_OTHER_GROUP",
                "impact": ["SOME_OTHER_GROUP"],
                "resolved": False,
            }
        ]
        result = derive_group_state(group, str(findings_dir), ambs)
        assert result["state"] == "code_converged"
        assert result["blocking_amb_ids"] == []


# ---------------------------------------------------------------------------
# Per-group state: verified  (MANDATORY KEYSTONE)
# ---------------------------------------------------------------------------

class TestGroupStateVerified:
    def test_status_string_verified_no_findings(self, tmp_path: Path) -> None:
        """KEYSTONE: implementation.status=='verified' => state 'verified', even with no findings file.

        This pins the string-only semantics introduced by DEVSPEC-38.
        status_ref is NOT read — the status string alone is authoritative.
        """
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        # No findings files at all
        group = _make_group("GRP_VERIFIED", impl_status="verified")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "verified"
        # Filesystem fields are null (no convergence file)
        assert result["implementation_converged_at"] is None
        assert result["findings_resolved_path"] is None

    def test_status_string_verified_beats_pending(self, tmp_path: Path) -> None:
        """verified state takes precedence over pending (no convergence file present)."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        group = _make_group("GRP_V2", impl_status="verified")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "verified"

    def test_fixtures_exercised(self, tmp_path: Path) -> None:
        """fixture_ref is captured in fixtures_exercised."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        group = _make_group("GRP_V3", impl_status="verified", fixture_ref="fix-my-contract")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["fixtures_exercised"] == ["fix-my-contract"]


# ---------------------------------------------------------------------------
# Per-group state: deferred
# ---------------------------------------------------------------------------

class TestGroupStateDeferred:
    def test_deferred_status(self, tmp_path: Path) -> None:
        """checklist_status=='deferred' => state 'deferred' regardless of impl status."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        group = _make_group("GRP_DEF", impl_status="verified", checklist_status="deferred")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "deferred"


# ---------------------------------------------------------------------------
# Per-group state: wont_do (DEVSPEC-122 follow-up)
# ---------------------------------------------------------------------------

class TestGroupStateWontDo:
    def test_wont_do_status(self, tmp_path: Path) -> None:
        """checklist_status=='wont_do' => state 'wont_do' regardless of impl status."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        group = _make_group("GRP_WONT", impl_status="pending", checklist_status="wont_do")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "wont_do"

    def test_wont_do_status_outranks_verified_impl(self, tmp_path: Path) -> None:
        """wont_do takes precedence even when implementation.status=='verified'."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        group = _make_group("GRP_WONT_V", impl_status="verified", checklist_status="wont_do")
        result = derive_group_state(group, str(findings_dir), [])
        assert result["state"] == "wont_do"


# ---------------------------------------------------------------------------
# well_formed predicate
# ---------------------------------------------------------------------------

class TestWellFormed:
    def _find_health(self, ambs: list[dict], findings_dir: Path) -> list[dict]:
        """Helper: derive health for GRP_WF group with converged state."""
        _write_findings(findings_dir, "findings_GRP_WF_1.json", [])
        group = _make_group("GRP_WF")
        result = derive_group_state(group, str(findings_dir), ambs)
        return result["blocking_amb_health"]

    def test_well_formed_true(self, tmp_path: Path) -> None:
        """Amb with severity + description present → well_formed True."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        ambs = [{
            "id": "amb-wf-ok",
            "status": "blocked",
            "severity": "high",
            "description": "GRP_WF is blocked",
            "impact": ["GRP_WF"],
            "resolved": False,
        }]
        health = self._find_health(ambs, findings_dir)
        assert len(health) == 1
        assert health[0]["well_formed"] is True

    def test_well_formed_false_missing_severity(self, tmp_path: Path) -> None:
        """Missing severity → well_formed False."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        ambs = [{
            "id": "amb-wf-bad",
            "status": "blocked",
            # no "severity"
            "description": "GRP_WF is blocked",
            "impact": ["GRP_WF"],
            "resolved": False,
        }]
        health = self._find_health(ambs, findings_dir)
        assert len(health) == 1
        assert health[0]["well_formed"] is False

    def test_well_formed_false_missing_description(self, tmp_path: Path) -> None:
        """Missing description → well_formed False."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        ambs = [{
            "id": "amb-wf-bad2",
            "status": "blocked",
            "severity": "medium",
            # no "description"
            "impact": ["GRP_WF"],
            "resolved": False,
        }]
        health = self._find_health(ambs, findings_dir)
        assert len(health) == 1
        assert health[0]["well_formed"] is False


# ---------------------------------------------------------------------------
# Filesystem robustness
# ---------------------------------------------------------------------------

class TestFilesystemRobustness:
    def test_non_dict_findings_file_skipped(self, tmp_path: Path) -> None:
        """A findings file whose top-level JSON is a list is skipped gracefully."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        # Write a file with a JSON list (not dict) at top level
        bad = findings_dir / "findings_GRP_ROB_1.json"
        bad.write_text(json.dumps([{"kind": "bug"}]), encoding="utf-8")
        group = _make_group("GRP_ROB")
        result = derive_group_state(group, str(findings_dir), [])
        # Should not crash; file skipped → pending
        assert result["state"] == "pending"


# ---------------------------------------------------------------------------
# Phase position transitions
# ---------------------------------------------------------------------------

class TestDerivePhasePosition:
    """Tests for derive_phase_position covering all 7 positions."""

    def _make_group_state(
        self,
        group_id: str,
        state: str,
        blocking_amb_health: list[dict] | None = None,
    ) -> dict:
        return {
            "group_id": group_id,
            "state": state,
            "implementation_converged_at": None,
            "reviewer_rounds": 0,
            "findings_resolved_path": None,
            "blocking_amb_ids": [],
            "blocking_amb_health": blocking_amb_health or [],
            "fixtures_exercised": [],
        }

    def test_pending_all_groups_pending(self, tmp_path: Path) -> None:
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("A", "pending"),
            self._make_group_state("B", "pending"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "pending"

    def test_pending_all_deferred(self, tmp_path: Path) -> None:
        """All-deferred milestone → pending (nothing to track)."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [self._make_group_state("D", "deferred")]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "pending"

    def test_pending_all_wont_do(self, tmp_path: Path) -> None:
        """All-wont_do milestone → pending (nothing to track), same as all-deferred."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [self._make_group_state("W", "wont_do")]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "pending"

    def test_pending_mixed_deferred_and_wont_do(self, tmp_path: Path) -> None:
        """All groups either deferred or wont_do → pending (nothing active to track)."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("D", "deferred"),
            self._make_group_state("W", "wont_do"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "pending"

    def test_closed_excludes_wont_do_group_regression(self, tmp_path: Path) -> None:
        """REGRESSION GUARD: a wont_do group must not block 'closed' the way an
        unhandled non-excluded status would -- without the wont_do exclusion, this
        milestone would incorrectly report impl_in_progress/pending forever since
        the wont_do group would never reach 'verified'."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("V", "verified"),
            self._make_group_state("W", "wont_do"),  # excluded from roll-up
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "closed"

    def test_impl_in_progress_mixed(self, tmp_path: Path) -> None:
        """≥1 code_converged AND ≥1 pending → impl_in_progress."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("A", "code_converged"),
            self._make_group_state("B", "pending"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "impl_in_progress"

    def test_impl_in_progress_verified_and_pending(self, tmp_path: Path) -> None:
        """verified + pending → impl_in_progress (verified counts as progress)."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("A", "verified"),
            self._make_group_state("B", "pending"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "impl_in_progress"

    def test_impl_complete_all_advanced_no_review_file(self, tmp_path: Path) -> None:
        """All non-deferred advanced, no review file → impl_complete."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("A", "code_converged"),
            self._make_group_state("B", "blocked"),
            self._make_group_state("C", "verified"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch2") == "impl_complete"

    def test_review_pending_has_review_file_not_empty(self, tmp_path: Path) -> None:
        """All advanced + milestone-review file exists but has findings → review_pending."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        # Create a non-empty review file
        _write_findings(findings_dir, "findings_batch3_review_1_r1.json", [{"kind": "bug"}])
        groups = [
            self._make_group_state("A", "code_converged"),
            self._make_group_state("B", "verified"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch3") == "review_pending"

    def test_review_complete_empty_review_file_no_blockers(self, tmp_path: Path) -> None:
        """All advanced + empty milestone-review file + no blocked groups → review_complete."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_batch4_review_1.json", [])
        groups = [
            self._make_group_state("A", "code_converged"),
            self._make_group_state("B", "verified"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch4") == "review_complete"

    def test_operator_pending_blocked_group(self, tmp_path: Path) -> None:
        """review_complete conditions + a blocked group → operator_pending."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_batch5_review_1.json", [])
        groups = [
            self._make_group_state("A", "blocked"),
            self._make_group_state("B", "code_converged"),
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch5") == "operator_pending"

    def test_operator_pending_unresolved_blocking_amb(self, tmp_path: Path) -> None:
        """review_complete + unresolved blocking amb health → operator_pending."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_batch6_review_1.json", [])
        # code_converged group with an unresolved blocking amb in health
        g = self._make_group_state(
            "A",
            "code_converged",
            blocking_amb_health=[
                {"id": "amb-x", "status": "blocked", "resolved": False, "well_formed": True}
            ],
        )
        groups = [g, self._make_group_state("B", "verified")]
        assert derive_phase_position(groups, str(findings_dir), "batch6") == "operator_pending"

    def test_closed_all_verified(self, tmp_path: Path) -> None:
        """KEYSTONE: all non-deferred groups verified → closed.

        This pins the string-only 'verified' semantics. status_ref is NOT consulted.
        """
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        groups = [
            self._make_group_state("A", "verified"),
            self._make_group_state("B", "verified"),
            self._make_group_state("DEF", "deferred"),  # excluded from roll-up
        ]
        assert derive_phase_position(groups, str(findings_dir), "batch7") == "closed"


# ---------------------------------------------------------------------------
# compute_milestone_state integration
# ---------------------------------------------------------------------------

class TestComputeMilestoneState:
    """Integration tests for compute_milestone_state."""

    def test_all_pending_returns_pending_position(self, tmp_path: Path) -> None:
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        plan = _make_plan([
            _make_group("G1"),
            _make_group("G2"),
        ])
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        # milestone_id is always batch_id per output contract (specdev-scope.md:238)
        assert result["milestone_id"] == "batchX"
        assert result["derived_phase_position"] == "pending"
        assert len(result["groups"]) == 2
        assert result["blockers"] == []

    def test_verified_and_pending_gives_impl_in_progress(self, tmp_path: Path) -> None:
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        plan = _make_plan([
            _make_group("G1", impl_status="verified"),
            _make_group("G2", impl_status="in_progress"),
        ])
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        assert result["derived_phase_position"] == "impl_in_progress"

    def test_all_verified_gives_closed(self, tmp_path: Path) -> None:
        """MANDATORY POSITIVE CASE: all groups verified => milestone closed.

        Tests the full pipeline:
          implementation.status == 'verified'
          => derive_group_state() returns state='verified'
          => derive_phase_position() returns 'closed'

        No status_ref consulted anywhere in this path.
        """
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        plan = _make_plan([
            _make_group("G1", impl_status="verified"),
            _make_group("G2", impl_status="verified"),
        ])
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        # Per-group state must be verified
        for g in result["groups"]:
            assert g["state"] == "verified", f"group {g['group_id']} expected verified"
        # Milestone position must be closed
        assert result["derived_phase_position"] == "closed"

    def test_deferred_excluded_from_rollup(self, tmp_path: Path) -> None:
        """Deferred groups do not participate in the roll-up."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        plan = _make_plan([
            _make_group("G1", impl_status="verified"),
            _make_group("G2", checklist_status="deferred"),
        ])
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        assert result["groups"][1]["state"] == "deferred"
        assert result["derived_phase_position"] == "closed"

    def test_wont_do_excluded_from_rollup(self, tmp_path: Path) -> None:
        """REGRESSION GUARD (DEVSPEC-122 follow-up): wont_do groups do not
        participate in the roll-up, same as deferred. Without this, a wont_do
        checklist item (which the schema does not require an 'implementation'
        object for) would derive state 'pending' and the milestone would never
        reach 'closed' even after all real work is verified."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        plan = _make_plan([
            _make_group("G1", impl_status="verified"),
            _make_group("G2", checklist_status="wont_do"),
        ])
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        assert result["groups"][1]["state"] == "wont_do"
        assert result["derived_phase_position"] == "closed"

    def test_blockers_populated(self, tmp_path: Path) -> None:
        """Blocking ambs appear in both blocking_amb_ids and top-level blockers[]."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        _write_findings(findings_dir, "findings_G1_1.json", [])
        ambs = [{
            "id": "amb-block-1",
            "status": "blocked",
            "severity": "high",
            "description": "G1 is blocked",
            "impact": ["G1"],
            "resolved": False,
        }]
        plan = _make_plan([_make_group("G1")], ambs=ambs)
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        g = result["groups"][0]
        assert "amb-block-1" in g["blocking_amb_ids"]
        assert any(b["id"] == "amb-block-1" for b in result["blockers"])

    def test_output_contract_shape(self, tmp_path: Path) -> None:
        """Output object has all required top-level and per-group keys."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        plan = _make_plan([_make_group("G1")])
        result = compute_milestone_state(plan, str(findings_dir), "batchX")
        # Top-level keys
        assert set(result.keys()) == {"milestone_id", "groups", "derived_phase_position", "blockers"}
        # Per-group keys
        required_group_keys = {
            "group_id", "state", "implementation_converged_at",
            "reviewer_rounds", "findings_resolved_path",
            "blocking_amb_ids", "blocking_amb_health", "fixtures_exercised",
        }
        for g in result["groups"]:
            assert required_group_keys.issubset(g.keys())

    def test_milestone_id_is_batch_id(self, tmp_path: Path) -> None:
        """milestone_id in output is always batch_id per specdev-scope.md:238.

        The plan may have a different 'id' field, but the output contract
        specifies "milestone_id": "<batch_id>" — the plan id is ignored.
        """
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        # Plan has an id that differs from batch_id — it must not leak into output
        plan = _make_plan([_make_group("G1")])  # _make_plan sets id="ms-test-plan"
        result = compute_milestone_state(plan, str(findings_dir), "my_batch_42")
        assert result["milestone_id"] == "my_batch_42"

    def test_milestone_id_is_batch_id_when_plan_has_no_id(self, tmp_path: Path) -> None:
        """milestone_id == batch_id even when the plan dict has no 'id' key."""
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        # Build a plan without the 'id' field
        plan = {
            "plan": {"spec_alignment": {"checklist": [_make_group("G1")]}},
            "execution": {"emergent_ambiguities": []},
        }
        result = compute_milestone_state(plan, str(findings_dir), "no_id_batch")
        assert result["milestone_id"] == "no_id_batch"

    def test_verified_group_with_blocking_amb_is_verified_and_surfaces_blocker(
        self, tmp_path: Path
    ) -> None:
        """F1: verified outranks blocked; amb is advisory, not a gate.

        A group with implementation.status=='verified' AND a matching unresolved
        blocking ambiguity must:
          - resolve to group state 'verified' (verified beats blocked, pins precedence)
          - still populate blocking_amb_ids (amb is surfaced for visibility)

        At the milestone level (all non-deferred groups verified):
          - derived_phase_position == 'closed' (closed is still reached)
          - blockers[] is non-empty (documents the advisory advisory behavior)

        Downstream consumers MUST gate on derived_phase_position, not blockers[].
        """
        findings_dir = tmp_path / ".specdev" / "findings"
        findings_dir.mkdir(parents=True)
        ambs = [
            {
                "id": "amb-advisory-001",
                "status": "blocked",
                "severity": "high",
                "description": "G_VER group has an outstanding concern",
                "impact": ["G_VER"],
                "resolved": False,
            }
        ]
        # Group is verified but the amb references it and is unresolved
        plan = _make_plan([_make_group("G_VER", impl_status="verified")], ambs=ambs)
        result = compute_milestone_state(plan, str(findings_dir), "batchF1")

        # Per-group: state is verified (verified outranks blocked)
        g = result["groups"][0]
        assert g["state"] == "verified", "verified must outrank blocked"
        # Amb is still surfaced in blocking_amb_ids (advisory, not suppressed)
        assert "amb-advisory-001" in g["blocking_amb_ids"], (
            "blocking_amb_ids must be non-empty even for verified group"
        )

        # Milestone: closed (all non-deferred verified), blockers[] non-empty (advisory)
        assert result["derived_phase_position"] == "closed", (
            "derived_phase_position must be closed when all groups verified"
        )
        assert len(result["blockers"]) > 0, (
            "blockers[] CAN be non-empty even when closed — amb is advisory, not a gate"
        )
