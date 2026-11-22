import unittest

from specdev_tools.validation.validators import (
    step_04,
    step_05,
    step_06,
    step_07,
    step_08,
    step_09,
    step_11,
    step_12,
    step_13,
    step_14,
)

from ...graph._synth import spec_check_graph_findings, unique_id_errors


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


class StepValidatorsTests(unittest.TestCase):
    def test_step_05_duplicate_api(self):
        errs = step_05.validate_step_05({"apis": [{"api_id": "a", "method": "GET", "path": "/"}, {"api_id": "a", "method": "GET", "path": "/"}]}, ".")
        self.assertTrue(errs)

    def test_step_06_does_not_read_trace_or_scope_object(self):
        rule = {"inv_id": "inv-1", "trace": "not-a-list", "scope": {"components": 7, "apis": "x"}}
        self.assertEqual(step_06.validate_step_06({"rules": [rule]}, "."), [])

    def test_step_07_invalid_stage(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "n1", "stage": "qa"}]}, ".")
        self.assertTrue(any("invalid stage" in e for e in _render(errs)))

    def test_step_09_unordered_dates(self):
        errs = step_09.validate_step_09({"milestones": [{"milestone_id": "m1", "target_date": "2026-12-01"}, {"milestone_id": "m2", "target_date": "2026-01-01"}]}, ".")
        self.assertTrue(errs)

    def test_step_09_does_not_read_removed_milestone_fields(self):
        milestone = {"milestone_id": "m1", "status": 7, "deliverables": "x", "depends_on": {"a": 1}, "dependencies": [3]}
        self.assertEqual(step_09.validate_step_09({"milestones": [milestone], "tech_stack": 5, "trace": "x"}, "."), [])

    def test_step_11_does_not_read_target_ids_or_mitigations(self):
        threat = {"threat_id": "t1", "target_ids": [{"type": "weird"}], "mitigations": "not-a-list"}
        self.assertEqual(step_11.validate_step_11({"threats": [threat], "trace": [3]}, "."), [])

    def test_step_12_unknown_require(self):
        jobs = [{"job_id": "j1", "depends_on": ["j2"], "steps": [{"name": "s", "command": "echo"}]}]
        self.assertEqual(step_12.validate_step_12({"jobs": jobs}, "."), [])
        findings = spec_check_graph_findings({"12_ci_gates.json": {"jobs": jobs}})
        self.assertEqual([(f["code"], f["owner"], f["node_id"]) for f in findings], [("E700", "step:12", "j1")])

    def test_step_13_missing_required_schema_sections(self):
        errs = step_13.validate_step_13({"extensions": [{"extension_id": "e1"}]}, ".")
        self.assertTrue(errs)

    def test_step_13_domain_section_names_accepted(self):
        """Domain-style section names like 'tables', 'indexes' must not fire E320."""
        ext = {
            "extension_id": "ext-01-db",
            "required_schema_sections": ["tables", "indexes", "my-section", "step_13"],
            "justification": "Extends schema with domain-specific sections.",
            "schema_design_guidelines": "Verify all tables have a primary key and check referential integrity.",
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
            "schema_design_guidelines": "Verify section exists in schema registry and check naming conventions.",
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
            "schema_design_guidelines": "Verify and check all naming constraints for empty section testing.",
        }
        errs = step_13.validate_step_13({"extensions": [ext]}, ".")
        section_errs = [e for e in _render(errs) if "not a valid identifier" in e]
        self.assertTrue(section_errs, "Expected an error for empty section name string")

    def test_step_14_duplicate_task_id(self):
        milestone = {"milestone_id": "ms-a", "target_date": "2026-01-01", "tasks": [{"task_id": "task-a"}, {"task_id": "task-a"}]}
        self.assertEqual(step_14.validate_step_14({"milestones": [milestone]}), [])
        errs = unique_id_errors({"14_roadmap.json": {"milestones": [milestone]}})
        self.assertEqual([(e.code, e.owner, e.node_id) for e in errs], [("E704", "step:14", "task-a")])

    def test_step_14_wrong_typed_values_do_not_raise(self):
        for milestones in ("nope", [None, 3], [{"milestone_id": ["x"], "target_date": 5, "tasks": "t"}],
                           [{"milestone_id": "ms-a", "tasks": [None, {"task_id": ["t"], "depends_on": "task-b"}, {"task_id": "task-b", "depends_on": [3, None]}]}]):
            with self.subTest(milestones=milestones):
                self.assertEqual(step_14.validate_step_14({"milestones": milestones}), [])

    def test_step_14_does_not_read_removed_fields(self):
        milestone = {"milestone_id": "ms-a", "source_milestones": ["ghost"], "fr_refs": ["fr-ghost"], "tasks": []}
        removed = {"tech_stack": {"languages": [{"name": "x"}]}, "dependencies": [{"type": "external", "id": "dep"}]}
        self.assertEqual(step_14.validate_step_14({"milestones": [milestone], **removed}), [])


    # T09a: step_04 tests
    def test_step_04_bad_fr_id_format(self):
        errs = step_04.validate_step_04({"functional_requirements": [{"fr_id": "BAD_ID"}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_04_valid_fr_id(self):
        errs = step_04.validate_step_04({"functional_requirements": [{"fr_id": "fr-login", "title": "User login"}]}, ".")
        self.assertFalse(any("convention" in e for e in _render(errs)))

    # T10a: step_06 tests
    def test_step_06_bad_inv_id_format(self):
        errs = step_06.validate_step_06({"rules": [{"inv_id": "BAD", "constrains": ["fr-a"]}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_06_duplicate_inv_id(self):
        rules = [{"inv_id": "inv-a"}, {"inv_id": "inv-a"}]
        self.assertEqual(step_06.validate_step_06({"rules": rules}, "."), [])
        errs = unique_id_errors({"06_invariants.json": {"rules": rules}})
        self.assertEqual([(e.code, e.owner, e.node_id) for e in errs], [("E704", "step:06", "inv-a")])

    def test_step_06_wrong_typed_rules_do_not_raise(self):
        for rules in (7, {"inv_id": "inv-a"}, ["inv-a", 3, None]):
            self.assertEqual(step_06.validate_step_06({"rules": rules}, "."), [])

    # T11a: step_07 tests
    def test_step_07_bad_nfr_id_format(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "BAD"}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_07_target_no_digit(self):
        errs = step_07.validate_step_07({"nfrs": [{"nfr_id": "nfr-perf", "target": "high"}]}, ".")
        self.assertTrue(any("no digit" in e for e in _render(errs)))

    # T12a: step_08 tests
    def test_step_08_bad_fixture_id(self):
        errs = step_08.validate_step_08({"fixtures": [{"fixture_id": "BAD", "verifies": ["ac-a"]}]}, ".")
        self.assertTrue(any("convention" in e for e in _render(errs)))

    def test_step_08_does_not_read_targets_or_out_of_scope(self):
        instance = {"fixtures": [{"fixture_id": "fix-a", "targets": ["not-valid"]}], "out_of_scope": [{"fr_id": "fr-gone"}]}
        self.assertEqual(step_08.validate_step_08(instance, "."), [])

    def test_step_08_wrong_typed_fixtures_do_not_raise(self):
        for fixtures in (7, {"fixture_id": "fix-a"}, ["fix-a", 3, None]):
            self.assertEqual(step_08.validate_step_08({"fixtures": fixtures}, "."), [])

    # T13a: step_12 tests
    def test_step_12_circular_dependency(self):
        errs = step_12.validate_step_12(
            {"jobs": [
                {"job_id": "j1", "depends_on": ["j2"], "steps": [{"name": "s", "command": "echo"}]},
                {"job_id": "j2", "depends_on": ["j1"], "steps": [{"name": "s", "command": "echo"}]},
            ]}, "."
        )
        self.assertEqual(errs, [])
        jobs = [
            {"job_id": "j1", "depends_on": ["j2"], "steps": [{"name": "s", "command": "echo"}]},
            {"job_id": "j2", "depends_on": ["j1"], "steps": [{"name": "s", "command": "echo"}]},
        ]
        findings = spec_check_graph_findings({"12_ci_gates.json": {"jobs": jobs}})
        self.assertEqual([(f["code"], f["owner"]) for f in findings], [("E703", "step:12")])

    def test_step_12_valid_dag(self):
        errs = step_12.validate_step_12(
            {"jobs": [
                {"job_id": "j1", "depends_on": [], "steps": [{"name": "s", "command": "echo"}]},
                {"job_id": "j2", "depends_on": ["j1"], "steps": [{"name": "s", "command": "echo"}]},
            ]}, "."
        )
        self.assertFalse(any("Circular" in e for e in _render(errs)))


def test_step_02a_duplicate_gate_id():
    gates = [{"gate_id": "gate-lint"}, {"gate_id": "gate-lint"}]
    errs = unique_id_errors({"02a_delivery_baseline.json": {"ci_gates": gates}})
    assert [(e.code, e.owner, e.node_id) for e in errs] == [("E704", "step:02a", "gate-lint")]


def test_step_02a_duplicate_secret_id():
    secrets = [{"secret_id": "sec-db"}, {"secret_id": "sec-db"}]
    errs = unique_id_errors({"02a_delivery_baseline.json": {"secrets": secrets}})
    assert [(e.code, e.owner, e.node_id) for e in errs] == [("E704", "step:02a", "sec-db")]


if __name__ == "__main__":
    unittest.main()
