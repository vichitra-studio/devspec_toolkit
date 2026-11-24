import unittest

from specdev_tools.validation.validators.step_03 import validate_step_03
from specdev_tools.validation.validators.step_04 import validate_step_04


class Step0310Tests(unittest.TestCase):
    def test_step_03_reads_the_nfr_metrics_and_no_other_key(self):
        errs = validate_step_03(
            {
                "terms": [
                    {"term_id": "term-1", "term": "Latency", "definition": "x" * 30, "units": "ms"}
                ]
            },
            ".",
            nfrs_data={"nfrs": [{"metric": "Error Rate"}], "other": [{"nfrs": [{"metric": "Throughput"}]}]},
        )
        self.assertEqual(["NFR metric 'Error Rate' not found in glossary"], [e.message for e in errs])

    def test_step04_accepts_valid_fr_with_trace(self):
        """Validate that FR items with non-empty trace array pass validation."""
        errs = validate_step_04(
            {
                "functional_requirements": [
                    {
                        "fr_id": "fr-test-valid-trace",
                        "statement": "This FR has a valid non-empty trace array",
                        "acceptance_criteria": [
                            {"criterion_id": "ac-1", "text": "First acceptance criterion"},
                            {"criterion_id": "ac-2", "text": "Second acceptance criterion"}
                        ],
                        "trace": [
                            {"type": "capability", "id": "cap-test", "note": "Links to capability"}
                        ]
                    }
                ]
            },
            ".",
        )
        self.assertEqual([], errs)


if __name__ == "__main__":
    unittest.main()
