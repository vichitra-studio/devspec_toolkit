from __future__ import annotations
import json
import os
import tempfile
import unittest

from specdev_tools.validation.traceability_closure import check_traceability_closure
from specdev_tools.core.errors import render_errors


def _write(d: str, name: str, data: dict) -> None:
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        json.dump(data, f)


CHARTER_WITH_GOALS = {
    "goals": [
        {"goal_id": "goal-auth", "description": "Provide authentication"},
        {"goal_id": "goal-perf", "description": "High performance"}
    ]
}

CAPS_WITH_CHARTER_TRACE = {
    "capabilities": [
        {
            "capability_id": "cap-auth",
            "trace": [{"type": "charter-goal", "id": "goal-auth"}]
        }
    ]
}

CAPS_WITH_FULL_CHARTER_TRACE = {
    "capabilities": [
        {
            "capability_id": "cap-auth",
            "trace": [{"type": "charter-goal", "id": "goal-auth"}]
        },
        {
            "capability_id": "cap-perf",
            "trace": [{"type": "charter-goal", "id": "goal-perf"}]
        }
    ]
}

CAPS = {"capabilities": [{"capability_id": "cap-auth"}]}
FRS_FULL = {"functional_requirements": [{"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]}]}
FRS_NO_TRACE = {"functional_requirements": [{"fr_id": "fr-login", "trace": []}]}
FRS_MISSING_MS = {"functional_requirements": [{"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]}]}
ROADMAP_FULL = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": ["fr-login"], "tasks": [{"task_id": "task-1", "fr_refs": ["fr-login"]}]}]}
ROADMAP_EMPTY = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": [{"task_id": "task-1"}]}]}
IMPL_FULL = {"id": "ms-v1", "plan": {"spec_alignment": {"checklist": [{"spec_ref": {"id": "task-1"}}]}}}
IMPL_EMPTY = {"id": "ms-v1", "plan": {"spec_alignment": {"checklist": []}}}
IMPL_UNRELATED_TASK = {"id": "ms-v1", "plan": {"spec_alignment": {"checklist": [{"spec_ref": {"id": "task-UNRELATED"}}]}}}


class TestTraceabilityClosure(unittest.TestCase):

    def _write_all(self, d: str, caps=CAPS, frs=FRS_FULL, roadmap=ROADMAP_FULL, impl=IMPL_FULL):
        _write(d, "01_capabilities.json", caps)
        _write(d, "04_fr_list.json", frs)
        _write(d, "14_roadmap.json", roadmap)
        _write(d, "16a_impl_planner.json", impl)

    def test_complete_chain_no_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d)
            # Write minimal 05_interface_contracts.json so W564 is exercised (not silently skipped)
            _write(d, "05_interface_contracts.json", {
                "$schema": "vc:05-interface-contracts",
                "apis": [
                    {
                        "api_id": "api-login",
                        "name": "Login API",
                        "version": "1.0.0",
                        "protocol": "REST",
                        "owner": "api",
                        "interface_ref": "if-login",
                        "trace": [{"type": "fr", "id": "fr-login"}]
                    }
                ]
            })
            # Write minimal 08_fixtures.json so W565 is exercised (not silently skipped)
            _write(d, "08_fixtures.json", {
                "$schema": "vc:08-fixtures",
                "fixtures": [
                    {
                        "fixture_id": "fix-login",
                        "name": "Login fixture",
                        "owner": "api",
                        "targets": [{"type": "fr", "id": "fr-login"}]
                    }
                ]
            })
            errs = check_traceability_closure(d)
            self.assertEqual(errs, [])

    def test_capability_without_fr(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=FRS_NO_TRACE)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            # The E560 `capability_without_fr` message variant was removed; E560 remains for `charter_goal_without_capability`. W568 UNCOVERED_CAPABILITY is the new code for untraced capabilities.
            self.assertTrue(
                any("UNCOVERED_CAPABILITY" in e for e in rendered)
                or any("capability_without_fr" in e for e in rendered)
            )

    def test_fr_without_milestone(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, roadmap=ROADMAP_EMPTY)
            errs = check_traceability_closure(d)
            self.assertTrue(any("W561" in e and "UNCOVERED_FR" in e for e in render_errors(errs)))

    def test_milestone_without_checklist(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, impl=IMPL_EMPTY)
            errs = check_traceability_closure(d)
            self.assertTrue(any("W562" in e and "ORPHAN_MILESTONE" in e for e in render_errors(errs)))

    def test_milestone_with_unrelated_checklist_task_is_gap(self):
        """Checklist with entries that don't cover the milestone's task IDs should still be a gap."""
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, impl=IMPL_UNRELATED_TASK)
            errs = check_traceability_closure(d)
            self.assertTrue(any("W562" in e for e in render_errors(errs)))

    def test_task_without_checklist_emits_W563(self):
        """Roadmap task not present in checklist emits W563."""
        with tempfile.TemporaryDirectory() as d:
            roadmap_two_tasks = {
                "milestones": [{
                    "milestone_id": "ms-v1",
                    "fr_refs": ["fr-login"],
                    "tasks": [{"task_id": "task-1"}, {"task_id": "task-2"}]
                }]
            }
            # Checklist only covers task-1
            self._write_all(d, roadmap=roadmap_two_tasks, impl=IMPL_FULL)
            errs = check_traceability_closure(d)
            self.assertTrue(
                any("W563" in e and "task-2" in e for e in render_errors(errs)),
                f"Expected W563 for task-2. Got: {errs}"
            )

    def test_charter_goal_without_capability_detected(self):
        """Charter goal with no matching capability trace raises E560."""
        with tempfile.TemporaryDirectory() as d:
            # Write charter with 2 goals
            _write(d, "00_charter.json", CHARTER_WITH_GOALS)
            # Capabilities only trace goal-auth, not goal-perf
            self._write_all(d, caps=CAPS_WITH_CHARTER_TRACE)
            errs = check_traceability_closure(d)
            self.assertTrue(
                any("charter_goal_without_capability" in e and "goal-perf" in e for e in render_errors(errs)),
                f"Expected E560 for goal-perf. Got: {errs}"
            )
            # goal-auth should NOT appear as a gap
            self.assertFalse(
                any("charter_goal_without_capability" in e and "goal-auth" in e for e in render_errors(errs))
            )

    def test_full_chain_with_charter_valid(self):
        """Complete chain from charter->cap->FR->roadmap->checklist passes."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "00_charter.json", CHARTER_WITH_GOALS)
            # Use CAPS_WITH_FULL_CHARTER_TRACE for full coverage
            # But the existing FRS_FULL traces cap-auth, not cap-perf
            frs_full_both = {
                "functional_requirements": [
                    {"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]},
                    {"fr_id": "fr-perf", "trace": [{"type": "capability", "id": "cap-perf"}]}
                ]
            }
            roadmap_full_both = {
                "milestones": [{
                    "milestone_id": "ms-v1",
                    "fr_refs": ["fr-login", "fr-perf"],
                    "tasks": [{"task_id": "task-1"}]
                }]
            }
            self._write_all(
                d,
                caps=CAPS_WITH_FULL_CHARTER_TRACE,
                frs=frs_full_both,
                roadmap=roadmap_full_both,
            )
            errs = check_traceability_closure(d)
            charter_errs = [e for e in render_errors(errs) if "charter_goal_without_capability" in e]
            self.assertEqual(charter_errs, [], f"Expected no charter gaps. Got: {charter_errs}")

    def test_charter_absent_still_works(self):
        """When charter file is missing, the rest of the chain still works."""
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d)
            # Don't write 00_charter.json
            errs = check_traceability_closure(d)
            self.assertEqual(errs, [])

    def test_missing_spec_file_graceful(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            # 16a_impl_planner.json intentionally absent
            errs = check_traceability_closure(d)
            # B5 fix: missing files now emit W570 warnings instead of silent pass
            w570 = [e for e in render_errors(errs) if "W570" in e]
            hard_errors = [e for e in render_errors(errs) if not e.startswith("W")]
            self.assertEqual(hard_errors, [])
            # Should warn about the missing impl_planner file
            self.assertTrue(
                any("16a_impl_planner" in w or "16_impl_context" in w for w in w570),
                f"Expected W570 for missing impl_planner, got: {w570}",
            )


    def test_w564_fires_when_fr_has_no_api_coverage(self):
        """W564 fires when an FR has no API trace pointing to it; clears when covered."""
        frs = {"functional_requirements": [{"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]}]}
        apis_no_trace = {"apis": [{"api_id": "api-session", "trace": []}]}
        apis_covering = {"apis": [{"api_id": "api-session", "trace": [{"type": "fr", "id": "fr-login"}]}]}

        # W564 should fire when no API covers fr-login
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs)
            _write(d, "05_interface_contracts.json", apis_no_trace)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertTrue(
                any("W564" in e and "fr-login" in e for e in rendered),
                f"Expected W564 for fr-login. Got: {rendered}"
            )

        # W564 should NOT fire when an API covers fr-login
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs)
            _write(d, "05_interface_contracts.json", apis_covering)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W564" in e and "fr-login" in e for e in rendered),
                f"Did not expect W564 for fr-login. Got: {rendered}"
            )

    def test_w565_fires_when_fr_has_no_fixture_coverage(self):
        """W565 fires when an FR has no fixture target pointing to it; clears when covered."""
        frs = {"functional_requirements": [{"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]}]}
        fixtures_no_target = {"fixtures": [{"fixture_id": "fix-auth", "targets": []}]}
        fixtures_covering = {"fixtures": [{"fixture_id": "fix-auth", "targets": [{"type": "fr", "id": "fr-login"}]}]}

        # W565 should fire when no fixture covers fr-login
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs)
            _write(d, "08_fixtures.json", fixtures_no_target)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertTrue(
                any("W565" in e and "fr-login" in e for e in rendered),
                f"Expected W565 for fr-login. Got: {rendered}"
            )

        # W565 should NOT fire when a fixture covers fr-login
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs)
            _write(d, "08_fixtures.json", fixtures_covering)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W565" in e and "fr-login" in e for e in rendered),
                f"Did not expect W565 for fr-login. Got: {rendered}"
            )

    def test_w566_fires_when_fr_not_in_milestone(self):
        """W566 fires when an FR is not listed in any milestone fr_refs; clears when added."""
        frs = {"functional_requirements": [{"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]}]}
        roadmap_missing = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": [{"task_id": "task-1"}]}]}
        roadmap_covered = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": ["fr-login"], "tasks": [{"task_id": "task-1", "fr_refs": ["fr-login"]}]}]}

        # W566 should fire when fr-login is not in any milestone
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs, roadmap=roadmap_missing)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertTrue(
                any("W566" in e and "fr-login" in e for e in rendered),
                f"Expected W566 for fr-login. Got: {rendered}"
            )

        # W566 should NOT fire when fr-login is in a milestone
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs, roadmap=roadmap_covered)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W566" in e and "fr-login" in e for e in rendered),
                f"Did not expect W566 for fr-login. Got: {rendered}"
            )

    def test_w567_fires_when_milestone_has_no_tasks(self):
        """W567 fires when a milestone has an empty tasks list; clears when tasks are added."""
        roadmap_empty_tasks = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": [], "tasks": []}]}
        roadmap_with_tasks = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": ["fr-login"], "tasks": [{"task_id": "task-1", "fr_refs": ["fr-login"]}]}]}

        # W567 should fire when ms-v1 has empty tasks
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, roadmap=roadmap_empty_tasks)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertTrue(
                any("W567" in e and "ms-v1" in e for e in rendered),
                f"Expected W567 for ms-v1. Got: {rendered}"
            )

        # W567 should NOT fire when ms-v1 has tasks
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, roadmap=roadmap_with_tasks)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            w567_msgs = [e for e in rendered if "W567" in e]
            self.assertEqual([], [e for e in w567_msgs if "ms-v1" in e and "fr_ref" not in e],
                f"Did not expect W567 empty-tasks for ms-v1. Got: {rendered}"
            )

    def test_w568_fires_when_capability_has_no_fr(self):
        """W568 fires when a capability has no FR tracing to it; clears when an FR covers it."""
        caps = {"capabilities": [{"capability_id": "cap-auth"}]}
        frs_no_trace = {"functional_requirements": [{"fr_id": "fr-login", "trace": []}]}
        frs_covering = {"functional_requirements": [{"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]}]}

        # W568 should fire when no FR traces to cap-auth
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, caps=caps, frs=frs_no_trace)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertTrue(
                any("W568" in e and "cap-auth" in e for e in rendered),
                f"Expected W568 for cap-auth. Got: {rendered}"
            )

        # W568 should NOT fire when an FR traces to cap-auth
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, caps=caps, frs=frs_covering)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W568" in e and "cap-auth" in e for e in rendered),
                f"Did not expect W568 for cap-auth. Got: {rendered}"
            )

    def test_w567_fires_when_milestone_fr_not_covered_by_task_fr_refs(self):
        """W567 fires when a milestone fr_ref is not present in any task's fr_refs."""
        # ms-v1 declares fr_refs: [fr-login], but the only task covers fr-other
        roadmap_partial_task = {
            "milestones": [{
                "milestone_id": "ms-v1",
                "fr_refs": ["fr-login"],
                "tasks": [{"task_id": "task-1", "fr_refs": ["fr-other"]}]
            }]
        }
        frs = {"functional_requirements": [
            {"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]},
            {"fr_id": "fr-other", "trace": [{"type": "capability", "id": "cap-auth"}]},
        ]}

        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs, roadmap=roadmap_partial_task)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            matching = [e for e in rendered if "W567" in e and "fr-login" in e and "not covered" in e]
            self.assertTrue(
                len(matching) > 0,
                f"Expected W567 mentioning 'fr-login not covered'. Got: {rendered}"
            )


    def test_w561_and_w566_co_fire_for_same_fr_id(self):
        """W561 and W566 both fire for the same FR ID when no milestone covers it.

        This verifies the co-fire invariant: W561 (legacy UNCOVERED_FR signal) and
        W566 (pairwise UNCOVERED_FR_MILESTONE) must both fire for the same uncovered
        FR ID. W561 is excluded from PROMOTABLE_PAIRS to prevent double-promotion,
        but the co-fire is required for completeness reporting accuracy.
        """
        frs = {"functional_requirements": [
            {"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]},
        ]}
        # Roadmap exists but fr-login is NOT in any milestone's fr_refs
        roadmap = {"milestones": [
            {"milestone_id": "ms-v1", "fr_refs": [], "tasks": [{"task_id": "t-1"}]}
        ]}
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=frs, roadmap=roadmap)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            # Both W561 and W566 must fire for fr-login
            self.assertTrue(
                any("W561" in e and "fr-login" in e for e in rendered),
                f"Expected W561 for fr-login. Got: {rendered}"
            )
            self.assertTrue(
                any("W566" in e and "fr-login" in e for e in rendered),
                f"Expected W566 for fr-login. Got: {rendered}"
            )


if __name__ == "__main__":
    unittest.main()
