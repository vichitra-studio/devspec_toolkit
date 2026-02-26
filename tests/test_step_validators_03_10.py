import unittest

from specdev_tools.validation.validators.step_03 import validate_step_03
from specdev_tools.validation.validators.step_10 import validate_step_10


class Step0310Tests(unittest.TestCase):
    def test_step_10_accepts_seed_docs_lint(self):
        errs = validate_step_10(
            {
                "owner": "system",
                "pr_rules": ["seed-lint", "docs-lint"],
                "commit_message_rules": {"pattern": "^feat:.+"},
                "trace": [{"type": "component", "id": "comp-a"}],
            },
            ".",
        )
        self.assertEqual([], errs)

    def test_step_03_optional_dataset_checks(self):
        errs = validate_step_03(
            {
                "terms": [
                    {"term_id": "term-1", "term": "Latency", "definition": "x" * 30, "units": "ms"}
                ]
            },
            ".",
            nfrs_data={"stage_nfrs": [{"stage": "prod", "nfrs": [{"metric": "Error Rate"}]}]},
            monitoring_data={"dashboards": [{"name": "api", "widgets": [{"metric": "Error Rate"}]}]},
        )
        self.assertTrue(any("not found in glossary" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
