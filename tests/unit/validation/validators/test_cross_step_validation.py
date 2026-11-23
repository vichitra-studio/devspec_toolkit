"""What the single-file validators of steps 06, 08, 09, 12 and 13 report about the ids of other steps: nothing.

None of them checks a link target; an unknown target (E700) and a link cycle (E703) are graph findings of ``spec-check``.

- step_12: an unknown or cyclic ``depends_on`` gives nothing from ``validate_step_12`` and E700 / E703 from ``spec-check``
- step_13: a ``governance_label_ref`` absent from step 10, or a missing step 10 file, gives no E590 and no W590
- steps 06, 08, 09, 12 and 13: with no spec directory the validator gives no W590
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

from ...graph._synth import spec_check_graph_findings


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

    @staticmethod
    def _spec_check_findings(jobs):
        return spec_check_graph_findings({"12_ci_gates.json": {"jobs": jobs}})

    def test_unknown_depends_on_job_yields_e700_from_spec_check(self):
        """An unknown ``depends_on`` target is E700 from ``spec-check``; the single-file validator reports nothing."""
        jobs = [self._job("job-a", ["job-ghost"])]
        self.assertEqual(_render(self._validate(jobs)), [])
        findings = self._spec_check_findings(jobs)
        self.assertEqual([(f["code"], f["owner"], f["node_id"]) for f in findings], [("E700", "step:12", "job-a")])
        self.assertIn("job-ghost", findings[0]["message"])

    def test_depends_on_cycle_yields_e703_from_spec_check(self):
        """A ``depends_on`` cycle is E703 from ``spec-check``; the single-file validator reports nothing."""
        jobs = [self._job("job-a", ["job-b"]), self._job("job-b", ["job-a"])]
        self.assertEqual(_render(self._validate(jobs)), [])
        findings = self._spec_check_findings(jobs)
        self.assertEqual([(f["code"], f["owner"]) for f in findings], [("E703", "step:12")])
        self.assertIn("job-a", findings[0]["message"])
        self.assertIn("job-b", findings[0]["message"])

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
    """step_13 does not cross-check governance_label_ref against step 10 (E-030).

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
# Edge cases — no spec dir at all
# ---------------------------------------------------------------------------

class TestCrossStepNoSpecDir(unittest.TestCase):
    """With no spec directory, the validators of steps 06, 08, 09, 12 and 13 emit no W590: none reads an upstream file."""

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


if __name__ == "__main__":
    unittest.main()
