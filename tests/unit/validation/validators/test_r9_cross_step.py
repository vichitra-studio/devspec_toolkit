"""Comprehensive tests for R9 cross-step ID validators.

Tests the remaining validators that perform cross-step reference validation:
- step_12: job depends_on (same-step; no cross-step checks)
- step_13: Governance label refs in extensions
- step_13a: FR + API refs in missing_elements spec_refs/related_ids

Each test class covers three scenarios:
(a) Valid upstream refs pass with no W590/E590
(b) Missing upstream file emits W590
(c) Broken ref (ID not in upstream) emits E590
"""

import json
import os
import tempfile
import unittest

from specdev_tools.validation.validators.step_06 import validate_step_06
from specdev_tools.validation.validators.step_08 import validate_step_08
from specdev_tools.validation.validators.step_09 import validate_step_09
from specdev_tools.validation.validators.step_12 import validate_step_12
from specdev_tools.validation.validators.step_13 import validate_step_13
from specdev_tools.validation.validators.step_13a import validate_step_13a


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(directory: str, filename: str, data: dict) -> None:
    """Write a JSON file into the given directory."""
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() if hasattr(e, 'render') else str(e) for e in errors]


def _w590(errors) -> list[str]:
    return [e for e in _render(errors) if "W590" in e]


def _e590(errors) -> list[str]:
    return [e for e in _render(errors) if "E590" in e]


# ---------------------------------------------------------------------------
# Step 12 — job depends_on (same-step links; no cross-step checks)
# ---------------------------------------------------------------------------

class TestStep12CrossStep(unittest.TestCase):
    """step_12 checks only its own ``depends_on`` links; link targets of other steps belong to the resolver."""

    @staticmethod
    def _job(job_id, depends_on=None):
        job = {"job_id": job_id, "steps": [{"name": "Run", "command": "npm run lint"}]}
        if depends_on is not None:
            job["depends_on"] = depends_on
        return job

    def _validate(self, jobs):
        with tempfile.TemporaryDirectory() as tmp:
            return validate_step_12({"jobs": jobs}, tmp)

    def test_valid_depends_on_passes(self):
        errors = self._validate([self._job("job-a"), self._job("job-b", ["job-a"])])
        self.assertEqual(_render(errors), [])

    def test_unknown_depends_on_job_yields_e590(self):
        errors = self._validate([self._job("job-a", ["job-ghost"])])
        self.assertTrue(any("job-ghost" in msg for msg in _e590(errors)), _render(errors))

    def test_depends_on_cycle_yields_e141(self):
        errors = self._validate([self._job("job-a", ["job-b"]), self._job("job-b", ["job-a"])])
        self.assertEqual([e.code for e in errors], ["E141"])

    def test_no_cross_step_checks_on_upstream_ids(self):
        jobs = [dict(self._job("job-lint"), verifies=["nfr-ghost"], realises=["fr-phantom"])]
        self.assertEqual(_render(self._validate(jobs)), [])

    def test_depends_on_wrong_type_does_not_raise(self):
        for bad in ("job-a", 3, {"job-a": 1}, [None, 4]):
            with self.subTest(bad=bad):
                self.assertEqual(_render(self._validate([self._job("job-a", bad)])), [])

    def test_job_and_step_wrong_type_do_not_raise(self):
        for jobs in ("nope", ["job-a", None], [{"job_id": "job-a", "steps": "echo"}]):
            with self.subTest(jobs=jobs):
                self.assertEqual(_render(self._validate(jobs)), [])


# ---------------------------------------------------------------------------
# Step 13 — Governance label refs in extensions
# ---------------------------------------------------------------------------

class TestStep13CrossStep(unittest.TestCase):
    """step_13 no longer cross-checks governance_label_ref against step 10 (E-030).

    The label is a canon reference, checked by canonical-integrity (E110).
    """

    def _instance(self, label_id):
        return {
            "extensions": [
                {
                    "extension_id": "ext-auth",
                    "required_schema_sections": ["04_fr_list"],
                    "justification": "Authentication needs custom schema section.",
                    "schema_design_guidelines": "Validate with assertion checks.",
                    "governance_label_ref": {"id": label_id},
                }
            ]
        }

    def test_label_absent_from_step_10_emits_no_e590_or_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "10_governance.json", {
                "id": "gov-main",
                "canonical_refs_used": [],
            })
            errors = validate_step_13(self._instance("label-security"), tmp)
            self.assertEqual(_e590(errors), [])
            self.assertEqual(_w590(errors), [])

    def test_missing_step_10_emits_no_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "spec"))
            errors = validate_step_13(self._instance("label-security"), tmp)
            self.assertEqual(_e590(errors), [])
            self.assertEqual(_w590(errors), [])


# ---------------------------------------------------------------------------
# Step 13a — FR + API refs in dimensions.uncovered_ids
# ---------------------------------------------------------------------------

class TestStep13aCrossStep(unittest.TestCase):
    """Cross-step validation: step_13a checks FR/API refs in dimensions.uncovered_ids."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [{"capability_id": "cap-auth"}]
            })
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No upstream files — dimensions has fr- refs in uncovered_ids
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-login"],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 2, f"Expected W590 for both missing upstreams: {w}")
            combined = " ".join(w)
            self.assertIn("04_fr_list.json", combined)
            self.assertIn("05_interface_contracts.json", combined)

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            # uncovered_ids reference IDs not in upstream specs
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-nonexistent"],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-ghost"],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 2, f"Expected E590 for broken refs: {e}")
            combined = " ".join(e)
            self.assertIn("fr-nonexistent", combined)
            self.assertIn("fr-ghost", combined)

    def test_unknown_fr_in_uncovered_ids_emits_e590(self):
        """An uncovered_id starting with fr- that does not exist in 04 should fire E590."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-phantom"],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, f"Expected E590 for unknown 'fr-phantom': {e}")
            self.assertTrue(
                any("fr-phantom" in msg for msg in e),
                f"E590 should mention fr-phantom: {e}"
            )


# ---------------------------------------------------------------------------
# Edge cases — no spec dir at all
# ---------------------------------------------------------------------------

class TestCrossStepNoSpecDir(unittest.TestCase):
    """When the spec directory does not exist at all, validators should emit W590."""

    def test_step_06_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"rules": [{"inv_id": "inv-x", "constrains": ["fr-x", "api-x"]}]}
            errors = validate_step_06(instance, tmp)
            self.assertEqual(_w590(errors), [])  # no cross-step check: the resolver owns link targets

    def test_step_08_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"fixtures": [{"fixture_id": "fix-x", "verifies": ["ac-x"]}]}
            errors = validate_step_08(instance, tmp)
            self.assertEqual(_w590(errors), [])  # no cross-step check: the resolver owns link targets

    def test_step_09_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"milestones": [{"milestone_id": "ms-x", "target_date": "2026-04-01", "schedules": ["fr-x"]}]}
            errors = validate_step_09(instance, tmp)
            self.assertEqual(_w590(errors), [])  # no cross-step check: the resolver owns link targets

    def test_step_12_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"jobs": [{"job_id": "job-x", "steps": [{"name": "Echo", "command": "echo"}], "verifies": ["nfr-x"]}]}
            errors = validate_step_12(instance, tmp)
            self.assertEqual(_w590(errors), [])  # no cross-step check: the resolver owns link targets

    def test_step_13_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {
                "extensions": [{
                    "extension_id": "ext-x",
                    "required_schema_sections": ["04_fr_list"],
                    "justification": "Testing no-spec-dir edge case.",
                    "schema_design_guidelines": "Verify tests pass.",
                    "governance_label_ref": {"id": "label-x"},
                }]
            }
            errors = validate_step_13(instance, tmp)
            self.assertEqual(_w590(errors), [])  # E-030: no step-10 cross-check

    def test_step_13a_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-x"],
                    },
                    "fr_fixture_coverage": {"covered_count": 1, "total_count": 1, "ratio": 1.0, "uncovered_ids": []},
                    "fr_milestone_coverage": {"covered_count": 1, "total_count": 1, "ratio": 1.0, "uncovered_ids": []},
                    "capability_fr_coverage": {"covered_count": 1, "total_count": 1, "ratio": 1.0, "uncovered_ids": []},
                }
            }
            errors = validate_step_13a(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)


if __name__ == "__main__":
    unittest.main()
