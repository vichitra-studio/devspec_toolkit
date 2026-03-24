import unittest

from specdev_tools.validation.validators import (
    step_04,
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


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


class StepValidatorsTests(unittest.TestCase):
    def test_step_02a_duplicate_ci_gate(self):
        errs = step_02a.validate_step_02a({"ci_gates": ["validate-all", "validate-all"]}, ".")
        self.assertTrue(any("Duplicate ci_gates" in e for e in _render(errs)))

    def test_step_05_duplicate_api(self):
        errs = step_05.validate_step_05({"apis": [{"api_id": "a", "method": "GET", "path": "/"}, {"api_id": "a", "method": "GET", "path": "/"}]}, ".")
        self.assertTrue(errs)

    def test_step_06_missing_trace(self):
        errs = step_06.validate_step_06({"rules": [{"inv_id": "inv-1"}]}, ".")
        self.assertTrue(any("missing trace" in e for e in _render(errs)))

    def test_step_07_invalid_stage(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "n1", "stage": "qa"}]}, ".")
        self.assertTrue(any("invalid stage" in e for e in _render(errs)))

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
        self.assertTrue(any("invalid mitigation type" in e for e in _render(errs)))

    def test_step_12_unknown_require(self):
        errs = step_12.validate_step_12({"jobs": [{"job_id": "j1", "requires": ["j2"], "steps": [{"id": "s", "command": "echo"}]}]}, ".")
        self.assertTrue(errs)

    def test_step_13_missing_required_schema_sections(self):
        errs = step_13.validate_step_13({"extensions": [{"extension_id": "e1"}]}, ".")
        self.assertTrue(errs)

    def test_step_13_domain_section_names_accepted(self):
        """Domain-style section names like 'tables', 'indexes' must not fire E320."""
        ext = {
            "extension_id": "ext-01-db",
            "required_schema_sections": ["tables", "indexes", "my-section", "step_13"],
            "justification": "Extends schema with domain-specific sections.",
            "verification_rules": ["all tables have a primary key"],
        }
        errs = step_13.validate_step_13({"extensions": [ext]}, ".")
        section_errs = [e for e in _render(errs) if "not a valid identifier" in e]
        self.assertFalse(section_errs, f"Unexpected section pattern errors: {section_errs}")

    def test_step_13_numeric_prefixed_section_names_accepted(self):
        """Numeric-prefixed section names like '13_extensions' must still be accepted."""
        ext = {
            "extension_id": "ext-02-step",
            "required_schema_sections": ["13_extensions", "04_functional_requirements"],
            "justification": "Extends step-numbered schema sections.",
            "verification_rules": ["section exists in schema registry"],
        }
        errs = step_13.validate_step_13({"extensions": [ext]}, ".")
        section_errs = [e for e in _render(errs) if "not a valid identifier" in e]
        self.assertFalse(section_errs, f"Unexpected section pattern errors: {section_errs}")

    def test_step_13_empty_string_section_rejected(self):
        """An empty string section name must still be caught (fails the identifier pattern)."""
        ext = {
            "extension_id": "ext-03-bad",
            "required_schema_sections": [""],
            "justification": "Testing empty section name.",
            "verification_rules": ["check"],
        }
        errs = step_13.validate_step_13({"extensions": [ext]}, ".")
        section_errs = [e for e in _render(errs) if "not a valid identifier" in e]
        self.assertTrue(section_errs, "Expected an error for empty section name string")

    def test_step_13a_missing_dimensions(self):
        errs = step_13a.validate_step_13a({}, ".")
        self.assertTrue(any("MISSING_DIMENSIONS" in e for e in _render(errs)))

    def test_step_14_external_dependency_missing_owner(self):
        errs = step_14.validate_step_14({"milestones": [], "dependencies": [{"type": "external", "id": "auth-service"}]}, ".")
        self.assertTrue(errs)


    # T09a: step_04 tests
    def test_step_04_bad_fr_id_format(self):
        errs = step_04.validate_step_04({"functional_requirements": [{"fr_id": "BAD_ID"}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_04_valid_fr_id(self):
        errs = step_04.validate_step_04({"functional_requirements": [{"fr_id": "fr-login", "title": "User login"}]}, ".")
        self.assertFalse(any("convention" in e for e in _render(errs)))

    # T10a: step_06 tests
    def test_step_06_bad_inv_id_format(self):
        errs = step_06.validate_step_06({"rules": [{"inv_id": "BAD", "trace": ["fr-a"]}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_06_bad_trace_target(self):
        errs = step_06.validate_step_06({"rules": [{"inv_id": "inv-a", "trace": ["not-a-valid-id"]}]}, ".")
        self.assertTrue(any("pattern" in e for e in _render(errs)))

    # T11a: step_07 tests
    def test_step_07_bad_nfr_id_format(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "BAD"}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_07_target_no_digit(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "nfr-perf", "target": "high"}]}, ".")
        self.assertTrue(any("no digit" in e for e in _render(errs)))

    # T12a: step_08 tests
    def test_step_08_bad_fixture_id(self):
        errs = step_08.validate_step_08({"fixtures": [{"fixture_id": "BAD", "targets": ["fr-a"]}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_08_bad_target_format(self):
        errs = step_08.validate_step_08({"fixtures": [{"fixture_id": "fix-a", "targets": ["not-valid"]}]}, ".")
        self.assertTrue(any("pattern" in e for e in _render(errs)))

    # T13a: step_12 tests
    def test_step_12_circular_dependency(self):
        errs = step_12.validate_step_12(
            {"jobs": [
                {"job_id": "j1", "requires": ["j2"], "steps": [{"id": "s", "command": "echo"}]},
                {"job_id": "j2", "requires": ["j1"], "steps": [{"id": "s", "command": "echo"}]},
            ]}, "."
        )
        self.assertTrue(any("Circular" in e for e in _render(errs)))

    def test_step_12_valid_dag(self):
        errs = step_12.validate_step_12(
            {"jobs": [
                {"job_id": "j1", "requires": [], "steps": [{"id": "s", "command": "echo"}]},
                {"job_id": "j2", "requires": ["j1"], "steps": [{"id": "s", "command": "echo"}]},
            ]}, "."
        )
        self.assertFalse(any("Circular" in e for e in _render(errs)))

    # T14a: step_13a tests
    def test_step_13a_ratio_inconsistency(self):
        errs = step_13a.validate_step_13a({
            "dimensions": {
                "fr_api_coverage": {"covered_count": 3, "total_count": 10, "ratio": 0.99, "uncovered_ids": ["fr-a", "fr-b", "fr-c", "fr-d", "fr-e", "fr-f", "fr-g"]},
                "fr_fixture_coverage": {"covered_count": 10, "total_count": 10, "ratio": 1.0, "uncovered_ids": []},
                "fr_milestone_coverage": {"covered_count": 10, "total_count": 10, "ratio": 1.0, "uncovered_ids": []},
                "capability_fr_coverage": {"covered_count": 5, "total_count": 5, "ratio": 1.0, "uncovered_ids": []},
            }
        }, ".")
        self.assertTrue(any("RATIO_INCONSISTENCY" in e for e in _render(errs)))

    def test_step_13a_below_threshold_fires_w592(self):
        errs = step_13a.validate_step_13a({
            "dimensions": {
                "fr_api_coverage": {"covered_count": 0, "total_count": 10, "ratio": 0.0, "uncovered_ids": ["fr-a", "fr-b", "fr-c", "fr-d", "fr-e", "fr-f", "fr-g", "fr-h", "fr-i", "fr-j"]},
                "fr_fixture_coverage": {"covered_count": 10, "total_count": 10, "ratio": 1.0, "uncovered_ids": []},
                "fr_milestone_coverage": {"covered_count": 10, "total_count": 10, "ratio": 1.0, "uncovered_ids": []},
                "capability_fr_coverage": {"covered_count": 5, "total_count": 5, "ratio": 1.0, "uncovered_ids": []},
            }
        }, ".")
        self.assertTrue(any("W592" in e for e in _render(errs)))


if __name__ == "__main__":
    unittest.main()
