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
ROADMAP_FULL = {"milestones": [{"milestone_id": "ms-v1", "fr_refs": ["fr-login"], "tasks": [{"task_id": "task-1"}]}]}
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
            errs = check_traceability_closure(d)
            self.assertEqual(errs, [])

    def test_capability_without_fr(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, frs=FRS_NO_TRACE)
            errs = check_traceability_closure(d)
            self.assertTrue(any("capability_without_fr" in e for e in render_errors(errs)))

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


if __name__ == "__main__":
    unittest.main()
