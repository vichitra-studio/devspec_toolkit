from __future__ import annotations
import json
import os
import tempfile
import unittest

from specdev_tools.traceability_closure import check_traceability_closure


def _write(d: str, name: str, data: dict) -> None:
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        json.dump(data, f)


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
        _write(d, "04_functional_requirements.json", frs)
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
            self.assertTrue(any("capability_without_fr" in e for e in errs))

    def test_fr_without_milestone(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, roadmap=ROADMAP_EMPTY)
            errs = check_traceability_closure(d)
            self.assertTrue(any("fr_without_milestone" in e for e in errs))

    def test_milestone_without_checklist(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, impl=IMPL_EMPTY)
            errs = check_traceability_closure(d)
            self.assertTrue(any("milestone_without_checklist" in e for e in errs))

    def test_milestone_with_unrelated_checklist_task_is_gap(self):
        """Checklist with entries that don't cover the milestone's task IDs should still be a gap."""
        with tempfile.TemporaryDirectory() as d:
            self._write_all(d, impl=IMPL_UNRELATED_TASK)
            errs = check_traceability_closure(d)
            self.assertTrue(any("milestone_without_checklist" in e for e in errs))

    def test_missing_spec_file_graceful(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_functional_requirements.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            # 16a_impl_planner.json intentionally absent
            errs = check_traceability_closure(d)
            self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
