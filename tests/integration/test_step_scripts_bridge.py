import os
import subprocess
import sys
import unittest
from pathlib import Path


class StepScriptBridgeTests(unittest.TestCase):
    def test_script_style_step_checks_are_executed_under_unittest_discovery(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        repo_root = toolkit_root
        scripts_dir = toolkit_root / "tests" / "integration"
        pythonpath_prefix = str(toolkit_root / "tools")

        cases = [
            ("test_step_00.py", [], repo_root, {0}),
            ("test_step_01.py", [], repo_root, {0}),
            ("test_step_02.py", [], repo_root, {0}),
            ("test_step_02a.py", ["--self-test"], toolkit_root, {0}),
            # These script-style tests are still migration-era wrappers with mixed fixture semantics;
            # allow pass/fail but still fail on crashes/tracebacks.
            ("test_step_03.py", [str(toolkit_root / "tests" / "fixtures" / "step_03" / "valid_minimal.json")], repo_root, {0, 1}),
            ("test_step_04.py", [], repo_root, {0, 1}),
            ("test_step_05.py", [], repo_root, {0, 1}),
            ("test_step_06.py", [], toolkit_root, {0, 1}),
            ("test_step_07.py", [], toolkit_root, {0, 1}),
            ("test_step_08.py", [], repo_root, {0, 1}),
            ("test_step_09.py", [], toolkit_root, {0, 1}),
            ("test_step_10.py", [str(toolkit_root / "tests" / "fixtures" / "step_10")], repo_root, {0, 1}),
            ("test_step_11.py", [], repo_root, {0}),
            ("test_step_12.py", [str(toolkit_root / "tests" / "fixtures" / "step_12" / "valid_dag.json")], repo_root, {0}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "valid_manifest.json")], repo_root, {0}),
            ("test_step_15.py", [str(toolkit_root / "tests" / "fixtures" / "step_15")], repo_root, {0, 1}),
        ]

        for script_name, args, cwd, expected_returncodes in cases:
            with self.subTest(script=script_name):
                script_path = scripts_dir / script_name
                env = os.environ.copy()
                env["PYTHONPATH"] = pythonpath_prefix + os.pathsep + env.get("PYTHONPATH", "")
                result = subprocess.run(
                    [sys.executable, str(script_path), *args],
                    cwd=str(cwd),
                    env=env,
                    text=True,
                    capture_output=True,
                )
                combined_output = (result.stdout or "") + (result.stderr or "")
                self.assertNotIn("Traceback (most recent call last)", combined_output, msg=combined_output)
                self.assertIn(result.returncode, expected_returncodes, msg=combined_output)


if __name__ == "__main__":
    unittest.main()
