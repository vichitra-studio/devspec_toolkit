import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.dependency_order_lint import lint_dependency_order
from specdev_tools.core.errors import render_errors


class DependencyOrderLintTests(unittest.TestCase):
    def test_detects_forward_and_self_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            fixture_path = (
                Path(__file__).resolve().parents[3]
                / "fixtures"
                / "dependency_order"
                / "prompt_01_with_forward_ref.md"
            )
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8"
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                fixture_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("self-edge" in e for e in render_errors(errs)))
            self.assertTrue(any("forward-edge" in e for e in render_errors(errs)))
            self.assertEqual(len(errs), len(set(errs)))

    def test_detects_absolute_path_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8"
            )
            (root / "prompts" / "prompt_01_abs.md").write_text(
                "/repo/spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("forward-edge" in e for e in render_errors(errs)))

    def test_ignores_plain_step_number_mentions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_text.md").write_text(
                "This is Step 01 and references 00 in prose only.",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_forward_dependency_enforced(self):
        """Forward references (to steps after the current step) are flagged as forward-edge violations.

        Under derive_allowed_upstream, all prior steps are valid upstreams.
        Only references to later steps (forward edges) are disallowed.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8",
            )
            # prompt_01 references spec/02_*.json which comes AFTER step 01 -> disallowed forward edge
            (root / "prompts" / "prompt_01_text.md").write_text(
                "Use spec/00_charter.json and spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("forward-edge" in e for e in render_errors(errs)))

    def test_ignores_example_spec_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_test.md").write_text(
                "Example only: example/devspec_kit/spec/00_charter.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_does_not_match_space_separated_path_fragment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_text.md").write_text(
                "Broken token: /repo path/spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_policy_can_allow_forward_and_self_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps(
                    {
                        "steps": ["00", "01", "02"],
                        "policy": {"allow_self_dependency": True, "allow_forward_dependency": True},
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                "spec/01_capabilities.json and spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_invalid_step_order_json_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text("{bad", encoding="utf-8")
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("invalid_step_order" in e for e in render_errors(errs)))

    def test_works_with_downstream_consumers_format(self):
        """Verify lint works with new step_order.json format (downstream_consumers, no step_metadata)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({
                    "steps": ["00", "01", "02"],
                    "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                }),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                "Use spec/00_charter.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)


class StepMetadataConsistencyTests(unittest.TestCase):
    """Consistency check: step_metadata.required_spec_inputs must be inverse of downstream_consumers."""

    def _write_order(self, root: Path, data: dict) -> None:
        (root / "tools").mkdir(exist_ok=True)
        (root / "prompts").mkdir(exist_ok=True)
        (root / "tools" / "step_order.json").write_text(
            json.dumps(data), encoding="utf-8",
        )

    def test_absent_step_metadata_is_no_op(self):
        """When step_metadata is absent the consistency check emits no errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_consistent_step_metadata_passes(self):
        """Correctly inverted step_metadata produces no errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": [], "extraction_intent": ""},
                    "01": {"required_spec_inputs": ["00"], "required_seed_inputs": [], "extraction_intent": ""},
                    "02": {"required_spec_inputs": ["00", "01"], "required_seed_inputs": [], "extraction_intent": ""},
                },
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_missing_required_spec_input_reported(self):
        """E540 fires when downstream_consumers implies an edge not declared in required_spec_inputs."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": [], "extraction_intent": ""},
                    "01": {"required_spec_inputs": ["00"], "required_seed_inputs": [], "extraction_intent": ""},
                    # 02 is missing "01" — should trigger E540
                    "02": {"required_spec_inputs": ["00"], "required_seed_inputs": [], "extraction_intent": ""},
                },
            })
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any("STEP_METADATA_INCONSISTENT" in e and "missing" in e for e in rendered),
                f"Expected missing-edge error, got: {rendered}",
            )

    def test_extra_required_spec_input_reported(self):
        """E540 fires when required_spec_inputs lists a step not in downstream_consumers."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01"], "01": [], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": [], "extraction_intent": ""},
                    # 01 claims to depend on 02 but downstream_consumers says otherwise
                    "01": {"required_spec_inputs": ["00", "02"], "required_seed_inputs": [], "extraction_intent": ""},
                    "02": {"required_spec_inputs": [], "required_seed_inputs": [], "extraction_intent": ""},
                },
            })
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any("STEP_METADATA_INCONSISTENT" in e and "extra" in e for e in rendered),
                f"Expected extra-edge error, got: {rendered}",
            )


if __name__ == "__main__":
    unittest.main()
