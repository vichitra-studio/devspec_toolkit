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


def _write_anchor_with_plan(d: str, milestone_id: str, plan: dict, plan_filename: str = "ms_v1_plan.json") -> None:
    """Write a Trinity Anchor registering one milestone plan, and the plan file itself.

    Uses the `spec/impl_context/...` path convention accepted by
    `_resolve_context_path` — callers are not required to name their spec dir
    "spec" because the resolver also accepts paths relative to spec_dir.
    """
    os.makedirs(os.path.join(d, "impl_context"), exist_ok=True)
    plan_path = os.path.join("impl_context", plan_filename)
    anchor = {
        "plan": {
            "milestone_index": [{
                "milestone_id": milestone_id,
                "context_path": plan_path,
            }]
        }
    }
    _write(d, "16_impl_context.json", anchor)
    _write(d, plan_path, plan)


class TestTraceabilityClosure(unittest.TestCase):

    def _write_all(self, d: str, caps=CAPS, frs=FRS_FULL, roadmap=ROADMAP_FULL, impl=IMPL_FULL):
        _write(d, "01_capabilities.json", caps)
        _write(d, "04_fr_list.json", frs)
        _write(d, "14_roadmap.json", roadmap)
        _write_anchor_with_plan(d, "ms-v1", impl)

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
            # 16_impl_context.json (Trinity Anchor) intentionally absent
            errs = check_traceability_closure(d)
            w570 = [e for e in render_errors(errs) if "W570" in e]
            hard_errors = [e for e in render_errors(errs) if not e.startswith("W")]
            self.assertEqual(hard_errors, [])
            self.assertTrue(
                any("16_impl_context.json" in w for w in w570),
                f"Expected W570 for missing anchor file, got: {w570}",
            )

    def test_anchor_declares_missing_context_path_silently_skipped(self):
        """Missing declared context_path is owned by W607 (step_16_anchor), not W588 here.

        traceability_closure deliberately stays silent when a declared plan file is
        absent — the anchor validator emits W607 ANCHOR_CONTEXT_PATH_MISSING for the
        exact same condition. Double-reporting the same root cause from two
        validators under different codes would clutter spec-check output.

        This test pins the quiet contract so a future regression that re-introduces
        a W588 "does not exist" emission here surfaces immediately.
        """
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            anchor = {
                "plan": {
                    "milestone_index": [{
                        "milestone_id": "ms-v1",
                        "context_path": "impl_context/ms_missing_plan.json",
                    }]
                }
            }
            _write(d, "16_impl_context.json", anchor)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W588" in e and "does not exist" in e for e in rendered),
                f"traceability_closure must not emit W588 for a missing declared "
                f"context_path — that signal belongs to W607 on the anchor validator. "
                f"Got: {rendered}",
            )

    def test_anchor_declares_unparseable_context_path_fires_w588(self):
        """Anchor registers a context_path that is not valid JSON."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            anchor = {
                "plan": {
                    "milestone_index": [{
                        "milestone_id": "ms-v1",
                        "context_path": "impl_context/ms_broken_plan.json",
                    }]
                }
            }
            _write(d, "16_impl_context.json", anchor)
            os.makedirs(os.path.join(d, "impl_context"), exist_ok=True)
            with open(os.path.join(d, "impl_context", "ms_broken_plan.json"), "w", encoding="utf-8") as f:
                f.write("{ not: valid json,")
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertTrue(
                any("W588" in e and "ms-v1" in e and "not valid JSON" in e for e in rendered),
                f"Expected W588 for ms-v1 unparseable plan. Got: {rendered}",
            )

    def test_anchor_merges_checklists_across_milestones(self):
        """Two milestone plans contribute independent checklist items; both cover their tasks."""
        roadmap = {"milestones": [
            {
                "milestone_id": "ms-auth",
                "fr_refs": ["fr-login"],
                "tasks": [{"task_id": "task-auth-1", "fr_refs": ["fr-login"]}],
            },
            {
                "milestone_id": "ms-session",
                "fr_refs": ["fr-session"],
                "tasks": [{"task_id": "task-session-1", "fr_refs": ["fr-session"]}],
            },
        ]}
        frs = {"functional_requirements": [
            {"fr_id": "fr-login", "trace": [{"type": "capability", "id": "cap-auth"}]},
            {"fr_id": "fr-session", "trace": [{"type": "capability", "id": "cap-auth"}]},
        ]}
        plan_auth = {"plan": {"spec_alignment": {"checklist": [{"spec_ref": {"id": "task-auth-1"}}]}}}
        plan_session = {"plan": {"spec_alignment": {"checklist": [{"spec_ref": {"id": "task-session-1"}}]}}}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_fr_list.json", frs)
            _write(d, "14_roadmap.json", roadmap)
            os.makedirs(os.path.join(d, "impl_context"), exist_ok=True)
            anchor = {
                "plan": {
                    "milestone_index": [
                        {"milestone_id": "ms-auth", "context_path": "impl_context/ms_auth_plan.json"},
                        {"milestone_id": "ms-session", "context_path": "impl_context/ms_session_plan.json"},
                    ]
                }
            }
            _write(d, "16_impl_context.json", anchor)
            _write(d, os.path.join("impl_context", "ms_auth_plan.json"), plan_auth)
            _write(d, os.path.join("impl_context", "ms_session_plan.json"), plan_session)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            # Neither ORPHAN_MILESTONE nor CHECKLIST_ROADMAP_MISMATCH should fire — each plan
            # covers its milestone's task.
            self.assertFalse(
                any("W562" in e for e in rendered),
                f"Did not expect any W562 ORPHAN_MILESTONE. Got: {rendered}",
            )
            self.assertFalse(
                any("W563" in e for e in rendered),
                f"Did not expect any W563 CHECKLIST_ROADMAP_MISMATCH. Got: {rendered}",
            )

    def test_anchor_without_milestone_index_skips_checklist_checks(self):
        """An anchor with empty milestone_index has no plans; W562/W563 should not fire.

        Rationale: an empty milestone_index represents the 'Trinity Loop has not
        yet run' state for this cycle. Checklist-coverage errors against the
        roadmap are not meaningful in that state and belong to a separate code
        (the anchor is already responsible for carrying that state across
        cycles via W587 ANCHOR_DRIFT_CHECKS_STALE when non-empty).
        """
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write(d, "16_impl_context.json", {"plan": {"milestone_index": []}})
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W562" in e or "W563" in e for e in rendered),
                f"Did not expect W562/W563 on empty milestone_index. Got: {rendered}",
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


class TestSuccessMetricsTraceability(unittest.TestCase):

    def test_success_metric_traced_by_capability_no_error(self):
        charter = {"success_metrics": [{"metric_id": "metric-auth", "description": "Auth rate"}]}
        caps = {"capabilities": [{"capability_id": "cap-auth", "success_metric_refs": ["metric-auth"]}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "00_charter.json", charter)
            _write(d, "01_capabilities.json", caps)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("E560" in e and "charter_success_metric_without_capability" in e for e in rendered),
                f"Did not expect E560 for success_metric. Got: {rendered}"
            )

    def test_success_metric_not_traced_fires_e560(self):
        charter = {"success_metrics": [{"metric_id": "metric-auth"}, {"metric_id": "metric-perf"}]}
        caps = {"capabilities": [{"capability_id": "cap-auth", "success_metric_refs": ["metric-auth"]}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "00_charter.json", charter)
            _write(d, "01_capabilities.json", caps)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            matching = [e for e in rendered if "E560" in e and "charter_success_metric_without_capability" in e and "metric-perf" in e]
            self.assertEqual(len(matching), 1, f"Expected exactly one E560 for metric-perf. Got: {rendered}")
            self.assertFalse(
                any("E560" in e and "charter_success_metric_without_capability" in e and "metric-auth" in e for e in rendered),
                f"Did not expect E560 for metric-auth. Got: {rendered}"
            )

    def test_no_success_metrics_no_error(self):
        charter = {"success_metrics": []}
        caps = {"capabilities": [{"capability_id": "cap-auth"}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "00_charter.json", charter)
            _write(d, "01_capabilities.json", caps)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("charter_success_metric_without_capability" in e for e in rendered),
                f"Did not expect any success_metric errors. Got: {rendered}"
            )

    def test_success_metrics_no_capabilities_file_skips(self):
        charter = {"success_metrics": [{"metric_id": "metric-auth"}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "00_charter.json", charter)
            # No 01_capabilities.json written — charter+capabilities guard not met
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("charter_success_metric_without_capability" in e for e in rendered),
                f"Did not expect E560 for success_metric when capabilities missing. Got: {rendered}"
            )


class TestGovernanceCICrossValidation(unittest.TestCase):

    def test_pr_rule_covered_by_ci_command_no_warning(self):
        governance = {"pr_rules": ["validate-all"]}
        ci_gates = {"jobs": [{"job_id": "job-1", "steps": [{"id": "s1", "name": "Validate", "command": "specdev validate-all spec"}]}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "10_governance.json", governance)
            _write(d, "12_ci_gates.json", ci_gates)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W569" in e for e in rendered),
                f"Did not expect W569. Got: {rendered}"
            )

    def test_pr_rule_not_in_any_ci_command_fires_w569(self):
        governance = {"pr_rules": ["validate-all", "matrix"]}
        ci_gates = {"jobs": [{"job_id": "job-1", "steps": [{"id": "s1", "name": "Validate", "command": "specdev validate-all spec"}]}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "10_governance.json", governance)
            _write(d, "12_ci_gates.json", ci_gates)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            matching = [e for e in rendered if "W569" in e and "matrix" in e]
            self.assertEqual(len(matching), 1, f"Expected exactly one W569 for matrix. Got: {rendered}")

    def test_no_governance_file_skips_check(self):
        ci_gates = {"jobs": [{"job_id": "job-1", "steps": [{"id": "s1", "command": "specdev validate-all spec"}]}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "12_ci_gates.json", ci_gates)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W569" in e for e in rendered),
                f"Did not expect W569 without governance file. Got: {rendered}"
            )

    def test_empty_pr_rules_no_warning(self):
        governance = {"pr_rules": []}
        ci_gates = {"jobs": [{"job_id": "job-1", "steps": [{"id": "s1", "command": "specdev validate-all spec"}]}]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "10_governance.json", governance)
            _write(d, "12_ci_gates.json", ci_gates)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W569" in e for e in rendered),
                f"Did not expect W569 for empty pr_rules. Got: {rendered}"
            )

    def test_no_ci_gates_file_skips_check(self):
        governance = {"pr_rules": ["validate-all"]}
        with tempfile.TemporaryDirectory() as d:
            _write(d, "10_governance.json", governance)
            # 12_ci_gates.json intentionally absent
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "14_roadmap.json", ROADMAP_FULL)
            _write_anchor_with_plan(d, "ms-v1", IMPL_FULL)
            errs = check_traceability_closure(d)
            rendered = render_errors(errs)
            self.assertFalse(
                any("W569" in e for e in rendered),
                f"Did not expect W569 without ci_gates file. Got: {rendered}"
            )


class TestW576TaskExecutionCoverage(unittest.TestCase):
    """W576 resolves executed task IDs via satisfied_checklist_ids → checklist.spec_ref.id."""

    def _plan(self, milestone_id: str, checklist_id: str, task_id: str, satisfied: list[str]) -> dict:
        return {
            "id": milestone_id,
            "plan": {
                "spec_alignment": {
                    "checklist": [{"id": checklist_id, "spec_ref": {"id": task_id}}]
                }
            },
            "execution": {
                "execution_results": [
                    {
                        "status": "passed",
                        "outcome_description": "ok",
                        "reasoning": "covered",
                        "command": "pytest",
                        "evidence": "5 passed in 0.10s",
                    }
                ],
                "critical_evidence": {"satisfied_checklist_ids": satisfied},
            },
        }

    def _write_base(self, d: str, plan: dict, tasks: list[dict] | None = None) -> None:
        _write(d, "01_capabilities.json", CAPS)
        _write(d, "04_fr_list.json", FRS_FULL)
        if tasks is None:
            tasks = [{"task_id": "task-1", "fr_refs": ["fr-login"], "status": "pending"}]
        _write(
            d,
            "14_roadmap.json",
            {"milestones": [{"milestone_id": "ms-v1", "fr_refs": ["fr-login"], "tasks": tasks}]},
        )
        _write_anchor_with_plan(d, "ms-v1", plan)

    def test_satisfied_checklist_resolves_task_suppresses_W576(self):
        with tempfile.TemporaryDirectory() as d:
            plan = self._plan("ms-v1", "AUTH_LOGIN_OK", "task-1", ["AUTH_LOGIN_OK"])
            self._write_base(d, plan)
            rendered = render_errors(check_traceability_closure(d))
            self.assertFalse(
                any("W576" in e for e in rendered),
                f"W576 should be suppressed when satisfied_checklist_ids resolves task-1. Got: {rendered}",
            )

    def test_missing_satisfaction_emits_W576(self):
        with tempfile.TemporaryDirectory() as d:
            plan = self._plan("ms-v1", "AUTH_LOGIN_OK", "task-1", [])
            self._write_base(d, plan)
            rendered = render_errors(check_traceability_closure(d))
            self.assertTrue(
                any("W576" in e and "task-1" in e for e in rendered),
                f"Expected W576 for task-1. Got: {rendered}",
            )

    def test_done_task_does_not_require_execution(self):
        with tempfile.TemporaryDirectory() as d:
            plan = self._plan("ms-v1", "AUTH_LOGIN_OK", "task-1", [])
            tasks = [{"task_id": "task-1", "fr_refs": ["fr-login"], "status": "done"}]
            self._write_base(d, plan, tasks=tasks)
            rendered = render_errors(check_traceability_closure(d))
            self.assertFalse(
                any("W576" in e for e in rendered),
                f"W576 should not fire for status=done tasks. Got: {rendered}",
            )

    def test_unknown_satisfied_id_is_ignored(self):
        """A satisfied_checklist_id that does not match any checklist item should not
        accidentally resolve to a task — W576 should still fire for the uncovered task."""
        with tempfile.TemporaryDirectory() as d:
            plan = self._plan("ms-v1", "AUTH_LOGIN_OK", "task-1", ["UNKNOWN_ID"])
            self._write_base(d, plan)
            rendered = render_errors(check_traceability_closure(d))
            self.assertTrue(
                any("W576" in e and "task-1" in e for e in rendered),
                f"Expected W576 when satisfied id is unknown. Got: {rendered}",
            )

    def test_cross_milestone_checklist_id_collision_resolves_per_plan(self):
        """If two milestone plans share a checklist id but map it to different tasks,
        satisfaction in plan A must only credit task A, not task B."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01_capabilities.json", CAPS)
            _write(d, "04_fr_list.json", FRS_FULL)
            _write(
                d,
                "14_roadmap.json",
                {
                    "milestones": [
                        {
                            "milestone_id": "ms-a",
                            "fr_refs": ["fr-login"],
                            "tasks": [
                                {"task_id": "task-a", "fr_refs": ["fr-login"], "status": "pending"},
                                {"task_id": "task-b", "fr_refs": ["fr-login"], "status": "pending"},
                            ],
                        }
                    ]
                },
            )
            # Build an anchor that registers two plan files with a colliding checklist id.
            os.makedirs(os.path.join(d, "impl_context"), exist_ok=True)
            anchor = {
                "plan": {
                    "milestone_index": [
                        {"milestone_id": "ms-a", "context_path": "impl_context/ms_a_plan.json"},
                        {"milestone_id": "ms-b", "context_path": "impl_context/ms_b_plan.json"},
                    ]
                }
            }
            _write(d, "16_impl_context.json", anchor)
            # Both plans use checklist id "SHARED_ID" but map it to different tasks.
            _write(d, "impl_context/ms_a_plan.json", self._plan("ms-a", "SHARED_ID", "task-a", ["SHARED_ID"]))
            _write(d, "impl_context/ms_b_plan.json", self._plan("ms-b", "SHARED_ID", "task-b", []))
            rendered = render_errors(check_traceability_closure(d))
            # task-a satisfied in its own plan — no W576 for it.
            self.assertFalse(
                any("W576" in e and "task-a" in e for e in rendered),
                f"task-a was satisfied in plan-a. Got: {rendered}",
            )
            # task-b was not satisfied in its own plan, so W576 must fire.
            self.assertTrue(
                any("W576" in e and "task-b" in e for e in rendered),
                f"task-b was not satisfied — expected W576. Got: {rendered}",
            )


if __name__ == "__main__":
    unittest.main()
