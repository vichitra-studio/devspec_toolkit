import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.dependency_order_lint import lint_dependency_order


class DependencyOrderLintTests(unittest.TestCase):
    def test_detects_forward_and_self_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            fixture_path = (
                Path(__file__).resolve().parents[0]
                / "fixtures"
                / "dependency_order"
                / "prompt_01_with_forward_ref.md"
            )
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"], "allowed_upstream_dependencies": {"00": [], "01": ["00"], "02": ["00", "01"]}}),
                encoding="utf-8"
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                fixture_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("self-edge" in e for e in errs))
            self.assertTrue(any("forward-edge" in e for e in errs))
            self.assertEqual(len(errs), len(set(errs)))

    def test_detects_absolute_path_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"], "allowed_upstream_dependencies": {"00": [], "01": ["00"], "02": ["00", "01"]}}),
                encoding="utf-8"
            )
            (root / "prompts" / "prompt_01_abs.md").write_text(
                "/repo/spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("forward-edge" in e for e in errs))

    def test_ignores_plain_step_number_mentions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"], "allowed_upstream_dependencies": {"00": [], "01": ["00"]}}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_text.md").write_text(
                "This is Step 01 and references 00 in prose only.",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_disallowed_upstream_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"], "allowed_upstream_dependencies": {"00": [], "01": ["00"], "02": ["01"]}}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_02_text.md").write_text(
                "Use spec/00_project_charter.json and spec/01_capabilities.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("disallowed-upstream" in e for e in errs))

    def test_ignores_example_spec_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"], "allowed_upstream_dependencies": {"00": [], "01": ["00"]}}),
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
                json.dumps({"steps": ["00", "01", "02"], "allowed_upstream_dependencies": {"00": [], "01": ["00"], "02": ["00", "01"]}}),
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
                        "allowed_upstream_dependencies": {"00": [], "01": ["00"], "02": ["00", "01"]},
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
            self.assertTrue(any("invalid_step_order" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
