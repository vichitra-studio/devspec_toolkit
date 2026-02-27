import json
import os
import tempfile
import unittest

from specdev_tools.validation.validators.step_03 import validate_step_03
from specdev_tools.validation.validators.step_04 import validate_step_04
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

    def test_step04_rejects_fr_missing_trace(self):
        """Validate that FR items missing trace field entirely are rejected."""
        errs = validate_step_04(
            {
                "functional_requirements": [
                    {
                        "fr_id": "fr-test-missing-trace",
                        "statement": "This FR is missing the trace field entirely",
                        "acceptance_criteria": [
                            {"criterion_id": "ac-1", "text": "First acceptance criterion"},
                            {"criterion_id": "ac-2", "text": "Second acceptance criterion"}
                        ],
                        "capability_ref": "cap-test"
                        # NOTE: trace field is completely absent
                    }
                ]
            },
            ".",
        )
        self.assertTrue(any("missing required 'trace' field" in e for e in errs))

    def test_step04_rejects_fr_empty_trace(self):
        """Validate that FR items with empty trace array are rejected."""
        errs = validate_step_04(
            {
                "functional_requirements": [
                    {
                        "fr_id": "fr-test-empty-trace",
                        "statement": "This FR has an empty trace array",
                        "acceptance_criteria": [
                            {"criterion_id": "ac-1", "text": "First acceptance criterion"},
                            {"criterion_id": "ac-2", "text": "Second acceptance criterion"}
                        ],
                        "trace": [],  # Empty array
                        "capability_ref": "cap-test"
                    }
                ]
            },
            ".",
        )
        self.assertTrue(any("empty 'trace' array" in e for e in errs))

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
                        ],
                        "capability_ref": "cap-test"
                    }
                ]
            },
            ".",
        )
        self.assertEqual([], errs)

    def test_step04_capability_ref_cross_validation(self):
        """Validate capability_ref cross-checking works with temp fixture."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temporary spec directory with capabilities file
            spec_dir = os.path.join(tmpdir, "spec")
            os.makedirs(spec_dir)

            # Write a valid capabilities fixture
            capabilities_file = os.path.join(spec_dir, "01_capabilities.json")
            capabilities_data = {
                "capabilities": [
                    {"capability_id": "cap-user-auth"},
                    {"capability_id": "cap-user-session"}
                ]
            }
            with open(capabilities_file, "w") as f:
                json.dump(capabilities_data, f)

            # Test 1: Valid capability_ref should pass
            valid_errs = validate_step_04(
                {
                    "functional_requirements": [
                        {
                            "fr_id": "fr-valid-cap-ref",
                            "statement": "This FR references a valid capability",
                            "acceptance_criteria": [
                                {"criterion_id": "ac-1", "text": "First acceptance criterion"},
                                {"criterion_id": "ac-2", "text": "Second acceptance criterion"}
                            ],
                            "trace": [{"type": "capability", "id": "cap-user-auth"}],
                            "capability_ref": "cap-user-auth"
                        }
                    ]
                },
                tmpdir,
            )
            self.assertEqual([], valid_errs)

            # Test 2: Invalid capability_ref should fail
            invalid_errs = validate_step_04(
                {
                    "functional_requirements": [
                        {
                            "fr_id": "fr-invalid-cap-ref",
                            "statement": "This FR references a non-existent capability",
                            "acceptance_criteria": [
                                {"criterion_id": "ac-1", "text": "First acceptance criterion"},
                                {"criterion_id": "ac-2", "text": "Second acceptance criterion"}
                            ],
                            "trace": [{"type": "capability", "id": "cap-unknown"}],
                            "capability_ref": "cap-unknown"
                        }
                    ]
                },
                tmpdir,
            )
            self.assertTrue(any("unknown capability" in e for e in invalid_errs))


if __name__ == "__main__":
    unittest.main()
