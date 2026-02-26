import unittest

from specdev_tools.validation.validators import (
    step_05,
    step_02a,
    step_06,
    step_07,
    step_08,
    step_09,
    step_11,
    step_12,
    step_13,
    step_13a,
    step_14,
)


class StepValidatorsTests(unittest.TestCase):
    def test_step_02a_duplicate_ci_gate(self):
        errs = step_02a.validate_step_02a({"ci_gates": ["validate-all", "validate-all"]}, ".")
        self.assertTrue(any("Duplicate ci_gates" in e for e in errs))

    def test_step_05_duplicate_api(self):
        errs = step_05.validate_step_05({"apis": [{"api_id": "a", "method": "GET", "path": "/"}, {"api_id": "a", "method": "GET", "path": "/"}]}, ".")
        self.assertTrue(errs)

    def test_step_06_missing_trace(self):
        errs = step_06.validate_step_06({"rules": [{"inv_id": "inv-1"}]}, ".")
        self.assertTrue(any("missing trace" in e for e in errs))

    def test_step_07_invalid_stage(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "n1", "stage": "qa"}]}, ".")
        self.assertTrue(any("invalid stage" in e for e in errs))

    def test_step_08_missing_targets(self):
        errs = step_08.validate_step_08({"fixtures": [{"fixture_id": "f1", "targets": []}]}, ".")
        self.assertTrue(errs)

    def test_step_09_unordered_dates(self):
        errs = step_09.validate_step_09({"milestones": [{"milestone_id": "m1", "target_date": "2026-12-01"}, {"milestone_id": "m2", "target_date": "2026-01-01"}]}, ".")
        self.assertTrue(errs)

    def test_step_11_invalid_target_type(self):
        errs = step_11.validate_step_11({"threats": [{"threat_id": "t1", "target_ids": [{"type": "weird"}]}]}, ".")
        self.assertTrue(errs)

    def test_step_11_invalid_mitigation_type(self):
        errs = step_11.validate_step_11(
            {
                "threats": [
                    {
                        "threat_id": "t1",
                        "target_ids": [{"type": "api", "id": "api-a"}],
                        "mitigations": [{"type": "component", "id": "component-a"}],
                    }
                ]
            },
            ".",
        )
        self.assertTrue(any("invalid mitigation type" in e for e in errs))

    def test_step_12_unknown_require(self):
        errs = step_12.validate_step_12({"jobs": [{"job_id": "j1", "requires": ["j2"], "steps": [{"id": "s", "command": "echo"}]}]}, ".")
        self.assertTrue(errs)

    def test_step_13_missing_required_schema_sections(self):
        errs = step_13.validate_step_13({"extensions": [{"extension_id": "e1"}]}, ".")
        self.assertTrue(errs)

    def test_step_13a_bad_score(self):
        errs = step_13a.validate_step_13a({"missing_elements": [{"element_id": "x", "impact_score": 1000}]}, ".")
        self.assertTrue(errs)

    def test_step_14_external_dependency_missing_owner(self):
        errs = step_14.validate_step_14({"milestones": [], "dependencies": [{"type": "external", "id": "auth-service"}]}, ".")
        self.assertTrue(errs)


if __name__ == "__main__":
    unittest.main()
